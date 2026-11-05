# Person A: Host / Impact

**Clock:** 0:00–1:05 (1:05 · ~150 words)  
**You:** Stand center. Don't touch the laptop.  
**Screen:** Live landing (empty chat + example chips), URL visible.

---

## Say (word-for-word)

Parents don't lose good schools because the ratings are wrong.

They lose them because the one fact they need isn't on the card. After-school care. A gifted program. And calling every office during work hours turns into a second job.

GreatSchools reaches about forty million families a year, across more than a hundred and fifty thousand school profiles. So this gap shows up all the time.

We measured it. In our eval, sixty-eight percent of searches with a real need show at least one Unknown in the top eight results. After-school care is missing on all twenty-five GreatSchools sample schools. And in Washington's public report card data, it's missing for all two thousand three hundred sixty-four schools.

So we built Guided Search.

*(pause)* We investigate. You decide.

Missing facts stay on screen. And when parents ask, we call the school and fill in the answer for everyone.

Here's the live demo.

---

## Stage notes

- Land **"We investigate. You decide."** cleanly, then pause for half a beat.
- Say the numbers slowly. They're the only numbers in your section.
- Look at Person B on "live demo". Their cursor should already be on the first chip.

## Where the numbers come from

| Line | Source |
| --- | --- |
| ~40M families, 150k+ profiles | [About GreatSchools](https://www.greatschools.org/gk/about/), `docs/pitch/impact.md` |
| 68% (23/34) | `docs/pitch/impact_counts.py` on `eval/queries.jsonl` |
| 25/25 after-care Unknown | same script, `Sample Data/` |
| 2,364 WA schools, none with after-care | `data/wa/schools.json` (OSPI has no after-care field) |
