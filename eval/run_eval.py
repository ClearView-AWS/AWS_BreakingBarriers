"""Score extraction, the ask-or-not decision, citations, and dropped schools.

Run from the repo root:  python eval/run_eval.py
Bedrock stays off. The rules engine is what this file measures.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from agent.citations import citations_in, validate_text
from agent.extractor import extract
from agent.router import route_message
from evidence.engine import get_path
from pipeline import turn
from search.corpus import known_cities, load_schools
from search.engine import passes_hard_filters, search_schools
from store import State

QUERIES = ROOT / "eval" / "queries.jsonl"


def main() -> None:
    rows = [json.loads(line) for line in QUERIES.read_text().splitlines() if line.strip()]
    cities = known_cities()
    need_hit = need_total = 0
    extra = predicted = 0
    strength_hit = strength_total = 0
    ask_hit = ask_total = 0
    failures = []
    durations = []

    for row in rows:
        if row.get("route"):
            got, _ = route_message(row["query"], has_session=True)
            if got != row["route"]:
                failures.append(f"{row['id']} route {got} != {row['route']}")
            continue
        started = time.perf_counter()
        found, _ = extract(row["query"], cities)
        expected = row.get("needs") or {}
        got_needs = {item.need: item.strength for item in found if item.need}
        for need, strength in expected.items():
            need_total += 1
            if need in got_needs:
                need_hit += 1
                strength_total += 1
                if got_needs[need] == strength:
                    strength_hit += 1
            else:
                failures.append(f"{row['id']} missing {need}")
        for need, strength in got_needs.items():
            predicted += 1
            if need in expected and expected[need] == strength:
                extra += 0
            elif need not in expected:
                failures.append(f"{row['id']} extra {need}:{strength}")
            else:
                failures.append(f"{row['id']} strength {need} {strength} != {expected[need]}")
        grade = next((item.value for item in found if item.kind == "grade"), None)
        city = next((item.value for item in found if item.kind == "location"), None)
        school_type = next((item.value for item in found if item.kind == "school_type"), None)
        for label, got, want in (
            ("grade", grade, row.get("grade")),
            ("city", city, row.get("city")),
            ("type", school_type, row.get("school_type")),
        ):
            if got != want:
                failures.append(f"{row['id']} {label} {got} != {want}")
                predicted += 1
            elif want is not None:
                need_hit += 1
                need_total += 1
                predicted += 1
                extra += 1
        unmapped = any(item.kind == "need" and item.need is None for item in found)
        if bool(row.get("unmapped")) != unmapped:
            failures.append(f"{row['id']} unmapped {unmapped}")
        if unmapped:
            predicted += 1
            if row.get("unmapped"):
                extra += 1
                need_hit += 1
                need_total += 1
        elif row.get("unmapped"):
            need_total += 1

        with State() as state:
            response = turn(state, {"message": row["query"]})
        durations.append(time.perf_counter() - started)
        asked = any(block.type == "question" for block in response.blocks)
        ask_total += 1
        if asked == bool(row.get("ask")):
            ask_hit += 1
        else:
            reason = next((block.payload.get("reason") for block in response.blocks if block.type == "question"), None)
            failures.append(f"{row['id']} ask {asked} ({reason}) != {row.get('ask')}")

    recall = need_hit / need_total if need_total else 0
    # Precision uses needs that were expected and matched, over needs we emitted.
    emitted = 0
    matched = 0
    for row in rows:
        if row.get("route"):
            continue
        found, _ = extract(row["query"], cities)
        expected = row.get("needs") or {}
        for item in found:
            if item.kind == "need" and item.need:
                emitted += 1
                if expected.get(item.need) == item.strength:
                    matched += 1
            elif item.kind == "need" and item.need is None:
                emitted += 1
                if row.get("unmapped"):
                    matched += 1
            elif item.kind == "grade":
                emitted += 1
                if item.value == row.get("grade"):
                    matched += 1
            elif item.kind == "location":
                emitted += 1
                if item.value == row.get("city"):
                    matched += 1
            elif item.kind == "school_type":
                emitted += 1
                if item.value == row.get("school_type"):
                    matched += 1
    precision = matched / emitted if emitted else 0
    strength = strength_hit / strength_total if strength_total else 0
    ask = ask_hit / ask_total if ask_total else 0

    citation_ok, citation_total = _citations()
    dropped = _dropped_for_missing_data()
    durations.sort()
    median = durations[len(durations) // 2] if durations else 0

    print(f"criteria recall: {recall:.1%} ({need_hit}/{need_total}) target 90%")
    print(f"criteria precision: {precision:.1%} ({matched}/{emitted}) target 85%")
    print(f"strength accuracy: {strength:.1%} ({strength_hit}/{strength_total}) target 85%")
    print(f"ask decision: {ask:.1%} ({ask_hit}/{ask_total}) target 80%")
    print(f"cited claims kept: {citation_ok}/{citation_total}")
    print(f"schools dropped for missing data: {dropped}")
    print(f"median turn: {median:.2f}s")
    if failures:
        print("failures:")
        for line in failures:
            print(" -", line)
        sys.exit(1)


def _citations() -> tuple[int, int]:
    kept = total = 0
    with State() as state:
        response = turn(
            state,
            {"message": "Middle school in Jacksonville with STEM and after-school care. Money is tight."},
        )
    for block in response.blocks:
        if block.type != "results":
            continue
        for card in block.payload["schools"] + block.payload["missed"] + block.payload["gaps"]:
            for row in card["evidence"]:
                note = row.get("note") or ""
                if not note or "[[cite:" not in note:
                    continue
                total += 1
                allowed = set(citations_in(note))
                # Every cite token has to be a path we can defend.
                source = (row.get("source") or {}).get("path")
                school = next(item for item in load_schools() if item["id"] == card["id"])
                defended = set()
                if source:
                    defended.add(source)
                defended.update(row.get("review_ids") or [])
                for token in allowed:
                    if token.startswith(("funding.", "glossary.", "programs/", "reviews_full[")):
                        defended.add(token)
                    elif get_path(school, token) is not None:
                        defended.add(token)
                checked = validate_text(note, defended)
                if checked and citations_in(checked):
                    kept += 1
    return kept, total


def _dropped_for_missing_data() -> int:
    """Schools that pass location, grade, and type but are absent from search."""
    from contracts import Criterion

    schools = load_schools()
    criteria = [
        Criterion(id="c1", text="Jacksonville", kind="location", value="Jacksonville", strength="require"),
        Criterion(id="c2", text="middle", kind="grade", value="m", strength="require"),
        Criterion(id="c3", text="top school", need="high_performing", strength="require", kind="need"),
    ]
    eligible = [school for school in schools if passes_hard_filters(school, criteria)]
    found = {school["id"] for school in search_schools(schools, [], criteria, limit=None)}
    return sum(1 for school in eligible if school["id"] not in found)


if __name__ == "__main__":
    main()
