"""Explain a missing school from the evidence, including what would move it up."""

from __future__ import annotations

from agent.citations import strip_cites, validate_text
from contracts import EvidenceRecord
from evidence.engine import evaluate_criterion
from evidence.scorer import WEIGHT, score_school, status_value

_LEVELS = {"p": "pre-k", "e": "elementary", "m": "middle", "h": "high"}


def explain_absence(
    school: dict,
    criteria: list,
    programs: list[dict],
    overlays: dict | None,
    ranked_ids: list[str],
) -> dict:
    reasons = _filter_reasons(school, criteria)
    if reasons:
        text = " ".join(reasons)
        allowed = {"level_codes", "city", "entity_type", "name"}
        clean = validate_text(text, allowed) or text
        return {
            "school_id": school["id"],
            "school_name": school["name"],
            "listed": False,
            "filtered_out": True,
            "text": strip_cites(clean),
            "cited": clean,
            "change": _filter_change(school, criteria),
        }

    rows = []
    records: list[EvidenceRecord] = []
    for criterion in criteria:
        if criterion.kind not in {"need", "distance"} or (criterion.kind == "need" and not criterion.need):
            continue
        record = evaluate_criterion(school, criterion, programs, overlays)
        records.append(record)
        rows.append((criterion.strength, record))
    scored = score_school(rows)
    position = ranked_ids.index(school["id"]) + 1 if school["id"] in ranked_ids else None
    worst = _worst_row(rows)
    change = ""
    if worst is not None:
        strength, record = worst
        lifted = _counterfactual(rows, record.criterion_id)
        change = (
            f"If { _label(criteria, record.criterion_id) } were confirmed, "
            f"the match would go from {scored['match']:.2f} to {lifted:.2f}."
        )
    where = f"It is number {position} of {len(ranked_ids)}." if position else "It is in the scored set."
    if scored["missed_must"] and worst is not None:
        where = "It is under Missed a must-have, so it stays visible."
    sentence = f"{school['name']} matches the location, grade, and school type. {where}"
    if worst is not None and worst[1].note:
        sentence = f"{sentence} {worst[1].note}"
    if change:
        sentence = f"{sentence} {change}"
    allowed = set()
    for record in records:
        if record.source:
            allowed.add(record.source.path)
        allowed.update(record.review_ids)
    # The counterfactual sentence has no cite of its own; keep it only alongside a cited note.
    cited_parts = []
    for record in records:
        if record.note:
            kept = validate_text(record.note, allowed)
            if kept:
                cited_parts.append(kept)
    cited = " ".join(cited_parts)
    if change and cited:
        cited = f"{cited} {change}"
    return {
        "school_id": school["id"],
        "school_name": school["name"],
        "listed": position is not None and position <= 8 and not scored["missed_must"],
        "filtered_out": False,
        "match": scored["match"],
        "verified": scored["verified"],
        "position": position,
        "missed_must": scored["missed_must"],
        "text": strip_cites(cited) if cited else sentence,
        "cited": cited,
        "change": change,
        "evidence": [record.model_dump() for record in records],
    }


def _label(criteria, criterion_id: str) -> str:
    for criterion in criteria:
        if criterion.id == criterion_id:
            return criterion.text
    return "that criterion"


def _worst_row(rows: list[tuple[str, EvidenceRecord]]):
    if not rows:
        return None
    return min(rows, key=lambda row: (status_value(row[1].status, row[0]), -WEIGHT[row[0]]))


def _counterfactual(rows, criterion_id: str) -> float:
    adjusted = []
    for strength, record in rows:
        if record.criterion_id == criterion_id:
            cloned = record.model_copy(update={"status": "confirmed" if strength != "avoid" else "needs_attention"})
            adjusted.append((strength, cloned))
        else:
            adjusted.append((strength, record))
    return score_school(adjusted)["match"]


def _filter_reasons(school: dict, criteria: list) -> list[str]:
    reasons = []
    levels = school.get("level_codes") or []
    pretty = ", ".join(_LEVELS.get(code, code) for code in levels) or "an unlisted grade"
    for criterion in criteria:
        if criterion.kind == "grade" and criterion.value not in levels:
            asked = _LEVELS.get(criterion.value, criterion.value)
            reasons.append(
                f"{school['name']} serves {pretty}, and this search is for {asked} [[cite:level_codes]]."
            )
        if criterion.kind == "location" and str(school.get("city") or "").casefold() != str(criterion.value).casefold():
            reasons.append(
                f"{school['name']} is in {school.get('city')}, not {criterion.value} [[cite:city]]."
            )
        if criterion.kind == "school_type" and school.get("entity_type") != criterion.value:
            reasons.append(
                f"{school['name']} is {school.get('entity_type')}, not {criterion.value} [[cite:entity_type]]."
            )
    return reasons


def _filter_change(school: dict, criteria: list) -> str:
    for criterion in criteria:
        if criterion.kind == "grade" and criterion.value not in (school.get("level_codes") or []):
            return f"Include {_LEVELS.get(criterion.value, 'those grades')} along with the grades this school serves, and it can be scored."
        if criterion.kind == "location":
            return f"Search {school.get('city')} and it can be scored."
        if criterion.kind == "school_type":
            return f"Include {school.get('entity_type')} schools and it can be scored."
    return ""
