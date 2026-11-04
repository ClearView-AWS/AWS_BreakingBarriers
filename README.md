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
| `SES_ENABLED=1` plus `SES_SOURCE` and `SES_VERIFIED_TO` | The inbox records a message and also sends it through SES in sandbox mode. |
| `TRANSLATE_ENABLED=1` | Amazon Translate detects the language of each parent message and hands the pipeline English, so every language Translate supports works with the same rules and prompts. The chat keeps the parent's own words and shows "Read from Spanish". A failed call reads the message as written. The role needs `translate:TranslateText` and `comprehend:DetectDominantLanguage` (used by automatic detection). |

Sessions, saved lists, and the school inbox are a JSON file at `data/runtime/state.json` (`GS_STATE_PATH` overrides it). That file is the stand-in for DynamoDB.

### AgentCore Gateway (MCP tools)

`GsGatewayStack` serves four school tools over MCP through an AgentCore Gateway: `find_schools`, `get_school_facts`, `estimate_school_cost`, and `define_term`. They run in one Lambda (`backend/mcp_tools.py`) on the same corpus, funding rules, and glossary as the app. The schemas are in `backend/config/mcp_tools.json`. Callers sign requests with SigV4 (`AWS_IAM`). The demo deploy does not include this stack.

```bash
cd infra && npx cdk deploy GsGatewayStack -c enableOpenSearch=false
cd .. && AWS_REGION=us-east-1 .venv/bin/python scripts/gateway_demo.py "Which Jacksonville middle schools have after-school care?"
```

The script lists the tools and lets the Bedrock agent (`backend/agent/gateway.py`) call them through the gateway. It prints each call. If your credentials come from `aws login`, run `pip install "botocore[crt]"` first.

## Evaluation

`eval/queries.jsonl` has 42 parent queries, including "how liberal", a city name used in more than one state, Spanish, negations, and "a good school". The latest run is the rules engine with Bedrock off.

| Check | Result | Target |
|---|---|---|
| Criteria found (recall) | 100% (110/110) | 90%+ |
| Criteria correct (precision) | 100% (110/110) | 85%+ |
| Require / prefer / avoid correct | 100% (39/39) | 85%+ |
| Ask-or-not decision correct | 100% (39/39) | 80%+ |
| Claims with a valid citation | 30/30 | 100%, required |
| Schools dropped for missing data | 0 | 0, required |
| Turn time, median | 0.02 s | under 6 s |

These numbers measure the deterministic extractor and the evidence rules, not a live model.
