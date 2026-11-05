# 8-slide deck outline

Map each slide to hackathon criteria. Speakers: keep each slide ≤20 s except demo (slide 5).

| # | Slide title | One-line content | Criterion focus | Speaker cue |
| --- | --- | --- | --- | --- |
| 1 | **We investigate. You decide.** | Parent need vs filter maze; GS scale 150k+ profiles / ~40M family visits | Impact (hook) | Problem in one breath; logo + live URL in corner |
| 2 | **The gap is the product** | 68% of need-bearing eval searches show Unknown in top 8; after-care 25/25 missing on sample | Impact | Show impact_counts numbers; not a rare edge case |
| 3 | **Architecture on AWS** | Browser → CloudFront → Fargate API; Bedrock / OpenSearch / DynamoDB; Connect→Lex→Lambda phone loop | Technical Capability | Mermaid from `docs/how-it-works.md`; flags + local fallback |
| 4 | **UI that tells the truth** | Brief → ranked cards with Confirmed / Partial / Unknown + citations; Unknown never drops a school | UI/UX & architecture | Screenshot of Beauclerc Unknown after-care |
| 5 | **One call, every parent** | 13 Beauclerc after-care asks; Have AI call; consent → transcript → card updates for all | Originality + Technical | Live demo or 90 s video (`demo-script.md`) |
| 6 | **Responsible by default** | AI disclosure; Fla. § 934.03 consent; model drafts / code decides; Guardrails PII; no login | Originality / trust | Point at opening line + safety.py |
| 7 | **Feasible unit economics** | ~$0.11 / 3-min call; $0.008 / parent at N=13; search median 0.02 s rules-first | Feasibility + Impact | Table from `cost.md` |
| 8 | **Ask us anything** | Equity (Translate: ES, HT, PT, VI…); scale path; what's next | All / Q&A | Hand to `judge-qa.md` |

## Slide → criterion checklist

| Criterion | Primary slides |
| --- | --- |
| Technical Capability & AWS integration | 3, 5 |
| UI/UX & architecture | 4, 5 |
| Impact | 1, 2, 7, 8 |
| Originality & feasibility | 5, 6, 7 |

## Evidence appendix (not slides — leave-behind)

- `docs/pitch/impact.md` + `impact_counts.py`
- `docs/pitch/cost.md` (AWS pricing links dated 2026-11-04)
- `docs/pitch/responsible-ai.md`
- `docs/pitch/demo-script.md`
- `docs/how-it-works.md`, README eval table
