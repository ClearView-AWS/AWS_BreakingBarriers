# Spanish close beat (20–30 s)

Slot: the last beat of the 8-minute pitch, on slide 8 (**Ask us anything**), right before Q&A. It replaces the "Optional 10 s" Spanish line in `demo-script.md` with a full beat.

Criterion focus: Impact (equity, no login) + Technical (the rules engine reads Spanish).

---

## Type exactly

```text
Escuela intermedia en Jacksonville con robotica y cuidado después de la escuela. No tenemos mucho dinero.
```

("Middle school in Jacksonville with robotics and after-school care. We don't have much money." It's the same search as the demo, said the way a Spanish-speaking parent would say it.)

Each phrase comes from `backend/config/needs.yaml` or the grade list in `backend/agent/extractor.py`:

| Parent says | Reads as | Source |
| --- | --- | --- |
| escuela intermedia | Middle school (grade) | `extractor.py` grade patterns |
| robotica | STEM-focused (`stem`) | `needs.yaml` phrases |
| cuidado después de la escuela | After-school care (`after_care`) | `needs.yaml` phrases |
| no tenemos mucho dinero | Low cost (`low_cost`) | `needs.yaml` phrases |

Checked 2026-11-04 with `TRANSLATE_ENABLED` off: `extract()` returns all five criteria (grade, Jacksonville, `after_care`, `low_cost`, `stem`). The brief shows up even if Translate is down.

---

## Say (~25 s, about 65 words)

> "One more parent. This one types in Spanish — no settings, no login. *Escuela intermedia… cuidado después de la escuela… no tenemos mucho dinero.* Same brief, same Beauclerc card, same Unknown on after-care. The phrases live in a config file, so GreatSchools can add one without a deploy. With Translate on, they get the answer back in Spanish. The parent who couldn't call during work hours now doesn't have to. Questions?"

**Show:** the brief chips (Middle school · Jacksonville · STEM-focused · After-school care · Low cost) as you say "same brief." Point at the Beauclerc card on "same Unknown."

**Stop talking** on "Questions?" and hand off to `judge-qa.md` (Translate answer at line 38).

---

## Timing guardrails

- Start typing while you say "One more parent." Paste it if the presenter's hands are busy.
- Results haven't come back by "same Beauclerc card"? Point at the brief chips and keep going. The brief alone makes the point.
- Live UI down: show a screenshot of the Spanish brief from `docs/screenshots/` (take it before judging) and say the line as written.
- Only say "they get the answer back in Spanish" if `TRANSLATE_ENABLED=1` on the live stack. Otherwise say: "Translate is one flag away from replying in Spanish."
