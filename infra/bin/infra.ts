#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib/core';
import { AppStack } from '../lib/app-stack';
import { InfraStack } from '../lib/infra-stack';

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
const openSearchEndpoint = app.node.tryGetContext('openSearchEndpoint') as string | undefined;

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
});
