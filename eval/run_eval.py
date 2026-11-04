"""Score extraction, the ask-or-not decision, citations, and dropped schools.

Run from the repo root:  python eval/run_eval.py
Bedrock stays off. The rules engine is what this file measures.
"""

from __future__ import annotations

import json
import os
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
POST_DRAFTS = ROOT / "eval" / "post_drafts.jsonl"


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
    access_ok, access_total, access_odds = _getting_in_lines()
    if access_ok != access_total:
        failures.append(f"{access_total - access_ok} getting in lines lack an official link or school source")
    if access_odds:
        failures.append(f"getting in lines that estimate odds or promise a seat: {access_odds}")
    convo = _conversations(failures)
    # Paraphrased follow-ups measure how well the message is read, so the rules alone
    # are expected to miss some. Misses are listed, but they don't fail the run.
    paraphrase_misses: list[str] = []
    paraphrased = _conversations(paraphrase_misses, ROOT / "eval" / "conversations_paraphrased.jsonl")
    durations.sort()
    median = durations[len(durations) // 2] if durations else 0

    print(f"criteria recall: {recall:.1%} ({need_hit}/{need_total}) target 90%")
    print(f"criteria precision: {precision:.1%} ({matched}/{emitted}) target 85%")
    print(f"strength accuracy: {strength:.1%} ({strength_hit}/{strength_total}) target 85%")
    print(f"ask decision: {ask:.1%} ({ask_hit}/{ask_total}) target 80%")
    print(f"getting in lines with an official link or school source: {access_ok}/{access_total} target 100%")
    print(f"getting in lines that estimate odds or promise a seat: {access_odds} target 0")
    print(f"follow-up routing: {convo['route_ok']}/{convo['route_total']} target 90%")
    print(f"follow-up school and topic: {convo['ref_ok']}/{convo['ref_total']} target 90%")
    print(f"follow-up answer lines with a citation: {convo['cited_ok']}/{convo['cited_total']} target 100%")
    print(f"follow-up answers that estimate odds: {convo['odds']} target 0")
    reader = "bedrock" if os.environ.get("BEDROCK_ENABLED", "").lower() in {"1", "true", "yes"} else "rules only"
    print(
        f"paraphrased follow-ups ({reader}): routing {paraphrased['route_ok']}/{paraphrased['route_total']}, "
        f"school and topic {paraphrased['ref_ok']}/{paraphrased['ref_total']} target 90% with Bedrock"
    )
    for line in paraphrase_misses:
        print("   paraphrase miss:", line)
    print(f"cited claims kept: {citation_ok}/{citation_total}")
    print(f"schools dropped for missing data: {dropped}")
    print(f"median turn: {median:.2f}s")
    leaked, blocked_clean, total_pii, total_clean = _post_safety()
    print(f"draft posts with personal info published: {leaked}/{total_pii} target 0")
    print(f"clean draft posts wrongly blocked: {blocked_clean}/{total_clean}")
    if leaked:
        failures.append(f"{leaked} draft posts with personal info passed the safety check")
    if failures:
        print("failures:")
        for line in failures:
            print(" -", line)
        sys.exit(1)


def _post_safety() -> tuple[int, int, int, int]:
    """Personal info that would be published, and clean posts that were blocked."""
    from community.safety import check_post

    leaked = blocked_clean = total_pii = total_clean = 0
    for line in POST_DRAFTS.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        ok = check_post(row["text"])["ok"]
        if row["pii"]:
            total_pii += 1
            leaked += int(ok)
        else:
            total_clean += 1
            blocked_clean += int(not ok)
    return leaked, blocked_clean, total_pii, total_clean


def _citations() -> tuple[int, int]:
    kept = total = 0
    with State() as state:
        response = turn(
            state,
            {"message": "Middle school in Seattle with STEM and after-school care. Money is tight."},
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
                defended.update(row.get("post_ids") or [])
                if row.get("status") == "unknown":
                    # An "unknown" claim may cite a field only if that field really is empty.
                    defended.update(p for p in row.get("missing_paths") or [] if get_path(school, p) is None)
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
        Criterion(id="c1", text="Seattle", kind="location", value="Seattle", strength="require"),
        Criterion(id="c2", text="middle", kind="grade", value="m", strength="require"),
        Criterion(id="c3", text="top school", need="high_performing", strength="require", kind="need"),
    ]
    eligible = [school for school in schools if passes_hard_filters(school, criteria)]
    found = {school["id"] for school in search_schools(schools, [], criteria, limit=None)}
    return sum(1 for school in eligible if school["id"] not in found)


_ODDS_WORDS = ("chance", "odds", "likely", "probab", "guarantee", "percent", "%", "will get in", "you'll get")


def _getting_in_lines() -> tuple[int, int, int]:
    """Every school's Getting in line, at every level it serves.

    Returns (lines with an official link or a school source, all lines, lines that
    estimate odds or promise a seat).
    """
    import re

    from enrollment.access import getting_in

    ok = total = odds = 0
    for school in load_schools():
        for grade in school.get("level_codes") or [None]:
            record = getting_in(school, grade)
            total += 1
            official = str((record.get("official") or {}).get("url") or "").startswith("https://")
            school_source = (record.get("source") or {}).get("type") in {"school_reported", "school_profile"}
            ok += official or school_source
            # The line and the plain text are what a parent reads; the rule summary is quoted law.
            shown = f"{record['line']} {record['text']} {record.get('detail') or ''}".casefold()
            odds += any(re.search(rf"\b{re.escape(word)}" if word[0].isalpha() else re.escape(word), shown) for word in _ODDS_WORDS)
    return ok, total, odds


def _conversations(failures: list[str], path: Path | None = None) -> dict:
    """Run the scripted chats in eval/conversations.jsonl through the conversation layer.

    Each turn may expect a route, the schools a follow-up is about (by name, by its
    position in the shown list, or the whole list) and its topic. Every line of an
    answer must carry a citation, and no answer may estimate a family's odds.
    """
    import re

    from agent.conversation import chat_turn

    odds_words = re.compile(r"\b(likely|probab\w*|percent|odds of|chance of|you will get in|guarantee\w*)\b|%")
    out = {"route_ok": 0, "route_total": 0, "ref_ok": 0, "ref_total": 0, "cited_ok": 0, "cited_total": 0, "odds": 0}
    by_name = {school["name"]: school["id"] for school in load_schools()}
    path = path or ROOT / "eval" / "conversations.jsonl"
    for row in (json.loads(line) for line in path.read_text().splitlines() if line.strip()):
        state = {"sessions": {}, "inbox": [], "overlays": {}}
        session_id = None
        for step, spec in enumerate(row["turns"]):
            shown = list(state["sessions"][session_id]["focus"]["results"]) if session_id else []
            response = chat_turn(state, {"session_id": session_id, "message": spec["say"]})
            session_id = response["session_id"]
            label = f"{row['id']} turn {step}"
            if "route" in spec:
                out["route_total"] += 1
                if response["route"] == spec["route"]:
                    out["route_ok"] += 1
                else:
                    failures.append(f"{label} route {response['route']} != {spec['route']}")
            answer = next((b["payload"] for b in response["blocks"] if b["type"] == "answer"), None)
            detail = next((b["payload"] for b in response["blocks"] if b["type"] == "school_detail"), None)
            about = answer["school_ids"] if answer else ([detail["school"]["id"]] if detail else [])
            if response["route"] == "save":
                about = list(state["sessions"][session_id].get("saved") or [])[-1:]
            expected = None
            if "schools" in spec:
                expected = [by_name[name] for name in spec["schools"]]
            elif "ordinal" in spec:
                expected = shown[spec["ordinal"] - 1 : spec["ordinal"]]
            elif spec.get("scope") == "results":
                expected = shown[:8]
            if expected is not None or "topic" in spec:
                out["ref_total"] += 1
                topic = None
                if answer:
                    kind, need = answer["topic"]["kind"], answer["topic"]["need"]
                    topic = f"need:{need}" if kind == "need" else kind
                ok = (expected is None or about == expected) and ("topic" not in spec or topic == spec["topic"])
                out["ref_ok"] += ok
                if not ok:
                    failures.append(f"{label} about {about} topic {topic} != {expected} {spec.get('topic')}")
            if answer:
                message = next(b["payload"] for b in response["blocks"] if b["type"] == "message")
                for line in filter(None, (message.get("cited") or "").split("\n")):
                    out["cited_total"] += 1
                    out["cited_ok"] += bool(citations_in(line))
                shown_text = f"{message.get('text') or ''} {message.get('prompt') or ''}".casefold()
                if odds_words.search(shown_text):
                    out["odds"] += 1
                    failures.append(f"{label} answer estimates odds")
    if out["cited_ok"] != out["cited_total"]:
        failures.append(f"{out['cited_total'] - out['cited_ok']} follow-up answer lines lack a citation")
    return out


if __name__ == "__main__":
    main()
