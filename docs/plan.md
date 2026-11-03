# Implementation Plan: GreatSchools Guided Agent and Parent Community

*Draft · Nov 3, 2026 · Scope: P1–P4, parent community, differentiators · Data: synthetic, Florida*

How we build a school-search platform for parents in an empty AWS sandbox: what each part does, who builds it, the order we build in, and where we can stop if time runs out.

The platform has two halves that feed each other. A **guided agent** makes sure it understands what the parent needs before it searches, then returns ranked, evidence-backed schools. A **parent community** gives every school Reddit-style threads where parents ask questions and share what it's really like. When the data can't answer something, the agent asks the community or the school, and their answers flow back into the agent's results.

> **The model reads the parent. Code decides what's true.**
> Bedrock turns plain language into criteria and writes the explanations. Every fact a parent sees comes from code that reads the data and cites where it came from. Parents' posts can support a criterion; only data or the school itself can confirm one.

## Contents

- [What Sets It Apart](#what-sets-it-apart)
- [Ground Rules](#ground-rules)
- [How a Turn Works](#how-a-turn-works)
- [Understanding the Request](#understanding-the-request)
- [Parent Community](#parent-community)
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

The vision asks for ranked, explained results with confirmed / partial / needs-attention evidence. We meet that, then go further in seven places.

| Differentiator | What the parent sees |
|---|---|
| **Evidence with sources** | Every criterion on every card shows a status, where the answer came from, and how old it is. |
| **Understands before it searches** | Like a planning step: the agent asks a few quick questions, shows a short brief of what it understood, and searches once the parent approves or edits it. |
| **Parent community** | Reddit-style threads on every school where parents ask questions and share experiences, with replies and upvotes. |
| **Ask the school, with demand counts** | "14 parents asked about after-school care this month." The school gets one summary email and answers once, in its own thread. |
| **Cost after scholarships** | Private school cards show likely scholarship eligibility, linked to the official source. |
| **Map view** | Schools, and the nearby programs that fill their gaps, on one map. Tapping the map is part of the conversation. |
| **Measured** | An evaluation set reports extraction, citation and privacy-check accuracy in the README. |

---

## Ground Rules

These are decisions, so every track can build against them without checking in.

- The LLM never decides whether a fact is true. It extracts criteria, routes the message, words questions, and writes explanations from evidence that code produced.
- Hard filters apply only to location, grade level and school type. Every other criterion is scored in code, so missing data never drops a school, and a school with no data on something is marked unknown.
- Match score and evidence coverage are separate numbers. We rank by match and show coverage beside it ("Verified 3 of 4").
- Every claim on screen cites a field path, review ID or post ID. A sentence without a valid citation is not shown.
- The agent asks before searching only when the request is thin: at most three questions, every one skippable, with "Just show me results" always available. A specific request goes straight to the brief, with results in the same turn.
- Reviews and community posts can support a criterion. They never confirm one. Only data or the school's own answer confirms.
- Nothing is posted to the community without the parent's tap on the draft, and every post passes a personal-information check first.
- Schools hear from us in one digest, not once per parent.
- The map never holds information on its own. The agent's message says in words what the map shows.
- We keep only a zip code or a rounded point for the parent's location, never a home address.
- Synthetic data keeps GreatSchools' document schema, so their real documents can replace it later. Every synthetic record, including seed posts, is marked `_synthetic: true`.

---

## How a Turn Works

A conversation has two phases. **LLM** = Bedrock call. **Code** = deterministic, testable. **UI** = browser.

### Understand (first message, and whenever the parent changes direction)

| # | Step | Who | What it does |
|---|---|---|---|
| 1 | Route | LLM | Classify the message: new search, refine, compare, school detail, define a term, cost, save, ask the school, ask the community. Taps on the map, questions and brief arrive as structured events and skip this step. |
| 2 | Extract | LLM | Turn the text into criteria with require / prefer / avoid, parameters and possible ambiguities. Infer needs the parent implies ("I work until 5" → after-school care until about 5:30). |
| 3 | Match needs | Code | Match each phrase to a need in `needs.yaml` with embeddings. Low similarity means unmatched; a small gap to the runner-up means ambiguous. |
| 4 | Plan questions | Code | Pick up to three questions that would change the results, using quick searches to test ambiguous readings. The LLM only words them. |
| 5 | Brief | UI | Show the questions as tap-to-answer chips and the brief: must have, nice to have, avoid. The parent answers, edits, approves, or taps "Just show me results." |

### Search (after the brief is approved, and on every refine)

| # | Step | Who | What it does |
|---|---|---|---|
| 6 | Search | Code | OpenSearch hybrid query: hard filters on location, grade and type, boosts per need, free text matched by keyword and vector. Returns about 100 candidates. |
| 7 | Evidence | Code | For each school and criterion: status, value, source type, date and citation. Sources include data, reviews, community posts and the school's own answers. |
| 8 | Score | Code | Match score from statuses and weights. Coverage computed separately. |
| 9 | Explain | LLM | Write card text from the evidence JSON. A validator drops any sentence that doesn't cite an evidence record. |
| 10 | Render | UI | Show the blocks the agent chose: message, brief, cards, grid, map, comparison, community threads. |

**Tools the agent can call on any turn:**

- **Ask the school:** adds the parent's question to the school's queue and its demand count.
- **Ask the community:** drafts a question for the school's thread. The parent approves it before it posts.
- **Cost estimator:** tuition minus likely scholarship, from a rules file with official links.
- **Saved list:** saved schools and the parent's open questions to schools and the community.

---

## Understanding the Request

The agent works like a planning step: understand first, agree on the plan, then act. It never interrogates. Questions only appear when the answers would change which schools come back.

**A thin request** gets questions and a brief before any results:

```text
You:    Looking for a middle school in Jacksonville. My son loves robotics
        and I work until 5. Money is tight.

Agent:  Two quick questions so I search for the right things:

        Is STEM a must-have or a nice-to-have?
        [Must-have]  [Nice-to-have]

        You work until 5. Does after-school care need to be at the school?
        [At the school]  [A nearby program is fine]

        [Just show me results]

        ┌ Here's what I'll look for ───────────────────────────────┐
        │ Must have     middle school · Jacksonville · STEM         │
        │               after-school care until 5:30                │
        │ Nice to have  low cost                                    │
        │ Avoid         —                                           │
        │                              [Looks right, search] [Edit] │
        └───────────────────────────────────────────────────────────┘
```

**A specific request** skips the questions. The brief appears at the top of the results in the same turn, and every item in it is an editable chip.

**"Just show me results"** uses each question's default, runs the search, and states the assumptions in the brief ("I assumed on-site care").

After the brief is approved, the parent keeps refining in conversation. Refining turns ask at most one question, and only when it would change the top results.

---

## Parent Community

Every school has a community page. It is part of the same app as the agent, not a separate site.

```text
Bayview Charter · Community                          [Ask a question]
──────────────────────────────────────────────────────────────────────
 Parents asked this month
   After-school care 14  ·  STEM 6  ·  Bus routes 3
──────────────────────────────────────────────────────────────────────
 ▲ 23   Does after-care run past 5:30?                  #after-care
        12 replies · ✓ School answered
 ▲ 17   How is the robotics club?                       #stem
        8 replies
 ▲  9   Our experience with the IEP process             #special-ed
        5 replies
                                                [Share your experience]
```

**What's in scope for the hackathon:** threads per school, replies, upvotes, and topic tags. Tags are the needs in `needs.yaml` (after-care, STEM, class size and so on), so the agent can find the right threads by school and need. When a parent writes a post, Haiku suggests tags and the parent confirms them.

**Out of scope:** direct messages, profiles, following, notifications and a moderation queue screen.

**Who's posting:** the vision rules out login, so a persona switcher stands in for accounts: Parent A, Parent B, and a staff member at one school. Posts from school staff carry a "Verified school" badge.

### How the agent and the community connect

| Direction | How |
|---|---|
| Agent → community | When the data can't answer a criterion, the card offers "Ask parents at this school" (a draft post the parent approves) next to "Ask the school." |
| Community → agent | The agent reads threads tagged with a criterion's need, the way it reads reviews. They can support a criterion, never confirm it. Cards link to them: "3 parents discussed after-care here." |
| Both → school | Questions from the agent and the community are counted by school, need and month. The school gets one digest email. It answers once, in its thread, and that answer becomes `school_reported` evidence, which turns the criterion Confirmed for every parent. |

### Demand counts

"14 parents asked about after-school care this month" shows on the school's community page and on the parent's card. It tells parents what others care about, and it tells the school what to answer first.

---

## Map View

Results can show on a map as well as in a list or grid. The map is part of the conversation: the agent chooses when to show it, and what the parent does on it becomes the next turn.

### What the parent sees

```text
┌ Chat ─────────────────────────┐ ┌ [List] [Grid] [Map] ──────────────────
│ You: Middle school in Jax     │ │
│ with STEM and after-care.     │ │      ①                ◆ STEM club
│                               │ │           ⌂ you
│ Agent: 6 schools fit your     │ │      ②          ③ ┄┄┄ ◆ after-school
│ brief. The 3 closest are      │ │                          program
│ north of the river.           │ │   ○ missed a must-have
│                               │ │
│ [Edit brief]                  │ │ ┌ ③ Bayview Charter · 78% · 2.1 mi
│                               │ │ │ STEM ✓   After-care ?   Cost ~
│ → You tapped ③                │ │ │ Program 0.4 mi away covers 3–6 pm
│                               │ │ │ 14 parents asked about after-care
│                               │ │ │ [Save] [Compare] [Ask the school]
└───────────────────────────────┘ └─────────────────────────────────────
```

*Sketch only; the school name is made up.*

- **Layout.** On a computer, chat on the left and a results panel on the right with List, Grid and Map tabs. On a phone, the map appears as a small card in the chat and opens full screen when tapped. Design for the phone first: many of the families this is for rely on one.
- **School pins** are numbered by rank, matching the list, and colored by match. Schools in "Missed a must-have" are hollow pins, so they stay visible.
- **Program pins** (◆) appear only when a program fills a gap at a school on the map, with a dashed line to that school.
- **"You" marker** is the parent's search point, from a zip code or a dropped pin. The parent can drag it. Distance rings show how far each school is.
- **Tapping a pin** opens a small card: match, distance, a status for each criterion, demand counts, and Save, Compare and Ask the school.
- **The agent says it in words too** ("the 3 closest are north of the river"), so screen readers and parents who don't read maps get the same information.

### Map events

What the parent does on the map is sent as a structured event, not text. The backend picks the route from the event and the session, with no LLM call. The chat logs each event ("You moved the search area to Arlington") so the history stays readable.

| Parent does | Event | Handled as |
|---|---|---|
| Taps a pin | `pin_selected` | School detail (P3) |
| Taps a hollow pin | `pin_selected` | School detail, leading with the must-have it missed |
| Selects two pins | `pins_compared` | Compare (P2) |
| Drags "you" or taps "Search this area" | `area_changed` | Refine: the location chip updates and the search reruns |

Chat, brief, list, grid and map all draw from the same session state, so a change in one shows in all of them.

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Models | Amazon Bedrock. A small, fast model (e.g. Claude Haiku) for routing, extraction and post tagging; a stronger one (e.g. Claude Sonnet) for explanations and comparisons. | Bedrock is required. The split keeps each turn fast. |
| Embeddings | A multilingual embedding model on Bedrock (Titan Text Embeddings V2 or Cohere Embed Multilingual; pick with the eval set) | Need matching, vector search, Spanish queries. |
| Search | Amazon OpenSearch Service, one small domain, hybrid keyword + vector query with a normalization search pipeline | Required, and it mirrors GreatSchools. |
| Backend | Python + FastAPI. Bedrock Converse API with tool use; Strands Agents optional. Community endpoints in the same app. | Tools are plain Python functions we can unit test. |
| State | DynamoDB: sessions, saved lists, feedback, community threads and posts, votes, question queue | Nothing to manage. |
| Safety | Bedrock Guardrails sensitive-information filter on every community post, through `ApplyGuardrail` | Blocks names and contact details before anything is published. |
| Email | Amazon SES in sandbox mode, for school digests | Delivers only to verified addresses, so it can't reach a real school. |
| Frontend | React + Vite + TypeScript on S3 + CloudFront | Renders typed blocks from the API, plus the community pages. |
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
- **Seed community posts:** threads and replies for the demo schools, written from the topics and tone of the 127 sample reviews, tagged with needs, with no names of students or staff. Include last month's questions so demand counts aren't empty.
- **`funding_rules.yaml`:** Florida scholarship programs (for example the Family Empowerment Scholarship and the Florida Tax Credit Scholarship). Fill rules and amounts from the official Florida Department of Education pages and keep the link beside each one.

### Indexing

Two indexes, `schools` and `programs`. Each document keeps its original fields and adds a `search_text` field (name, ESP text, profile values, recent review snippets) with its embedding. Both indexes map `latlon` as `geo_point` for distance filters and the map. The 40 or so needs stay in memory for matching; they don't need an index.

Community posts stay in DynamoDB, tagged with needs when they're written. The agent looks them up by school and need, so they don't need an index either.

---

## Shared Contracts

Agree on these six shapes in the first hour. Each track then builds against fixture files in these shapes until the real parts arrive.

### Criterion (output of Extract + Match needs)

```jsonc
{
  "id": "c3",
  "text": "after-school care",
  "need": "after_care",            // id in needs.yaml, or null if unmatched
  "strength": "require",           // require | prefer | avoid
  "params": { "until": "17:30" },
  "inferred_from": "I work until 5",  // set when the parent implied it rather than said it
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
```

The need IDs double as community topic tags. GreatSchools' team can add or change a need by editing this file. That is the handoff story for the README.

### Evidence record (output of Evidence)

```jsonc
{
  "school_id": "School fl-95390",
  "criterion_id": "c2",
  "status": "needs_attention",     // confirmed | partial | needs_attention | unknown
  "value": "large",
  "source": {
    "type": "state_data",          // state_data | school_reported | parent_reviews | community | computed
    "path": "class_size.tier",     // field path, review ID or post ID
    "as_of": "2026-07-15",
    "confidence": "high"
  },
  "note": "Classes are large compared with other elementary schools."
}
```

### API response (blocks the agent chooses)

A thin first request returns questions and a brief:

```jsonc
{
  "blocks": [
    { "type": "message", "text": "Two quick questions so I search for the right things:" },
    { "type": "questions", "skip_label": "Just show me results", "items": [
      { "id": "q1", "criterion_id": "c2", "text": "Is STEM a must-have or a nice-to-have?",
        "options": ["Must-have", "Nice-to-have"], "default": "Nice-to-have" },
      { "id": "q2", "criterion_id": "c3", "text": "Does after-school care need to be at the school?",
        "options": ["At the school", "A nearby program is fine"], "default": "At the school" } ] },
    { "type": "brief", "must": ["c1", "c2", "c3"], "nice": ["c4"], "avoid": [],
      "assumptions": [], "approved": false }
  ]
}
```

An approved brief returns results:

```jsonc
{
  "blocks": [
    { "type": "message", "text": "6 schools fit your brief. The 3 closest are north of the river." },
    { "type": "brief", "must": ["c1", "c2", "c3"], "nice": ["c4"], "avoid": [], "approved": true },
    { "type": "results", "schools": [{ "id": "…", "match": 0.78, "verified": "3 of 4",
      "demand": [{ "need": "after_care", "count": 14 }] }] },
    { "type": "evidence_grid", "schools": ["…", "…"], "criteria": ["c1", "c2", "c3"] },
    { "type": "map", "you": [30.32, -81.66],
      "schools": [{ "id": "…", "rank": 3, "match": 0.78, "missed_must_have": false }],
      "programs": [{ "id": "…", "fills": { "school": "…", "criterion": "c3" }, "miles": 0.4 }] }
  ]
}
// other block types: comparison, school_detail, definition, cost, community_threads, post_draft
```

### UI event (taps on questions, the brief and the map)

```jsonc
{
  "session_id": "…",
  "event": "pin_selected",          // answers_submitted | brief_approved | brief_edited | skip_to_results
                                    // | pin_selected | pins_compared | area_changed
  "school_ids": ["School fl-95390"],
  "answers": null,                  // answers_submitted: { "q1": "Must-have", "q2": "At the school" }
  "area": null                      // area_changed: { "center": [30.32, -81.66], "radius_mi": 5 }
}
```

Posting, replying and voting in the community go through plain REST endpoints, not agent turns.

### Community post

```jsonc
{
  "post_id": "p_123",
  "thread_id": "t_45",              // equals post_id for the opening post
  "school_id": "School fl-95390",
  "author": { "persona": "parent_a", "role": "parent" },   // role: parent | school (verified)
  "kind": "question",               // question | experience | reply | school_answer
  "needs": ["after_care"],          // tags from needs.yaml
  "text": "Does after-care run past 5:30?",
  "votes": 23,
  "origin": "agent",                // agent (drafted from a card) | community (written on the page)
  "created_at": "2026-11-03",
  "_synthetic": false
}
```

---

## Rules in Code

### Evidence status

| Status | When |
|---|---|
| ✅ **Confirmed** | Field present and meets the condition, source confidence high or medium, data less than 18 months old. Or the school answered in its thread. |
| 🟡 **Partial** | Meets the condition but confidence is "unknown" or data is older than 18 months; or only partly meets it (care until 5:00 when the parent needs 5:30); or supported only by reviews and community posts (2+ on the topic, mostly positive). |
| 🔴 **Needs attention** | Field present and fails the condition, or 3+ reviews or posts on the topic are mostly negative. |
| ⚪ **Unknown** | No field, and fewer than 2 reviews or posts on the topic. |

Reviews and posts older than five years count half. A program whose only sessions are in the past counts as stale.

### Scoring

```text
weight   = { require: 3, prefer: 1, avoid: 2 }        # avoid is scored inverted
value    = { confirmed: 1.0, partial: 0.6, unknown: 0.5, needs_attention: 0.0 }
match    = Σ weight × value / Σ weight
coverage = share of criteria that are confirmed or needs_attention   # shown, never multiplied in
```

Unknown scores 0.5, so missing data neither lifts nor buries a school. A require criterion with a high-confidence **Needs attention** moves the school to a "Missed a must-have" group under the results. It stays visible, and its detail view leads with the must-have it missed.

### Which questions to ask

Before the first search, check these in order and ask up to three:

1. Location or grade level is missing and not in the session.
2. A require criterion is ambiguous: run the search once per reading. If the top 10 overlap by less than 60%, ask.
3. Strength is unclear ("loves robotics" could be require or prefer) and the top 10 differ by reading.
4. A require criterion would be unknown for 30% or more of the top 10: ask whether it is a dealbreaker.
5. A phrase matches nothing (for example "how liberal"): offer related needs as chips, such as inclusion, cultural responsiveness, restorative discipline and non-religious.

If none apply, skip the questions and show the brief with results. Every question has a default, which "Just show me results" uses and the brief states. After the brief is approved, a refining turn asks at most one question, from rules 2 or 4.

### When to show the map

1. The parent asks for it or opens the Map tab.
2. A criterion is about place: "near me," "on my way to work," "within 15 minutes," or distance itself.
3. The top 10 results are spread over more than 10 miles.

Otherwise the agent shows the list and grid, and the Map tab stays one tap away.

- Pin color comes from the match score. Schools in "Missed a must-have" are hollow.
- A program pin appears only if it is within 1 mile of a school on the map and covers a criterion that is unknown or needs attention there. Programs whose only sessions are in the past don't appear.
- Distance is computed in code from `latlon` (straight line to start) and cited like any other evidence, with source type `computed`.

### Demand counts and digests

- Each question from "Ask the school," "Ask parents at this school," or a new question thread counts once per parent, per school, per need, per calendar month.
- The school's community page and the parent's card show the current month's counts, highest first.
- A digest groups each school's open questions by need, with counts and a link to answer in its thread. In the demo it goes out from a "Send digest" button.
- When the school answers a need in its thread, every open question on that need closes, and that criterion's evidence becomes `school_reported` with today's date.

### Community safety

- Every post and reply runs through the Bedrock Guardrails sensitive-information filter before it is published. Names, phone numbers, emails and addresses are blocked, and the parent is asked to rephrase.
- The agent drafts posts; it never publishes one without the parent's tap.
- Posts never confirm a criterion, and cards label them "Parents say."

---

## Milestones

Build in this order. Each stop point is a complete demo, so if time runs out we stop at the last one finished.

### D0 · Lead-time setup *(first hours)*

- Request Bedrock model access and create the OpenSearch domain; both can take a while.
- Verify each teammate's email in SES.
- Agree the six contracts and the demo city.
- Generate synthetic data and seed posts, and index the schools and programs.

### M1 · First end-to-end slice *(P1 core)*

- Search box, extraction, editable chips, search, evidence, scoring.
- Cards with a status, source and citation for every criterion.
- Save a school to a list.

**Stop point: demoable**

### M2 · Understands before it searches *(finishes P1)*

- Questions before the first search: up to three, skippable, with "Just show me results."
- The brief: must have, nice to have, avoid; editable; approved before results. Specific requests get the brief and results together.
- Inferred needs ("I work until 5").
- Vague requests such as "how liberal" turned into concrete chips.
- Thumbs up / down, with reason chips that refine the search.
- Map view: numbered pins colored by match, tap a pin for its card, a "you" marker from the parent's zip code.

**Stop point: meets every success criterion in the vision**

### M3 · Parent community

- School community pages: threads, replies, upvotes, need tags, persona switcher.
- Seed posts loaded.
- Guardrails check on every post.
- Community posts as evidence, linked from cards ("3 parents discussed after-care here").

**Stop point: the agent and the community work as one platform**

### M4 · Compare and explain *(P2–P4)*

- Evidence grid and two-school comparison with source labels.
- School detail view and term definitions ("What is CTE?").
- Review and post topics with counts, both sides and dates.
- On the map: select two pins to compare, tap a hollow pin for its detail, drag "you" or search this area to refine.

**Stop point: all four priorities done**

### M5 · Ask the school and show cost *(differentiators)*

- "Ask the school" and "Ask parents at this school" from any card.
- Demand counts on school pages and cards.
- Digest email through SES; the school answers in its thread with a verified badge, which turns the criterion Confirmed.
- Cost after likely scholarships for private schools.
- Program pins on the map, linked to the schools whose gaps they fill.

**Stop point: full demo script**

### M6 · Stretch *(only if M5 is done)*

- Spanish end to end.
- Bedrock Guardrails contextual grounding check as a second guard on explanations.
- Trade-off chart with what-if ("a 20-minute commute adds 3 schools").
- Drive-time areas on the map instead of straight-line distance.
- Digest on a daily schedule instead of a button.
- Notify the parent when a school answers or someone replies (Level 3 preview).
- Follow up on the parent's final choice and invite them to share their experience in the community.
- Suggest criteria from what other parents searched for, using structured criteria only, never chat text.

---

## Workstreams

Five tracks that can run in parallel once the contracts are agreed. With fewer people, merge A with C and B with D, and start E once M2 is done.

| Track | Owns |
|---|---|
| **A · Data and search** | Synthetic generator · Index mappings and indexer · Query builder from `needs.yaml` to OpenSearch · `funding_rules.yaml` with official links · `geo_point` mapping, distance filter and plausible coordinates |
| **B · Agent** | Router and extractor prompts and tool definitions · Need matcher with embeddings · Question, brief and explanation wording · Citation validator · Events from questions, brief and map · Evaluation runner |
| **C · Evidence and ranking** | `needs.yaml` and evidence rules · Review and post analysis with recency · Scorer and question rules · Cost estimator · When to show the map, pin rules, distance evidence |
| **D · Frontend** | Block renderer, chat, questions and brief · Result cards and evidence grid · Map view and phone layout · Saved list · Feedback controls |
| **E · Community** | Community pages, threads, replies, votes, need tags · Persona switcher · Seed posts · Guardrails check · Ask the school and ask the community, demand counts, SES digest, school answers |

---

## Demo Script

About seven minutes. Each step shows one thing from the vision's success criteria or one differentiator.

1. The parent types *"Looking for a middle school in Jacksonville. My son loves robotics and I work until 5. Money is tight."* The agent asks two quick questions with tap-to-answer chips: is STEM a must-have, and does after-school care need to be at the school. It asks because the answers change the top schools. "Just show me results" sits underneath.
2. The parent answers "Must-have" and "A nearby program is fine." The brief appears: *must have middle school, Jacksonville, STEM, after-school care until 5:30; nice to have low cost.* The parent didn't say 5:30; the agent inferred it from "I work until 5." The parent taps "Looks right."
3. Cards show Confirmed / Partial / Needs attention / Unknown for each criterion, with sources. One card has after-school care unknown, "14 parents asked about this," and an "Ask the school" button.
4. The parent opens the map. The agent says the three closest schools are north of the river. Next to the school with unknown after-care, a program pin 0.4 miles away covers 3–6 pm, with a dashed line to the school.
5. The parent asks *"How liberal are these schools?"* The agent says it doesn't rate schools on politics and offers chips it can back with data: inclusion, cultural responsiveness, restorative discipline, non-religious.
6. The parent opens a school's community page. The robotics club thread has 17 upvotes, and the card had linked it as "Parents say" evidence. The parent drafts a question that includes their son's name; the check catches it and asks them to rephrase.
7. The parent selects two pins and compares them. The evidence grid shows each answer's source and date. The private school shows likely cost after scholarship, with the official link.
8. The parent taps "Ask the school." The persona switches to the school: its page shows 15 parents asked about after-school care, and the digest has arrived in a teammate's inbox. The school answers in its thread. Back as the parent, the grid cell turns Confirmed, labeled school-reported with today's date.
9. The parent saves two schools. A thumbs-down with "too far" tightens the distance chip, and the map zooms in to match.

---

## Evaluation

A file of about 40 parent queries, each with the expected criteria, strengths, which questions (if any) should be asked, and whether the map should show. A second file of about 20 draft posts, some with names or contact details, checks the safety filter. Run both before every merge and put the latest numbers in the README. The targets are ours to adjust.

| Check | Target |
|---|---|
| Criteria found (recall) | 90%+ |
| Criteria correct (precision) | 85%+ |
| Require / prefer / avoid correct | 85%+ |
| Questions asked when needed and skipped when not | 80%+ |
| Show-map decision correct | 85%+ |
| Claims with a valid citation | 100%, required |
| Schools dropped for missing data | 0, required |
| Draft posts with personal info that get published | 0, required |
| Turn time, median | under 6 s |

Include the hard cases on purpose: "how liberal," a city name used in several states, Spanish queries, negations ("not religious"), vague ones ("a good school"), implied needs ("I work until 5"), and place phrases ("near my job," "on my way to work").

---

## Risks

| Risk | Plan |
|---|---|
| OpenSearch setup time and cost | Create it first. Smallest instance, one node. Delete it after the hackathon. |
| Model access not enabled | Request on day 0. The code takes model IDs from config, so we can switch to whatever is enabled. |
| Slow turns | Small model for routing and extraction. Run the per-reading searches in parallel. Stream the explanation. |
| Questions feel like a form | At most three, all skippable, only when the request is thin. Specific requests go straight to the brief with results. |
| Two products is too much scope | Finish M1 end to end before anything else. Keep the community thin: no messages, profiles or notifications. Stop points are the plan. |
| Empty community in the demo | Seed posts written from the sample reviews, marked synthetic, plus last month's questions for demand counts. |
| Personal information in posts | Guardrails filter on every post, drafts never auto-publish, and the eval set checks it. |
| Posts treated as fact | Posts support, never confirm. Cards label them "Parents say." |
| Claims not in the data | Citation validator drops uncited sentences. Grounding check in M6. |
| Wrong scholarship info | "You may qualify" wording, official link on every line, no promised amounts. |
| Emailing a real school | SES sandbox only delivers to verified addresses. School addresses in the data are synthetic. |
| Synthetic points look wrong on a map | The generator places schools and programs near real streets in the demo metro. Check every pin on the map before the demo. |
| Parent's location is sensitive | Keep only a zip code or a rounded point in the session. Never ask for a home address. |

---

## Open Questions

- [ ] **How long is the hackathon, and how many of us are there?** That decides which milestone we aim for and how the tracks merge.
- [ ] **How would a community fit GreatSchools' existing reviews?** They already have 850,000+ reviews and moderate them. Ask whether threads should sit beside reviews, replace them, or feed into them.
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
  mapping/                  need matcher (embeddings)
  search/                   query builder, OpenSearch client
  evidence/                 status rules, reviews and posts, scorer
  brief/                    question rules, overlap check, brief
  community/                threads, posts, votes, demand counts, digest (SES), safety check
  funding/                  cost estimator
  geo/                      distance, when to show the map, pin rules, zip lookup
  config/                   needs.yaml, funding_rules.yaml, models.yaml
data/
  sample/                   the 25 + 25 provided records, unchanged
  synthetic/                generator, seed community posts
  index/                    mappings, indexer
frontend/                   React + Vite: chat, questions and brief, cards, grid, map, community pages, saved list, persona switcher
eval/                       queries.jsonl, post_drafts.jsonl, run_eval.py
infra/                      optional CDK
README.md                   how to run, decisions, AWS services, eval results
```
