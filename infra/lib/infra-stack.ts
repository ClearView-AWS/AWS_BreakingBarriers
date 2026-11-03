import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as opensearch from 'aws-cdk-lib/aws-opensearchservice';

export class InfraStack extends cdk.Stack {
  public readonly domain: opensearch.Domain;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

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

    new cdk.CfnOutput(this, 'DomainEndpoint', { value: this.domain.domainEndpoint });
    new cdk.CfnOutput(this, 'DomainName', { value: this.domain.domainName });
  }
}
