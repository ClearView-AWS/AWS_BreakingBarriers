import * as fs from 'fs';
import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecrAssets from 'aws-cdk-lib/aws-ecr-assets';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecsPatterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';

export interface AppStackProps extends cdk.StackProps {
  /** OpenSearch endpoint hostname without https:// */
  openSearchEndpoint?: string;
  bedrockEnabled?: boolean;
}

function repoRootFrom(start: string): string {
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

    const environment: Record<string, string> = {
      GS_STATE_PATH: '/tmp/gs-state.json',
      GS_TODAY: '2026-11-03',
      AWS_REGION: cdk.Stack.of(this).region,
      BEDROCK_ENABLED: bedrockEnabled ? '1' : '0',
    };
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

    service.taskDefinition.addToTaskRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
        resources: ['*'],
      }),
    );
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
    new cdk.CfnOutput(this, 'BedrockEnabled', {
      value: environment.BEDROCK_ENABLED,
    });
  }
}
