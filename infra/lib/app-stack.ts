import * as fs from 'fs';
import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecrAssets from 'aws-cdk-lib/aws-ecr-assets';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecsPatterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';

export interface AppStackProps extends cdk.StackProps {
  /** OpenSearch endpoint hostname without https:// */
  openSearchEndpoint?: string;
  bedrockEnabled?: boolean;
  /** Amazon Translate: read and answer parents in any language. On unless set to false. */
  translateEnabled?: boolean;
  /**
   * Amazon SES sandbox mailer (backend/gaps/ses_mailer.py). Off by default.
   * When on, SES_SOURCE and SES_VERIFIED_TO must be set (props or env). Identities
   * are verified by hand in the console — CDK does not create them.
   */
  sesEnabled?: boolean;
  /** Verified From address. Falls back to process.env.SES_SOURCE. */
  sesSource?: string;
  /** Verified To address (sandbox delivers only here). Falls back to process.env.SES_VERIFIED_TO. */
  sesVerifiedTo?: string;
}

export function repoRootFrom(start: string): string {
  let dir = start;
  for (let i = 0; i < 8; i++) {
    if (fs.existsSync(path.join(dir, 'Dockerfile')) && fs.existsSync(path.join(dir, 'frontend'))) {
      return dir;
    }
    dir = path.dirname(dir);
  }
  throw new Error(`Could not locate repo root from ${start}`);
}

/**
 * Demo hosting: CloudFront → S3 (React) + ALB/Fargate (FastAPI).
 * Parents open the CloudFront URL; /api/* goes to the container.
 */
export class AppStack extends cdk.Stack {
  public readonly distributionDomainName: string;

  constructor(scope: Construct, id: string, props: AppStackProps = {}) {
    super(scope, id, props);

    const repoRoot = repoRootFrom(__dirname);
    const bedrockEnabled = props.bedrockEnabled ?? false;
    const translateEnabled = props.translateEnabled ?? true;
    const sesEnabled = props.sesEnabled ?? false;
    const sesSource = props.sesSource || process.env.SES_SOURCE || '';
    const sesVerifiedTo = props.sesVerifiedTo || process.env.SES_VERIFIED_TO || '';
    if (sesEnabled && (!sesSource || !sesVerifiedTo)) {
      throw new Error(
        'sesEnabled requires SES_SOURCE and SES_VERIFIED_TO (props or env). ' +
          'Verify both addresses in the SES console first (sandbox delivers only to verified identities).',
      );
    }

    const vpc = new ec2.Vpc(this, 'Vpc', {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        {
          name: 'public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
      ],
    });

    const cluster = new ecs.Cluster(this, 'Cluster', { vpc });

    // One table stands in for the local state.json so task replaces keep sessions.
    const stateTable = new dynamodb.Table(this, 'RuntimeState', {
      partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const environment: Record<string, string> = {
      GS_STATE_PATH: '/tmp/gs-state.json',
      GS_TODAY: '2026-11-03',
      AWS_REGION: cdk.Stack.of(this).region,
      BEDROCK_ENABLED: bedrockEnabled ? '1' : '0',
      TRANSLATE_ENABLED: translateEnabled ? '1' : '0',
      SES_ENABLED: sesEnabled ? '1' : '0',
      GS_DYNAMODB_TABLE: stateTable.tableName,
    };
    if (sesEnabled) {
      environment.SES_SOURCE = sesSource;
      environment.SES_VERIFIED_TO = sesVerifiedTo;
    }
    // Bedrock Guardrails: second check on every community post (backend/community/safety.py).
    let guardrail: bedrock.CfnGuardrail | undefined;
    if (bedrockEnabled) {
      const blocked = 'This post includes personal information. Please rephrase without it.';
      guardrail = new bedrock.CfnGuardrail(this, 'PostGuardrail', {
        name: `${cdk.Stack.of(this).stackName}-community-pii`,
        description: 'Blocks names, emails, phone numbers and addresses in parent community posts',
        blockedInputMessaging: blocked,
        blockedOutputsMessaging: blocked,
        sensitiveInformationPolicyConfig: {
          piiEntitiesConfig: ['NAME', 'EMAIL', 'PHONE', 'ADDRESS'].map((type) => ({ type, action: 'BLOCK' })),
        },
      });
      const version = new bedrock.CfnGuardrailVersion(this, 'PostGuardrailVersion', {
        guardrailIdentifier: guardrail.attrGuardrailId,
      });
      environment.BEDROCK_GUARDRAIL_ID = guardrail.attrGuardrailId;
      environment.BEDROCK_GUARDRAIL_VERSION = version.attrVersion;
    }
    // School phone calls (backend/gaps/phone.py). On only when the deploy shell sets all four;
    // VOICE_VERIFIED_TO is the one number calls may reach and never lives in the repo.
    const voiceKeys = ['VOICE_INSTANCE_ID', 'VOICE_FLOW_ID', 'VOICE_SOURCE', 'VOICE_VERIFIED_TO'];
    const voiceEnabled = voiceKeys.every((key) => !!process.env[key]);
    if (voiceEnabled) {
      environment.VOICE_ENABLED = '1';
      for (const key of voiceKeys) environment[key] = process.env[key] as string;
    }
    if (props.openSearchEndpoint) {
      environment.OPENSEARCH_URL = props.openSearchEndpoint.startsWith('http')
        ? props.openSearchEndpoint
        : `https://${props.openSearchEndpoint}`;
    }

    const service = new ecsPatterns.ApplicationLoadBalancedFargateService(this, 'Api', {
      cluster,
      cpu: 512,
      memoryLimitMiB: 1024,
      desiredCount: 1,
      publicLoadBalancer: true,
      assignPublicIp: true,
      listenerPort: 80,
      circuitBreaker: { rollback: true },
      // Single-task demo: allow 0 healthy during replace so deploys can proceed.
      minHealthyPercent: 0,
      maxHealthyPercent: 200,
      healthCheckGracePeriod: cdk.Duration.seconds(120),
      // Mac/Apple Silicon builds ARM images; Fargate default is amd64.
      runtimePlatform: {
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
        cpuArchitecture: ecs.CpuArchitecture.X86_64,
      },
      taskImageOptions: {
        image: ecs.ContainerImage.fromAsset(repoRoot, {
          file: 'Dockerfile',
          platform: ecrAssets.Platform.LINUX_AMD64,
        }),
        containerPort: 8000,
        environment,
      },
    });

    service.targetGroup.configureHealthCheck({
      path: '/api/health',
      healthyHttpCodes: '200',
      interval: cdk.Duration.seconds(15),
      timeout: cdk.Duration.seconds(5),
      healthyThresholdCount: 2,
      unhealthyThresholdCount: 5,
    });

    stateTable.grantReadWriteData(service.taskDefinition.taskRole);
    if (voiceEnabled) {
      const instance = `arn:aws:connect:${this.region}:${this.account}:instance/${process.env.VOICE_INSTANCE_ID}`;
      service.taskDefinition.addToTaskRolePolicy(
        new iam.PolicyStatement({
          actions: ['connect:StartOutboundVoiceContact', 'connect:DescribeContact'],
          resources: [instance, `${instance}/*`],
        }),
      );
    }
    service.taskDefinition.addToTaskRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
        resources: ['*'],
      }),
    );
    if (guardrail) {
      service.taskDefinition.addToTaskRolePolicy(
        new iam.PolicyStatement({
          actions: ['bedrock:ApplyGuardrail'],
          resources: [guardrail.attrGuardrailArn],
        }),
      );
    }
    // Amazon Translate (backend/agent/translate.py): each message is read in any language
    // (TranslateText with automatic detection, which calls Comprehend) and the reply and UI
    // strings are translated back (TranslateDocument, TranslateText). No resources to scope to.
    service.taskDefinition.addToTaskRolePolicy(
      new iam.PolicyStatement({
        actions: ['translate:TranslateText', 'translate:TranslateDocument', 'comprehend:DetectDominantLanguage'],
        resources: ['*'],
      }),
    );
    // Amazon SES sandbox (backend/gaps/ses_mailer.py). Identities stay out of CDK so a
    // deploy never emails an unverified address; verify Source and To in the console first.
    if (sesEnabled) {
      const identityArn = (address: string) =>
        `arn:aws:ses:${this.region}:${this.account}:identity/${address}`;
      service.taskDefinition.addToTaskRolePolicy(
        new iam.PolicyStatement({
          actions: ['ses:SendEmail', 'ses:SendRawEmail'],
          resources: [identityArn(sesSource), identityArn(sesVerifiedTo)],
        }),
      );
    }
    service.taskDefinition.addToTaskRolePolicy(
      new iam.PolicyStatement({
        actions: ['es:ESHttpGet', 'es:ESHttpPost', 'es:ESHttpPut', 'es:ESHttpHead'],
        resources: ['*'],
      }),
    );

