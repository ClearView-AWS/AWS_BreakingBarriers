# Inbound parent line

Parents who cannot read well or use the web can call the same Amazon Connect number the product uses to reach schools. They speak a need in any language; the line answers with the top three schools by voice, and can also text the same short summary by SMS.

No new AWS resources. The inbound contact flow reuses the Connect instance, Lex bot, Polly voice, Translate, and the existing FastAPI pipeline.

## Flow

1. **Answer.** Connect answers the inbound call on the existing number and plays a short disclosure ("This call is with an automated GreatSchools assistant…").
2. **Listen.** Lex captures speech. Amazon Translate (already behind `TRANSLATE_ENABLED`) turns a non-English utterance into English the same way `/api/chat` does.
3. **Search.** The Lambda (or the API) posts the English text to `pipeline.turn` with `action` omitted so routing and extraction run as for a typed chat message.
4. **Speak.** `gaps.inbound.spoken_summary` turns the turn’s `results` block into ≤ 60 words naming up to three schools. Polly reads that line; optionally SMS sends the same text to the caller’s number via the Connect SMS channel already available on the instance.
5. **Follow-ups.** Further speech ("tell me more about the first one", "why not Bayside") is another `pipeline.turn` on the same `session_id`, so compare / detail / ask-school behave as in chat.

## What stays out of scope for the hackathon

- A separate inbound phone number or new Connect instance.
- Changing the outbound school-call flow, Lex intents beyond a free-text catch-all, or CDK.
- Storing recordings of parent calls beyond what Connect already retains for the school-call path.

## Code

| Piece | Role |
| --- | --- |
| `backend/gaps/inbound.py` → `spoken_summary` | Pipeline result → short spoken/SMS line |
| `backend/pipeline.py` → `turn` | Same search the chat uses |
| `backend/voice/lex_turn.py` | Pattern for Lex ↔ Bedrock turns (outbound today; inbound reuses the shape) |
| `docs/inbound-voice.md` | This design |

## Example spoken line

> Top schools. 1. Beauclerc STEM Middle in Jacksonville: strong STEM and after-care until six. 2. Tidewater… 3. …

Under sixty words so Polly stays clear and an SMS fits one segment.
