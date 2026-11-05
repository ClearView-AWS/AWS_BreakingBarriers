"""Legacy path for the school phone call.

Prefer the CDK stack instead:

    cd infra
    npx cdk deploy GsVoiceStack \\
      -c voiceInstanceId=$VOICE_INSTANCE_ID \\
      -c voiceStateTable=<GsAppStack RuntimeState table name>

That creates the voice-turn Lambda, Lex V2 bot, Connect contact flow, and
CloudWatch log groups. Outputs include VOICE_FLOW_ID (and VOICE_SOURCE if you
pass -c voiceClaimNumber=true). The Connect instance itself is imported by id —
see infra/lib/voice-stack.ts for why.

This script still works if you need the old imperative setup. Each step reuses
what already exists.

    VOICE_INSTANCE_ID=<connect instance id> .venv/bin/python scripts/setup_voice.py

Prints the env vars the API needs (VOICE_INSTANCE_ID, VOICE_FLOW_ID, VOICE_SOURCE).
The destination number is never stored here: set VOICE_VERIFIED_TO on the API only.
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "us-east-1")
INSTANCE_ID = os.environ["VOICE_INSTANCE_ID"]
PREFIX = "GsVoice"
BOT_NAME = "GsSchoolCaller"
FLOW_NAME = "GS school call"
VOICE = "Joanna"
# The AI always finishes its sentence (no barge-in), then waits 5 s for the first word
# and 1 s of silence before a reply is done.
LISTEN = {
    "x-amz-lex:allow-interrupt:*:*": "false",
    "x-amz-lex:audio:start-timeout-ms:*:*": "5000",
    "x-amz-lex:audio:end-timeout-ms:*:*": "1000",
}
HANDLER = Path(__file__).resolve().parents[1] / "backend" / "voice" / "lex_turn.py"

iam = boto3.client("iam")
lam = boto3.client("lambda", region_name=REGION)
lex = boto3.client("lexv2-models", region_name=REGION)
connect = boto3.client("connect", region_name=REGION)
dynamo = boto3.client("dynamodb", region_name=REGION)
account = boto3.client("sts").get_caller_identity()["Account"]


def log(message: str) -> None:
    print(f"· {message}", flush=True)


def wait(check, what: str, timeout: int = 300) -> None:
    def ready() -> bool:
        try:
            return check()
        except ClientError as exc:  # a resource just created can be missing for a moment
            if exc.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
            return False

    start = time.time()
    while not ready():
        if time.time() - start > timeout:
            sys.exit(f"timed out waiting for {what}")
        time.sleep(4)


def role(name: str, service: str, policy: dict, managed: list[str] = ()) -> str:
    trust = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": service}, "Action": "sts:AssumeRole"}],
    }
    try:
        arn = iam.create_role(RoleName=name, AssumeRolePolicyDocument=json.dumps(trust))["Role"]["Arn"]
        log(f"created role {name}")
        time.sleep(10)  # IAM is eventually consistent
    except iam.exceptions.EntityAlreadyExistsException:
        arn = iam.get_role(RoleName=name)["Role"]["Arn"]
    iam.put_role_policy(RoleName=name, PolicyName="inline", PolicyDocument=json.dumps(policy))
    for policy_arn in managed:
        iam.attach_role_policy(RoleName=name, PolicyArn=policy_arn)
    return arn


def state_table() -> str:
    name = os.environ.get("GS_DYNAMODB_TABLE")
    if name:
        return name
    tables = [t for t in dynamo.list_tables()["TableNames"] if "RuntimeState" in t]
    if not tables:
        sys.exit("no RuntimeState table; set GS_DYNAMODB_TABLE")
    return tables[0]


def lambda_function(table: str) -> str:
    table_arn = f"arn:aws:dynamodb:{REGION}:{account}:table/{table}"
    arn = role(
        f"{PREFIX}LambdaRole",
        "lambda.amazonaws.com",
        {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Action": ["bedrock:InvokeModel"], "Resource": "*"},
                {"Effect": "Allow", "Action": ["dynamodb:PutItem", "dynamodb:GetItem"], "Resource": table_arn},
            ],
        },
        ["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.write(HANDLER, "lex_turn.py")
    code = buffer.getvalue()
    name = f"{PREFIX}Turn"
    env = {"Variables": {"GS_DYNAMODB_TABLE": table}}
    try:
        fn = lam.create_function(
            FunctionName=name, Runtime="python3.12", Role=arn, Handler="lex_turn.handler",
            Code={"ZipFile": code}, Timeout=20, MemorySize=256, Environment=env,
        )
        log(f"created lambda {name}")
    except lam.exceptions.ResourceConflictException:
        lam.update_function_code(FunctionName=name, ZipFile=code)
        wait(lambda: lam.get_function(FunctionName=name)["Configuration"]["LastUpdateStatus"] != "InProgress", "lambda update")
        fn = lam.update_function_configuration(FunctionName=name, Environment=env, Timeout=20)
        log(f"updated lambda {name}")
    wait(lambda: lam.get_function(FunctionName=name)["Configuration"]["State"] == "Active", "lambda active")
    return fn["FunctionArn"]


def bot(lambda_arn: str) -> str:
    bot_role = role(
        f"{PREFIX}LexRole",
        "lexv2.amazonaws.com",
        {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["polly:SynthesizeSpeech"], "Resource": "*"}]},
    )
    found = [b for b in lex.list_bots()["botSummaries"] if b["botName"] == BOT_NAME]
    if found:
        bot_id = found[0]["botId"]
    else:
        bot_id = lex.create_bot(
            botName=BOT_NAME, roleArn=bot_role, dataPrivacy={"childDirected": False}, idleSessionTTLInSeconds=600,
        )["botId"]
        log(f"created bot {bot_id}")
    wait(lambda: lex.describe_bot(botId=bot_id)["botStatus"] == "Available", "bot")

    try:
        lex.create_bot_locale(
            botId=bot_id, botVersion="DRAFT", localeId="en_US", nluIntentConfidenceThreshold=0.4,
            voiceSettings={"voiceId": VOICE, "engine": "neural"},
        )
        log("created en_US locale")
    except ClientError as exc:
        if "already exists" not in str(exc):
            raise
    wait(lambda: lex.describe_bot_locale(botId=bot_id, botVersion="DRAFT", localeId="en_US")["botLocaleStatus"]
         in {"NotBuilt", "Built", "ReadyExpressTesting", "Failed"}, "locale")

    # Every utterance goes to the Lambda. Lex needs one real intent, so it gets a phrase nobody says.
    # While the Lambda waits on Bedrock, Lex says "One moment" so the line never goes quiet.
    hook = {
        "enabled": True,
        "fulfillmentUpdatesSpecification": {
            "active": True,
            "startResponse": {
                "delayInSeconds": 1,
                "allowInterrupt": False,
                "messageGroups": [{"message": {"plainTextMessage": {"value": "One moment."}}}],
            },
            "updateResponse": {
                "frequencyInSeconds": 5,
                "allowInterrupt": False,
                "messageGroups": [{"message": {"plainTextMessage": {"value": "Still with you."}}}],
            },
            "timeoutInSeconds": 30,
        },
    }
    intents = {i["intentName"]: i["intentId"] for i in lex.list_intents(botId=bot_id, botVersion="DRAFT", localeId="en_US")["intentSummaries"]}
    if "Placeholder" not in intents:
        lex.create_intent(
            botId=bot_id, botVersion="DRAFT", localeId="en_US", intentName="Placeholder",
            sampleUtterances=[{"utterance": "zebra placeholder phrase"}], fulfillmentCodeHook=hook,
        )
    lex.update_intent(
        botId=bot_id, botVersion="DRAFT", localeId="en_US", intentId=intents.get("FallbackIntent", "FALLBCKINT"),
        intentName="FallbackIntent", parentIntentSignature="AMAZON.FallbackIntent", fulfillmentCodeHook=hook,
    )

    lex.build_bot_locale(botId=bot_id, botVersion="DRAFT", localeId="en_US")
    log("building bot")
    def built() -> bool:
        status = lex.describe_bot_locale(botId=bot_id, botVersion="DRAFT", localeId="en_US")["botLocaleStatus"]
        if status == "Failed":
            sys.exit("bot build failed")
        return status == "Built"
    wait(built, "bot build")

    version = lex.create_bot_version(botId=bot_id, botVersionLocaleSpecification={"en_US": {"sourceBotVersion": "DRAFT"}})["botVersion"]
    wait(lambda: lex.describe_bot_version(botId=bot_id, botVersion=version)["botStatus"] == "Available", "bot version")
    log(f"bot version {version}")

    locale_settings = {"en_US": {"enabled": True, "codeHookSpecification": {"lambdaCodeHook": {"lambdaARN": lambda_arn, "codeHookInterfaceVersion": "1.0"}}}}
    aliases = {a["botAliasName"]: a["botAliasId"] for a in lex.list_bot_aliases(botId=bot_id)["botAliasSummaries"]}
    if "live" in aliases:
        alias_id = aliases["live"]
        lex.update_bot_alias(botId=bot_id, botAliasId=alias_id, botAliasName="live", botVersion=version, botAliasLocaleSettings=locale_settings)
    else:
        alias_id = lex.create_bot_alias(botId=bot_id, botAliasName="live", botVersion=version, botAliasLocaleSettings=locale_settings)["botAliasId"]
    wait(lambda: lex.describe_bot_alias(botId=bot_id, botAliasId=alias_id)["botAliasStatus"] == "Available", "alias")
    alias_arn = f"arn:aws:lex:{REGION}:{account}:bot-alias/{bot_id}/{alias_id}"

    try:
        lam.add_permission(
            FunctionName=lambda_arn, StatementId="lex-invoke", Action="lambda:InvokeFunction",
            Principal="lexv2.amazonaws.com", SourceArn=alias_arn,
        )
    except lam.exceptions.ResourceConflictException:
        pass
    log(f"alias {alias_arn}")
    return alias_arn


def flow(alias_arn: str) -> str:
    # Flow logs show where a call ended (CloudWatch group /aws/connect/<alias>).
    connect.update_instance_attribute(InstanceId=INSTANCE_ID, AttributeType="CONTACTFLOW_LOGS", Value="true")
    try:
        connect.associate_bot(InstanceId=INSTANCE_ID, LexV2Bot={"AliasArn": alias_arn})
        log("associated bot with Connect")
    except connect.exceptions.DuplicateResourceException:
        pass
    session = {key: f"$.Attributes.{key}" for key in ("call_id", "school_name", "questions", "opening")}
    session.update(LISTEN)
    content = {
        "Version": "2019-10-30",
        "StartAction": "logs",
        "Actions": [
            {"Identifier": "logs", "Type": "UpdateFlowLoggingBehavior",
             "Parameters": {"FlowLoggingBehavior": "Enabled"},
             "Transitions": {"NextAction": "voice", "Errors": [], "Conditions": []}},
            {"Identifier": "voice", "Type": "UpdateContactTextToSpeechVoice",
             "Parameters": {"TextToSpeechVoice": VOICE, "TextToSpeechEngine": "Neural"},
             "Transitions": {"NextAction": "talk", "Errors": [], "Conditions": []}},
            {"Identifier": "talk", "Type": "ConnectParticipantWithLexBot",
             "Parameters": {"Text": "$.Attributes.opening", "LexV2Bot": {"AliasArn": alias_arn}, "LexSessionAttributes": session},
             "Transitions": {"NextAction": "end", "Errors": [
                 {"NextAction": "end", "ErrorType": "NoMatchingError"},
                 {"NextAction": "end", "ErrorType": "NoMatchingCondition"}], "Conditions": []}},
            {"Identifier": "end", "Type": "DisconnectParticipant", "Parameters": {}, "Transitions": {}},
        ],
    }
    flows = connect.list_contact_flows(InstanceId=INSTANCE_ID, ContactFlowTypes=["CONTACT_FLOW"])["ContactFlowSummaryList"]
    existing = [f for f in flows if f["Name"] == FLOW_NAME]
    if existing:
        flow_id = existing[0]["Id"]
        connect.update_contact_flow_content(InstanceId=INSTANCE_ID, ContactFlowId=flow_id, Content=json.dumps(content))
        log(f"updated flow {flow_id}")
    else:
        flow_id = connect.create_contact_flow(
            InstanceId=INSTANCE_ID, Name=FLOW_NAME, Type="CONTACT_FLOW", Content=json.dumps(content)
        )["ContactFlowId"]
        log(f"created flow {flow_id}")
    return flow_id


def source_number() -> str:
    numbers = connect.list_phone_numbers_v2(
        TargetArn=f"arn:aws:connect:{REGION}:{account}:instance/{INSTANCE_ID}"
    )["ListPhoneNumbersSummaryList"]
    if not numbers:
        sys.exit("claim a phone number for the instance first")
    return numbers[0]["PhoneNumber"]


def main() -> None:
    print(
        "Legacy setup. Prefer: cd infra && npx cdk deploy GsVoiceStack "
        f"-c voiceInstanceId={INSTANCE_ID} -c voiceStateTable=<RuntimeState table>",
        flush=True,
    )
    table = state_table()
    lambda_arn = lambda_function(table)
    alias_arn = bot(lambda_arn)
    flow_id = flow(alias_arn)
    print()
    print(f"VOICE_INSTANCE_ID={INSTANCE_ID}")
    print(f"VOICE_FLOW_ID={flow_id}")
    print(f"VOICE_SOURCE={source_number()}")


if __name__ == "__main__":
    main()
