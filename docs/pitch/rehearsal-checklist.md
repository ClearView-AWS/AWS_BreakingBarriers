# Rehearsal checklist (8-minute pitch)

Run this top to bottom on demo day. Do T-60 and T-15 again before each judging slot if there's more than one.

Timing and backup rules: `call-backup.md`. Recording: `call-backup-shotlist.md`. Q&A: `judge-qa.md`.

---

## Two call rules that will bite you in rehearsal

Both come from `backend/gaps/phone.py` and `backend/config/calls.yaml`. If either one fires, the API won't dial. The status is `blocked`, and the panel has no label for it.

1. **Office hours.** Calls go out only 09:00–15:30 America/New_York, Mon–Fri, by the real clock. A pitch slot at 16:00 ET can't place a live call. Plan for tier B up front, or move the slot.
2. **One call per school per 7 days.** Every placed call, rehearsal ones included, counts. `GS_TODAY` is pinned to 2026-11-03, but call dates come from the real clock. So after any real call to Beauclerc, the spacing check blocks the next one until you clear call history (see Reset).

Placing a call also marks Beauclerc's open questions answered. With no open questions, the call button doesn't render. Reset clears this too.

---

## T-1 day

- [ ] `main` deployed; live URL loads: https://dvpvz48phigre.cloudfront.net
- [ ] Voice env set on the API task: `VOICE_INSTANCE_ID`, `VOICE_FLOW_ID`, `VOICE_SOURCE`, `VOICE_VERIFIED_TO` (all four, or `VOICE_ENABLED` stays off)
- [ ] `VOICE_VERIFIED_TO` is the demo phone. Check that it's in the task env and not in any slide, doc, or commit
- [ ] Workshop Studio account still exists (it may be wiped after the event); Connect instance and toll-free number still claimed
- [ ] One full 8-minute run with a stopwatch, call included. Note the real call time: ______ s
- [ ] Record the backup clips and stills (`call-backup-shotlist.md`)
- [ ] Reset (below)

## T-60 min

- [ ] Venue Wi-Fi **and** phone hotspot both tested on the presenter laptop
- [ ] Demo phone: charged > 80%, ringer on, volume max, Do Not Disturb / Focus **off**, silence-unknown-callers **off**
- [ ] Person holding the demo phone has the office script (`call-backup-shotlist.md`)
- [ ] Test call **only if** you'll reset afterwards. Otherwise skip it and trust the T-1 run
- [ ] Look up the tier C ids and fill in the `curl` in a terminal:
  ```bash
  curl -s "$DEMO_URL/api/schools/$BEAUCLERC_ID/questions" | python3 -m json.tool
  ```
  Copy the open after-care question's `id` into `AFTER_CARE_QID`.
- [ ] Reset (below), then confirm the call button shows on Beauclerc's card

## T-15 min

- [ ] Clock check: pitch starts before 15:30 ET? If not, open with tier B ready and don't click the live button
- [ ] Browser: one window, fresh tab on the live URL, zoom 125%, bookmarks bar hidden, extensions that inject UI off
- [ ] `call-backup-call.mp4` open and paused in QuickTime; `call-backup-full.mp4` on the desktop and on USB
- [ ] `call-backup-after.png` on the desktop
- [ ] Laptop notifications off; Slack/Messages quit; screen-sharing resolution checked on the venue display
- [ ] Slides on slide 1, presenter view on the laptop
- [ ] Decide who watches the clock and calls "switch" (not the speaker)

## Reset (before every live pitch)

Clears call history and reopens Beauclerc's questions, so the 7-day rule and the hidden button don't bite.

- [ ] Hosted (DynamoDB): delete the `pk=META, sk=CALLS` item from the `StateTableName` table (CDK output of `GsAppStack`)
  ```bash
  aws dynamodb delete-item --table-name "$GS_DYNAMODB_TABLE" \
    --key '{"pk":{"S":"META"},"sk":{"S":"CALLS"}}'
  ```
- [ ] Reopen Beauclerc's inbox questions, or re-ask them from the UI (the community "Ask" path), so the call button shows with the right count
- [ ] Remove the call overlay if the card already shows the answered after-care: the `pk=META, sk=OVERLAYS` item holds it. Look at the item before you edit or delete it, since other schools' overlays live there too
- [ ] Local (`GS_STATE_PATH` JSON): same keys, `calls`, `inbox`, `overlays`, in the state file
- [ ] Reload the live URL, run the Jacksonville query, and confirm: after-care **Unknown**, 13 parents, call button visible

---

## Run-through script (stopwatch)

| Mark | Segment | Target | Actual |
| --- | --- | --- | --- |
| 0:45 | Hook + problem done | 0:45 | |
| 1:30 | Architecture done | 1:30 | |
| 3:15 | Results on screen, Beauclerc Unknown shown | 3:15 | |
| 3:45 | Community demand shown, call button clicked | 3:45 | |
| 5:15 | Call finished, card updated | 5:15 | |
| 6:45 | Responsible AI + economics done | 6:45 | |
| 8:00 | Close, stop talking | 8:00 | |

If you're over 3:45 at the call button, cut the community segment to one sentence. If you're over 5:15, skip the card refresh and say the line.

## Failure drills (do each once)

Practice the switch, not the fix. Each drill should take under 5 seconds from signal to the backup line.

- [ ] **No ring:** click call with the demo phone on airplane mode → at 15 s say the tier B line → `Cmd+Tab` → play Clip B
- [ ] **Panel frozen:** click call outside office hours (or without a reset) → at 5 s, switch to tier B
- [ ] **No answer on the card:** let the call run, have the office say "I'm not sure" to everything → tier C `curl` → re-run search
- [ ] **No network:** turn Wi-Fi off before slide 4 → tier A video, narrate over it
- [ ] **Judge asks "was that real?":** say the line from `call-backup.md` without hesitating

## After the pitch

- [ ] Reset again if another slot follows
- [ ] Note what failed and at what time: ______
- [ ] Don't leave the demo phone number in any shared screen, recording, or chat
