# Implementation Plan: GreatSchools Guided Agent

*Draft · Nov 3, 2026 · Scope: P1–P4 + differentiators · Data: synthetic, Florida*

How we build a guided school-search agent in an empty AWS sandbox: what each part does, who builds it, the order we build in, and where we can stop if time runs out.

> **The model reads the parent. Code decides what's true.**
> Bedrock turns plain language into criteria and writes the explanations. Every fact a parent sees comes from code that reads the data and cites the field it came from.

## Contents

- [What Sets It Apart](#what-sets-it-apart)
- [Ground Rules](#ground-rules)
- [How a Turn Works](#how-a-turn-works)
- [Map View](#map-view)
- [Stack](#stack)
- [Data](#data)
- [Shared Contracts](#shared-contracts)
- [Rules in Code](#rules-in-code)
- [Milestones](#milestones)
- [Workstreams](#workstreams)
- [Demo Script](#demo-script)
- [Evaluation](#evaluation)
- [Risks](#risks)
- [Open Questions](#open-questions)
- [Repo Layout](#repo-layout)

---

## What Sets It Apart

The vision asks for ranked, explained results with confirmed / partial / needs-attention evidence. We meet that, then go further in eight places.

| Differentiator | What the parent sees |
|---|---|
| **Evidence with sources** | Every criterion on every card shows a status, where the answer came from, and how old it is. |
| **Questions that matter** | The agent asks only when the answer would change the results, and shows results in the meantime. |
| **Missing data stays visible** | A school with no data on something is marked unknown and stays in the list. |
| **Filling the gaps** | The agent checks the school's website, can ask the school, and puts the rest on a visit checklist. |
| **"Why isn't this school here?"** | Answered from the evidence, including what would change the ranking. |
| **Cost after scholarships** | Private school cards show likely scholarship eligibility, linked to the official source. |
| **Map view** | Schools, and the nearby programs that fill their gaps, on one map. Tapping the map is part of the conversation. |
| **Measured** | An evaluation set reports extraction and citation accuracy in the README. |

---

## Ground Rules

These are decisions, so every track can build against them without checking in.

- The LLM never decides whether a fact is true. It extracts criteria, routes the message, words questions, and writes explanations from evidence that code produced.
- Hard filters apply only to location, grade level and school type. Every other criterion is scored in code, so missing data never drops a school.
- Match score and evidence coverage are separate numbers. We rank by match and show coverage beside it ("Verified 3 of 4").
- Every claim on screen cites a field path or review ID. A sentence without a valid citation is not shown.
- The agent asks at most one question per turn. Results appear in the same turn with assumptions stated.
- Reviews can support a criterion. They never confirm one.
- Synthetic data keeps GreatSchools' document schema, so their real documents can replace it later.
- The map never holds information on its own. The agent's message says in words what the map shows.
- We keep only a zip code or a rounded point for the parent's location, never a home address.

---

## How a Turn Works

Each parent message runs through the same steps. **LLM** = Bedrock call. **Code** = deterministic, testable. **UI** = browser.

| # | Step | Who | What it does |
|---|---|---|---|
| 1 | Route | LLM | Classify the message: new search, refine, compare, school detail, define a term, why-not, cost, save. Map taps arrive as structured events and skip this step. |
| 2 | Extract | LLM | Turn the text into criteria with require / prefer / avoid, parameters and possible ambiguities. |
| 3 | Map | Code | Match each phrase to a need in `needs.yaml` with embeddings. Low similarity means unmapped; a small gap to the runner-up means ambiguous. |
| 4 | Search | Code | OpenSearch hybrid query: hard filters on location, grade and type, boosts per need, free text matched by keyword and vector. Returns about 100 candidates. |
| 5 | Evidence | Code | For each school and criterion: status, value, source type, date and citation path. |
| 6 | Score | Code | Match score from statuses and weights. Coverage computed separately. |
| 7 | Clarify | Code | Decide whether one question is worth asking. The LLM only words the chosen question. |
| 8 | Explain | LLM | Write card text from the evidence JSON. A validator drops any sentence that doesn't cite an evidence record. |
| 9 | Render | UI | Show the blocks the agent chose: message, chips, question, cards, grid, map, comparison, checklist. |

**Tools the agent can call on any turn:**

- **Gap resolver:** other data, then the school website, then ask the school, then the visit checklist.
- **Cost estimator:** tuition minus likely scholarship, from a rules file with official links.
- **Saved list:** saves, visit checklist, pending questions to schools.

---

## Map View

Results can show on a map as well as in a list or grid. The map is part of the conversation: the agent chooses when to show it, and what the parent does on it becomes the next turn.

### What the parent sees

```text
┌ Chat ─────────────────────────┐ ┌ [List] [Grid] [Map] ──────────────────
│ You: Middle school in Jax     │ │
│ with STEM and after-care.     │ │      ①                ◆ STEM club
│                               │ │           ⌂ you
│ Agent: 6 schools fit. The 3   │ │      ②          ③ ┄┄┄ ◆ after-school
│ closest are north of the      │ │                          program
│ river. Does after-care need   │ │   ○ missed a must-have
│ to be at the school?          │ │
│ [At school] [Nearby is fine]  │ │ ┌ ③ Bayview Charter · 78% · 2.1 mi
│                               │ │ │ STEM ✓   After-care ?   Cost ~
│ → You tapped ③                │ │ │ Program 0.4 mi away covers 3–6 pm
│                               │ │ │ [Save] [Compare] [Ask the school]
└───────────────────────────────┘ └─────────────────────────────────────
```

*Sketch only; the school name is made up.*

- **Layout.** On a computer, chat on the left and a results panel on the right with List, Grid and Map tabs. On a phone, the map appears as a small card in the chat and opens full screen when tapped. Design for the phone first: many of the families this is for rely on one.
- **School pins** are numbered by rank, matching the list, and colored by match. Schools in "Missed a must-have" are hollow pins, so they stay visible.
- **Program pins** (◆) appear only when a program fills a gap at a school on the map, with a dashed line to that school.
- **"You" marker** is the parent's search point, from a zip code or a dropped pin. The parent can drag it. Distance rings show how far each school is.
- **Tapping a pin** opens a small card: match, distance, a status for each criterion, and Save, Compare and Ask the school.
- **The agent says it in words too** ("the 3 closest are north of the river"), so screen readers and parents who don't read maps get the same information.

### Map events

What the parent does on the map is sent as a structured event, not text. The backend picks the route from the event and the session, with no LLM call. The chat logs each event ("You moved the search area to Arlington") so the history stays readable.

| Parent does | Event | Handled as |
|---|---|---|
| Taps a pin | `pin_selected` | School detail (P3) |
| Taps a hollow pin | `pin_selected` | Why-not for that school |
| Selects two pins | `pins_compared` | Compare (P2) |
| Drags "you" or taps "Search this area" | `area_changed` | Refine: the location chip updates and the search reruns |

Chat, chips, list, grid and map all draw from the same session state, so a change in one shows in all of them.

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Models | Amazon Bedrock. A small, fast model (e.g. Claude Haiku) for routing and extraction; a stronger one (e.g. Claude Sonnet) for explanations and comparisons. | Bedrock is required. The split keeps each turn fast. |
| Embeddings | A multilingual embedding model on Bedrock (Titan Text Embeddings V2 or Cohere Embed Multilingual; pick with the eval set) | Need mapping, vector search, Spanish queries. |
| Search | Amazon OpenSearch Service, one small domain, hybrid keyword + vector query with a normalization search pipeline | Required, and it mirrors GreatSchools. |
| Backend | Python + FastAPI. Bedrock Converse API with tool use; Strands Agents optional. | Tools are plain Python functions we can unit test. |
| State | DynamoDB: sessions, saved lists, feedback, questions sent to schools | Nothing to manage. |
| Email | Amazon SES in sandbox mode | Delivers only to verified addresses, so it can't reach a real school. |
| Frontend | React + Vite + TypeScript on S3 + CloudFront | Renders typed blocks from the API. |
| Maps | MapLibre GL JS, with Amazon Location Service for map tiles and zip-code lookup | Keeps the map on AWS. Leaflet with OpenStreetMap tiles is the fallback. |
| Hosting | Local during the build. ECS Fargate for the demo if time allows. | Fewest moving parts. |
| Region | us-east-1 | Matches GreatSchools production. |

---

## Data

### What the sample gives us

| Fact | Value |
|---|---|
| Schools | 25, all in Florida: 12 charter, 8 private, 5 public |
| Schools with no summary rating | 12 / 25 (same for student/teacher ratio) |
| Schools with no reviews | 12 / 25 |
| Review dates | 2010–2025, across 127 reviews |
| Programs in Florida | 3 / 25; many are adult library events |

Two quirks to code around:

- Signal blocks such as `class_size` and `high_attendance` carry their own `confidence`, `qualifies` and `source_generated_at`. We use all three.
- Each review's `overall_rating` is a sentiment score from −1 to 1, not stars, and every one is beyond ±0.93. It never goes on screen as a rating.

### What we add

- **Generator script** that expands to about 300 schools across three Florida metros, starting with Jacksonville. It keeps the exact schema and the same missing-data rates as the sample. The original 25 stay unchanged. Every generated school gets a `latlon` on land near a real street, because the map shows any point that lands in a river.
- **New fields in `osp` style:** tuition for private schools, after-school care hours, and a `_synthetic: true` marker on every generated record.
- **Programs near schools:** homework help, STEM clubs and after-school programs with real-looking times, placed within a mile of schools that lack that service, so a program can fill a school's gap.
- **Mock school websites:** one static page per school in S3. Some add facts the data lacks; a few contradict it, so the demo can show a conflict.
- **`funding_rules.yaml`:** Florida scholarship programs (for example the Family Empowerment Scholarship and the Florida Tax Credit Scholarship). Fill rules and amounts from the official Florida Department of Education pages and keep the link beside each one.

### Indexing

Two indexes, `schools` and `programs`. Each document keeps its original fields and adds a `search_text` field (name, ESP text, profile values, recent review snippets) with its embedding. The 40 or so needs stay in memory for mapping; they don't need an index. Both indexes map `latlon` as `geo_point` for distance filters and the map.

---

## Shared Contracts

Agree on these five shapes in the first hour. Each track then builds against fixture files in these shapes until the real parts arrive.

### Criterion (output of Extract + Map)

```jsonc
{
  "id": "c3",
  "text": "after-school care",
  "need": "after_care",            // id in needs.yaml, or null if unmapped
  "strength": "require",           // require | prefer | avoid
  "params": { "until": "17:30" },
  "mapping": { "score": 0.82, "runner_up": "extended_day", "margin": 0.04 },
  "ambiguities": [
    { "kind": "definition", "options": ["at the school", "nearby program is fine"] }
  ]
}
```

### Need definition (`needs.yaml`)

```yaml
high_performing:
  label: High-performing
  phrases: [top school, best school, high rated, escuela buena]
  evidence:
    - field: summary_rating
      source: state_data
      confirmed: ">= 8"
      partial: "== 7"
  search_boost:            # today this need is a hard filter; we boost so unrated schools stay
    summary_rating: { gte: 8 }
    avg_review_rating: { gte: 4 }
  review_topics: []
  ask_if_unknown: "Ratings are missing for {n} of these schools. Keep them in the list?"
  visit_question: "How did students do on state tests last year?"
```

GreatSchools' team can add or change a need by editing this file. That is the handoff story for the README.

### Evidence record (output of Evidence)

```jsonc
{
  "school_id": "School fl-95390",
  "criterion_id": "c2",
  "status": "needs_attention",     // confirmed | partial | needs_attention | unknown
  "value": "large",
  "source": {
    "type": "state_data",          // state_data | school_reported | school_website | parent_reviews | computed
    "path": "class_size.tier",
    "as_of": "2026-07-15",
    "confidence": "high"
  },
  "note": "Classes are large compared with other elementary schools."
}
```

### API response (blocks the agent chooses)

```jsonc
{
  "blocks": [
    { "type": "message", "text": "Here are 6 middle schools in Jacksonville…" },
    { "type": "criteria", "items": ["c1", "c2", "c3", "c4"] },
    { "type": "question", "text": "Does after-school care need to be at the school?",
      "options": ["At the school", "A nearby program is fine"] },
    { "type": "results", "schools": [{ "id": "…", "match": 0.78, "verified": "3 of 4" }] },
    { "type": "evidence_grid", "schools": ["…", "…"], "criteria": ["c1", "c2", "c3"] },
    { "type": "map", "you": [30.32, -81.66],
      "schools": [{ "id": "…", "rank": 3, "match": 0.78, "missed_must_have": false }],
      "programs": [{ "id": "…", "fills": { "school": "…", "criterion": "c3" }, "miles": 0.4 }] }
  ]
}
// other block types: comparison, school_detail, definition, cost, checklist, why_not
```

### UI event (map taps)

```jsonc
{
  "session_id": "…",
  "event": "pin_selected",          // pin_selected | pins_compared | area_changed
  "school_ids": ["School fl-95390"],
  "area": null                      // area_changed: { "center": [30.32, -81.66], "radius_mi": 5 }
}
```

---

## Rules in Code

### Evidence status

| Status | When |
|---|---|
| ✅ **Confirmed** | Field present and meets the condition, source confidence high or medium, data less than 18 months old. |
| 🟡 **Partial** | Meets the condition but confidence is "unknown" or data is older than 18 months; or only partly meets it (care until 5:00 when the parent needs 5:30); or supported only by reviews (2+ on the topic, mostly positive); or found on the school website. |
| 🔴 **Needs attention** | Field present and fails the condition, or 3+ reviews on the topic are mostly negative. |
| ⚪ **Unknown** | No field, or fewer than 2 reviews on the topic. |

Reviews older than five years count half. A program whose only sessions are in the past counts as stale.

### Scoring

```text
weight   = { require: 3, prefer: 1, avoid: 2 }        # avoid is scored inverted
value    = { confirmed: 1.0, partial: 0.6, unknown: 0.5, needs_attention: 0.0 }
match    = Σ weight × value / Σ weight
coverage = share of criteria that are confirmed or needs_attention   # shown, never multiplied in
```

Unknown scores 0.5, so missing data neither lifts nor buries a school. A require criterion with a high-confidence **Needs attention** moves the school to a "Missed a must-have" group under the results. It stays visible, and it feeds the why-not answer.

### When to ask a question

1. Location or grade level missing and not in the session: ask.
2. For each ambiguous criterion, run the search once per reading. If the top 10 overlap by less than 60%, it is a candidate. Pick require criteria first, then the largest difference.
3. A require criterion is unknown for 30% or more of the top 10: ask whether it is a dealbreaker and offer to ask the schools.
4. A phrase maps to nothing (for example "how liberal"): offer related needs as chips, such as inclusion, cultural responsiveness, restorative discipline and non-religious.

Ask the first that applies, at most one per turn. The results still show, with the assumption stated: "I assumed on-site care. Change it?"

### When to show the map

1. The parent asks for it or opens the Map tab.
2. A criterion is about place: "near me," "on my way to work," "within 15 minutes," or distance itself.
3. The top 10 results are spread over more than 10 miles.

Otherwise the agent shows the list and grid, and the Map tab stays one tap away.

- Pin color comes from the match score. Schools in "Missed a must-have" are hollow.
- A program pin appears only if it is within 1 mile of a school on the map and covers a criterion that is unknown or needs attention there. Programs whose only sessions are in the past don't appear.
- Distance is computed in code from `latlon` (straight line to start) and cited like any other evidence, with source type `computed`.

---

## Milestones

Build in this order. Each stop point is a complete demo, so if time runs out we stop at the last one finished.

### D0 · Lead-time setup *(first hours)*

- Request Bedrock model access and create the OpenSearch domain; both can take a while.
- Verify each teammate's email in SES.
- Agree the five contracts and the demo city.
- Generate synthetic data and index it.

### M1 · First end-to-end slice *(P1 core)*

- Search box, extraction, editable chips, search, evidence, scoring.
- Cards with a status, source and citation for every criterion.
- Save a school to a list.

**Stop point: demoable**

### M2 · Guided layer *(finishes P1)*

- Clarifier with the overlap check; assumptions stated alongside results.
- Dealbreaker questions for unknown must-haves.
- Vague requests such as "how liberal" turned into concrete chips.
- Thumbs up / down, with reason chips that refine the search.
- Map view: numbered pins colored by match, tap a pin for its card, a "you" marker from the parent's zip code.

**Stop point: meets every success criterion in the vision**

### M3 · Compare and explain *(P2–P4)*

- Evidence grid and two-school comparison with source labels.
- School detail view and term definitions ("What is CTE?").
- "Why isn't this school here?" with the change that would move it up.
- Review topics with counts, both sides and dates.
- On the map: select two pins to compare, tap a hollow pin for why-not, drag "you" or search this area to refine.

**Stop point: all four priorities done**

### M4 · Fill gaps and show cost *(differentiators)*

- Gap resolver: other data, mock school website, ask the school (SES + school inbox page), visit checklist on the saved list.
- Questions from many parents to one school grouped into one request.
- Cost after likely scholarships for private schools.
- Program pins on the map, linked to the schools whose gaps they fill.

**Stop point: full demo script**

### M5 · Stretch *(only if M4 is done)*

- Spanish end to end.
- Bedrock Guardrails contextual grounding check as a second guard on explanations.
- Trade-off chart with what-if ("a 20-minute commute adds 3 schools").
- Drive-time areas on the map instead of straight-line distance.
- Notify the parent when a school answers (Level 3 preview).
- Follow up on the parent's final choice.
- Suggest criteria from what other parents searched for, using structured criteria only, never chat text.

---

## Workstreams

Four tracks that can run in parallel once the contracts are agreed. With fewer people, merge A with C and B with D.

| Track | Owns |
|---|---|
| **A · Data and search** | Synthetic generator and mock school websites · Index mappings and indexer · Query builder from `needs.yaml` to OpenSearch · `funding_rules.yaml` with official links · `geo_point` mapping, distance filter and plausible coordinates |
| **B · Agent** | Router and extractor prompts and tool definitions · Need mapper with embeddings · Question wording and explainer · Citation validator · Evaluation runner · Map events in the router, map described in words |
| **C · Evidence and ranking** | `needs.yaml` and evidence rules · Review analysis with recency · Scorer, clarifier logic, why-not · Cost estimator and gap resolver · When to show the map, pin rules, distance evidence |
| **D · Frontend** | Block renderer, chat, editable chips · Result cards and evidence grid · Saved list with visit checklist · School inbox page for the demo · Feedback controls · Map view, phone layout, map events |

---

## Demo Script

About six minutes. Each step shows one thing from the vision's success criteria or one differentiator.

1. The parent types *"Middle school in Jacksonville with STEM and after-school care. Money is tight."* Chips appear: middle school, Jacksonville, STEM (require), after-school care (require), low cost (prefer). Results show right away.
2. In the same turn the agent asks one question: *"Does after-school care need to be at the school, or is a nearby program fine?"* It asks because the two answers produce different top schools.
3. Cards show Confirmed / Partial / Needs attention / Unknown for each criterion, with sources. One card has after-school care unknown and an "Ask the school" button.
4. The parent taps *"A nearby program is fine"* and opens the map. The agent says the three closest schools are north of the river. Next to the school with unknown after-care, a program pin 0.4 miles away covers 3–6 pm, with a dashed line to the school.
5. The parent asks *"How liberal are these schools?"* The agent says it doesn't rate schools on politics and offers chips it can back with data: inclusion, cultural responsiveness, restorative discipline, non-religious.
6. The parent asks why a school they know isn't listed. The agent names the criterion that held it back and what would change its rank.
7. The parent selects two pins and compares them. The evidence grid shows each answer's source and date. The private school shows likely cost after scholarship, with the official link.
8. The parent taps "Ask the school." A teammate answers in the school inbox, and the grid cell turns Confirmed, labeled school-reported with today's date.
9. The parent saves two schools. The saved list shows a visit checklist built from what is still unknown. A thumbs-down with "too far" tightens the distance chip, and the map zooms in to match.

---

## Evaluation

A file of about 40 parent queries, each with the expected criteria, strengths, whether a question should be asked, and whether the map should show. Run it before every merge and put the latest numbers in the README. The targets are ours to adjust.

| Check | Target |
|---|---|
| Criteria found (recall) | 90%+ |
| Criteria correct (precision) | 85%+ |
| Require / prefer / avoid correct | 85%+ |
| Ask-or-not decision correct | 80%+ |
| Show-map decision correct | 85%+ |
| Claims with a valid citation | 100%, required |
| Schools dropped for missing data | 0, required |
| Turn time, median | under 6 s |

Include the hard cases on purpose: "how liberal," a city name used in several states, Spanish queries, negations ("not religious"), vague ones ("a good school"), and place phrases ("near my job," "on my way to work").

---

## Risks

| Risk | Plan |
|---|---|
| OpenSearch setup time and cost | Create it first. Smallest instance, one node. Delete it after the hackathon. |
| Model access not enabled | Request on day 0. The code takes model IDs from config, so we can switch to whatever is enabled. |
| Slow turns | Small model for routing and extraction. Run the per-reading searches in parallel. Stream the explanation. |
| Claims not in the data | Citation validator drops uncited sentences. Grounding check in M5. |
| Wrong scholarship info | "You may qualify" wording, official link on every line, no promised amounts. |
| Emailing a real school | SES sandbox only delivers to verified addresses. School addresses in the data are synthetic. |
| Synthetic points look wrong on a map | The generator places schools and programs near real streets in the demo metro. Check every pin on the map before the demo. |
| Parent's location is sensitive | Keep only a zip code or a rounded point in the session. Never ask for a home address. |
| Scope creep | Finish M1 end to end before starting anything else. Stop points are the plan. |

---

## Open Questions

- [ ] **How long is the hackathon, and how many of us are there?** That decides which milestone we aim for and how the tracks merge.
- [ ] **Will GreatSchools' sample OpenSearch documents arrive?** If they do, we write an adapter to our contracts rather than change the contracts.
- [ ] **Which models are enabled in the sandbox?**
- [ ] **Demo city.** This plan assumes Jacksonville because it is in the sample data.
- [ ] **Is Amazon Location Service available in the sandbox?** If not, the map uses OpenStreetMap tiles and zip codes come from the Census Bureau's public ZIP code (ZCTA) gazetteer file.

---

## Repo Layout

```text
backend/
  app.py                    FastAPI entry point
  agent/                    router, extractor, explainer, prompts, tool definitions
  mapping/                  need mapper (embeddings)
  search/                   query builder, OpenSearch client
  evidence/                 status rules, reviews, scorer, why-not
  clarify/                  overlap check, question choice
  gaps/                     gap resolver, school inbox, SES
  funding/                  cost estimator
  geo/                      distance, when to show the map, pin rules, zip lookup
  config/                   needs.yaml, funding_rules.yaml, models.yaml
data/
  sample/                   the 25 + 25 provided records, unchanged
  synthetic/                generator, mock school websites
  index/                    mappings, indexer
frontend/                   React + Vite: blocks, chips, cards, grid, map, saved list, inbox
eval/                       queries.jsonl, run_eval.py
infra/                      optional CDK
README.md                   how to run, decisions, AWS services, eval results
```
