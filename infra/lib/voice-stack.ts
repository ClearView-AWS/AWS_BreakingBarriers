import * as crypto from 'crypto';
import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as connect from 'aws-cdk-lib/aws-connect';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as lex from 'aws-cdk-lib/aws-lex';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as cr from 'aws-cdk-lib/custom-resources';
import { repoRootFrom } from './app-stack';

export interface VoiceStackProps extends cdk.StackProps {
  /**
   * Existing Amazon Connect instance id. Imported, not created: an instance takes an
   * alias, an identity setup and a support case to unlock outbound calls, and deleting
   * it with the stack would drop its claimed number. Without it the stack builds only
   * the Lambda and the Lex bot.
   */
  instanceId?: string;
  /** The app's DynamoDB table (GsAppStack RuntimeState). Transcripts go under pk CALLS. */
  stateTableName?: string;
  /** Bedrock model for the phone turns. Same default as backend/voice/lex_turn.py. */
  modelId?: string;
  /**
   * Claim a US toll-free number for the instance. Off by default: a number bills by the
   * day, sandbox accounts have a small quota, and a released number cannot be got back,
   * so the demo keeps the number it already has (VOICE_SOURCE on the API).
   */
  claimNumber?: boolean;
}

const VOICE = 'Joanna';
// Same as backend/voice/lex_turn.py: the AI always finishes its sentence (no barge-in),
// then waits 5 s for the first word and 1 s of silence before a reply is done. With the
// 1 s "One moment" delay below, the caller hears it 2 s after they stop talking.
const LISTEN: Record<string, string> = {
  'x-amz-lex:allow-interrupt:*:*': 'false',
  'x-amz-lex:audio:start-timeout-ms:*:*': '5000',
  'x-amz-lex:audio:end-timeout-ms:*:*': '1000',
};

/**
 * The school phone call: Connect flow → Lex V2 bot → Lambda (backend/voice/lex_turn.py).
 * The API starts the call (backend/gaps/phone.py) with VOICE_FLOW_ID from this stack.
 */
export class VoiceStack extends cdk.Stack {
  public readonly turnFunction: lambda.Function;
  public readonly botAliasArn: string;

