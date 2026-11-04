import * as cdk from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import { AppStack } from '../lib/app-stack';

function synth(props: { translateEnabled?: boolean } = {}): Template {
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
