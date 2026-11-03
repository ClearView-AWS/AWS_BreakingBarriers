"""Card text. Code writes it from evidence notes; Bedrock may rewrite it, and code fact-checks every sentence."""

from __future__ import annotations

import logging
import re

from agent.citations import allowed_citations, known_numbers, strip_cites, validate_model_text, validate_text
from contracts import Criterion, EngineStep, EvidenceRecord
from evidence.engine import get_path

log = logging.getLogger(__name__)

_REVIEW = re.compile(r"^reviews_full\[(\d+)\]$")


def explain_school(records: list[EvidenceRecord], school: dict | None = None) -> str:
    allowed = allowed_citations(records, school)
    pieces = []
    for record in records:
        if not record.note:
            continue
        clean = validate_text(record.note, allowed)
        if clean:
            pieces.append(clean)
    return " ".join(pieces)


def public_summary(records: list[EvidenceRecord], school: dict | None = None) -> str:
    return strip_cites(explain_school(records, school))


def _path_value(school: dict, path: str):
    review = _REVIEW.match(path)
    if review:
        reviews = school.get("reviews_full") or []
        index = int(review.group(1))
        return reviews[index].get("text") if index < len(reviews) else None
    return get_path(school, path)


def facts_for(records: list[EvidenceRecord], school: dict) -> dict[str, set[str]]:
    """Number readings per citable path, taken from the data, never from generated text."""
    facts = {path: known_numbers([_path_value(school, path)]) for path in allowed_citations(records, school)}
    for record in records:
        if record.source:
            facts[record.source.path] |= known_numbers([record.value])
        if record.conflict:
            facts[record.conflict.path] |= known_numbers([record.conflict.profile_value, record.conflict.website_value])
    return facts


def _criteria_numbers(criteria: list[Criterion]) -> set[str]:
    values = []
    for criterion in criteria:
        values.append(criterion.value)
        values.extend((criterion.params or {}).values())
    return known_numbers(values)


def _card_input(card: dict, criteria: list[Criterion]) -> dict:
    by_id = {c.id: c for c in criteria}
    return {
        "id": card["id"],
        "name": card["name"],
        "criteria": [{"text": c.text, "strength": c.strength, "params": c.params} for c in criteria if c.kind in {"need", "distance"}],
        "evidence": [
            {
                "criterion": by_id[row["criterion_id"]].text if row["criterion_id"] in by_id else row["criterion_id"],
                "status": row["status"],
                "value": row["value"],
                "cite": (row.get("source") or {}).get("path"),
                "note": row["note"],
            }
            for row in card["evidence"]
        ],
    }


def _sentence_count(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s])


def model_summaries(cards: list[dict], schools_by_id: dict[str, dict], criteria: list[Criterion]) -> tuple[dict[str, str], EngineStep]:
    """Model-written summaries that pass the fact check, keyed by card id."""
    from agent.bedrock_client import maybe_bedrock_explanations

    drafts, step = maybe_bedrock_explanations([_card_input(card, criteria) for card in cards])
    if drafts is None:
        return {}, step
    extra = _criteria_numbers(criteria)
    kept: dict[str, str] = {}
    for card in cards:
        draft = drafts.get(card["id"], "")
        records = [EvidenceRecord(**row) for row in card["evidence"]]
        checked = validate_model_text(draft, facts_for(records, schools_by_id[card["id"]]), extra)
        if _sentence_count(checked) < _sentence_count(draft):
            log.warning("explain: dropped model sentences for %s: %r -> %r", card["id"], draft, checked)
        if checked:
            kept[card["id"]] = strip_cites(checked)
    if not kept:
        error = f"no model sentence passed the fact check for {len(cards)} cards"
        log.warning("%s", error)
        return {}, EngineStep(engine="rules_fallback", error=error)
    return kept, step
