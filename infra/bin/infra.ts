#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib/core';
import { AppStack } from '../lib/app-stack';
import { GatewayStack } from '../lib/gateway-stack';
import { InfraStack } from '../lib/infra-stack';
import { VoiceStack } from '../lib/voice-stack';

const app = new cdk.App();

const env =
  process.env.CDK_DEFAULT_ACCOUNT && process.env.CDK_DEFAULT_REGION
    ? {
        account: process.env.CDK_DEFAULT_ACCOUNT,
        region: process.env.CDK_DEFAULT_REGION,
      }
    : {
        // Account filled in at deploy time from the caller's credentials.
        region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
      };

const enableOpenSearch = String(app.node.tryGetContext('enableOpenSearch') ?? 'true') !== 'false';
const bedrockEnabled = String(app.node.tryGetContext('bedrockEnabled') ?? 'false') === 'true';
const translateEnabled = String(app.node.tryGetContext('translateEnabled') ?? 'true') !== 'false';
const sesEnabled = String(app.node.tryGetContext('sesEnabled') ?? 'false') === 'true';
const openSearchEndpoint = app.node.tryGetContext('openSearchEndpoint') as string | undefined;
const sesSource =
  (app.node.tryGetContext('sesSource') as string | undefined) || process.env.SES_SOURCE || undefined;
const sesVerifiedTo =
  (app.node.tryGetContext('sesVerifiedTo') as string | undefined) ||
  process.env.SES_VERIFIED_TO ||
  undefined;

if (enableOpenSearch) {
  new InfraStack(app, 'GsOpenSearchStack', {
    env,
    description: 'GreatSchools guided search — OpenSearch domain',
  });
}

new AppStack(app, 'GsAppStack', {
  env,
  description: 'GreatSchools guided search — CloudFront + Fargate demo',
  openSearchEndpoint,
  bedrockEnabled,
  translateEnabled,
  sesEnabled,
  sesSource,
  sesVerifiedTo,
});

new GatewayStack(app, 'GsGatewayStack', {
  env,
  description: 'GreatSchools guided search — AgentCore Gateway (MCP school tools)',
});

// Not in the default demo deploy. Connect instance is imported by id (see lib/voice-stack.ts).
const context = (key: string, envKey: string) =>
  (app.node.tryGetContext(key) as string | undefined) || process.env[envKey] || undefined;
new VoiceStack(app, 'GsVoiceStack', {
  env,
  description: 'GreatSchools guided search — school phone call (Connect, Lex V2, Lambda)',
  instanceId: context('voiceInstanceId', 'VOICE_INSTANCE_ID'),
  stateTableName: context('voiceStateTable', 'GS_DYNAMODB_TABLE'),
  modelId: context('voiceModelId', 'VOICE_MODEL_ID'),
  claimNumber: String(app.node.tryGetContext('voiceClaimNumber') ?? 'false') === 'true',
});
