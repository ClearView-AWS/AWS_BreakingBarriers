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

Bedrock is on by default; `BEDROCK=0` deploys the rules engine only. If `GsOpenSearchStack` exists, the script passes its endpoint to the app; `OPENSEARCH_ENDPOINT=none` keeps local search.

With Bedrock on, `GsAppStack` also creates the Bedrock Guardrail for community posts and passes `BEDROCK_GUARDRAIL_ID` / `BEDROCK_GUARDRAIL_VERSION` to the task.

## OpenSearch later

```bash
cd infra && npx cdk deploy GsOpenSearchStack
# then reindex:
OPENSEARCH_URL=https://<DomainEndpoint> ../.venv/bin/python ../data/index/indexer.py
# then redeploy the app (it reads the endpoint from the stack):
SKIP_OPENSEARCH=1 ./scripts/deploy-demo.sh
```

The API still works with the local hybrid engine if OpenSearch is missing.

## Auto-deploy from `main`

`.github/workflows/deploy-demo.yml` runs `./scripts/deploy-demo.sh` on every push to `main` (and on manual **Run workflow**).

The workflow signs in with GitHub OIDC, so no AWS keys are stored and nothing expires. Repo variable `AWS_DEPLOY_ROLE_ARN` names the IAM role `GsGitHubDeploy`, which trusts only pushes to this repo's `main`. The role and the `token.actions.githubusercontent.com` OIDC provider were created by hand in the sandbox account, not by CDK.

| Setting | Required | Notes |
|---|---|---|
| `vars.AWS_DEPLOY_ROLE_ARN` | yes | `arn:aws:iam::<account>:role/GsGitHubDeploy` |
| `secrets.OPENSEARCH_ENDPOINT` | no | Hostname only. Without it the script reads `GsOpenSearchStack`. |

Default flags in CI: `BEDROCK=1`, `SKIP_OPENSEARCH=1` (does not recreate the OpenSearch domain).

## Teardown (stop the bill)

```bash
cd infra
npx cdk destroy GsAppStack GsOpenSearchStack --force
aws iam detach-role-policy --role-name GsGitHubDeploy --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
aws iam delete-role --role-name GsGitHubDeploy
```
