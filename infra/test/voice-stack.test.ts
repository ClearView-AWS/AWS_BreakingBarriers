import * as cdk from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import { VoiceStack, VoiceStackProps } from '../lib/voice-stack';

const env = { account: '111111111111', region: 'us-east-1' };
const instanceArn = 'arn:aws:connect:us-east-1:111111111111:instance/00000000-aaaa-bbbb-cccc-000000000000';

function synth(props: VoiceStackProps = {}): Template {
  // Same flag as cdk.json, so ARNs read 'arn:aws:' instead of a partition token.
  const app = new cdk.App({ context: { '@aws-cdk/core:enablePartitionLiterals': true } });
  const stack = new VoiceStack(app, 'TestVoiceStack', {
    env,
    instanceId: '00000000-aaaa-bbbb-cccc-000000000000',
    stateTableName: 'GsAppStack-RuntimeState-TEST',
    ...props,
  });
  return Template.fromStack(stack);
}

const template = synth();

// Every IAM statement in the stack, flattened.
function statements(t: Template): any[] {
  return Object.values(t.findResources('AWS::IAM::Policy')).flatMap(
    (policy: any) => policy.Properties.PolicyDocument.Statement,
  );
}
const asList = (value: any) => (Array.isArray(value) ? value : [value]);

test('voice turn Lambda runs lex_turn.py on Python 3.12', () => {
  template.hasResourceProperties('AWS::Lambda::Function', {
    Runtime: 'python3.12',
    Handler: 'lex_turn.handler',
    Timeout: 20,
    Environment: { Variables: Match.objectLike({ GS_DYNAMODB_TABLE: 'GsAppStack-RuntimeState-TEST' }) },
  });
});

test('Lambda may only put call records on the one table', () => {
  const dynamo = statements(template).filter((s) => asList(s.Action).some((a: string) => a.startsWith('dynamodb:')));
  expect(dynamo).toHaveLength(1);
  expect(dynamo[0].Action).toBe('dynamodb:PutItem');
  expect(JSON.stringify(dynamo[0].Resource)).toContain('table/GsAppStack-RuntimeState-TEST');
  expect(dynamo[0].Condition).toEqual({ 'ForAllValues:StringEquals': { 'dynamodb:LeadingKeys': ['CALLS'] } });
});

test('Bedrock access is one model, not *', () => {
  const bedrock = statements(template).filter((s) => asList(s.Action).includes('bedrock:InvokeModel'));
  expect(bedrock).toHaveLength(1);
  const resources = JSON.stringify(bedrock[0].Resource);
  expect(resources).toContain('inference-profile/us.anthropic.claude-haiku-5-5');
  expect(resources).toContain('foundation-model/anthropic.claude-haiku-5-5');
  expect(bedrock[0].Resource).not.toContain('*');
});

test('Lex bot, version and alias are wired to the Lambda', () => {
  template.hasResourceProperties('AWS::Lex::Bot', {
    AutoBuildBotLocales: true,
    BotLocales: [
      Match.objectLike({
        LocaleId: 'en_US',
        VoiceSettings: { VoiceId: 'Joanna', Engine: 'neural' },
        Intents: Match.arrayWith([Match.objectLike({ ParentIntentSignature: 'AMAZON.FallbackIntent' })]),
      }),
    ],
  });
  template.resourceCountIs('AWS::Lex::BotVersion', 1);
  template.hasResourceProperties('AWS::Lex::BotAlias', {
    BotAliasName: 'live',
    BotVersion: { 'Fn::GetAtt': [Match.stringLikeRegexp('^BotVersion'), 'BotVersion'] },
    BotAliasLocaleSettings: [
      Match.objectLike({
        BotAliasLocaleSetting: Match.objectLike({
          CodeHookSpecification: {
            LambdaCodeHook: { LambdaArn: { 'Fn::GetAtt': [Match.stringLikeRegexp('^Turn'), 'Arn'] }, CodeHookInterfaceVersion: '1.0' },
          },
        }),
      }),
    ],
  });
  template.hasResourceProperties('AWS::Lambda::Permission', {
    Principal: 'lexv2.amazonaws.com',
    SourceArn: { 'Fn::GetAtt': [Match.stringLikeRegexp('^BotAlias'), 'Arn'] },
  });
});

test('Connect flow hands the call to the bot on the imported instance', () => {
  template.hasResourceProperties('AWS::Connect::IntegrationAssociation', {
    InstanceId: instanceArn,
    IntegrationType: 'LEX_BOT',
  });
  template.hasResourceProperties('AWS::Connect::ContactFlow', { InstanceArn: instanceArn, Type: 'CONTACT_FLOW' });
  const flow = JSON.stringify(template.findResources('AWS::Connect::ContactFlow'));
  for (const step of ['UpdateFlowLoggingBehavior', 'ConnectParticipantWithLexBot', 'x-amz-lex:allow-interrupt']) {
    expect(flow).toContain(step);
  }
  template.hasOutput('FlowId', {});
});

test('every Connect action is scoped to the one instance ARN', () => {
  const connect = statements(template).filter((s) => asList(s.Action).some((a: string) => a.startsWith('connect:')));
  expect(connect.length).toBeGreaterThan(0);
  for (const s of connect) {
    for (const resource of asList(s.Resource)) {
      expect(resource).toBe(instanceArn);
    }
  }
});

test('Lambda and Lex conversation logs have their own log groups with retention', () => {
  template.resourceCountIs('AWS::Logs::LogGroup', 2);
  template.hasResourceProperties('AWS::Logs::LogGroup', { RetentionInDays: 14 });
  template.hasResourceProperties('AWS::Lex::BotAlias', {
    ConversationLogSettings: { TextLogSettings: [Match.objectLike({ Enabled: true })] },
  });
});

test('no phone number is claimed unless asked', () => {
  template.resourceCountIs('AWS::Connect::PhoneNumber', 0);
  synth({ claimNumber: true }).hasResourceProperties('AWS::Connect::PhoneNumber', {
    TargetArn: instanceArn,
    Type: 'TOLL_FREE',
    CountryCode: 'US',
  });
});

test('without an instance id the stack still synthesizes Lambda + Lex only', () => {
  const bare = synth({ instanceId: undefined, stateTableName: undefined });
  bare.resourceCountIs('AWS::Lex::Bot', 1);
  bare.resourceCountIs('AWS::Connect::ContactFlow', 0);
  bare.resourceCountIs('AWS::Connect::IntegrationAssociation', 0);
  expect(statements(bare).some((s) => asList(s.Action).some((a: string) => a.startsWith('dynamodb:')))).toBe(false);
});
