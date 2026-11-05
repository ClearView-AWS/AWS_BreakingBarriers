# Person E: Front-office voice + Closer

**Clock:** answer the handset during D's beat (~4:30–5:30), then close 6:25–7:40 (1:15 · ~150 words)  
**You:** Hold the demo phone on speaker, near the mic. After the call, step to center.

---

## Part 1: Be the school office (on the call)

Short, clear, a little slow so Lex catches every word. Wait for the AI to finish each line.

| AI says | You say |
| --- | --- |
| *Phone rings* | "Front office, this is Dana." |
| "…Is it okay if I transcribe this call?" | "Yes, that's fine." |
| Asks about after-school care | "Yes, we have after-school care on campus until six p.m. every school day." |
| "Anything else?" / thanks | "No, that's all. Have a good day." |

Say **"six p.m."** exactly. The code reads that time itself, so don't improvise a different number.

If the AI mishears, repeat the same sentence once. Don't change the wording.

---

## Part 2: Close (word-for-word)

That call cost a parent nothing and took about a minute.

Here's what we measured. Sixty-eight percent of need-based searches hit an Unknown. After-care is missing for every Washington school in the state data. And across our eval, missing data dropped zero schools.

At list AWS prices, a three-minute call works out to about eleven cents. Connect, Lex, Polly, Lambda, and Haiku together. One answer then serves every parent who asks after it. So the more parents ask, the less each answer costs.

This isn't a prototype that only works on fake data. It runs on twenty-three hundred real Washington schools, it's deployed on AWS right now, and every service has a fallback.

GreatSchools already has the families and the trust. Guided Search gives them a way to fill the gaps parents care about, one call at a time.

We investigate. You decide.

Thank you. We'd love your questions.

---

## Stage notes

- **Stop talking** after "questions". Don't fill the silence. Q&A answers live in [`../judge-qa.md`](../judge-qa.md).
- If the clock reads past **7:30** when you start, skip the "This isn't a prototype" paragraph.

## Where the numbers come from

| Line | Source |
| --- | --- |
| ~$0.11 / 3-min call | `docs/pitch/cost.md`. AWS list prices as of 2026-11-04 on a modeled call shape, so it's priced, not billed |
| 68%, 0 dropped | `impact_counts.py`; README → Evaluation |
| 2,364 WA schools | `data/wa/schools.json` |
