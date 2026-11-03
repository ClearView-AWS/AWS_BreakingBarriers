import * as path from 'path';
import { execSync } from 'child_process';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecrAssets from 'aws-cdk-lib/aws-ecr-assets';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as opensearch from 'aws-cdk-lib/aws-opensearchservice';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';

const REPO_ROOT = path.join(__dirname, '..', '..');
const FRONTEND_DIR = path.join(REPO_ROOT, 'frontend');
const ORIGIN_HEADER = 'X-Origin-Verify';

export interface InfraStackProps extends cdk.StackProps {
  /**
   * Deploy the demo hosting (Fargate API, ALB, S3 + CloudFront). Default true.
   * Also settable with `-c hosting=false`, which leaves only OpenSearch and DynamoDB.
   */
  readonly hosting?: boolean;
  /** Frontend build to upload. Defaults to building `frontend/` during synth. Tests pass a stub. */
  readonly webSource?: s3deploy.ISource;
  /** API image. Defaults to `backend/Dockerfile` built from the repo root. Tests pass a stub. */
  readonly apiImage?: ecs.ContainerImage;
}

/**
 * Everything the guided-search demo runs on, in one stack so
 * `npx cdk deploy` needs no stack name.
 *
 *   Browser ──HTTPS──► CloudFront ─┬─ /*      ─► S3 web bucket (private, OAC)
 *                                  └─ /api/*  ─► ALB ─► Fargate task (FastAPI)
 *                                                        ├─► Bedrock (route, extract, embed)
 *                                                        ├─► OpenSearch (schools, programs)
 *                                                        ├─► DynamoDB (sessions, saved, feedback, inbox)
 *                                                        └─► CloudWatch Logs (one JSON line per turn)
 */
export class InfraStack extends cdk.Stack {
  public readonly domain: opensearch.Domain;
  public readonly stateTable: dynamodb.TableV2;

