# Parent community (Track E, milestone M4)

Every school gets a community page inside the same app: threads, replies, upvotes and need tags. It connects to the agent in three places.

| Direction | What happens |
|---|---|
| Agent to community | A card row with an unknown fact shows "Ask parents at this school" next to "Ask the school". It opens the school's page with a drafted question. Nothing posts until the parent taps Post. |
| Community to agent | Posts tagged with a need count as evidence. 2+ mostly positive posts turn Unknown into Partial ("Parents say", low confidence). 3+ mostly negative posts turn it into Needs attention. Posts never confirm, and they never move a school into "Missed a must-have". Cards link to the threads: "4 parents discussed after-school care here". |
| Both to school | Questions from "Ask the school", "Ask parents" and new question threads are counted once per parent, per school, per need, per month. Staff send one digest and answer once in the thread. The answer has a Verified school badge, closes the open inbox questions on that need, and becomes `school_reported` evidence, so the criterion turns Confirmed for every parent. |

## Safety

Every post and reply goes through `backend/community/safety.py` before it is saved:

1. Local rules always run: names in the common ways parents write them ("my son Ethan", "Mr. Lopez", "Leo is in 6th grade"), emails, phone numbers, street addresses.
2. Bedrock Guardrails `ApplyGuardrail` runs too when `BEDROCK_ENABLED=1` and `BEDROCK_GUARDRAIL_ID` are set. Create the guardrail with `bash scripts/create_guardrail.sh` after logging in to the sandbox.

A blocked post is never saved. The parent sees what was found and is asked to rephrase. `eval/post_drafts.jsonl` holds 20 drafts (10 with personal info). `python eval/run_eval.py` reports how many would be published. The target is 0.

## Who is posting

The vision rules out login, so a "Viewing as" switcher in the header stands in for accounts: Parent A, Parent B, and School staff. Staff can answer any school's threads in the demo. Time needs (after-school care, extended day, before care) take an end time. Other needs take "we offer it" or "we don't".

## Seed data

`python data/synthetic/generate_community.py` writes `data/synthetic/community_seed.json`: 31 posts on 7 demo schools plus last month's and this month's demand counts. Every seed record has `_synthetic: true` and shows "sample post" in the UI. After you regenerate it, delete `data/runtime/state.json` so the app loads the new seed.

Demo schools:
- **Beauclerc STEM Middle**: after-school care is unknown. 13 parents asked this month, so one more ask shows 14. Robotics thread with 17 upvotes.
- **Cedar Landing Academy**: parents say after-care is good, so it shows Partial (Parents say) until the school answers.
- **Mariner Elementary**: three negative posts about substitutes.

## Files

| Piece | Where |
|---|---|
| Threads, votes, demand, digest, school answers | `backend/community/service.py` |
| Personal-info check | `backend/community/safety.py` |
| Need tags and stance | `backend/community/tags.py` |
| Posts as evidence | `backend/community/evidence.py` (called from `pipeline._score_school`) |
| REST endpoints | `backend/app.py`, under `/api/community/...` |
| UI | `frontend/src/Community.tsx` |
| Tests | `backend/tests/test_community.py` |

## Endpoints

```
GET  /api/community/personas
GET  /api/community/schools/{school_id}?sort=top|new&need=after_care&persona=parent_a
GET  /api/community/threads/{thread_id}
POST /api/community/posts                      {school_id, persona, kind, text, needs, origin, session_id}
POST /api/community/threads/{thread_id}/replies {persona, text, answer?: {need, value} | {need, offers}}
POST /api/community/posts/{post_id}/vote       {persona}
POST /api/community/suggest-tags               {text}
POST /api/community/draft                      {school_id, need}
POST /api/community/schools/{school_id}/digest
```

## Not built yet

- A Haiku call for tags and stance. A word list stands in (`tags.py`).
- DynamoDB tables. The JSON state file stands in, like the rest of the app.
- Moderation screen, profiles, direct messages, notifications. These are out of scope in the plan.
