"""Match score and coverage. Coverage is shown beside the score and never multiplied in."""

from __future__ import annotations

from contracts import EvidenceRecord

WEIGHT = {"require": 3.0, "prefer": 1.0, "avoid": 2.0}
VALUE = {"confirmed": 1.0, "partial": 0.6, "unknown": 0.5, "needs_attention": 0.0}


def status_value(status: str, strength: str) -> float:
    base = VALUE[status]
    if strength == "avoid":
        if status == "unknown":
            return 0.5
        return round(1.0 - base, 4)
    return base


def is_missed_must(evidence: EvidenceRecord, strength: str) -> bool:
    confidence = (evidence.source.confidence if evidence.source else None) or ""
    solid = confidence in {"high", "medium"}
    if not solid:
        return False
    if strength == "require" and evidence.status == "needs_attention":
        return True
    if strength == "avoid" and evidence.status == "confirmed":
        return True
    return False


def score_school(rows: list[tuple[str, EvidenceRecord]]) -> dict:
    """rows are (strength, evidence) for scored criteria only."""
    if not rows:
        return {"match": 1.0, "coverage": 1.0, "verified": "0 of 0", "missed_must": False}
    weighted = 0.0
    total_weight = 0.0
    known = 0
    missed = False
    for strength, evidence in rows:
        weight = WEIGHT[strength]
        total_weight += weight
        weighted += weight * status_value(evidence.status, strength)
        if evidence.status in {"confirmed", "needs_attention"}:
            known += 1
        if is_missed_must(evidence, strength):
            missed = True
    match = weighted / total_weight if total_weight else 0.0
    coverage = known / len(rows)
    return {
        "match": round(match, 4),
        "coverage": round(coverage, 4),
        "verified": f"{known} of {len(rows)}",
        "missed_must": missed,
    }
