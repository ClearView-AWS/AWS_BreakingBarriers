# AWS Infrastructure: GreatSchools Guided Agent

*Draft · Nov 3, 2026 · Region: us-east-1 · Account: hackathon sandbox · Companion to [plan.md](plan.md)*

What runs in AWS, how a parent's message moves through it, and how to set it up and tear it down. [plan.md](plan.md) decides what we build; this document decides where it runs.

> **Managed services only, nothing to patch.**
> Bedrock, OpenSearch, DynamoDB, S3 and SES are shared by the whole team from day 0. The backend runs on our laptops while we build and moves to one Fargate task for the demo.

## Contents

- [Overview](#overview)
- [Two Phases](#two-phases)
- [How a Turn Uses AWS](#how-a-turn-uses-aws)
- [Indexing Path](#indexing-path)
- [Services](#services)
- [IAM](#iam)
- [Configuration](#configuration)
- [Day 0 Setup](#day-0-setup)
- [Cost and Teardown](#cost-and-teardown)
- [Alternatives We Passed On](#alternatives-we-passed-on)
- [Handoff to GreatSchools](#handoff-to-greatschools)
- [Open Questions](#open-questions)

---

## Overview

```text
Parent's browser
      │  HTTPS
      ▼
  CloudFront ─── /*  ──────►  S3: frontend bucket (React build, private, OAC)
      │
      └──── /api/* ──► ALB ──► ECS Fargate: FastAPI agent (image in ECR)
                                     │
      ┌──────────────┬───────────────┼───────────────┬──────────────────┐
      ▼              ▼               ▼               ▼                  ▼
   Bedrock       OpenSearch       DynamoDB          SES            S3: data bucket
 Haiku: route,   schools and      sessions,       "Ask the         sample and
  extract        programs         saved lists,    school" email    synthetic data,
 Sonnet: explain indexes          feedback,       (sandbox mode)   mock school
 Embeddings:     (keyword +       school                           websites
  Titan/Cohere    vector)         questions
```

Everything lives in one account and one region (us-east-1, matching GreatSchools production). Every resource is named with the prefix `gs-guided-` and tagged `Project=greatschools-guided-search`, so we can find it, see what it costs and delete it.

---

## Two Phases

| | Build (D0–M4) | Demo |
|---|---|---|
| Frontend | Vite dev server on each laptop, proxying `/api` to `localhost:8000` | Static build in S3, served by CloudFront |
| Backend | `uvicorn backend.app:app` on each laptop | One ECS Fargate task behind an ALB |
| AWS credentials | Each teammate's own sandbox profile | Fargate task role |
| Bedrock, OpenSearch, DynamoDB, S3, SES | Shared, created on day 0 | Same resources, unchanged |

The frontend calls `/api/...` in both phases. Locally Vite proxies it; in the demo CloudFront routes it. No CORS setup, and no code changes between phases.

If time runs out before the Fargate step, we demo from a laptop. Everything the parent sees still comes from the same AWS services.

---

## How a Turn Uses AWS

The steps from [plan.md › How a Turn Works](plan.md#how-a-turn-works), mapped onto services.

| # | Step | AWS call | Notes |
|---|---|---|---|
| 0 | Load session | DynamoDB `GetItem` on `sessions` | Criteria and answers so far |
| 1 | Route | Bedrock Converse (Haiku) | Tool use returns a typed route |
| 2 | Extract | Bedrock Converse (Haiku) | Tool use returns criteria JSON |
| 3 | Map | Bedrock embeddings | Need phrases are embedded once at startup and held in memory; only the parent's phrases are embedded per turn |
| 4 | Search | Bedrock embeddings, then OpenSearch hybrid query | One query embedding, one `_search` with the hybrid search pipeline |
| 5 | Evidence | DynamoDB `Query` on `school_questions`; S3 `GetObject` for mock websites (gap resolver only) | School-reported answers override "unknown" |
| 6 | Score | None | In-process |
| 7 | Clarify | OpenSearch, one search per reading, run in parallel | Only when a criterion is ambiguous |
| 8 | Explain | Bedrock ConverseStream (Sonnet) | Streamed to the browser; the citation validator runs on the finished text |
| 9 | Render | None | Browser |
| 10 | Save session | DynamoDB `PutItem` on `sessions` | |

Side actions on any turn: saves and thumbs up / down write to DynamoDB; "Ask the school" writes to `school_questions` and sends one SES email.

To meet the plan's median turn time of under 6 seconds, the critical path is two Haiku calls, one embedding, one or a few OpenSearch queries and one streamed Sonnet call. Steps 1 and 2 can be merged into a single Haiku call if timing is tight.

---

## Indexing Path

Run from a laptop, not in the request path.

```text
data/synthetic/generator  ──►  data/sample + data/synthetic (local files)
                                     │
                                     ├──►  S3 data bucket: raw/        (copy of record)
                                     │
                                     ▼
                              data/index/indexer
                                     │  builds search_text per document
                                     │  Bedrock embeddings, in batches
                                     ▼
                              OpenSearch: schools_vN, programs_vN
                                     │  swap aliases when complete
                                     ▼
                              aliases: schools, programs

data/synthetic/sites  ──►  S3 data bucket: school-sites/{school_id}.html
```

The indexer writes to a new versioned index and moves the `schools` and `programs` aliases only after it finishes. A teammate can reindex without breaking everyone else's searches, and a bad run can be rolled back by moving the alias back.

---

## Services

### Amazon Bedrock

| Use | Model | API |
|---|---|---|
| Route, extract | Claude Haiku (small, fast) | Converse with tool use |
| Explain, compare, word questions | Claude Sonnet (stronger) | ConverseStream |
| Need mapping, vector search | Titan Text Embeddings V2 or Cohere Embed Multilingual (chosen with the eval set) | InvokeModel |
| Grounding check (M5 stretch) | Bedrock Guardrails, contextual grounding | ApplyGuardrail |

- Request model access on day 0. Model availability in the sandbox is an open question in the plan.
- Model IDs live in `backend/config/models.yaml`, never in code. Newer Claude models on Bedrock are usually called through an inference profile ID (`us.anthropic.…`) rather than the base model ID; use whichever ID the console shows for on-demand use.
- Changing the embedding model changes the vector dimension and means a full reindex. Choose it before M1.

### Amazon OpenSearch Service

| Setting | Value | Why |
|---|---|---|
| Engine | OpenSearch 2.10 or later (latest offered) | Hybrid query and the normalization search pipeline need 2.10+ |
| Nodes | 1 data node, no dedicated master, no zone awareness | Smallest setup that works |
| Instance | Smallest type that supports the k-NN plugin | Check the console's instance list on day 0 |
| Storage | EBS gp3, 10 GB | The data is well under 1 GB |
| Network | Public endpoint | The backend runs on laptops during the build; a VPC-only domain can't be reached from them |
| Access | Domain access policy allowing the sandbox account's IAM principals; every request SigV4-signed (`opensearch-py` with `AWSV4SignerAuth`) | No passwords to share |
| Encryption | At rest and node-to-node on, HTTPS required | Defaults; costs nothing extra |

Indexes (`schools`, `programs` aliases) keep GreatSchools' original document fields and add:

- `search_text` (text): name, ESP text, profile values, recent review snippets
- `search_vector` (knn_vector): embedding of `search_text`; dimension matches the embedding model

One search pipeline, `gs-guided-hybrid`, with a normalization processor (min-max normalization, weighted arithmetic mean of keyword and vector scores). The weights are tuned with the eval set.

With IAM-only access, OpenSearch Dashboards is awkward to reach from a browser. Use a small script or `awscurl` for ad-hoc queries. If the team wants Dashboards, turn on fine-grained access control with an internal master user.

### Amazon DynamoDB

On-demand capacity for all four tables. No capacity to plan.

| Table | Partition key | Sort key | Holds | TTL |
|---|---|---|---|---|
| `gs-guided-sessions` | `session_id` | none | Criteria, answers, last results | 7 days |
| `gs-guided-saved` | `user_id` | `school_id` | Saved schools and visit checklist | none |
| `gs-guided-feedback` | `session_id` | `ts` | Thumbs up / down, reason chips, result IDs | none |
| `gs-guided-school-questions` | `school_id` | `question_id` | Questions to schools, status, answer, answered date | none |

`school_questions` is keyed by school so that questions from many parents to one school can be grouped into one request (plan M4). There is no login, so `user_id` is a fixed demo user or a browser-generated ID.

### Amazon S3

| Bucket | Prefixes | Access |
|---|---|---|
| `gs-guided-data-<account-id>` | `raw/` sample and synthetic data · `school-sites/` mock school websites | Private; backend and indexer only |
| `gs-guided-web-<account-id>` | React build | Private; CloudFront only, through origin access control (OAC) |

Block Public Access stays on for both buckets.

### Amazon SES

- Stays in **sandbox mode**. In sandbox, SES delivers only to verified addresses, so the agent cannot email a real school.
- Verify one sender address and each teammate's address on day 0.
- Synthetic school email addresses in the data point at verified teammate addresses, so the "Ask the school" demo lands in a real inbox.
- The school's answer comes back through the in-app school inbox page, which writes to `school_questions`. We don't receive email.

### Compute (demo)

| Resource | Setting |
|---|---|
| ECR | One repository, `gs-guided-api` |
| ECS cluster | Fargate only |
| Service | 1 task, 0.5 vCPU, 1 GB to start; health check `GET /api/health` |
| Network | Default VPC, public subnets, public IP on the task |
| ALB | Internet-facing, HTTP listener, target group on the task's port |
| ALB security group | Inbound only from the CloudFront origin-facing managed prefix list |
| Logs | CloudWatch Logs, 7-day retention |

Public subnets with a public IP avoid a NAT gateway, which would otherwise be the largest surprise on the bill after OpenSearch. Restricting the ALB to CloudFront's prefix list means nobody can reach the API except through CloudFront.

### Amazon CloudFront (demo)

| Behavior | Origin | Settings |
|---|---|---|
| `/api/*` | ALB, HTTP only | Caching disabled; all methods allowed; forward headers, query strings and cookies |
| Default (`/*`) | Web bucket via OAC | Default root object `index.html`; 403 and 404 return `/index.html` with 200 so client-side routes work |

Viewers get HTTPS from CloudFront's default certificate. No custom domain needed.

---

## IAM

### Fargate task role

| Service | Actions | Resources |
|---|---|---|
| Bedrock | `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream` (+ `bedrock:ApplyGuardrail` in M5) | The models in `models.yaml`. With inference profiles, allow both the profile ARN and the underlying foundation-model ARNs. |
| OpenSearch | `es:ESHttpGet`, `es:ESHttpPost` | The domain ARN and `/*` |
| DynamoDB | `GetItem`, `PutItem`, `UpdateItem`, `Query`, `DeleteItem` | The four tables |
| SES | `ses:SendEmail` | The verified sender identity |
| S3 | `s3:GetObject` | `gs-guided-data-*/school-sites/*` |

The runtime role cannot write to OpenSearch indexes or S3. The indexer runs with a teammate's own credentials and needs `es:ESHttpPut` and `es:ESHttpDelete` as well.

A separate **task execution role** (the AWS-managed `AmazonECSTaskExecutionRolePolicy`) lets ECS pull the image and write logs.

### Teammates

Each teammate uses their own sandbox credentials (an SSO profile or IAM user). Nobody shares access keys, and no keys go in the repo or in `.env` files that get committed.

---

## Configuration

The backend reads everything from environment variables and `backend/config/`. Locally, values come from a gitignored `.env`; on Fargate, from the task definition.

```bash
AWS_REGION=us-east-1
OPENSEARCH_ENDPOINT=https://search-gs-guided-xxxx.us-east-1.es.amazonaws.com
OPENSEARCH_PIPELINE=gs-guided-hybrid
DATA_BUCKET=gs-guided-data-<account-id>
TABLE_PREFIX=gs-guided-
SES_FROM_ADDRESS=<verified sender>
MODELS_FILE=backend/config/models.yaml
```

```yaml
# backend/config/models.yaml
router:    { id: "<Haiku inference profile ID>", max_tokens: 512 }
extractor: { id: "<Haiku inference profile ID>", max_tokens: 1024 }
explainer: { id: "<Sonnet inference profile ID>", max_tokens: 2048 }
embedding: { id: "<Titan V2 or Cohere Multilingual ID>", dimension: 1024 }
```

---

## Day 0 Setup

In order of lead time. Start the slow items first and do the rest while they finish.

1. **Bedrock model access.** Request Haiku, Sonnet and both embedding candidates. Approval can take a while.
2. **OpenSearch domain.** Create it with the settings above. Creation can take a while.
3. **SES identities.** Verify the sender and each teammate's address. Everyone clicks the link in their email.
4. **DynamoDB tables.** Create the four tables, then turn on TTL for `sessions`.
5. **S3 data bucket.** Upload `raw/` once the generator runs.
6. **When the domain is active:** create the search pipeline, create the index mappings, run the indexer, point the aliases.
7. **Smoke test.** One hybrid query from a laptop and one Bedrock Converse call, both through the same config the backend uses.

Fargate, ALB, ECR, the web bucket and CloudFront wait until M1 works end to end locally.

These can be created by hand in the console or with CDK in `infra/` (optional, per the plan). If we use CDK, the day 0 resources go in one stack and the demo hosting in a second, so the demo stack can be created and destroyed on its own.

---

## Cost and Teardown

| Billed by the hour, even when idle | Billed per use |
|---|---|
| OpenSearch domain (by far the largest) · ALB · Fargate task | Bedrock tokens · DynamoDB on-demand · S3 · SES · CloudFront |

Things we deliberately avoid: NAT gateways, multi-AZ OpenSearch, dedicated master nodes, provisioned DynamoDB capacity.

Check the sandbox's billing page daily using the `Project` tag.

**Teardown after the hackathon** (or `cdk destroy` on both stacks if we used CDK):

1. CloudFront distribution: disable, wait for it to deploy, then delete
2. ECS service and cluster, ALB and target group, ECR repository
3. OpenSearch domain
4. DynamoDB tables
5. S3 buckets: empty them, then delete
6. SES identities, CloudWatch log groups, IAM roles

---

## Alternatives We Passed On

| Option | Why not, for now |
|---|---|
| Lambda for the whole backend | Good for small tool backends. A full agent turn streams a long response and keeps embeddings in memory, which is simpler in a long-running container. |
| OpenSearch Serverless | Bills a minimum capacity even when idle, and GreatSchools runs a managed domain, which is what we're mirroring. |
| OpenSearch in a VPC | Safer for production, but laptops can't reach it during the build without a VPN or bastion. |
| App Runner instead of Fargate + ALB | Fewer pieces, but a less direct match for how GreatSchools would run it. Worth revisiting if Fargate setup eats time. |
| Aurora or RDS for state | GreatSchools uses MySQL, but a database server is more to manage than four DynamoDB tables for a demo. |

---

## Handoff to GreatSchools

How each piece maps onto GreatSchools' stack (self-managed EC2, Ruby on Rails, MySQL, OpenSearch, S3/Athena) if they pick the work up.

| Here | At GreatSchools |
|---|---|
| OpenSearch indexes in GreatSchools' document schema, plus `search_text` and `search_vector` | Add the two fields and the search pipeline to their existing indexes |
| FastAPI agent service | Runs beside the Rails app as its own service; Rails calls `/api` |
| DynamoDB tables | Equivalent MySQL tables in the Rails app |
| Bedrock | Bedrock; today their query parsing uses OpenAI gpt-5.4-nano |
| S3 data bucket | Their S3 data lake; feedback could flow there for Athena |
| SES sandbox | Their transactional email provider |
| `needs.yaml`, `funding_rules.yaml`, `models.yaml` | Edited by their team without code changes |

---

## Open Questions

- [ ] **Does the sandbox allow everything here?** Some sandbox accounts block public OpenSearch endpoints, SES or CloudFront. Check on day 0.
- [ ] **Is there a default VPC?** Fargate in the demo phase needs one with public subnets.
- [ ] **Which Bedrock models are enabled?** Shared with [plan.md › Open Questions](plan.md#open-questions).
- [ ] **CDK or console?** CDK is cleaner to tear down and hand off. The console is faster if nobody on the team knows CDK.
