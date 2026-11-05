import * as cdk from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import { AppStack } from '../lib/app-stack';

type SynthProps = {
  translateEnabled?: boolean;
  bedrockEnabled?: boolean;
  sesEnabled?: boolean;
  sesSource?: string;
  sesVerifiedTo?: string;
};

function synth(props: SynthProps = {}): Template {
  const app = new cdk.App();
  const stack = new AppStack(app, 'TestAppStack', { env: { account: '111111111111', region: 'us-east-1' }, ...props });
  return Template.fromStack(stack);
}

const template = synth();

test('API task can call Amazon Translate', () => {
  const policies = JSON.stringify(template.findResources('AWS::IAM::Policy'));
  for (const action of ['translate:TranslateText', 'translate:TranslateDocument', 'comprehend:DetectDominantLanguage']) {
    expect(policies).toContain(action);
  }
});

test('translation is on by default and can be turned off', () => {
  const env = (value: string) => ({
    ContainerDefinitions: Match.arrayWith([
      Match.objectLike({ Environment: Match.arrayWith([{ Name: 'TRANSLATE_ENABLED', Value: value }]) }),
    ]),
  });
  template.hasResourceProperties('AWS::ECS::TaskDefinition', env('1'));
  synth({ translateEnabled: false }).hasResourceProperties('AWS::ECS::TaskDefinition', env('0'));
});

test('runtime state uses a DynamoDB table shared across Fargate replaces', () => {
  template.hasResourceProperties('AWS::DynamoDB::Table', {
    BillingMode: 'PAY_PER_REQUEST',
    KeySchema: [
      { AttributeName: 'pk', KeyType: 'HASH' },
      { AttributeName: 'sk', KeyType: 'RANGE' },
    ],
  });
  const task = JSON.stringify(template.findResources('AWS::ECS::TaskDefinition'));
  expect(task).toContain('GS_DYNAMODB_TABLE');
});

test('Bedrock on creates the post guardrail and lets the task apply it', () => {
  const withBedrock = synth({ bedrockEnabled: true });
  withBedrock.hasResourceProperties('AWS::Bedrock::Guardrail', {
    SensitiveInformationPolicyConfig: {
      PiiEntitiesConfig: Match.arrayWith([{ Type: 'NAME', Action: 'BLOCK' }, { Type: 'EMAIL', Action: 'BLOCK' }]),
    },
  });
  withBedrock.resourceCountIs('AWS::Bedrock::GuardrailVersion', 1);
  const task = JSON.stringify(withBedrock.findResources('AWS::ECS::TaskDefinition'));
  expect(task).toContain('BEDROCK_GUARDRAIL_ID');
  expect(task).toContain('BEDROCK_GUARDRAIL_VERSION');
  expect(JSON.stringify(withBedrock.findResources('AWS::IAM::Policy'))).toContain('bedrock:ApplyGuardrail');
});

test('Bedrock off creates no guardrail', () => {
  template.resourceCountIs('AWS::Bedrock::Guardrail', 0);
});

test('SES is off by default with no SendEmail permission', () => {
  template.hasResourceProperties('AWS::ECS::TaskDefinition', {
    ContainerDefinitions: Match.arrayWith([
      Match.objectLike({ Environment: Match.arrayWith([{ Name: 'SES_ENABLED', Value: '0' }]) }),
    ]),
  });
  const policies = JSON.stringify(template.findResources('AWS::IAM::Policy'));
  expect(policies).not.toContain('ses:SendEmail');
  const task = JSON.stringify(template.findResources('AWS::ECS::TaskDefinition'));
  expect(task).not.toContain('SES_SOURCE');
  expect(task).not.toContain('SES_VERIFIED_TO');
});

test('SES on sets env and scopes SendEmail to the verified identities', () => {
  const withSes = synth({
    sesEnabled: true,
    sesSource: 'sender@example.com',
    sesVerifiedTo: 'verified@example.com',
  });
  withSes.hasResourceProperties('AWS::ECS::TaskDefinition', {
    ContainerDefinitions: Match.arrayWith([
      Match.objectLike({
        Environment: Match.arrayWith([
          { Name: 'SES_ENABLED', Value: '1' },
          { Name: 'SES_SOURCE', Value: 'sender@example.com' },
          { Name: 'SES_VERIFIED_TO', Value: 'verified@example.com' },
        ]),
      }),
    ]),
  });
  const policies = JSON.stringify(withSes.findResources('AWS::IAM::Policy'));
  expect(policies).toContain('ses:SendEmail');
  expect(policies).toContain('identity/sender@example.com');
  expect(policies).toContain('identity/verified@example.com');
});

test('SES on without addresses fails at synth', () => {
  expect(() => synth({ sesEnabled: true })).toThrow(/SES_SOURCE and SES_VERIFIED_TO/);
});
