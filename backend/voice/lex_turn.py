"""Lambda behind the Lex bot on a school call. One invocation per thing the school says.

Amazon Connect plays the opening line, then Lex turns each reply into text and calls
this handler. The model writes the next spoken line and its reading of the answers.
Both are untrusted: the app checks every answer in code before a card changes
(backend/gaps/phone.py). The transcript goes to the app's DynamoDB table under pk CALLS.

Runs on its own in Lambda, so it imports only boto3.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import boto3

MODEL_ID = os.environ.get("VOICE_MODEL_ID", "us.anthropic.claude-haiku-5-5")
TABLE = os.environ.get("GS_DYNAMODB_TABLE", "")
REGION = os.environ.get("AWS_REGION", "us-east-1")
MAX_TURNS = 12
# Same as the Connect flow: never cut the AI off, wait 5 s for an answer, 1 s of silence ends it.
LISTEN = {
    "x-amz-lex:allow-interrupt:*:*": "false",
    "x-amz-lex:audio:start-timeout-ms:*:*": "5000",
    "x-amz-lex:audio:end-timeout-ms:*:*": "1000",
}

SYSTEM = """You are an automated AI assistant on a phone call with a school's front office,
calling on behalf of parents who use GreatSchools. You already introduced yourself as an
AI and asked whether the call may be transcribed.

School: {school}
Questions parents asked (ask each one, one at a time, in this order):
{questions}

Rules:
- Speech is transcribed by machine and can be garbled. Read it generously: "okay", "sure",
  "all right", "go ahead", or anything close is a yes. Then ask the first question.
- Speak in short, natural sentences. One or two sentences per turn. No lists, no markup.
- If the person declines the transcript, is busy, or asks you to stop: thank them, say the
  families will follow up by email, and end the call.
- If an answer is unclear, ask once to clarify, then move on.
- Never invent an answer. Record only what the person said.
- When every question is answered or skipped, thank them and say goodbye.

Reply with only a JSON object:
{{"say": "<your next spoken line>",
  "done": <true when your line ends the call>,
  "consent": <true, false, or null if not said yet>,
  "answers": {{"<question id>": {{"value": "<short value, e.g. 18:00 or yes/no>", "quote": "<the person's exact words>"}}}}}}
Include in "answers" every question answered so far."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _converse(system: str, transcript: list[dict]) -> dict:
    client = boto3.client("bedrock-runtime", region_name=REGION)
    # Bedrock needs alternating turns that start with the user; the office is the user.
    messages: list[dict] = []
    for line in transcript:
        role = "assistant" if line["who"] == "agent" else "user"
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"][0]["text"] += " " + line["text"]
        else:
            messages.append({"role": role, "content": [{"text": line["text"]}]})
    if messages and messages[0]["role"] == "assistant":
        messages.insert(0, {"role": "user", "content": [{"text": "(phone picks up)"}]})
    response = client.converse(
        modelId=MODEL_ID,
        system=[{"text": system}],
        messages=messages,
        inferenceConfig={"maxTokens": 250},
    )
    raw = "".join(block.get("text", "") for block in response["output"]["message"]["content"])
    start, end = raw.find("{"), raw.rfind("}")
    return json.loads(raw[start : end + 1])


def _save(call_id: str, record: dict) -> None:
    if not TABLE or not call_id:
        return
    table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE)
    table.put_item(Item={"pk": "CALLS", "sk": call_id, "data_json": json.dumps(record)})


def _reply(event: dict, attrs: dict, say: str, done: bool) -> dict:
    intent = (event.get("sessionState") or {}).get("intent") or {"name": "FallbackIntent"}
    action = {"type": "Close"} if done else {"type": "ElicitIntent"}
    state = {"sessionAttributes": attrs, "dialogAction": action}
    if done:
        state["intent"] = {"name": intent["name"], "state": "Fulfilled"}
    return {"sessionState": state, "messages": [{"contentType": "PlainText", "content": say}]}


def handler(event, context):
    attrs = dict((event.get("sessionState") or {}).get("sessionAttributes") or {})
    call_id = attrs.get("call_id", "")
    school = attrs.get("school_name", "the school")
    questions = json.loads(attrs.get("questions") or "[]")
    transcript = json.loads(attrs.get("transcript") or "[]")
    if not transcript and attrs.get("opening"):
        transcript.append({"who": "agent", "text": attrs["opening"], "at": _now()})
    heard = (event.get("inputTranscript") or "").strip()
    transcript.append({"who": "school", "text": heard or "(silence)", "at": _now()})

    record = {
        "call_id": call_id,
        "contact_id": event.get("sessionId"),
        "school_name": school,
        "questions": questions,
        "status": "in_call",
        "answers": {},
        "consent": None,
    }
    try:
        listed = "\n".join(f"- id={q['id']}: {q['question']}" for q in questions)
        turn = _converse(SYSTEM.format(school=school, questions=listed), transcript)
        say = str(turn.get("say") or "Thank you. Goodbye.")
        done = bool(turn.get("done")) or len(transcript) >= MAX_TURNS * 2
        record["answers"] = turn.get("answers") or {}
        record["consent"] = turn.get("consent")
    except Exception as exc:  # the call must still end politely
        say = "Sorry, I'm having trouble on my end. The families will follow up by email. Goodbye."
        done = True
        record["error"] = str(exc)[:300]

    transcript.append({"who": "agent", "text": say, "at": _now()})
    record["transcript"] = transcript
    if done:
        record["status"] = "completed"
        record["ended"] = _now()
    attrs["transcript"] = json.dumps(transcript)
    attrs.update(LISTEN)
    _save(call_id, record)
    return _reply(event, attrs, say, done)
