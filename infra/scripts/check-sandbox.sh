#!/usr/bin/env bash
# Read-only check of what this AWS sandbox allows, before building on it.
# Run with the credentials you will deploy with:
#   bash infra/scripts/check-sandbox.sh            # us-east-1
#   AWS_REGION=us-west-2 bash infra/scripts/check-sandbox.sh
# Nothing is created, changed or sent.
set -u
REGION="${AWS_REGION:-us-east-1}"
export AWS_REGION="$REGION" AWS_PAGER=""

ok()   { printf '  \033[32mOK\033[0m    %s\n' "$*"; }
warn() { printf '  \033[33mCHECK\033[0m %s\n' "$*"; }
fail() { printf '  \033[31mNO\033[0m    %s\n' "$*"; }
try()  { "$@" >/dev/null 2>&1; }

echo "Account and region"
if ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null); then
  ok "account $ID, region $REGION"
else
  fail "no AWS credentials. Configure a profile or SSO first."
  exit 1
fi

echo "Core (Track 4, tasks 1-7)"
try aws opensearch list-domain-names && ok "OpenSearch" || fail "OpenSearch: list-domain-names denied"
aws opensearch list-domain-names --query 'DomainNames[].DomainName' --output text 2>/dev/null | tr '\t' '\n' | sed '/^$/d; s/^/          domain: /'
try aws dynamodb list-tables && ok "DynamoDB" || fail "DynamoDB denied"
try aws ecs list-clusters && ok "ECS (Fargate)" || fail "ECS denied"
try aws elbv2 describe-load-balancers --page-size 1 && ok "Elastic Load Balancing" || fail "ELB denied"
try aws cloudfront list-distributions --max-items 1 && ok "CloudFront" || fail "CloudFront denied"
try aws logs describe-log-groups --limit 1 && ok "CloudWatch Logs" || fail "CloudWatch Logs denied"
try aws cloudformation describe-stacks --stack-name CDKToolkit && ok "CDK bootstrapped" || warn "CDK not bootstrapped in $REGION yet: run npx cdk bootstrap"

echo "Bedrock models (task 2)"
if PROFILES=$(aws bedrock list-inference-profiles \
    --query 'inferenceProfileSummaries[?contains(inferenceProfileId, `anthropic`)].inferenceProfileId' \
    --output text 2>/dev/null); then
  if [ -n "$PROFILES" ]; then
    ok "Claude inference profiles:"
    echo "$PROFILES" | tr '\t' '\n' | sed 's/^/          /'
  else
    warn "no Claude inference profiles listed"
  fi
else
  fail "bedrock:ListInferenceProfiles denied"
fi
aws bedrock list-foundation-models --by-provider amazon \
    --query 'modelSummaries[?contains(modelId, `titan-embed-text-v2`)].modelId' --output text 2>/dev/null | grep -q titan \
  && ok "Titan Text Embeddings V2" || warn "Titan Text Embeddings V2 not listed"
echo "  Pick a Haiku profile id above and deploy with: npx cdk deploy -c fastModelId=<id>"

echo "Stretch (task 8: only if community + ask-the-school are built)"
if PROD=$(aws sesv2 get-account --query 'ProductionAccessEnabled' --output text 2>/dev/null); then
  if [ "$PROD" = "False" ]; then ok "SES, sandbox mode (sends only to verified addresses)"; else ok "SES, production access"; fi
  aws sesv2 list-email-identities \
      --query 'EmailIdentities[?VerificationStatus==`SUCCESS`].IdentityName' --output text 2>/dev/null \
    | tr '\t' '\n' | sed '/^$/d; s/^/          verified: /'
else
  fail "SES denied"
fi
try aws bedrock list-guardrails && ok "Bedrock Guardrails" || fail "Bedrock Guardrails denied"
try aws location list-keys --max-results 1 && ok "Amazon Location (API keys)" || fail "Amazon Location denied"
