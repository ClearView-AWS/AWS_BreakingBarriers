# Live-call backup: shot list

Record these on demo day, in office hours (09:00–15:30 ET, Mon–Fri), on the deployed build you'll pitch from. `call-backup.md` says when each one is used.

**Settings for every clip:** 1920×1080, 30 fps, browser zoom 125%, light theme, bookmarks bar hidden, notifications off. Burn in captions (large, bottom third). Record system audio and the phone's speaker on separate tracks, so the office side can be muted.

**Never visible:** the demo phone number, the AWS console account id, other tabs, Slack/Messages popups. Crop or blur in edit if one slips in.

---

## Clip A: full offline demo (`call-backup-full.mp4`, 90 s)

This covers slide 4 through slide 5 if the network is gone.

| :t | Shot | On screen | Caption / VO |
| --- | --- | --- | --- |
| 0–5 | Title card | "Guided Search · GreatSchools" + live URL | "We investigate. You decide." |
| 5–20 | Browser, empty chat | Type: `Middle school in Jacksonville with STEM and after-school care. Money is tight.` | "Plain language in." |
| 20–28 | Brief | Skip questions → **Just show me results** | "Up to three questions, all skippable." |
| 28–40 | Results | Zoom on Beauclerc STEM Middle: after-care **Unknown**, citations | "Missing facts stay visible. Filters would hide this school." |
| 40–48 | Community demand | 13 parents asked about after-care | "Thirteen parents asked the same question." |
| 48–75 | Call | Click **Have AI call Beauclerc** → Calling… → transcript streams → consent line → answer | "Amazon Connect places the call. It says it's an AI and asks consent first." |
| 75–85 | Card update | After-care off Unknown, with the office quote | "Code checks the answer, then every parent sees it." |
| 85–90 | End card | Live URL + "Connect · Lex · Polly · Bedrock" | "One call, thirteen families." |

---

## Clip B: the call only (`call-backup-call.mp4`, about 60 s)

The usual backup. Start recording **after** the results are on screen, with Beauclerc's card in view.

| :t | Shot | On screen | Notes |
| --- | --- | --- | --- |
| 0–3 | Card, button visible | "📞 Have AI call Beauclerc STEM Middle · N questions not on file" | Hold 2 s before clicking |
| 3–8 | Click | Panel: "Calling Beauclerc STEM Middle…", "Asking for 13 parents" | |
| 8–15 | Phone rings | Picture-in-picture of the phone screen (number cropped) **or** caption "Office phone rings" | Answer on the 2nd ring |
| 15–25 | Opening line | Transcript shows the AI disclosure and consent question | Caption: "Discloses AI · asks to transcribe (Fla. § 934.03)" |
| 25–30 | Consent | Office: "Yes, that's fine." | |
| 30–50 | Questions | AI asks about after-school care; office answers with a time | Script below |
| 50–55 | Close | AI thanks, hangs up → "Call finished" | |
| 55–60 | Learned | "What the school said" + "Updated this school's card." | Hold 3 s |

### Office script (the person on the demo phone reads this)

Keep it short and clear, so Lex transcribes it on the first try and the parser finds a time.

| AI asks | Office says |
| --- | --- |
| Consent question | "Yes, that's fine." |
| After-school care | "Yes, we have after-school care every school day until 6 pm." |
| Any other open question | "I'm not sure, please email the front office." |
| Anything else? | "No, that's all. Thanks." |

Speak slowly. No "um"s before the time. Say "six p m", not "six-ish".

---

## Stills

| # | File | Shot | Use |
| --- | --- | --- | --- |
| 1 | `call-backup-before.png` | Beauclerc card, after-care **Unknown**, call button visible | Slide 5 background if the browser is down |
| 2 | `call-backup-transcript.png` | Call panel mid-call: opening line + consent + first answer | Q&A: "show me the consent line" |
| 3 | `call-backup-after.png` | Beauclerc card after refresh: after-care with the office quote | Tier B/C finish |

---

## After recording

- [ ] Watch each clip once at full screen: captions readable from 5 m away, no phone number visible.
- [ ] Copy clips + stills to the presenter laptop desktop **and** a USB stick.
- [ ] Open Clip B in QuickTime, paused at frame 0, before walking up.
- [ ] Do **not** commit the media to the repo (size; the phone screen may show private info).
- [ ] Reset state before the live pitch: recording placed a call to Beauclerc, and the 7-day rule will block the next one (`rehearsal-checklist.md` → Reset).