  constructor(scope: Construct, id: string, props: InfraStackProps = {}) {
    super(scope, id, props);
    cdk.Tags.of(this).add('Project', 'greatschools-guided-search');

    // ---------------------------------------------------------------- shared, day 0
    // Construct id 'SearchDomain' must not change: the shared sandbox already runs this domain.
    this.domain = new opensearch.Domain(this, 'SearchDomain', {
      version: opensearch.EngineVersion.OPENSEARCH_2_17,
      capacity: {
        dataNodes: 1,
        dataNodeInstanceType: 't3.small.search',
        multiAzWithStandbyEnabled: false,
      },
      ebs: { volumeSize: 10 },
      zoneAwareness: { enabled: false },
      enforceHttps: true,
      nodeToNodeEncryption: true,
      encryptionAtRest: { enabled: true },
      // Trusts the account. Each caller still needs its own IAM permission (see the task role below).
      accessPolicies: [
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          principals: [new iam.AccountRootPrincipal()],
          actions: ['es:*'],
          resources: ['*'],
        }),
      ],
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // One table for sessions, saved lists, feedback, the school inbox and school answers.
    // Key layout is documented in backend/store.py.
    this.stateTable = new dynamodb.TableV2(this, 'StateTable', {
      partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
      billing: dynamodb.Billing.onDemand(),
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    new cdk.CfnOutput(this, 'DomainEndpoint', { value: this.domain.domainEndpoint });
    new cdk.CfnOutput(this, 'DomainName', { value: this.domain.domainName });
    new cdk.CfnOutput(this, 'StateTableName', { value: this.stateTable.tableName });

    const hostingContext = this.node.tryGetContext('hosting');
    const hosting = props.hosting ?? (hostingContext === undefined ? true : String(hostingContext) !== 'false');
    if (hosting) {
      this.addHosting(props);
    }
  }

  private addHosting(props: InfraStackProps): void {
    const ctx = (key: string): string | undefined => {
      const value = this.node.tryGetContext(key);
      return value === undefined || value === '' ? undefined : String(value);
    };

    // ---------------------------------------------------------------- logs
    const logGroup = new logs.LogGroup(this, 'ApiLogs', {
      logGroupName: '/gs-guided/api',
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Saved Logs Insights queries: open CloudWatch > Logs Insights > Saved queries.
    new logs.QueryDefinition(this, 'TurnsQuery', {
      queryDefinitionName: 'gs-guided/turns',
      logGroups: [logGroup],
      queryString: new logs.QueryString({
        fields: ['@timestamp', 'trace_id', 'session_id', 'message', 'route', 'criteria', 'searches', 'results', 'bedrock', 'duration_ms'],
        filterStatements: ['event = "turn"'],
        sort: '@timestamp desc',
        limit: 100,
      }),
    });
    new logs.QueryDefinition(this, 'FallbacksQuery', {
      queryDefinitionName: 'gs-guided/fallbacks-and-errors',
      logGroups: [logGroup],
      queryString: new logs.QueryString({
        fields: ['@timestamp', 'trace_id', 'session_id', 'message', 'error', 'searches.0.opensearch', 'searches.0.error', 'bedrock.0.ok', 'bedrock.0.error'],
        filterStatements: [
          'ispresent(error) or searches.0.opensearch != "on" or bedrock.0.ok = 0 or ispresent(searches.0.not_in_index)',
        ],
        sort: '@timestamp desc',
        limit: 100,
      }),
    });

    // ---------------------------------------------------------------- network
    // Public subnets only: the task gets a public IP to reach AWS APIs, so no NAT gateway to pay for.
    const vpc = new ec2.Vpc(this, 'Vpc', {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [{ name: 'public', subnetType: ec2.SubnetType.PUBLIC, cidrMask: 24 }],
    });

    // ---------------------------------------------------------------- API on Fargate
    const cluster = new ecs.Cluster(this, 'Cluster', { vpc });

    const taskDefinition = new ecs.FargateTaskDefinition(this, 'ApiTask', {
      cpu: 512,
      memoryLimitMiB: 1024,
      runtimePlatform: {
        cpuArchitecture: ecs.CpuArchitecture.X86_64,
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
      },
    });
    const taskRole = taskDefinition.taskRole;

    // Bedrock: Converse (route, extract) and InvokeModel (Titan embeddings).
    // Cross-region inference profiles (us.anthropic.*) route to several regions,
    // so the foundation-model ARNs use a region wildcard.
    taskRole.addToPrincipalPolicy(
      new iam.PolicyStatement({
        sid: 'BedrockInvoke',
        actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
        resources: [
          'arn:aws:bedrock:*::foundation-model/anthropic.*',
          'arn:aws:bedrock:*::foundation-model/amazon.titan-embed-*',
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
        ],
      }),
    );
    // The domain policy trusts the account; the role still needs its own es:ESHttp* grant.
    // Write access lets the task build the indexes once at startup (INDEX_ON_START).
    this.domain.grantReadWrite(taskRole);
    this.stateTable.grantReadWriteData(taskRole);

    const image =
      props.apiImage ??
      ecs.ContainerImage.fromAsset(REPO_ROOT, {
        file: 'backend/Dockerfile',
        platform: ecrAssets.Platform.LINUX_AMD64,
      });

    const environment: Record<string, string> = {
      AWS_REGION: this.region,
      STATE_TABLE: this.stateTable.tableName,
      OPENSEARCH_URL: `https://${this.domain.domainEndpoint}`,
      BEDROCK_ENABLED: ctx('bedrock') ?? '1',
      INDEX_ON_START: '1',
      TURN_LOG: '1',
    };
    const fastModel = ctx('fastModelId');
    const strongModel = ctx('strongModelId');
    if (fastModel) environment.FAST_MODEL_ID = fastModel;
    if (strongModel) environment.STRONG_MODEL_ID = strongModel;

    taskDefinition.addContainer('api', {
      image,
      environment,
      portMappings: [{ containerPort: 8000 }],
      logging: ecs.LogDrivers.awsLogs({ logGroup, streamPrefix: 'api' }),
    });

    const service = new ecs.FargateService(this, 'ApiService', {
      cluster,
      taskDefinition,
      desiredCount: 1,
      assignPublicIp: true,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      minHealthyPercent: 100,
      maxHealthyPercent: 200,
      circuitBreaker: { rollback: true },
      healthCheckGracePeriod: cdk.Duration.seconds(60),
    });

    // ---------------------------------------------------------------- load balancer
    // Only CloudFront knows the header value (the stack's GUID), so the ALB answers
    // 403 to anyone who finds its DNS name and skips CloudFront.
    const originSecret = cdk.Fn.select(2, cdk.Fn.split('/', this.stackId));
    const alb = new elbv2.ApplicationLoadBalancer(this, 'Alb', { vpc, internetFacing: true });
    const listener = alb.addListener('Http', {
      port: 80,
      open: true,
      defaultAction: elbv2.ListenerAction.fixedResponse(403, { contentType: 'text/plain', messageBody: 'Forbidden' }),
    });
    listener.addTargets('Api', {
      priority: 1,
      conditions: [elbv2.ListenerCondition.httpHeader(ORIGIN_HEADER, [originSecret])],
      port: 8000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [service],
      deregistrationDelay: cdk.Duration.seconds(10),
      healthCheck: { path: '/api/health', healthyHttpCodes: '200', interval: cdk.Duration.seconds(15) },
    });

    // ---------------------------------------------------------------- frontend: S3 + CloudFront
    const webBucket = new s3.Bucket(this, 'WebBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const distribution = new cloudfront.Distribution(this, 'Site', {
      comment: 'GreatSchools guided search demo',
      defaultRootObject: 'index.html',
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(webBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      additionalBehaviors: {
        '/api/*': {
          origin: new origins.HttpOrigin(alb.loadBalancerDnsName, {
            protocolPolicy: cloudfront.OriginProtocolPolicy.HTTP_ONLY,
            customHeaders: { [ORIGIN_HEADER]: originSecret },
            readTimeout: cdk.Duration.seconds(60),
          }),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        },
      },
    });

    new s3deploy.BucketDeployment(this, 'WebDeploy', {
      sources: [props.webSource ?? frontendBuild()],
      destinationBucket: webBucket,
      distribution,
      distributionPaths: ['/*'],
      memoryLimit: 512,
    });

    new cdk.CfnOutput(this, 'SiteUrl', { value: `https://${distribution.distributionDomainName}` });
    new cdk.CfnOutput(this, 'ApiLogGroup', { value: logGroup.logGroupName });
    new cdk.CfnOutput(this, 'ClusterName', { value: cluster.clusterName });
    new cdk.CfnOutput(this, 'ServiceName', { value: service.serviceName });
  }
}

/**
 * Build `frontend/` with the local npm during synth (falls back to a Node
 * container if that fails). Hashing the source lets CDK skip the build when the
 * frontend has not changed.
 */
function frontendBuild(): s3deploy.ISource {
  return s3deploy.Source.asset(FRONTEND_DIR, {
    exclude: ['node_modules', 'dist', '.env'],
    assetHashType: cdk.AssetHashType.SOURCE,
    bundling: {
      image: cdk.DockerImage.fromRegistry('public.ecr.aws/docker/library/node:22'),
      command: [
        'bash',
        '-c',
        'cp -r /asset-input /tmp/web && cd /tmp/web && npm ci && npm run build && cp -r dist/. /asset-output/',
      ],
      local: {
        tryBundle(outputDir: string): boolean {
          try {
            execSync('npm ci && npm run build', { cwd: FRONTEND_DIR, stdio: ['ignore', process.stderr, process.stderr] });
            execSync(`cp -r dist/. "${outputDir}/"`, { cwd: FRONTEND_DIR, stdio: ['ignore', process.stderr, process.stderr] });
            return true;
          } catch (err) {
            process.stderr.write(`Local frontend build failed, trying Docker: ${err}\n`);
            return false;
          }
        },
      },
    },
  });
}
