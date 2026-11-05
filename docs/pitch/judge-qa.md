# Judge Q&A (15 hard questions)

Crisp answers. Cite repo or public sources; mark assumptions.

---

**1. How do you scale beyond Jacksonville?**  
Hard filters are city / grade / type; needs and evidence rules live in YAML. Swap the corpus and OpenSearch index for another metro. GreatSchools already has **150k+** profiles nationally ([About](https://www.greatschools.org/gk/about/)). Voice stays the same AWS pattern per region.

**2. What's real vs synthetic?**  
**25** GreatSchools sample schools in `Sample Data/` plus **275** synthetic Jacksonville schools, programs, and pages (`data/synthetic/`). Community demand (13 Beauclerc asks) is seeded and labeled `_synthetic: true`. Architecture and AWS wiring are real; national production data is not in this sandbox.

**3. What stops hallucinations on a school card?**  
Models draft; **code decides**. Evidence status is computed in `backend/evidence/`. Phone answers pass `backend/gaps/phone.py` before a card changes. Reviews and parent posts never Confirm. Failed Bedrock parses fall back to the rules engine.

**4. What if a school pushes back or refuses the call?**  
Opening line asks transcription consent. Decline / busy → thank them, offer email follow-up, end (`lex_turn.py`). SES digest and community staff reply are non-voice paths. We do not invent answers when consent is refused.

**5. Isn't calling schools with AI illegal in Florida?**  
**Not legal advice.** Fla. Stat. § 934.03 requires **all-party consent** to intercept — we disclose AI and ask before continuing. Calls are informational to a verified school business line, not telemarketing; TCPA/marketing rules still need production counsel. Demo: one `VOICE_VERIFIED_TO` number only. Details: `docs/pitch/responsible-ai.md`.

**6. What does a call cost?**  
About **$0.11** variable for a 3-minute reference call (Connect + US outbound + Lex + Polly Neural + Lambda + Haiku). At **N=13** parents: **~$0.008 / parent**. Sources: `docs/pitch/cost.md` + AWS pricing pages (as of 2026-11-04).

**7. What about latency?**  
Rules-first eval median turn **0.02 s** (README). Live Bedrock adds model time but stays under the plan's 6 s target for thin turns. The phone path is async: UI polls the transcript while Connect runs.

**8. Why AWS instead of a single LLM API?**  
We need **telephony** (Connect), **speech** (Lex/Polly), **translation**, **Guardrails**, **OpenSearch**, **DynamoDB**, and IAM-deployed infra in one account — not only chat completions. Every feature is flag-gated with a local fallback for the empty sandbox.

**9. How often is data actually missing?**  
On eval need-searches: **68%** show ≥1 Unknown in the top 8; **62%** of need cells there are Unknown. After-care is **25/25 Unknown** on the GreatSchools sample. Script: `docs/pitch/impact_counts.py`.

**10. Does this replace GreatSchools ratings?**  
No. Ratings and profiles stay. We add investigation: keep unknowns visible, cite sources, and close gaps parents already asked about. Mission fit: move from search to explore ("We investigate. You decide.").

**11. How do non-English speakers use it?**  
`TRANSLATE_ENABLED`: Comprehend detects language; Translate carries the pipeline in English and returns UI/chat in the parent's language. Florida-relevant: Spanish, Haitian Creole, Portuguese, Vietnamese (and others Translate supports). No login required.

**12. What's next after the hackathon?**  
Real GS corpus + identity; transcript retention TTL; multi-number voice with counsel-approved compliance; school opt-in portal; AgentCore gateway tools already sketched for partner agents; proactive Level-3 nudges only after Level-2 trust.

**13. How do you measure quality?**  
`eval/queries.jsonl` (42 queries): extractor precision/recall, require/prefer/avoid, ask-or-not, citation validity, **0 schools dropped for missing data**, median turn time. Community PII eval on `post_drafts.jsonl`. pytest suite on backend.

**14. What if Bedrock is down?**  
Flags off → rules extractor, hash embedder, local hybrid search, JSON state. Same UX path with less fluent prose. Phone Lambda needs Bedrock; without it, fall back to SES / community staff answer.

**15. Why is this original?**  
School search products filter on what's on file. We **keep the gap on screen and go get the answer**, then share it across every parent who asked. We know of no other school-search product that closes its own data gaps with a consented AI office call.
