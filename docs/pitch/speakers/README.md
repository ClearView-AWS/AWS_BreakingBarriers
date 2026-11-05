# 8-minute pitch: five speakers

**Live demo:** https://dvpvz48phigre.cloudfront.net  
**Total:** 8:00. Finish speaking by **7:40** and keep 20 s for load lag before Q&A.  
**Pace:** scripts are timed at ~140 wpm, including click time and ~60 s of live call audio.  
**One mouse:** B drives until 3:00, then hands the laptop to D. Nobody else touches it.

| # | Role | File | Clock | Spoken words | Criterion |
| --- | --- | --- | --- | ---: | --- |
| A | Host / Impact | [01-host-impact.md](./01-host-impact.md) | 0:00–1:05 | ~150 | Impact |
| B | Demo driver | [02-demo-driver.md](./02-demo-driver.md) | 1:05–3:00 | ~165 + ~35 s clicks | UI/UX + Technical |
| C | AWS architect | [03-aws-architect.md](./03-aws-architect.md) | 3:00–4:10 | ~160 | Technical + AWS |
| D | Call lead | [04-call-lead.md](./04-call-lead.md) | 4:10–6:25 | ~160 + ~60 s call audio | Originality + AWS |
| E | Front office + Closer | [05-closer.md](./05-closer.md) | handset in D's beat; close 6:25–7:40 | ~30 + ~150 | Feasibility + Impact |
| — | Buffer → Q&A | [../judge-qa.md](../judge-qa.md) | 7:40–8:00 | — | — |

Print [cue-sheet.md](./cue-sheet.md) for the stage. [spanish-beat.md](./spanish-beat.md) is optional and off by default.

## The demo in one line

Seattle search (gifted + after-school care) → after-care shows **Unknown** but the school stays on the list → **📞 Have AI call** → E answers the demo handset as the front office → the card updates with the school's quote.

First chip (B):

```text
Middle school in Seattle that must have a gifted program and after-school care. Prefer a small school.
```

Backup call (D), only if the Seattle call fails:

```text
Middle school in Jacksonville with STEM and after-school care. Money is tight.
```

→ Beauclerc STEM Middle → **Have AI call** ("Asking for 13 parents", seeded demo data).

## Numbers we say on stage

These are measured or cited. Nothing projected. Don't add others.

| Claim | Value | Source |
| --- | --- | --- |
| GreatSchools reach | ~40M families/yr, 150k+ profiles | [About GreatSchools](https://www.greatschools.org/gk/about/) |
| Need-searches with an Unknown in the top 8 | 68% (23/34) | `docs/pitch/impact_counts.py` |
| After-care on the GreatSchools sample | 25/25 Unknown | same |
| WA schools loaded / with after-care on file | 2,364 / 0 | `data/wa/schools.json` (OSPI Report Card) |
| Schools dropped for missing data | 0 | README → Evaluation |
| Rules-path median first turn | 0.01 s | README → Evaluation |
| Holdout recall, Bedrock on (never tuned) | 97% (96/99) | README → Evaluation |
| AI call cost, 3 min | ≈ $0.11 at AWS list price | `docs/pitch/cost.md` (priced call shape, not a bill) |
| Parents on Beauclerc after-care | 13 | `data/synthetic/community_seed.json`. **Seeded**, so always say "in our seeded demo data" |

**Don't say on stage:** the parent-hours, 94k-hours/year, or "1% of visits" lines from `impact.md`. Those are assumptions, and Q&A only covers them if a judge asks.

## Honesty lines (keep them in)

- The call rings **our demo handset, never a real school** (`backend/gaps/phone.py`). D says so out loud.
- Jacksonville is **synthetic**. Seattle is **real public data**.
- $0.11 is **priced**, not measured from a bill.

## Stage rules

1. One voice at a time. Everyone else stays still and quiet.
2. If you're running long, cut from the kill list on the cue sheet. Don't speed up.
3. Never debug live. A failure means you go to the backup line within 5 seconds.
4. B hard-refreshes once before walking on. D runs one test call within the hour before.

## Rehearsal

Do two full runs with a phone timer and a real call each time. Write each speaker's actual split on the cue sheet. If someone is out, keep the **clock** and hand their file to someone else.
