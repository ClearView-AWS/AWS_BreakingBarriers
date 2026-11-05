# 3-minute demo script

**Live URL:** https://dvpvz48phigre.cloudfront.net  
**Backup:** local API + UI (README), or the 90-second video shot list at the bottom.

Total talk time: **3:00**. Leave ~15 s slack for judges' screens to load.

---

## 0:00–0:20 — Hook (Impact + Originality)

**Say:** "Parents don't lose schools because of bad ratings — they lose them because the fact they need isn't on the card, and calling every office during work hours is a second job. We investigate. You decide."

**Show:** landing / empty chat. No deep dive yet.

**Judges notice:** problem is equity + missing data, not another chatbot.

---

## 0:20–1:10 — Guided search (Technical + UI)

**Type exactly:**

```text
Middle school in Jacksonville with STEM and after-school care. Money is tight.
```

**Click / do:**

1. Answer or **skip** clarifying questions (≤3).
2. Approve the brief (or tap **Just show me results**).

**Say while it loads:** "Hard filters are only city, grade, type. Missing after-care never drops a school — Unknown scores 0.5 and stays on screen."

**Judges notice:**

- Brief they can edit.
- Cards with Confirmed / Partial / **Unknown** and citations.
- Beauclerc (or peer) shows after-care **Unknown**.
- Cost line says **You may qualify** with Florida links — no fake award amount.
- Median rules-engine turn in eval is **0.02 s** (mention; don't wait for a stopwatch).

---

## 1:10–1:40 — Community demand (Impact)

**Click:** open Beauclerc STEM Middle → community / ask path, or the card affordance **Ask parents** / demand chip.

**Say:** "Thirteen parents already asked Beauclerc about after-school care this month in our seed. Without us, that's thirteen phone calls."

**Judges notice:** demand count **13** on after_care (`community_seed.json`); one answer will serve all.

---

## 1:40–2:35 — Have AI call the school (Originality + AWS)

**Click:** **Have AI call Beauclerc** (button copy: questions not on file).

**Say over dial tone:** "Amazon Connect places the call. Polly Joanna speaks. Lex turns speech to text. Lambda asks Bedrock Haiku for the next line. The opening line discloses AI and asks Florida all-party consent before any question."

**Point at transcript panel** as lines stream.

**If the office answers (happy path):** after-care flips toward Confirmed with a **quote** from the school; mention parent_count on the panel.

**Judges notice:** live AWS voice path; consent; "model drafts, code decides" (card updates only after backend check).

### Backup if the live call fails (use immediately — do not debug live)

1. Say: "Sandbox numbers flake — here's the recorded path."
2. Open a **saved transcript** panel or pre-captured screenshot/video of a completed call (prepare before judging: one successful `CALLS` record or screen recording).
3. Click **refresh** / re-run search so the card shows the school-reported after-care value.
4. Continue to close.

SES inbox digest is a second backup: "Ask the school" without voice.

---

## 2:35–3:00 — Close (Impact + Feasibility)

**Optional 10 s:** type a Spanish line (e.g. need from `needs.yaml` Spanish phrases) or say Translate is on — UI follows the parent, no login.

**Say:** "One call, thirteen families. Sixty-eight percent of our need-bearing eval searches hit an Unknown in the top eight. GreatSchools already reaches on the order of forty million families a year — this is how the database fills itself where parents actually care. Happy to take questions."

**Stop talking.** Hand to Q&A (`docs/pitch/judge-qa.md`).

---

## Criterion map (what to emphasize)

| Criterion | Moment |
| --- | --- |
| Technical Capability & AWS | Connect → Lex → Lambda → Bedrock; Translate; Guardrails mention if asked |
| UI/UX & architecture | Brief, citations, Unknown kept on list, compare tray if time |
| Impact | 68% Unknown hit rate; 13 parents; hours saved; equity / language / no login |
| Originality & feasibility | Phone closes the data gap; rules-first cheap path; cost ~$0.11/call shared |

---

## 90-second fallback video — shot list

| :t | Shot | Audio / VO |
| --- | --- | --- |
| 0–8 | Title card: Guided Search · GreatSchools | "We investigate. You decide." |
| 8–25 | Screen: paste the Jacksonville STEM + after-care query → brief → results | "Plain language in; ranked schools out. Missing facts stay visible." |
| 25–40 | Zoom card: after-care **Unknown** + citation UI | "Filters would hide this school. We don't." |
| 40–55 | Community: **13 parents** asked Beauclerc after-care | "One question, thirteen families." |
| 55–80 | Call button → dialing → transcript → consent line → after-care Confirmed with quote | "Connect, Lex, Polly, Bedrock — one AI call updates every parent." |
| 80–90 | Map / saved list + end card with live URL | "Built on AWS. Live now." |

Record 1080p; burn in large captions; keep office audio optional (consent already on-screen).