    const webBucket = new s3.Bucket(this, 'WebBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const distribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultRootObject: 'index.html',
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(webBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      additionalBehaviors: {
        '/api/*': {
          origin: new origins.LoadBalancerV2Origin(service.loadBalancer, {
            protocolPolicy: cloudfront.OriginProtocolPolicy.HTTP_ONLY,
            httpPort: 80,
          }),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER,
        },
      },
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.minutes(1),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.minutes(1),
        },
      ],
    });

    const frontendDist = path.join(repoRoot, 'frontend/dist');
    if (!fs.existsSync(path.join(frontendDist, 'index.html'))) {
      throw new Error(
        `Missing ${frontendDist}/index.html. Run: cd frontend && npm ci && npm run build`,
      );
    }

    new s3deploy.BucketDeployment(this, 'DeployWeb', {
      sources: [s3deploy.Source.asset(frontendDist)],
      destinationBucket: webBucket,
      distribution,
      distributionPaths: ['/*'],
    });

    this.distributionDomainName = distribution.distributionDomainName;

    new cdk.CfnOutput(this, 'CloudFrontURL', {
      value: `https://${distribution.distributionDomainName}`,
      description: 'Parent-facing demo URL (replaces the old IP address)',
    });
    new cdk.CfnOutput(this, 'LoadBalancerDNS', {
      value: service.loadBalancer.loadBalancerDnsName,
    });
    new cdk.CfnOutput(this, 'StateTableName', {
      value: stateTable.tableName,
      description: 'Pass as voiceStateTable to GsVoiceStack',
    });
    new cdk.CfnOutput(this, 'BedrockEnabled', {
      value: environment.BEDROCK_ENABLED,
    });
  }
}