  constructor(scope: Construct, id: string, props: VoiceStackProps = {}) {
    super(scope, id, props);

    const repoRoot = repoRootFrom(__dirname);
    const modelId = props.modelId ?? 'us.anthropic.claude-haiku-5-5';

    const turnLogs = new logs.LogGroup(this, 'TurnLogs', {
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    const environment: Record<string, string> = { VOICE_MODEL_ID: modelId };
    if (props.stateTableName) environment.GS_DYNAMODB_TABLE = props.stateTableName;

    const turn = new lambda.Function(this, 'Turn', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'lex_turn.handler',
      code: lambda.Code.fromAsset(path.join(repoRoot, 'backend/voice')),
      timeout: cdk.Duration.seconds(20),
      memorySize: 256,
      environment,
      logGroup: turnLogs,
      description: 'One turn of the school phone call (backend/voice/lex_turn.py)',
    });
    this.turnFunction = turn;

    // Bedrock: only the one model, through its cross-region inference profile.
    const foundationModel = modelId.replace(/^(us|eu|apac|global)\./, '');
    turn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel'],
        resources: [
          `arn:${this.partition}:bedrock:${this.region}:${this.account}:inference-profile/${modelId}`,
          `arn:${this.partition}:bedrock:*::foundation-model/${foundationModel}*`,
        ],
      }),
    );
    // DynamoDB: put only, on the one table, only call records (pk CALLS).
    if (props.stateTableName) {
      turn.addToRolePolicy(
        new iam.PolicyStatement({
          actions: ['dynamodb:PutItem'],
          resources: [`arn:${this.partition}:dynamodb:${this.region}:${this.account}:table/${props.stateTableName}`],
          conditions: { 'ForAllValues:StringEquals': { 'dynamodb:LeadingKeys': ['CALLS'] } },
        }),
      );
    } else {
      cdk.Annotations.of(this).addWarning('No voiceStateTable: call transcripts will not be saved.');
    }

    // Lex V2: every utterance goes to the Lambda. Lex needs one real intent, so it gets a
    // phrase nobody says. While the Lambda waits on Bedrock, Lex says "One moment".
    const lexLogs = new logs.LogGroup(this, 'LexLogs', {
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    const botRole = new iam.Role(this, 'BotRole', {
      assumedBy: new iam.ServicePrincipal('lexv2.amazonaws.com'),
    });
    botRole.addToPolicy(new iam.PolicyStatement({ actions: ['polly:SynthesizeSpeech'], resources: ['*'] }));
    lexLogs.grantWrite(botRole);

    const hook = {
      enabled: true,
      fulfillmentUpdatesSpecification: {
        active: true,
        startResponse: {
          delayInSeconds: 1,
          allowInterrupt: false,
          messageGroups: [{ message: { plainTextMessage: { value: 'One moment.' } } }],
        },
        updateResponse: {
          frequencyInSeconds: 5,
          allowInterrupt: false,
          messageGroups: [{ message: { plainTextMessage: { value: 'Still with you.' } } }],
        },
        timeoutInSeconds: 30,
      },
    };
    const locales = [
      {
        localeId: 'en_US',
        nluConfidenceThreshold: 0.4,
        voiceSettings: { voiceId: VOICE, engine: 'neural' },
        intents: [
          { name: 'Placeholder', sampleUtterances: [{ utterance: 'zebra placeholder phrase' }], fulfillmentCodeHook: hook },
          { name: 'FallbackIntent', parentIntentSignature: 'AMAZON.FallbackIntent', fulfillmentCodeHook: hook },
        ],
      },
    ];
    const bot = new lex.CfnBot(this, 'Bot', {
      name: `${this.stackName}-SchoolCaller`,
      description: 'Speech to text and turn-taking for school phone calls',
      roleArn: botRole.roleArn,
      dataPrivacy: { ChildDirected: false },
      idleSessionTtlInSeconds: 600,
      autoBuildBotLocales: true,
      botLocales: locales,
    });
    // Lex versions are immutable: a new logical id per bot definition makes a new version
    // and moves the alias to it.
    const digest = crypto.createHash('sha256').update(JSON.stringify(locales)).digest('hex').slice(0, 8);
    const version = new lex.CfnBotVersion(this, `BotVersion${digest}`, {
      botId: bot.attrId,
      botVersionLocaleSpecification: [{ localeId: 'en_US', botVersionLocaleDetails: { sourceBotVersion: 'DRAFT' } }],
    });
    const alias = new lex.CfnBotAlias(this, 'BotAlias', {
      botId: bot.attrId,
      botAliasName: 'live',
      botVersion: version.attrBotVersion,
      botAliasLocaleSettings: [
        {
          localeId: 'en_US',
          botAliasLocaleSetting: {
            enabled: true,
            codeHookSpecification: {
              lambdaCodeHook: { lambdaArn: turn.functionArn, codeHookInterfaceVersion: '1.0' },
            },
          },
        },
      ],
      conversationLogSettings: {
        textLogSettings: [
          {
            enabled: true,
            destination: { cloudWatch: { cloudWatchLogGroupArn: lexLogs.logGroupArn, logPrefix: 'calls/' } },
          },
        ],
      },
    });
    this.botAliasArn = alias.attrArn;
    turn.addPermission('LexInvoke', {
      principal: new iam.ServicePrincipal('lexv2.amazonaws.com'),
      sourceArn: alias.attrArn,
    });

    new cdk.CfnOutput(this, 'TurnFunction', { value: turn.functionName });
    new cdk.CfnOutput(this, 'BotAliasArn', { value: alias.attrArn });

    if (!props.instanceId) {
      cdk.Annotations.of(this).addWarning('No voiceInstanceId: skipping the Connect flow and bot association.');
      return;
    }

    const instanceArn = `arn:${this.partition}:connect:${this.region}:${this.account}:instance/${props.instanceId}`;

    // Flow logs land in the instance's group /aws/connect/<alias>. The instance is imported,
    // so the attribute is set by an SDK call scoped to this one instance.
    const flowLogs = new cr.AwsCustomResource(this, 'FlowLogs', {
      onUpdate: {
        service: 'Connect',
        action: 'updateInstanceAttribute',
        parameters: { InstanceId: props.instanceId, AttributeType: 'CONTACTFLOW_LOGS', Value: 'true' },
        physicalResourceId: cr.PhysicalResourceId.of(`${props.instanceId}-flow-logs`),
      },
      policy: cr.AwsCustomResourcePolicy.fromStatements([
        new iam.PolicyStatement({ actions: ['connect:UpdateInstanceAttribute'], resources: [instanceArn] }),
      ]),
      installLatestAwsSdk: false,
    });

    // Lets the flow hand the call to the bot (same as connect:AssociateBot).
    const association = new connect.CfnIntegrationAssociation(this, 'BotAssociation', {
      instanceId: instanceArn,
      integrationType: 'LEX_BOT',
      integrationArn: alias.attrArn,
    });

    const session: Record<string, string> = {};
    for (const key of ['call_id', 'school_name', 'questions', 'opening']) session[key] = `$.Attributes.${key}`;
    Object.assign(session, LISTEN);
    const content = {
      Version: '2019-10-30',
      StartAction: 'logs',
      Actions: [
        {
          Identifier: 'logs',
          Type: 'UpdateFlowLoggingBehavior',
          Parameters: { FlowLoggingBehavior: 'Enabled' },
          Transitions: { NextAction: 'voice', Errors: [], Conditions: [] },
        },
        {
          Identifier: 'voice',
          Type: 'UpdateContactTextToSpeechVoice',
          Parameters: { TextToSpeechVoice: VOICE, TextToSpeechEngine: 'Neural' },
          Transitions: { NextAction: 'talk', Errors: [], Conditions: [] },
        },
        {
          Identifier: 'talk',
          Type: 'ConnectParticipantWithLexBot',
          Parameters: { Text: '$.Attributes.opening', LexV2Bot: { AliasArn: alias.attrArn }, LexSessionAttributes: session },
          Transitions: {
            NextAction: 'end',
            Errors: [
              { NextAction: 'end', ErrorType: 'NoMatchingError' },
              { NextAction: 'end', ErrorType: 'NoMatchingCondition' },
            ],
            Conditions: [],
          },
        },
        { Identifier: 'end', Type: 'DisconnectParticipant', Parameters: {}, Transitions: {} },
      ],
    };
    const flow = new connect.CfnContactFlow(this, 'Flow', {
      instanceArn,
      name: `GS school call (${this.stackName})`,
      type: 'CONTACT_FLOW',
      description: 'AI disclosure, then the Lex bot runs the call',
      content: this.toJsonString(content),
    });
    flow.node.addDependency(association, flowLogs);

    // Flow ARN: arn:aws:connect:<region>:<account>:instance/<instance id>/contact-flow/<flow id>
    new cdk.CfnOutput(this, 'FlowId', {
      value: cdk.Fn.select(3, cdk.Fn.split('/', flow.attrContactFlowArn)),
      description: 'Set as VOICE_FLOW_ID on the API',
    });
    new cdk.CfnOutput(this, 'InstanceId', { value: props.instanceId, description: 'VOICE_INSTANCE_ID' });

    if (props.claimNumber) {
      const number = new connect.CfnPhoneNumber(this, 'Number', {
        targetArn: instanceArn,
        type: 'TOLL_FREE',
        countryCode: 'US',
        description: 'Outbound caller id for school calls',
      });
      new cdk.CfnOutput(this, 'SourceNumber', { value: number.attrAddress, description: 'VOICE_SOURCE' });
    }
  }
}
