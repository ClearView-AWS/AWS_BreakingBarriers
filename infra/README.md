# infra

One CDK stack, `InfraStack`: the shared OpenSearch domain, the DynamoDB state table, the Fargate API behind an ALB, and the frontend in S3 behind CloudFront. See the [root README](../README.md#deploy-to-aws) for what each piece does.

```bash
npm install
npx cdk bootstrap
npx cdk deploy
```

Needs Docker running (CDK builds `backend/Dockerfile`) and AWS credentials for the target account. Options: `-c fastModelId=<id>`, `-c strongModelId=<id>`, `-c bedrock=0`, `-c hosting=false`.

* `bash scripts/check-sandbox.sh`: read-only check of which services and models the account allows
* `npx jest`: template tests
* `npx cdk diff`: compare with what is deployed
* `npx cdk destroy`: delete everything
