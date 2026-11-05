# Responsible AI

Not legal advice. Demo practices and the statutes we designed against.

## AI disclosure on every school call

Before any question, Connect plays the opening line from `backend/gaps/phone.py`:

> Hi, this is an automated AI assistant calling on behalf of families who use GreatSchools. I have {N} question(s) about {school}. Is it okay if I transcribe this call?

The Lex turn handler (`backend/voice/lex_turn.py`) treats consent as a first-class field. If the office declines, is busy, or asks to stop, the model thanks them, says families will follow up by email, and ends — no invented answers.

## All-party consent (Florida)

Florida Statute **§ 934.03(2)(d)** makes interception lawful when **all parties** have given prior consent ([Florida Senate](https://www.flsenate.gov/Laws/Statutes/2025/934.03)). Florida is an all-party consent state for call recording/transcription.

**What we do:** ask explicitly before continuing; do not keep a usable transcript path if consent is refused; store transcripts under the call record for the product purpose only.

## TCPA and school business lines

**Not legal advice.** The Telephone Consumer Protection Act (TCPA) and Florida's telemarketing rules focus on marketing / sales calls, especially to wireless numbers, often requiring prior express (sometimes written) consent for autodialed or prerecorded *telemarketing*.

Our calls are:

- **Informational** — asking a school office for a fact parents already requested (hours, programs), not selling a product.
- Aimed at a **school business / front-office line** that the demo configures via `VOICE_VERIFIED_TO` (one verified number only).
- Prefaced with **AI disclosure + transcription consent**.

That is a different purpose from telemarketing, but it is **not** a blanket exemption: wireless numbers, autodialer definitions, and state mini-TCPA rules still matter. Production would need counsel review, number verification, and opt-out / do-not-call handling. The hackathon demo stays on one verified line for that reason.

## "Model drafts, code decides"

| Layer | Trust |
| --- | --- |
| Bedrock (Haiku / Sonnet) | Untrusted draft: route, extract, phone lines, summaries |
| Rules + YAML (`needs.yaml`, evidence engine) | Authoritative match / Confirmed / Partial / Unknown |
| `backend/gaps/phone.py` | Call answers change a card **only after code checks** them |
| Reviews / community posts | Can support Partial; **never Confirm** a need |

A fluent wrong answer cannot silently become a Confirmed fact.

## PII guardrails

Community posts and replies (`backend/community/safety.py`):

1. Local rules always: names in common parent phrasing, emails, phones, street addresses.
2. Bedrock Guardrails `ApplyGuardrail` when `BEDROCK_ENABLED=1` and `BEDROCK_GUARDRAIL_ID` are set.

Blocked text is never saved. Eval target: 0 publishable drafts with personal info (`eval/post_drafts.jsonl`).

No login in product vision — less account PII by default; the demo "Viewing as" switcher is not production identity.

## Data retention (demo / design)

| Data | Where | Intent |
| --- | --- | --- |
| Sessions, inbox, answers | DynamoDB (or `data/runtime/state.json` locally) | Product state |
| Call transcripts | DynamoDB `pk=CALLS` | Show parents what was said; audit consent |
| Community posts | Same state store | School page; PII-scrubbed at write |

**Assumption for production:** retain call transcripts only as long as needed for the answer + dispute window, then delete or anonymize; do not train public models on school-office audio. Hackathon build does not implement automated TTL — flag for post-hackathon hardening.

## Judge one-liner

We disclose AI, ask Florida-required consent, keep models off the write path for facts, strip PII from community posts, and call only a verified school line for information parents already asked.
