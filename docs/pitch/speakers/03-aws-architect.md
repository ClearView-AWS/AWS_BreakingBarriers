# Person C — AWS architect

**Clock:** 3:25–4:25 (~1:00 · ~140 words)  
**You:** Talk over the **still-visible** results. Optional: flip to a one-slide architecture if the deck is up; otherwise stay on the live UI.  
**Do not** take the mouse unless B offers it.

---

## Say (word-for-word)

What you’re looking at is not a single chat API with a pretty skin.

The browser hits CloudFront, then an API on Fargate. Search can use OpenSearch when it’s on; sessions and overlays land in DynamoDB. Bedrock drafts extraction and card prose — behind flags — and the rules engine always has a local fallback so an empty sandbox still runs.

Translate and Comprehend follow the parent’s language with no login. Community posts pass Bedrock Guardrails for PII before they publish.

The piece judges remember is the voice loop: Amazon Connect places the call, Polly speaks, Lex turns speech to text, Lambda asks Bedrock for the next line — and our backend checks every answer before a card flips.

Model drafts. Code decides.

Call lead — show them the phone.

---

## Stage notes

- Keep this under a minute. Cut the Translate sentence first if you’re long.
- Do not deep-dive IAM or CDK unless a judge asks in Q&A.
