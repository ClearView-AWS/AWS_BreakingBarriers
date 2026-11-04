#!/usr/bin/env bash
# Deploy the parent-facing CloudFront + Fargate demo.
# Usage:
#   ./scripts/deploy-demo.sh
#   BEDROCK=1 ./scripts/deploy-demo.sh
#   TRANSLATE=0 ./scripts/deploy-demo.sh      # turn off Amazon Translate (on by default)
#   SKIP_OPENSEARCH=1 ./scripts/deploy-demo.sh   # URL first; OpenSearch later

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Checking AWS credentials"
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  cat <<'EOF'
No AWS credentials found.

Log into the hackathon sandbox first, then re-run this script:

  aws configure   # or: aws sso login --profile <hackathon>
  export AWS_REGION=us-east-1
  export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
  export CDK_DEFAULT_REGION=us-east-1

EOF
  exit 1
fi

export AWS_REGION="${AWS_REGION:-us-east-1}"
export CDK_DEFAULT_REGION="${CDK_DEFAULT_REGION:-$AWS_REGION}"
export CDK_DEFAULT_ACCOUNT="${CDK_DEFAULT_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text)}"

echo "Account=$CDK_DEFAULT_ACCOUNT Region=$CDK_DEFAULT_REGION"

echo "==> Building frontend"
cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  npm ci
fi
npm run build

cd "$ROOT/infra"
if [[ ! -d node_modules ]]; then
  npm ci
fi

npx cdk bootstrap "aws://${CDK_DEFAULT_ACCOUNT}/${CDK_DEFAULT_REGION}"

CONTEXT=()
if [[ "${SKIP_OPENSEARCH:-}" == "1" ]]; then
  CONTEXT+=(-c enableOpenSearch=false)
fi
if [[ "${BEDROCK:-}" == "1" ]]; then
  CONTEXT+=(-c bedrockEnabled=true)
fi
if [[ "${TRANSLATE:-}" == "0" ]]; then
  CONTEXT+=(-c translateEnabled=false)
fi
if [[ -n "${OPENSEARCH_ENDPOINT:-}" ]]; then
  CONTEXT+=(-c "openSearchEndpoint=${OPENSEARCH_ENDPOINT}")
fi

echo "==> Deploying GsAppStack (CloudFront + Fargate)"
npx cdk deploy GsAppStack "${CONTEXT[@]}" --require-approval never

if [[ "${SKIP_OPENSEARCH:-}" != "1" ]]; then
  echo "==> Deploying GsOpenSearchStack (can take 15–25 minutes)"
  npx cdk deploy GsOpenSearchStack "${CONTEXT[@]}" --require-approval never || true
fi

echo
echo "Done. Open the CloudFrontURL output above in a browser."
echo "That URL replaces yesterday's IP address."
