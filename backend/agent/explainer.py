"""Card text is assembled from evidence notes. A sentence without a citation is dropped."""

from __future__ import annotations

from agent.citations import allowed_citations, strip_cites, validate_text
from contracts import EvidenceRecord


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
