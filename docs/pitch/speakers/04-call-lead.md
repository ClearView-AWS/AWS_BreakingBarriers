# Person D: Call lead

**Clock:** 4:10–6:25 (2:15 · ~160 of your words + ~60 s of live call audio)  
**You:** Take the laptop from B. You're the only one clicking from here on.  
**Screen:** Seattle results → top card → **📞 Have AI call {school} · 1 question not on file**  
**Handset:** The demo phone is on speaker, on the table, near the mic. Person E answers it as the school office (see `05-closer.md`).

---

## Say + do

**[Hover the call button on the top Seattle card]**

The card says after-school care is Unknown. Today the parent's next step is a phone call during work hours.

So we make the call for them.

**[Click 📞 Have AI call]**

Amazon Connect is placing a real outbound call. For the demo it rings our own handset, never a real school office. My teammate is playing the front desk.

**[Phone rings → E answers. Stop talking while the AI speaks.]**

*(AI opening, from `backend/gaps/phone.py`):* "Hi, this is an automated AI assistant calling on behalf of families who use GreatSchools… Is it okay if I transcribe this call?"

**[After E consents, speak over the AI's question, quietly]**

It opens by saying it's an AI and asking consent to transcribe. Washington and Florida both require every party's consent.

**[Point at the transcript panel as lines stream in]**

Polly speaks and Lex turns the office's speech into text. Then a Lambda asks Bedrock Haiku for the next line.

**[Call finishes → "What the school said" + "Updated this school's card."]**

Here's the key part. The model proposes an answer, and code checks that the quote was actually said on the call. Code also reads "six p.m." itself. Only then does the card change.

**[Point at after-school care on the card]**

That Unknown is now an answer from the school, with the quote attached. Every parent who asks next gets it without a single extra call.

Over to close.

---

## Backup 1: Jacksonville call (Seattle call fails or the button is missing)

Decide within **5 seconds**. Don't debug. Say:

> "Let me show the same call where it was built, on Jacksonville."

Paste into chat:

```text
Middle school in Jacksonville with STEM and after-school care. Money is tight.
```

Tap **Just show me results** → open **Beauclerc STEM Middle** → **📞 Have AI call Beauclerc**. The panel shows **"Asking for 13 parents."** Add one line:

> "In our seeded demo data, thirteen parents asked this same question. One call answers all of them."

Then pick the main script back up at "Amazon Connect is placing a real outbound call".

## Backup 2: no call at all (Connect down, phone dead)

Say: "Live telephony is flaky in a hackathon sandbox, so here's the recorded run." Play the saved screen recording of a completed call (record it before judging). Read the same lines from "It opens by saying it's an AI".

**Never** refresh more than once and **never** open a terminal on stage.

## Pre-flight (before judging)

- [ ] Handset charged, ringer at max, Do Not Disturb **off**
- [ ] One test call on the deployed URL in the last hour
- [ ] Backup recording open in a background tab
- [ ] Jacksonville query copied to a sticky note
