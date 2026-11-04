import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import { InfraStack } from '../lib/infra-stack';

function synth(props: { hosting?: boolean } = {}): Template {
  const app = new cdk.App();
  const stack = new InfraStack(app, 'TestStack', {
    ...props,
    webSource: s3deploy.Source.asset(path.join(__dirname, 'fixtures', 'web')),
    apiImage: ecs.ContainerImage.fromRegistry('public.ecr.aws/docker/library/python:3.12-slim'),
  });
  return Template.fromStack(stack);
}

test('keeps the shared OpenSearch domain under its original logical id', () => {
  const template = synth({ hosting: false });
  const domains = template.findResources('AWS::OpenSearchService::Domain');
  expect(Object.keys(domains)).toHaveLength(1);
  expect(Object.keys(domains)[0]).toMatch(/^SearchDomain/);
  template.resourceCountIs('AWS::ECS::Service', 0);
});

test('state table is on-demand with pk/sk', () => {
  synth().hasResourceProperties('AWS::DynamoDB::GlobalTable', {
    KeySchema: [
      { AttributeName: 'pk', KeyType: 'HASH' },
      { AttributeName: 'sk', KeyType: 'RANGE' },
    ],
    BillingMode: 'PAY_PER_REQUEST',
  });
});

test('task role can call Bedrock, OpenSearch and DynamoDB', () => {
  const template = synth();
  const policies = JSON.stringify(template.findResources('AWS::IAM::Policy'));
  for (const action of ['bedrock:InvokeModel', 'aws-marketplace:Subscribe', 'es:ESHttpGet', 'es:ESHttpPost', 'dynamodb:PutItem', 'dynamodb:Query']) {
    expect(policies).toContain(action);
  }
});

test('API container gets the AWS wiring and logs to CloudWatch', () => {
  const template = synth();
  template.hasResourceProperties('AWS::ECS::TaskDefinition', {
    ContainerDefinitions: Match.arrayWith([
      Match.objectLike({
        Environment: Match.arrayWith([
          Match.objectLike({ Name: 'STATE_TABLE' }),
          Match.objectLike({ Name: 'OPENSEARCH_URL' }),
          { Name: 'BEDROCK_ENABLED', Value: '1' },
          { Name: 'INDEX_ON_START', Value: '1' },
        ]),
        LogConfiguration: Match.objectLike({ LogDriver: 'awslogs' }),
      }),
    ]),
  });
  template.hasResourceProperties('AWS::Logs::LogGroup', { LogGroupName: '/gs-guided/api', RetentionInDays: 7 });
  template.resourceCountIs('AWS::Logs::QueryDefinition', 2);
});

test('frontend bucket is private and served through CloudFront OAC, /api/* goes to the ALB', () => {
  const template = synth();
  template.hasResourceProperties('AWS::S3::Bucket', {
    PublicAccessBlockConfiguration: {
      BlockPublicAcls: true,
      BlockPublicPolicy: true,
      IgnorePublicAcls: true,
      RestrictPublicBuckets: true,
    },
  });
  template.resourceCountIs('AWS::CloudFront::OriginAccessControl', 1);
  template.hasResourceProperties('AWS::CloudFront::Distribution', {
    DistributionConfig: Match.objectLike({
      CacheBehaviors: [Match.objectLike({ PathPattern: '/api/*' })],
    }),
  });
  // The ALB refuses requests that did not come through CloudFront.
  template.hasResourceProperties('AWS::ElasticLoadBalancingV2::Listener', {
    DefaultActions: [Match.objectLike({ Type: 'fixed-response' })],
  });
  template.resourceCountIs('AWS::EC2::NatGateway', 0);
});
