# Cost model

Prices looked up **2026-11-04** from AWS public pricing pages (US East / N. Virginia unless noted). Taxes and free-tier credits ignored. Marked **Assumption** where the repo does not measure usage.

## Unit prices (cited)

| Component | Unit price | Source |
| --- | --- | --- |
| Amazon Connect outbound voice (service) | **$0.018 / min** | [Amazon Connect pricing](https://aws.amazon.com/connect/pricing/) — Voice & video table |
| US outbound telephony | **$0.0048 / min** | Same page, worked examples (US destination) |
| US toll-free number (TFN) | **$0.06 / day** | Same page (outbound-campaigns example); DID alternative **$0.03 / day** |
| Amazon Lex V2 speech request | **$0.004 / request** | [Amazon Lex pricing](https://aws.amazon.com/lex/pricing/) |
| Amazon Polly Neural TTS | **$16 / 1M characters** | [Amazon Polly pricing](https://aws.amazon.com/polly/pricing/) |
| AWS Lambda request | **$0.20 / 1M requests** | [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/) |
| AWS Lambda duration (x86, first tier) | **$0.0000166667 / GB-second** | Same |
| Claude Haiku 5.5 (≤100k prompt) | **$0.10 / 1M input · $0.50 / 1M output** | [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing); Bedrock bills via Marketplace — confirm live rate on [Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) |
| Search turn (rules-first, Bedrock off) | **median 0.02 s** wall time | README evaluation table / `eval/run_eval.py` |

Voice stack in this app: Connect outbound + Lex V2 + Polly Neural "Joanna" + Lambda `GsVoiceTurn` (256 MB, 20 s timeout) + Bedrock Haiku (`backend/config/models.yaml`, `scripts/setup_voice.py`).

## Reference AI school call

**Assumption — call shape** (matches a short after-care ask; not a measured average):

| Piece | Assumed volume |
| --- | --- |
| Connected duration | **3.0 minutes** |
| School speech turns (Lex) | **6** |
| Agent spoken characters (Polly Neural) | **800** |
| Haiku turns (one Converse per school reply) | **6** × ~800 input + ~100 output tokens |
| Lambda invocations | **6** × ~1.0 s at 256 MB |

### Cost of that call

| Line item | Calc | USD |
| --- | --- | --- |
| Connect voice | 3 × $0.018 | 0.0540 |
| US outbound telephony | 3 × $0.0048 | 0.0144 |
| Lex speech | 6 × $0.004 | 0.0240 |
| Polly Neural | 800 / 1e6 × $16 | 0.0128 |
| Lambda duration | 6 × (0.25 GB × 1 s) × $0.0000166667 | ≈ 0.000025 |
| Lambda requests | 6 × $0.0000002 | ≈ 0.000001 |
| Bedrock Haiku 5.5 | 6 × (800 × $0.10 + 100 × $0.50) / 1e6 | ≈ 0.00078 |
| **Variable cost / call** | | **≈ $0.11** |

Toll-free day charge ($0.06) is shared across all calls that day (~$0.002 if 30 calls/day). Negligible per call at demo volume; include in monthly ops, not per-parent unit cost.

## Cost per parent served (shared question)

One call answers every parent who asked that `(school, need, month)`.

| Parents N | Cost / call | **Cost / parent** |
| --- | --- | --- |
| 1 | $0.11 | **$0.11** |
| 5 | $0.11 | **$0.022** |
| 13 (Beauclerc seed) | $0.11 | **$0.008** |

Versus **Assumption** $0 of AWS spend but **12 parent-minutes** each if every parent calls the office themselves (`docs/pitch/impact.md`).

## Cost per search turn (chat)

| Mode | What runs | Cost / turn |
| --- | --- | --- |
| Rules-first (default local / eval) | Extractor + evidence in process; no Bedrock | **~$0** variable + median **0.02 s** |
| Bedrock on (route + extract on Haiku) | **Assumption** ~1,500 in + 400 out tokens once | ≈ **$0.00035** at Haiku 5.5 rates |
| Plus Titan embed (256-d) when OpenSearch path is on | Titan V2 pricing on Bedrock page | small vs voice; cite Bedrock pricing at demo time |

Search is cheap on purpose: Unknown facts stay on the card; the expensive path is the **shared** school call, not every parent chat turn.

## Monthly sketch (demo scale)

**Assumption:** 100 AI school calls/month, 3 min each, one TFN.

| Item | Calc | USD / month |
| --- | --- | --- |
| Variable call stack | 100 × $0.11 | 11 |
| Toll-free number | 30 × $0.06 | 1.80 |
| Chat Haiku (Assumption 10k Bedrock turns) | 10k × $0.00035 | 3.50 |
| **Order of magnitude** | | **≈ $16** |

Fargate, OpenSearch, DynamoDB, and CloudFront dominate a full production bill; this sheet isolates the **AI call** and **search turn** unit costs judges ask about.
