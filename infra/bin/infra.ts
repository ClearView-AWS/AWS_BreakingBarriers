#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib/core';
import { InfraStack } from '../lib/infra-stack';

// One stack, so `npx cdk deploy` works without naming it. It deploys to the
// account and region of your current AWS credentials (use us-east-1 for the
// `us.anthropic.*` Bedrock inference profiles).
//
// Options (pass with -c key=value):
//   hosting=false        only OpenSearch + DynamoDB, no Fargate/CloudFront
//   bedrock=0            run the API on the rules engine (no Bedrock calls)
//   fastModelId=...      override the router/extractor model id in models.yaml
//   strongModelId=...    override the explainer model id
const app = new cdk.App();
new InfraStack(app, 'InfraStack', {
  description: 'GreatSchools guided search: OpenSearch, DynamoDB, Fargate API, S3 + CloudFront frontend',
});
