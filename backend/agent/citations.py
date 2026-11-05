"""Drop any sentence that does not cite a real evidence path."""

from __future__ import annotations

import re

from catalog import funding_rules, funding_rules_for, glossary
from contracts import EvidenceRecord
from evidence.engine import get_path
from school_state import school_state

# A path can hold brackets ("reviews_full[1]"), so a citation ends at the last "]]" in a run of "]".
_CITE = re.compile(r"\[\[cite:(.+?)\]\](?!\])")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
# A period after these is part of a name or title, not the end of a sentence ("St. Johns STEM Middle").
_ABBREVIATIONS = ("st.", "mt.", "ft.", "dr.", "mr.", "mrs.", "ms.", "jr.", "sr.")


def split_sentences(text: str) -> list[str]:
    parts: list[str] = []
    for part in _SENTENCE.split(text):
        if parts and parts[-1].casefold().endswith(_ABBREVIATIONS):
            parts[-1] = f"{parts[-1]} {part}"
        else:
            parts.append(part)
    return parts


def citations_in(text: str) -> list[str]:
    return _CITE.findall(text or "")


def allowed_citations(records: list[EvidenceRecord], school: dict | None = None) -> set[str]:
    allowed: set[str] = set()
    for record in records:
        if record.source:
            allowed.add(record.source.path)
        allowed.update(record.review_ids)
        allowed.update(record.post_ids)
        allowed.update(record.missing_paths)
        if record.conflict:
            allowed.add(record.conflict.path)
    rules = funding_rules() if school is None else funding_rules_for(school_state(school))
    for rule in rules.values():
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
        r"([.!?])(\s*)((?:\[\[cite:.+?\]\](?!\])\s*)+)",
        lambda match: f" {match.group(3).strip()}{match.group(1)}{match.group(2)}",
        text,
    )


def validate_text(text: str, allowed: set[str]) -> str:
    if not text:
        return ""
    kept = []
    for sentence in split_sentences(_attach_trailing_cites(text).strip()):
        cites = citations_in(sentence)
        if cites and all(cite in allowed for cite in cites):
            kept.append(sentence.strip())
    return " ".join(kept)


def strip_cites(text: str) -> str:
    cleaned = _CITE.sub("", text or "")
    cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


# Fact check for model-written text. Citations prove where a sentence came from;
# this proves its numbers and times are in that source.
_TIME_MERIDIEM = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s?m\b\.?", re.IGNORECASE)
_TIME_CLOCK = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _time(hour: int, minute: int) -> str:
    return f"t:{hour % 24:02d}:{minute:02d}"


def number_claims(text: str) -> list[set[str]]:
    """Each number or time in the text, as the set of readings it could mean."""
    rest = _CITE.sub(" ", str(text))
    claims: list[set[str]] = []

    def meridiem(match: re.Match) -> str:
        hour, minute = int(match.group(1)) % 12, int(match.group(2) or 0)
        if match.group(3).lower() == "p":
            hour += 12
        claims.append({_time(hour, minute)})
        return " "

    def clock(match: re.Match) -> str:
        hour, minute = int(match.group(1)), int(match.group(2))
        claims.append({_time(hour, minute), _time(hour + 12, minute)} if hour < 12 else {_time(hour, minute)})
        return " "

    rest = _TIME_MERIDIEM.sub(meridiem, rest)
    rest = _TIME_CLOCK.sub(clock, rest)
    for token in _NUMBER.findall(rest):
        claims.append({f"n:{float(token.replace(',', '')):g}"})
    return claims


def known_numbers(values: list) -> set[str]:
    """Every reading of every number or time that appears in trusted values."""
    known: set[str] = set()
    for value in values:
        if value is None:
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            for claim in number_claims(str(item)):
                known |= claim
    return known


def validate_model_text(text: str, facts: dict[str, set[str]], extra: set[str]) -> str:
    """Keep sentences whose citations exist and whose numbers appear in what they cite.

    `facts` maps each citable path to the number readings in its trusted values.
    `extra` holds readings any sentence may use, such as the parent's own criteria.
    """
    kept = []
    for sentence in split_sentences(validate_text(text, set(facts))):
        if not sentence:
            continue
        allowed = set(extra)
        for cite in citations_in(sentence):
            allowed |= facts[cite]
        if all(claim & allowed for claim in number_claims(sentence)):
            kept.append(sentence)
    return " ".join(kept)
