"""Drop any sentence that does not cite a real evidence path."""

from __future__ import annotations

import re

from catalog import funding_rules, glossary
from contracts import EvidenceRecord
from evidence.engine import get_path

_CITE = re.compile(r"\[\[cite:([^\]]+)\]\]")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def citations_in(text: str) -> list[str]:
    return _CITE.findall(text or "")


def allowed_citations(records: list[EvidenceRecord], school: dict | None = None) -> set[str]:
    allowed: set[str] = set()
    for record in records:
        if record.source:
            allowed.add(record.source.path)
        allowed.update(record.review_ids)
        if record.conflict:
            allowed.add(record.conflict.path)
    for rule in funding_rules().values():
        allowed.add(rule["cite_path"])
    for entry in glossary().values():
        allowed.add(entry["cite_path"])
    if school is not None:
        for token in ("entity_type", "level_codes", "name", "latlon", "summary_rating", "osp.tuition", "osp.school_sub_type", "osp.after_school_until"):
            if get_path(school, token) is not None:
                allowed.add(token)
    return allowed


def _attach_trailing_cites(text: str) -> str:
    """A citation written after a period belongs to the sentence it follows."""
    return re.sub(
        r"([.!?])(\s*)((?:\[\[cite:[^\]]+\]\]\s*)+)",
        lambda match: f" {match.group(3).strip()}{match.group(1)}{match.group(2)}",
        text,
    )


def validate_text(text: str, allowed: set[str]) -> str:
    if not text:
        return ""
    kept = []
    for sentence in _SENTENCE.split(_attach_trailing_cites(text).strip()):
        cites = citations_in(sentence)
        if cites and all(cite in allowed for cite in cites):
            kept.append(sentence.strip())
    return " ".join(kept)


def strip_cites(text: str) -> str:
    cleaned = _CITE.sub("", text or "")
    cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()
