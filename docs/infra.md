# AWS Infrastructure: GreatSchools Guided Search

*Living docs · Nov 4, 2026 · Region: `us-east-1` · Matches shipped CDK in `infra/`*

What runs in AWS today, how a parent's request moves through it, and how to deploy or tear it down. For product intent and milestones see [plan.md](plan.md) (aspirational). For judge-facing narrative see [how-it-works.md](how-it-works.md). For ops commands see [`infra/README.md`](../infra/README.md).

> **What ships:** four CDK stacks, one DynamoDB `RuntimeState` table (`pk`/`sk` + `data_json`), CloudFront → S3 + ALB → Fargate, Bedrock (+ Guardrails) and Translate behind flags, OpenSearch optional, voice (Connect/Lex/Lambda) optional, maps via **Leaflet + OpenStreetMap** (not Amazon Location). SES is an optional app flag, not created by CDK.

## Contents

- [Overview](#overview)
- [CDK stacks](#cdk-stacks)
- [Request path](#request-path)
- [Services (as shipped)](#services-as-shipped)
- [Configuration](#configuration)
- [Deploy and teardown](#deploy-and-teardown)
- [Not implemented](#not-implemented)

---

## Overview

```text
Parent's browser
      │  HTTPS
      ▼
  CloudFront ─── /*     ──►  S3: React build (private, OAC)
      │
      └──── /api/* ──► ALB ──► ECS Fargate: FastAPI (image built by CDK)
                                     │
      ┌──────────────┬───────────────┼───────────────┬────────────────┐
      ▼              ▼               ▼               ▼                ▼
   Bedrock       OpenSearch      DynamoDB        Translate      (optional)
  Claude +        hybrid         RuntimeState    + Comprehend    SES when
  Titan +         keyword +      one pk/sk       language        SES_ENABLED=1
  Guardrails      vector         table           detect
                                     │
                              Leaflet map tiles ← OpenStreetMap (browser)
```

Optional phone loop (not on the default demo deploy):

```text
API starts Connect outbound call
  → Connect contact flow (Polly disclosure / consent)
  → Lex V2 speech turns
  → Lambda (backend/voice/lex_turn.py) asks Bedrock, writes transcript to DynamoDB
API reads transcript, verifies answers, updates cards
```

Everything is in one account and region (`us-east-1`). Stack names are the resource prefixes (`GsAppStack`, `GsOpenSearchStack`, …).

---

## CDK stacks

Defined in `infra/bin/infra.ts`:

| Stack | What it creates | Default demo deploy? |
|---|---|---|
| **GsAppStack** | VPC (public subnets, no NAT), ECS Fargate + ALB, S3 + CloudFront, one DynamoDB `RuntimeState` table, Bedrock Guardrail when Bedrock is on, task IAM | Yes (`./scripts/deploy-demo.sh`) |
| **GsOpenSearchStack** | Single-node OpenSearch domain | Optional — CI uses `SKIP_OPENSEARCH=1` so it does not recreate the domain every push |
| **GsGatewayStack** | AgentCore Gateway + school-tools Lambda (MCP) | No — `DEPLOY_GATEWAY=1` |
| **GsVoiceStack** | Voice Lambda, Lex V2 bot, Connect contact flow (imports Connect instance by id) | No — `DEPLOY_VOICE=1` + `VOICE_INSTANCE_ID` |

`main` auto-deploys through `.github/workflows/deploy-demo.yml` (GitHub OIDC → IAM role `GsGitHubDeploy`). Live parent URL: https://dvpvz48phigre.cloudfront.net

---

## Request path

| Step | What runs | AWS / local |
|---|---|---|
| Load / save session | `backend/store.py` | DynamoDB `RuntimeState` when `GS_DYNAMODB_TABLE` is set; else `data/runtime/state.json` |
| Route / extract / explain | Bedrock Converse (Haiku / Sonnet) when `BEDROCK_ENABLED=1` | Falls back to rules engine |
| Need embeddings | Titan Text Embeddings V2 when Bedrock is on | Hash embedder otherwise |
| Language | Translate + Comprehend when `TRANSLATE_ENABLED=1` | Message used as written on failure |
| Search | Hybrid keyword + vector; hard filters only on city, grade, type | OpenSearch when `OPENSEARCH_URL` is set; else in-memory corpus |
| Community post check | Local PII rules + Bedrock `ApplyGuardrail` when guardrail IDs are set | Either layer can block |
| Map | Leaflet in the browser | OSM tiles (`tile.openstreetmap.org`); school lat/lon from data — no Amazon Location |
| Ask the school (email) | Inbox always records; SES send only if `SES_ENABLED=1` | Sandbox: verified addresses only |
| Ask the school (phone) | Connect outbound when voice env vars are set | Otherwise SES / staff answer paths |

Median turn time under 6 s is a product target; rules-only eval median is ~0.02 s.

---

## Services (as shipped)

### Amazon Bedrock

| Use | Model / API | Flag |
|---|---|---|
| Route, extract, phone turns | Claude Haiku via Converse | `BEDROCK_ENABLED=1` |
| Stronger drafting | Claude Sonnet via Converse / stream | same |
| Embeddings | Titan Text Embeddings V2 (256-d) | same |
| Community PII | Guardrail created by `GsAppStack` when Bedrock is on | `BEDROCK_GUARDRAIL_ID` / `VERSION` |

Model IDs live in `backend/config/models.yaml`.

### Amazon OpenSearch Service (`GsOpenSearchStack`)

- Optional. Domain is billed while idle; skip recreate in CI with `SKIP_OPENSEARCH=1`.
- Indexes: `schools`, `programs` (indexer at `data/index/indexer.py`).
- Search builds hybrid DSL (`backend/search/query.py`) and calls OpenSearch when `OPENSEARCH_URL` is set (`backend/search/opensearch_client.py`).

### Amazon DynamoDB (`GsAppStack` → `RuntimeState`)

**One table**, on-demand:

| Key | Shape |
|---|---|
| Partition key | `pk` (string) |
| Sort key | `sk` (string) |
| Payload | `data_json` (JSON string — keeps floats/bools AttributeValues reject) |

Typical keys (see `backend/store.py` and voice Lambda):

| `pk` | `sk` | Holds |
|---|---|---|
| `SESSIONS` | session id | Parent session blob |
| `META` | `INBOX` / `OVERLAYS` / `CALLS` / `DO_NOT_CALL` | Shared lists/maps |
| `CALLS` | call id | Voice transcripts (written by Lex turn Lambda) |

There is **no** six-table design in the live stack.

### Amazon S3 + CloudFront + Fargate

| Piece | Role |
|---|---|
| S3 web bucket | React `frontend/dist`, private, CloudFront OAC |
| CloudFront | HTTPS; `/*` → S3; `/api/*` → ALB (caching off); forwards `CloudFront-Viewer-Address` for rate limits |
| ECR asset + ECS Fargate | One task, 0.5 vCPU / 1 GB, public subnet + public IP (no NAT); `GS_STAFF_KEY` from Secrets Manager |
| ALB | HTTP listener open only to the CloudFront origin-facing prefix list (not `0.0.0.0/0`) |

### Amazon Translate (+ Comprehend)

On unless `translateEnabled=false` / `TRANSLATE_ENABLED=0`. Detects parent language and translates for the pipeline; UI can follow the parent language.

### Amazon SES (optional — not CDK)

- **Not** provisioned by the stacks. App code in `backend/gaps/ses_mailer.py`.
- Sends only when `SES_ENABLED=1` with `SES_SOURCE` and `SES_VERIFIED_TO`.
- Sandbox delivers only to verified addresses. Digests / inbox emails are a fallback when a call is not placed (see `backend/config/calls.yaml` limits).

### Maps: Leaflet + OpenStreetMap

- Frontend: `leaflet` (`frontend/src/Views.tsx`).
- Tiles: `https://tile.openstreetmap.org/{z}/{x}/{y}.png`.
- **Amazon Location Service and MapLibre are not used.**

### Voice: Connect + Lex + Polly + Lambda (`GsVoiceStack`)

- Imports an existing Connect instance (`voiceInstanceId` / `VOICE_INSTANCE_ID`).
- Needs the app's RuntimeState table name (`voiceStateTable` / `GS_DYNAMODB_TABLE`).
- API enables dialing only when `VOICE_INSTANCE_ID`, `VOICE_FLOW_ID`, `VOICE_SOURCE`, and `VOICE_VERIFIED_TO` are all set.
- Call guardrails (daily cap, business hours, do-not-call) live in `backend/config/calls.yaml`.

### AgentCore Gateway (`GsGatewayStack`)

Optional MCP school tools (`find_schools`, `get_school_facts`, `estimate_school_cost`, `define_term`). Not part of the default parent demo path.

---

## Configuration

Fargate task env (set by `GsAppStack` / deploy script) includes:

```bash
AWS_REGION=us-east-1
GS_DYNAMODB_TABLE=<RuntimeState table name>
GS_STAFF_KEY=<from Secrets Manager>   # required for staff writes and AI dials
BEDROCK_ENABLED=1          # or 0 for rules only
TRANSLATE_ENABLED=1
OPENSEARCH_URL=https://…   # omitted → local hybrid search
BEDROCK_GUARDRAIL_ID=…     # when Bedrock on
BEDROCK_GUARDRAIL_VERSION=…
# Voice (optional, from deploy shell — never commit VOICE_VERIFIED_TO)
VOICE_ENABLED=1
VOICE_INSTANCE_ID=…
VOICE_FLOW_ID=…
VOICE_SOURCE=…
VOICE_VERIFIED_TO=…
# SES (optional — not set by CDK today)
SES_ENABLED=1
SES_SOURCE=…
SES_VERIFIED_TO=…
```

Locally the same flags apply; without DynamoDB, state is `data/runtime/state.json` (`GS_STATE_PATH` overrides).

---

## Deploy and teardown

```bash
# Fast path: CloudFront URL without recreating OpenSearch
SKIP_OPENSEARCH=1 ./scripts/deploy-demo.sh

# OpenSearch domain (billed while idle)
cd infra && npx cdk deploy GsOpenSearchStack

# Optional stacks
npx cdk deploy GsGatewayStack -c enableOpenSearch=false
npx cdk deploy GsVoiceStack \
  -c voiceInstanceId=$VOICE_INSTANCE_ID \
  -c voiceStateTable=<RuntimeState table name>
```

**Teardown** (stop the largest idle bill first — OpenSearch):

```bash
cd infra
npx cdk destroy GsAppStack GsOpenSearchStack GsGatewayStack GsVoiceStack --force
```

Also remove the hand-created `GsGitHubDeploy` role if the sandbox is done (see `infra/README.md`).

| Billed while idle | Billed per use |
|---|---|
| OpenSearch domain · ALB · Fargate task | Bedrock · Guardrails · DynamoDB on-demand · S3 · CloudFront · Translate · Connect/Lex/Polly/Lambda when voice is used · SES when enabled |

Deliberately avoided: NAT gateways, multi-AZ OpenSearch, provisioned DynamoDB, Amazon Location.

---

## API hardening (terminal / curl)

The parent demo URL is public, but a stranger with curl cannot dial the demo phone, answer as school staff, or inject free text into school emails:

- **Staff code** (`GS_STAFF_KEY` from Secrets Manager): required only to *answer as the school* (inbox/school answers, do-not-call, digests, posting as school staff). **Have AI call** stays open in the browser — no unlock.
- **Catalog-only needs**: `/api/calls` and community drafts reject unknown need ids, so request text never becomes the phone prompt.
- **Rate limits + body size** (`backend/security.py`): per-IP and global caps on AI, call, and write routes; 64 KB body cap — this is what stops a terminal script from spam-dialing.
- **ALB**: security group allows only CloudFront origin-facing IPs, so the LoadBalancerDNS is not a public API.

## Not implemented

Do **not** treat these as current architecture (they appear in older drafts of this file and in [plan.md](plan.md)):

- Amazon Location Service map tiles or geocoding
- MapLibre GL JS
- Six separate DynamoDB tables (`sessions`, `saved`, `feedback`, `posts`, `votes`, `questions`)
- SES as an always-on CDK resource
- `VITE_LOCATION_API_KEY` / browser Location API keys

For historical morning-of-Nov-4 notes see [HANDOFF.md](HANDOFF.md). For live URL and post-grade10 status see [HANDOFF-CURRENT.md](HANDOFF-CURRENT.md).
