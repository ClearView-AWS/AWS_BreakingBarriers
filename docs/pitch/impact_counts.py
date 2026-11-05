"""Count how often a parent search shows an Unknown fact, using the app's own code.

Run from the repo root:  .venv/bin/python docs/pitch/impact_counts.py
Bedrock stays off, so the rules engine reads each query in eval/queries.jsonl.
The numbers feed docs/pitch/impact.md.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from agent.extractor import extract  # noqa: E402
from catalog import needs as need_catalog  # noqa: E402
from contracts import Criterion  # noqa: E402
from evidence.engine import evaluate_criterion  # noqa: E402
from pipeline import _rank_key, _score_school, _stamp_distances  # noqa: E402
from search.corpus import known_cities, load_programs, load_schools  # noqa: E402
from search.engine import search_schools  # noqa: E402
from store import State  # noqa: E402

SHOWN = 8  # main list length in pipeline._search_response


def main() -> None:
    rows = [json.loads(line) for line in (ROOT / "eval" / "queries.jsonl").read_text().splitlines() if line.strip()]
    cities = known_cities()
    schools = load_schools()
    programs = load_programs()
    searches = with_needs = hit = 0
    cells = unknown_cells = 0
    unknown_schools = []
    by_need = Counter()
    with State() as state:
        for row in rows:
            if row.get("route"):
                continue
            criteria, _ = extract(row["query"], cities)
            needs = [c for c in criteria if c.kind == "need" and c.need]
            searches += 1
            if not needs:
                continue
            with_needs += 1
            _stamp_distances(schools, criteria, None)
            matched = search_schools(schools, programs, criteria, row["query"], {}, limit=None)
            cards = [card for card in (_score_school(s, criteria, programs, state) for s in matched) if card]
            cards.sort(key=_rank_key)
            top = cards[:SHOWN]
            need_of = {c.id: c.need for c in needs}
            n_unknown = 0
            for card in top:
                card_unknown = False
                for item in card["evidence"]:
                    need = need_of.get(item["criterion_id"])
                    if not need:
                        continue
                    cells += 1
                    if item["status"] == "unknown":
                        unknown_cells += 1
                        by_need[need] += 1
                        card_unknown = True
                n_unknown += card_unknown
            unknown_schools.append(n_unknown)
            hit += n_unknown > 0

    print(f"searches (non-routing eval queries): {searches}")
    print(f"searches with at least one need: {with_needs}")
    print(f"searches whose top {SHOWN} show at least one Unknown fact: {hit}/{with_needs} ({hit / with_needs:.0%})")
    print(f"need cells in top {SHOWN} that are Unknown: {unknown_cells}/{cells} ({unknown_cells / cells:.0%})")
    print(f"mean schools with an Unknown per search (top {SHOWN}): {sum(unknown_schools) / len(unknown_schools):.1f}")
    print("most-unknown needs:", ", ".join(f"{need} {n}" for need, n in by_need.most_common(8)))

    seed = json.loads((ROOT / "data" / "synthetic" / "community_seed.json").read_text())
    groups = Counter((a["school_id"], a["need"], a["month"]) for a in seed["asks"])
    print("parents per (school, need, month) in the community seed:")
    for (school, need, month), n in groups.most_common():
        print(f"  {school} {need} {month}: {n}")
    sample = json.loads((ROOT / "Sample Data" / "schools_sample.json").read_text())
    print(f"sample schools: {len(sample)}, total corpus: {len(schools)}")

    # Every need against every school: how much of the catalog is Unknown on file.
    print("share of schools where a need is Unknown on file (GreatSchools sample / synthetic):")
    real_total = real_unknown = syn_total = syn_unknown = 0
    for need in need_catalog():
        criterion = Criterion(id=f"c_{need}", text=need, need=need)
        counts = {True: [0, 0], False: [0, 0]}
        for school in schools:
            record = evaluate_criterion(school, criterion, programs, {})
            bucket = counts[bool(school.get("_synthetic"))]
            bucket[0] += 1
            bucket[1] += record.status == "unknown"
        (rt, ru), (st, su) = counts[False], counts[True]
        real_total += rt
        real_unknown += ru
        syn_total += st
        syn_unknown += su
        print(f"  {need}: {ru}/{rt} / {su}/{st}")
    print(f"all needs, GreatSchools sample: {real_unknown}/{real_total} ({real_unknown / real_total:.0%})")
    print(f"all needs, synthetic: {syn_unknown}/{syn_total} ({syn_unknown / syn_total:.0%})")


if __name__ == "__main__":
    main()
