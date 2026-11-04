# Guided school search

A guided school-search agent for an empty AWS sandbox. The parent writes in plain language. Code decides what is true. Every fact on a card cites the field or review it came from.

This build runs locally through the demo script (milestones M1–M4). Bedrock, OpenSearch, SES, and DynamoDB stay behind flags so the same code can move into the sandbox later. The demo city is Seattle, Washington. GreatSchools' 25 sample schools (Florida in the original files) are moved to Seattle by the generator; the original files stay unchanged. The clock the age rules use is 2026-11-03 (`GS_TODAY`).

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

Open http://127.0.0.1:5173. The demo query is:

> Middle school in Seattle with STEM and after-school care. Money is tight.

Then: answer the care question, ask a school from the inbox, ask why Mariner Elementary is missing, compare a private school (the cost panel says each school sets its own aid, links the State Board of Education, and does not subtract an award), save a school with an unknown fact, ask "How liberal are these schools?", and mark a result "Too far".

```bash
.venv/bin/python -m pytest -q
.venv/bin/python eval/run_eval.py
```

Parent community demo: on the Arbor Heights STEM Middle card, tap "Ask parents at this school". Try posting with a child's name (it is blocked), then post without it. Switch "Viewing as" to School staff, tap "Send digest", and answer the after-care thread. Switch back to Parent A and go back to results. After-school care is now Confirmed, school-reported. See `docs/community.md`.

Regenerate the synthetic corpus with `python data/synthetic/generate.py`. The 25 sample schools in `Sample Data/` stay unchanged; the generator writes their Seattle copies, 275 more Seattle schools, nearby programs, and one static page per generated school.

## Decisions

- Hard filters are location, grade, and school type. Every other criterion is scored, so a missing field never drops a school.
- Match score and evidence coverage are separate. Unknown scores 0.5. A high-confidence miss on a required criterion moves the school into "Missed a must-have" and keeps it on screen.
- Reviews can support a criterion. They never confirm one. A school website can fill a gap only up to Partial, and a conflict stays visible.
- The agent asks at most one question per turn, and only when the answer would change the top results, a required fact is unknown for many of them, or the phrase does not map to a need. Results show in the same turn, with the assumption stated.
- Private-school cost lines say each Washington private school sets its own tuition and aid, link the State Board of Education, and note that the federal Education Freedom Tax Credit (from Jan 1, 2027) depends on Washington opting in. The screen does not promise an award amount. Net price stays empty.
- Getting in follows Seattle Public Schools (attendance area schools, Open Enrollment for School Choice) and Washington law (RCW 28A.710.050 for charter lotteries), each with its official link.
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
| Parent community, safety check, demand counts | `backend/community/` (see `docs/community.md`) |
| Blocks the browser renders | `frontend/src/App.tsx` |

GreatSchools can add or change a need by editing `needs.yaml`. A need has phrases (including Spanish), the field conditions for confirmed and partial, search boosts, and the question to ask on a visit. The mapper matches a parent's phrase to those entries. Unmapped phrases such as "how liberal" offer the needs marked `offer_when_unmapped`: inclusion, cultural responsiveness, restorative discipline, and non-religious.

## AWS, when the sandbox is available

Region `us-east-1`. Leave the flags off and the rules engine, the local index, the JSON session file, and the HTML pages stand in.

| Flag | What it turns on |
|---|---|
| `BEDROCK_ENABLED=1` | Converse for routing, extraction, and explanations, using the ids in `models.yaml`. A failed parse falls back to the rules engine. Embeddings use Titan Text Embeddings V2; otherwise a fixed hash embedder keeps mapping repeatable. |
| `OPENSEARCH_URL` | `data/index/indexer.py` pushes the `schools` and `programs` documents. Search still builds the hybrid DSL (keyword plus vector, hard filters only on city, level, and type) and applies it locally when the domain is absent. |
| `SES_ENABLED=1` plus `SES_SOURCE` and `SES_VERIFIED_TO` | The inbox records a message and also sends it through SES in sandbox mode. |

Sessions, saved lists, and the school inbox are a JSON file at `data/runtime/state.json` (`GS_STATE_PATH` overrides it). That file is the stand-in for DynamoDB.

## Evaluation

`eval/queries.jsonl` has 42 parent queries, including "how liberal", a city name used in more than one state, Spanish, negations, and "a good school". The latest run is the rules engine with Bedrock off.

| Check | Result | Target |
|---|---|---|
| Criteria found (recall) | 100% (110/110) | 90%+ |
| Criteria correct (precision) | 100% (110/110) | 85%+ |
| Require / prefer / avoid correct | 100% (39/39) | 85%+ |
| Ask-or-not decision correct | 100% (39/39) | 80%+ |
| Claims with a valid citation | 30/30 | 100%, required |
| Draft posts with personal info that get published | 0/10 | 0, required |
| Schools dropped for missing data | 0 | 0, required |
| Turn time, median | 0.02 s | under 6 s |

These numbers measure the deterministic extractor and the evidence rules, not a live model.
