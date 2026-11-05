# Live-call backup pack (8-minute pitch)

The live AI call is the riskiest 90 seconds of the pitch. This page says when to stop waiting on it, what to show instead, and what to say so the switch sounds planned.

Related: `demo-script.md` (3-minute cut), `call-backup-shotlist.md` (the recording to make), `rehearsal-checklist.md` (the run-through before judging).

---

## Where the call sits in 8 minutes

| Time | Segment | Live dependency |
| --- | --- | --- |
| 0:00–0:45 | Hook + problem (slides 1–2) | none |
| 0:45–1:30 | Architecture (slide 3) | none |
| 1:30–3:15 | Guided search on the live URL (slide 4 → browser) | CloudFront, Fargate, Bedrock |
| 3:15–3:45 | Community demand: 13 parents asked Beauclerc about after-care | DynamoDB state |
| **3:45–5:15** | **Have AI call Beauclerc** (slide 5) | **Connect, Lex, Lambda, Bedrock, the demo phone** |
| 5:15–6:00 | Card updates for every parent | the call finished with an answer |
| 6:00–6:45 | Responsible AI (slide 6) | none |
| 6:45–7:30 | Unit economics (slide 7) | none |
| 7:30–8:00 | Close (slide 8) | none |

The call segment has 90 seconds. A clean call takes about 60. That leaves 30 seconds of slack, and no more.

---

## Decision rule: when to switch

Switch to the backup **at the first of these**. Do not retry the call on stage.

| Signal | When you see it | Switch to |
| --- | --- | --- |
| Panel shows anything other than "Calling Beauclerc STEM Middle…" after you click | 0–3 s | **B** (recording) |
| Panel says "Phone calls are off in this build" or "We emailed the questions instead" | 0–3 s | **B** |
| Panel shows a raw `call.blocked` label or does not change at all | 0–5 s | **B** (see below) |
| Phone has not rung | 15 s after click | **B** |
| Phone rang, no AI voice after you answer | 8 s after pickup | hang up → **B** |
| Transcript panel stays empty while the AI is talking | 20 s into the call | let it finish → **C** if the card does not update |
| Call ended, card still shows after-care **Unknown** | 5 s after "Call finished" | **C** |
| Clock reads 5:15 and the call is still running | 5:15 | narrate over it, move on; card update is optional |
| Venue Wi-Fi drops (live URL will not load) | any time | **A** for the whole demo |

`blocked` is the API refusing to dial (outside office hours, already called Beauclerc within 7 days, or the daily cap). The panel has no label for it, so it looks frozen. Rehearsal should prevent it; see `rehearsal-checklist.md`.

---

## Backup tiers

### A. Full offline video (worst case: no network)

- File: `call-backup-full.mp4` on the presenter laptop desktop **and** a USB stick. 90 seconds, captioned. Shot list: `call-backup-shotlist.md` → Clip A.
- Play it from slide 4 to the end of slide 5, then go back to slides. Narrate over it; the audio track is optional.

### B. Call recording only (the usual failure)

- File: `call-backup-call.mp4`, about 60 seconds. Shot list: `call-backup-shotlist.md` → Clip B.
- Keep it open in a second browser tab or QuickTime window behind the browser. One switch (`Cmd+Tab`) and press play.
- After it plays, go back to the live browser and re-run the search, or show the after-state screenshot (`call-backup-after.png`) if the card did not update.

### C. Card update without voice (call ran, no answer reached the card)

The staff-answer endpoint writes through the same overlay path as a call answer. Run it from a terminal you prepared before the pitch:

```bash
# Question id comes from GET /api/schools/<beauclerc id>/questions (look up during rehearsal).
curl -s -X POST "$DEMO_URL/api/schools/$BEAUCLERC_ID/questions/$AFTER_CARE_QID/answer" \
  -H 'Content-Type: application/json' \
  -d '{"text": "Yes, after-school care runs until 6 pm every school day."}'
```

Then re-run the search in the browser. After-care moves off Unknown, with the office quote.

Say this honestly: "That's the school-staff reply path. Same check, same card update; a call or a staff email both land here." Do not call it the phone answer.

---

## What to say

Say one of these lines word for word, then keep going. Don't apologize more than once, and don't explain the cause.

**Switching to B (no ring, or the panel failed):**
> "Sandbox phone numbers flake under event Wi-Fi, so here is the same call we recorded this morning on this build."

**Switching mid-call (rang, then went wrong):**
> "I'll let that one go. Here is a full run of the same call."

**Switching to C (call ran, card did not update):**
> "The answer didn't pass our check, so the card stays Unknown. That's the rule working: code decides, not the model. Here's a staff reply going through the same check."

**Switching to A (network gone):**
> "The venue network is down, so I'll walk you through a recording of the live build. The URL on the slide works afterward."

**If a judge asks "was that real?":**
> "The recording is a real Connect call to our verified demo phone, from this build, today. Happy to place one live after the session."

---

## While the backup plays: points to say

Spread these over the 60 seconds. They're the same points the live call would make.

1. "Amazon Connect places the call from our toll-free number. The only destination it can reach is one verified number."
2. "The first thing it says is that it's an AI, and it asks to transcribe. Florida needs consent from everyone on the call." (Point at the opening line.)
3. "Lex turns the office's speech into text. Lambda asks Bedrock Haiku for the next line."
4. "At most three questions per call. It calls only in office hours, and never the same school twice in a week." (`backend/config/calls.yaml`)
5. "The model drafts the answer. Code checks it before the card changes." (`backend/gaps/phone.py`)
6. "One call, thirteen families. About eleven cents."

---

## Assets to have open before you walk up

| Asset | Where | Made from |
| --- | --- | --- |
| `call-backup-full.mp4` | desktop + USB | shot list Clip A |
| `call-backup-call.mp4` | desktop, open paused in QuickTime | shot list Clip B |
| `call-backup-after.png` | desktop | shot list Still 3 |
| Terminal with tier C `curl` filled in | second desktop / Space | rehearsal checklist |
| Demo phone, charged, ringer on, Do Not Disturb off | in the speaker's hand | rehearsal checklist |

The demo phone number never goes on a slide, in the recording, or in this repo. It is set only as `VOICE_VERIFIED_TO` on the API.
