import * as fs from 'fs';
import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as agentcore from 'aws-cdk-lib/aws-bedrockagentcore';
import * as ecrAssets from 'aws-cdk-lib/aws-ecr-assets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { repoRootFrom } from './app-stack';

/**
 * AgentCore Gateway: the school tools in backend/mcp_tools.py, served over MCP.
 * Callers sign requests with SigV4 (AWS_IAM); the gateway invokes one Lambda target.
 */
export class GatewayStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: cdk.StackProps = {}) {
    super(scope, id, props);

    const repoRoot = repoRootFrom(__dirname);
    const toolSchemas = JSON.parse(
      fs.readFileSync(path.join(repoRoot, 'backend/config/mcp_tools.json'), 'utf8'),
    );

    const toolsFn = new lambda.DockerImageFunction(this, 'SchoolTools', {
      code: lambda.DockerImageCode.fromImageAsset(repoRoot, {
        file: 'Dockerfile.gateway',
        platform: ecrAssets.Platform.LINUX_AMD64,
      }),
      architecture: lambda.Architecture.X86_64,
      memorySize: 1024,
      timeout: cdk.Duration.seconds(30),
      description: 'MCP tools for the AgentCore Gateway (backend/mcp_tools.py)',
    });

    const gatewayRole = new iam.Role(this, 'GatewayRole', {
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
    });
    toolsFn.grantInvoke(gatewayRole);

    const gateway = new agentcore.CfnGateway(this, 'Gateway', {
      name: 'gs-school-tools',
      description: 'GreatSchools guided search — school data tools over MCP',
      protocolType: 'MCP',
      authorizerType: 'AWS_IAM',
      roleArn: gatewayRole.roleArn,
    });

    const target = new agentcore.CfnGatewayTarget(this, 'SchoolDataTarget', {
      gatewayIdentifier: gateway.attrGatewayIdentifier,
      name: 'school-data',
      description: 'Schools, facts, cost, and glossary from the app corpus',
      credentialProviderConfigurations: [{ credentialProviderType: 'GATEWAY_IAM_ROLE' }],
      targetConfiguration: {
        mcp: {
          lambda: {
            lambdaArn: toolsFn.functionArn,
            toolSchema: { inlinePayload: toolSchemas },
          },
        },
      },
    });
    // The gateway checks it can invoke the Lambda when the target is created.
    target.node.addDependency(gatewayRole);

    new cdk.CfnOutput(this, 'GatewayUrl', { value: gateway.attrGatewayUrl });
    new cdk.CfnOutput(this, 'GatewayId', { value: gateway.attrGatewayIdentifier });
    new cdk.CfnOutput(this, 'ToolsFunction', { value: toolsFn.functionName });
  }
}
