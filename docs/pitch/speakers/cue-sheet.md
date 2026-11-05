# Cue sheet (print one page)

**Live:** https://dvpvz48phigre.cloudfront.net · **Handset:** E holds it, on speaker, ringer max, DND off

| Clock | Who | Action | Cue line |
| ---: | --- | --- | --- |
| 0:00 | A | Landing visible | "Parents don't lose good schools because the ratings are wrong." |
| 0:35 | A | — | "Sixty-eight percent… at least one Unknown in the top eight." |
| 0:55 | A | Pause | "We investigate. You decide." |
| 1:05 | A→B | Hand off | "Here's the live demo." |
| 1:05 | B | Click **first chip** (Seattle gifted + after-care + small) | "A parent types the way they talk." |
| 1:25 | B | Skip clarifier · approve brief | "That brief is the contract." |
| 1:50 | B | Point at Confirmed gifted + citation | "…the citation names the exact field it came from." |
| 2:10 | B | Point at Unknown after-care | "A normal filter would hide this school." |
| 2:35 | B | *Optional* Map | "The pins show how the matches spread across the city." |
| 3:00 | B→C | Leave results up | "Over to architecture. Then we'll ask the school." |
| 3:00 | C | Talk over UI | "…four CDK stacks." |
| 3:50 | C | — | "…a model never marks a fact Confirmed. Code does that." |
| 4:10 | C→D | D takes laptop | "We pick up the phone." |
| 4:25 | D | Click **📞 Have AI call** | "…never a real school office." |
| 4:35 | E | Answer handset | "Front office, this is Dana." |
| 4:45 | E | Consent | "Yes, that's fine." |
| 5:00 | E | Answer | "…after-school care on campus until six p.m. every school day." |
| 5:30 | D | Card updates | "Only then does the card change." |
| 6:25 | D→E | Hand off | "Over to close." |
| 6:25 | E | Close | "That call cost a parent nothing…" |
| 7:00 | E | — | "…about eleven cents." |
| 7:35 | E | Tagline | "We investigate. You decide." |
| 7:40 | All | **Stop** | Q&A → A hosts, [../judge-qa.md](../judge-qa.md) |

## Kill list (cut in this order if behind)

1. B: Map (−10 s)
2. C: Translate sentence (−6 s)
3. E: "This isn't a prototype" paragraph (−12 s)
4. A: the GreatSchools sample sentence; keep the Washington one (−6 s)

## Failures (decide in 5 s, never debug)

| Failure | Owner | Do / say |
| --- | --- | --- |
| Site down / search hangs | B | Backup tab or screenshot: "Conference Wi-Fi. Here's the same search from this morning." |
| No **Have AI call** on the Seattle card | D | Jacksonville query → Beauclerc → call ("thirteen parents, seeded") |
| Seattle call doesn't ring | D | Same Jacksonville backup |
| Nothing rings at all | D | Recorded call: "Live telephony is flaky in a hackathon sandbox, so here's the recorded run." |
| AI mishears E | E | Repeat the same sentence once, word for word |
| Running past 7:30 at close | E | Jump to "GreatSchools already has the families…" |

## Actual splits (fill in at rehearsal)

| Run | A | B | C | D | E | Total |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | |
| 2 | | | | | | |
