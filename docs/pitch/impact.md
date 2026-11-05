# Impact model

Numbers come from the repo unless marked **Assumption** or cited to a public source.
Re-run counts with: `.venv/bin/python docs/pitch/impact_counts.py`

## What parents hit today

On the 39 non-routing eval queries (`eval/queries.jsonl`), the app's own extractor + evidence engine show:

| Metric | Value | Source |
| --- | --- | --- |
| Searches with at least one need | 34 / 39 | `docs/pitch/impact_counts.py` |
| Those whose top-8 list shows ≥1 Unknown fact | **23 / 34 (68%)** | same |
| Need cells in the top 8 that are Unknown | **175 / 281 (62%)** | same |
| Mean schools with an Unknown per search (top 8) | **4.7** | same |
| Needs most often Unknown in those lists | high_performing, sports, small_classes, magnet, gifted… | same |

Corpus coverage (every need × every school on file):

| Corpus | Unknown share | Source |
| --- | --- | --- |
| GreatSchools sample (25 schools) | **769 / 1,025 (75%)** | `Sample Data/` via impact_counts |
| Synthetic Jacksonville (275 schools) | **9,061 / 11,275 (80%)** | `data/synthetic/` via impact_counts |
| After-care on the real sample | **25 / 25 Unknown** | same |

After-care is the demo gap: every GreatSchools sample school lacks it on file, so a filter-based search would hide or fail those schools; Guided Search keeps them on screen as Unknown.

## Shared questions (the 13-parent demo)

`data/synthetic/community_seed.json` groups parent asks by `(school, need, month)`:

| School | Need | Month | Parents |
| --- | --- | --- | --- |
| Beauclerc STEM Middle (`School fl-180019`) | after_care | 2026-11 | **13** |
| Cedar Landing Academy | low_cost | 2026-11 | 7 |
| Beauclerc STEM Middle | stem | 2026-11 | 6 |
| Mariner Elementary | after_care | 2026-11 | 5 |

One AI call (or one school-staff reply) answers every parent who asked that month. Without grouping, those are 13 separate office calls for the same after-care question.

## Parent-hours saved

**Assumption — time per parent call:** 12 minutes (dial, hold, ask one fact, write it down). Marked as assumption; not measured in this repo.

**Assumption — without Guided Search:** for each search that shows Unknown facts, a motivated parent tries **2** school offices (less than the 4.7 Unknown schools on screen; many parents stop earlier).

Per **1,000** parent searches (using the eval mix: 34/39 ≈ 87% have a need; 68% of those hit Unknown):

| Step | Calc | Result |
| --- | --- | --- |
| Searches with a need | 1,000 × 34/39 | ≈ 872 |
| Of those, hit ≥1 Unknown | 872 × 23/34 | ≈ 590 |
| Parent call attempts | 590 × 2 | ≈ 1,180 |
| Parent-hours (status quo) | 1,180 × 12 min | **≈ 236 hours / 1,000 searches** |

**With Guided Search (search path only, no call yet):** the card already shows Unknown instead of dropping the school, and cites the field — the parent stops guessing. Hours above are the *avoidable call load* if families chase those gaps by phone.

**Per school call that closes a shared question:**

| Parents asking (N) | Status-quo parent-minutes | One AI call answers all | Hours saved |
| --- | --- | --- | --- |
| 1 | 12 | replaces that 1 call | 0 parent-hours (shifts work to AI; parent still gets the fact) |
| 5 | 60 | 1 call | **1.0 hour** |
| 13 (Beauclerc demo) | 156 | 1 call | **2.6 hours** |

At Beauclerc's seed demand, **one successful call returns ~2.6 parent-hours** that would otherwise be spent on the same question.

## Scale to GreatSchools

| Fact | Figure | Source |
| --- | --- | --- |
| School profiles | **150,000+** public, charter, and private | [About GreatSchools](https://www.greatschools.org/gk/about/) |
| Annual reach | **~40M** families / ~half of U.S. K–12 households visit each year | Vision doc + AEI interview citing GreatSchools CEO; About page: "Nearly half of all K–12 households" |
| Community reviews | **850,000+** | `docs/Vision - Final - GreatSchools.md` |

**Assumption — searchable share:** if 1% of annual visits become a Guided Search with needs (400,000 searches/year), and the eval Unknown rate holds:

- ~236 parent-hours avoided call-chasing per 1,000 searches → **~94,000 parent-hours / year** before counting shared AI calls.
- If only 1 in 50 of those Unknown-hitting searches triggers a shared school call at average N=5 → 8,000 calls × 1.0 hour saved = **+8,000 parent-hours**, with each answer stored for later parents.

These scale lines are order-of-magnitude, not a forecast. The durable claim is structural: **one investigation fills a gap for every parent who asked, then for every parent after them.**

## Equity

| Barrier | What Guided Search does | Evidence in repo |
| --- | --- | --- |
| Language | Amazon Translate + Comprehend detect the parent's language and answer in it; UI strings follow | `backend/agent/translate.py`, `TRANSLATE_ENABLED`, `frontend/src/i18n.ts` |
| Florida-relevant languages | Spanish, Haitian Creole, Portuguese, Vietnamese (plus every other language Translate supports) | Task brief + AWS Translate; phrases in `needs.yaml` include Spanish |
| No login | Parent uses the product without an account; demo uses a "Viewing as" switcher | `docs/community.md`, README |
| Money / jargon | "You may qualify" scholarship links to official Florida pages; glossary for charter, lottery, ESA | `funding_rules.yaml`, `glossary.yaml` |
| Work-hour phone tax | AI calls the school office; transcript updates the card for every asker | `frontend/src/Call.tsx`, `backend/gaps/phone.py` |

Families with the least time and English lose the most under today's "phone each office yourself" model. Grouped calls and Translate shrink that gap without requiring an account.

## Bottom line for judges

1. **68%** of need-bearing eval searches surface an Unknown in the top 8 — the product is aimed at a common failure, not a rare edge.
2. **13 parents** already share Beauclerc after-care in the seed; one call serves all 13.
3. At GreatSchools' **150k+** profiles and **~40M** family visits/year, closing gaps once is how a national nonprofit compounds trust — "We investigate. You decide."
