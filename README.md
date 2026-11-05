# Guided school search

A guided school-search agent for an empty AWS sandbox. The parent writes in plain language. Code decides what is true. Every fact on a card cites the field or review it came from.

**Live demo:** [https://dvpvz48phigre.cloudfront.net](https://dvpvz48phigre.cloudfront.net)  
(CloudFront + Fargate, deployed from `main` on every merge. Bedrock, OpenSearch, DynamoDB and Translate are on.)

This build also runs locally. Bedrock, OpenSearch, SES, and DynamoDB stay behind flags. The demo city is Jacksonville. The clock the age rules use is 2026-11-03 (`GS_TODAY`).

## How to run

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install && cd ..

# API
cd backend && ../.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000

# UI (another terminal)
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

> Middle school in Jacksonville with STEM and after-school care. Money is tight.

Then: answer or skip the brief questions, approve the brief, ask a school from the inbox, ask why Mariner Elementary is missing, compare a private school (the cost panel links the official Florida pages and does not subtract an award), save a school with an unknown fact, ask "How liberal are these schools?", and mark a result "Too far".

Merging to `main` redeploys the hosted demo through GitHub Actions. To redeploy by hand (Bedrock on, and the existing OpenSearch domain picked up automatically):

```bash
SKIP_OPENSEARCH=1 ./scripts/deploy-demo.sh
```

```bash
.venv/bin/python -m pytest backend/tests -q
.venv/bin/python eval/run_eval.py
```

### Frontend accessibility checks

```bash
cd frontend
npm install
npx playwright install chromium   # once
npm run test:a11y                 # axe against mocked API fixtures; fails on serious/critical
npm run test:screenshots          # writes desktop + 360px light/dark PNGs to docs/screenshots/
```

`test:a11y` builds the Vite app, serves it on port 4173, and loads the main chat, results (360px), map, saved, and community views with `frontend/tests/fixtures/` instead of a live backend.

Regenerate the synthetic corpus with `python data/synthetic/generate.py`. The 25 sample schools in `Sample Data/` stay unchanged. The generator writes 275 more schools, nearby programs, and one static page per generated school.

## Decisions

- Hard filters are location, grade, and school type. Every other criterion is scored, so a missing field never drops a school.
- Match score and evidence coverage are separate. Unknown scores 0.5. A high-confidence miss on a required criterion moves the school into "Missed a must-have" and keeps it on screen.
- Reviews can support a criterion. They never confirm one. A school website can fill a gap only up to Partial, and a conflict stays visible.
- Before the first search, the agent asks up to three skippable questions and shows a brief. Search runs after the parent approves or taps "Just show me results" (defaults apply). After that, refining asks at most one question.
- Scholarship lines say "You may qualify" and link the Florida Department of Education page. The screen does not promise an award amount. Net price stays empty.
- School email addresses are on `example.org`. SES sends only when `SES_ENABLED=1`, and only to `SES_VERIFIED_TO`.

## What code owns

| Piece | Where |
|---|---|
| Needs, phrases, evidence conditions | `backend/config/needs.yaml` |
| Scholarship rules and official links | `backend/config/funding_rules.yaml` |
| Term definitions | `backend/config/glossary.yaml` |
| Model ids | `backend/config/models.yaml` |
| Status, scoring, why-not | `backend/evidence/` |
| When to ask | `backend/clarify/` |
| Route, extract, cite, explain | `backend/agent/` |
| Search (local hybrid, OpenSearch DSL) | `backend/search/` |
| Website, inbox, SES | `backend/gaps/` |
| Blocks the browser renders | `frontend/src/App.tsx` |

GreatSchools can add or change a need by editing `needs.yaml`. A need has phrases (including Spanish), the field conditions for confirmed and partial, search boosts, and the question to ask on a visit. The mapper matches a parent's phrase to those entries. Unmapped phrases such as "how liberal" offer the needs marked `offer_when_unmapped`: inclusion, cultural responsiveness, restorative discipline, and non-religious.

## AWS, when the sandbox is available

Region `us-east-1`. Leave the flags off and the rules engine, the local index, the JSON session file, and the HTML pages stand in.

| Flag | What it turns on |
|---|---|
| `BEDROCK_ENABLED=1` | Converse for routing, extraction, and explanations, using the ids in `models.yaml`. A failed parse falls back to the rules engine. Embeddings use Titan Text Embeddings V2; otherwise a fixed hash embedder keeps mapping repeatable. |
| `OPENSEARCH_URL` | `data/index/indexer.py` pushes the `schools` and `programs` documents. Search still builds the hybrid DSL (keyword plus vector, hard filters only on city, level, and type) and applies it locally when the domain is absent. |
| `SES_ENABLED=1` plus `SES_SOURCE` and `SES_VERIFIED_TO` | The inbox records a message and also sends it through SES in sandbox mode. Off in the default deploy. Turn on with `SES=1` (and the two addresses) in `./scripts/deploy-demo.sh`, or `-c sesEnabled=true` after verifying both identities in the SES console — CDK wires IAM `ses:SendEmail` and the task env; it does not create identities. |
| `BEDROCK_GUARDRAIL_ID` (with `BEDROCK_ENABLED=1`) | Every community post and reply also goes through Bedrock Guardrails `ApplyGuardrail` (names, emails, phones, addresses). Either layer can block. A Guardrails address hit without a house number (a neighborhood, a street, a school name) is ignored. `GsAppStack` creates the guardrail when Bedrock is on; for local runs use `scripts/create_guardrail.sh`. |
| `TRANSLATE_ENABLED=1` | Amazon Translate detects the language of each parent message and hands the pipeline English, so every language Translate supports works with the same rules and prompts. The chat keeps the parent's own words and shows "Read from Spanish". A failed call reads the message as written. The role needs `translate:TranslateText` and `comprehend:DetectDominantLanguage` (used by automatic detection). |

Sessions, saved lists, and the school inbox are a JSON file at `data/runtime/state.json` (`GS_STATE_PATH` overrides it). That file is the stand-in for DynamoDB.

### CDK stacks

| Stack | What | In the default demo deploy? |
|---|---|---|
| `GsAppStack` | CloudFront + S3 frontend, ALB + Fargate API, DynamoDB, Guardrail; optional SES (flag-gated) | Yes (`./scripts/deploy-demo.sh`; SES off unless `SES=1`) |
| `GsOpenSearchStack` | OpenSearch domain | Optional (`SKIP_OPENSEARCH=1` skips it in CI) |
| `GsGatewayStack` | AgentCore Gateway + school-tools Lambda | No — set repo variable `DEPLOY_GATEWAY=1`, or deploy by hand |
| `GsVoiceStack` | Voice-turn Lambda, Lex V2 bot, Connect contact flow | No — set repo variable `DEPLOY_VOICE=1`, or deploy by hand |

Architecture detail (one DynamoDB table, Leaflet/OSM maps, SES optional): [`docs/infra.md`](docs/infra.md). Judge-facing narrative: [`docs/how-it-works.md`](docs/how-it-works.md). Ops: [`infra/README.md`](infra/README.md).

The Connect instance and its phone number are imported by id (context `voiceInstanceId` / `VOICE_INSTANCE_ID`): an instance needs an alias and outbound unlock, and deleting it with the stack would drop the claimed number. Claiming a number in CDK is off (`voiceClaimNumber=true` to opt in).

### AgentCore Gateway (MCP tools)

`GsGatewayStack` serves four school tools over MCP through an AgentCore Gateway: `find_schools`, `get_school_facts`, `estimate_school_cost`, and `define_term`. They run in one Lambda (`backend/mcp_tools.py`) on the same corpus, funding rules, and glossary as the app. The schemas are in `backend/config/mcp_tools.json`. Callers sign requests with SigV4 (`AWS_IAM`).

```bash
cd infra && npx cdk deploy GsGatewayStack -c enableOpenSearch=false
cd .. && AWS_REGION=us-east-1 .venv/bin/python scripts/gateway_demo.py "Which Jacksonville middle schools have after-school care?"
```

The script lists the tools and lets the Bedrock agent (`backend/agent/gateway.py`) call them through the gateway. It prints each call. If your credentials come from `aws login`, run `pip install "botocore[crt]"` first.

### School phone call (Connect + Lex + Lambda)

`GsVoiceStack` defines the voice-turn Lambda (`backend/voice/lex_turn.py`), Lex V2 bot/alias, Connect contact flow, Lex association, and CloudWatch log groups. Pass the existing Connect instance id and the app's RuntimeState table:

```bash
cd infra && npx cdk deploy GsVoiceStack \
  -c voiceInstanceId=$VOICE_INSTANCE_ID \
  -c voiceStateTable=<GsAppStack RuntimeState table name>
```

Stack outputs include `FlowId` (set as `VOICE_FLOW_ID` on the API). `scripts/setup_voice.py` remains as a legacy imperative path and prints the same env vars.

## Evaluation

`eval/queries.jsonl` (42) is the set we tune against. `eval/holdout.jsonl` (30) is never tuned against — report those scores honestly. The CI / local gate is **rules-only** (`eval/run_eval.py` with Bedrock off). For call economics vs eval token cost, see [`docs/pitch/cost.md`](docs/pitch/cost.md).

### Tuned `queries` — rules only

```bash
.venv/bin/python eval/run_eval.py --set queries
```

| Check | Result | Target |
|---|---|---|
| Criteria found (recall) | 100% (110/110) | 90%+ |
| Criteria correct (precision) | 100% (110/110) | 85%+ |
| Require / prefer / avoid correct | 100% (39/39) | 85%+ |
| Ask-or-not decision correct | 100% (39/39) | 80%+ |
| Cited claims kept (full suite) | 33/33 | 100%, required |
| Schools dropped for missing data | 0 | 0, required |
| Median first turn | 0.01 s | under 6 s |

These numbers measure the deterministic extractor and the evidence rules, not a live model.

### Holdout — rules only

```bash
.venv/bin/python eval/run_eval.py --set holdout
```

| Check | Result |
|---|---|
| Queries | 30 |
| Criteria found (recall) | 55.6% (55/99) |
| Criteria correct (precision) | 89.5% (51/57) |
| Require / prefer / avoid correct | 66.7% (8/12) |
| Ask-or-not decision correct | 40.0% (12/30) |
| Median first turn | 0.01 s |

### Holdout — Bedrock on

```bash
.venv/bin/python eval/run_eval.py --set holdout --bedrock
```

Requires AWS credentials that can call Bedrock Runtime, plus `pip install "botocore[crt]"` when using login/SSO-style providers. Metered from `eval/prices.yaml`.

| Check | Result |
|---|---|
| Queries | 30 |
| Criteria found (recall) | 97.0% (96/99) |
| Criteria correct (precision) | 80.4% (82/102) |
| Require / prefer / avoid correct | 58.8% (20/34) |
| Ask-or-not decision correct | 80.0% (24/30) |
| Median first turn | 4.72 s |
| Extract fell back to rules | 0 |
| Est. cost per first turn | $0.00702 |
| Bedrock calls | 108 |
| Bedrock tokens in / out | 94486 / 24123 |
| Bedrock latency per call, mean | 2.07 s |
| Est. Bedrock cost, whole set | $0.2801 |
| Wall time | 202.5 s |
