import * as cdk from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import { GatewayStack } from '../lib/gateway-stack';

const app = new cdk.App();
const stack = new GatewayStack(app, 'TestGatewayStack', { env: { account: '111111111111', region: 'us-east-1' } });
const template = Template.fromStack(stack);

test('school tools Lambda is an x86_64 container image', () => {
  template.hasResourceProperties('AWS::Lambda::Function', {
    PackageType: 'Image',
    Architectures: ['x86_64'],
    Timeout: 30,
  });
});

test('gateway serves MCP and requires SigV4', () => {
  template.hasResourceProperties('AWS::BedrockAgentCore::Gateway', {
    ProtocolType: 'MCP',
    AuthorizerType: 'AWS_IAM',
  });
  template.hasResourceProperties('AWS::BedrockAgentCore::GatewayTarget', {
    CredentialProviderConfigurations: [{ CredentialProviderType: 'GATEWAY_IAM_ROLE' }],
  });
});

test('gateway role is trusted only by AgentCore and invokes only the tools Lambda', () => {
  template.hasResourceProperties('AWS::IAM::Role', {
    AssumeRolePolicyDocument: {
      Statement: [Match.objectLike({ Principal: { Service: 'bedrock-agentcore.amazonaws.com' } })],
    },
  });
  const statements = Object.values(template.findResources('AWS::IAM::Policy')).flatMap(
    (policy: any) => policy.Properties.PolicyDocument.Statement,
  );
  expect(statements).toHaveLength(1);
  expect(statements[0].Action).toBe('lambda:InvokeFunction');
  for (const resource of statements[0].Resource) {
    expect(JSON.stringify(resource)).toContain('SchoolTools');
  }
});
