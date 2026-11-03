#!/usr/bin/env bash
# Create the Bedrock Guardrail that checks every community post for personal info.
#
# Before running: log in to the sandbox (Workshop Studio "Get AWS CLI credentials",
# paste the export lines) and set:  export AWS_DEFAULT_REGION=us-east-1
#
# Run from the repo root:  bash scripts/create_guardrail.sh
# It prints two export lines. Paste them into the terminal that runs the API.
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
NAME="gs-community-pii"

existing=$(aws bedrock list-guardrails --region "$REGION" \
  --query "guardrails[?name=='$NAME'].id | [0]" --output text 2>/dev/null || true)

if [[ -n "$existing" && "$existing" != "None" ]]; then
  id="$existing"
  echo "Guardrail $NAME already exists: $id"
else
  id=$(aws bedrock create-guardrail --region "$REGION" \
    --name "$NAME" \
    --description "Blocks names, emails, phone numbers and addresses in parent community posts" \
    --blocked-input-messaging "This post includes personal information. Please rephrase without it." \
    --blocked-outputs-messaging "This post includes personal information. Please rephrase without it." \
    --sensitive-information-policy-config '{
      "piiEntitiesConfig": [
        {"type": "NAME", "action": "BLOCK"},
        {"type": "EMAIL", "action": "BLOCK"},
        {"type": "PHONE", "action": "BLOCK"},
        {"type": "ADDRESS", "action": "BLOCK"}
      ]
    }' \
    --query guardrailId --output text)
  echo "Created guardrail: $id"
fi

version=$(aws bedrock create-guardrail-version --region "$REGION" \
  --guardrail-identifier "$id" --query version --output text)

echo
echo "Paste these into the terminal that runs the API:"
echo "  export BEDROCK_ENABLED=1"
echo "  export BEDROCK_GUARDRAIL_ID=$id"
echo "  export BEDROCK_GUARDRAIL_VERSION=$version"
