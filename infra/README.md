# GreatSchools Guided Search — AWS infra

Two stacks:

| Stack | What | When |
|---|---|---|
| **GsAppStack** | CloudFront + S3 frontend, ALB + Fargate FastAPI | Deploy first → demo URL today |
| **GsOpenSearchStack** | OpenSearch domain | Parallel / after; billed while idle |

## Prerequisites

- Docker running (CDK builds the API image and the frontend)
- AWS credentials for the hackathon sandbox (`us-east-1`)
- Node 20+

```bash
aws sts get-caller-identity
export AWS_REGION=us-east-1
export CDK_DEFAULT_REGION=us-east-1
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
```

## Fast path (URL today)

```bash
# From repo root — skips OpenSearch so CloudFront comes up sooner
SKIP_OPENSEARCH=1 ./scripts/deploy-demo.sh
```

Outputs include `CloudFrontURL` — that is the parent-facing link (no IP).
Current demo: https://dvpvz48phigre.cloudfront.net

Turn Bedrock on after model access is approved:

```bash
BEDROCK=1 SKIP_OPENSEARCH=1 ./scripts/deploy-demo.sh
```

## OpenSearch later

```bash
cd infra && npx cdk deploy GsOpenSearchStack
# then reindex:
OPENSEARCH_URL=https://<DomainEndpoint> ../.venv/bin/python ../data/index/indexer.py
# then redeploy app with the endpoint:
OPENSEARCH_ENDPOINT=<DomainEndpoint> ./scripts/deploy-demo.sh
```

The API still works with the local hybrid engine if OpenSearch is missing.

## Auto-deploy from `main`

`.github/workflows/deploy-demo.yml` runs `./scripts/deploy-demo.sh` on every push to `main` (and on manual **Run workflow**).

Repo secrets (Workshop Studio keys expire — refresh after `aws login`):

| Secret | Required | Notes |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | yes | From the sandbox session |
| `AWS_SECRET_ACCESS_KEY` | yes | |
| `AWS_SESSION_TOKEN` | yes if temporary | Workshop Studio needs this |
| `OPENSEARCH_ENDPOINT` | no | Hostname only; wires the existing domain into the app |

Default flags in CI: `BEDROCK=1`, `SKIP_OPENSEARCH=1` (does not recreate the OpenSearch domain).

## Teardown (stop the bill)

```bash
cd infra
npx cdk destroy GsAppStack GsOpenSearchStack --force
```
