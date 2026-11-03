"""In-memory hybrid search.

The OpenSearch DSL is still built for every turn. This engine applies the same
hard filters and uses boosts only to rank. It does not drop a school because a
rated field is missing. Keyword and vector scores are capped so they cannot
outrank a real need boost.
"""

from __future__ import annotations

import re

from evidence.engine import field_meets, program_support
from mapping.embedder import cosine, embed_hash
from mapping.mapper import normalize
from search.geo import distance_from_city
from search.query import build_query

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "in", "with", "and", "or", "for", "of", "to", "is", "are",
    "school", "schools", "me", "my", "i", "want", "need", "looking",
}


def search_text_for(school: dict) -> str:
    parts = [
        school.get("name") or "",
        school.get("city") or "",
        school.get("entity_type") or "",
        " ".join(school.get("level_codes") or []),
    ]
    esp = school.get("esp_text") or []
    if isinstance(esp, list):
        parts.extend(str(x) for x in esp)
    elif esp:
        parts.append(str(esp))
    osp = school.get("osp") or {}
    if isinstance(osp, dict):
        for key, value in osp.items():
            parts.append(key.replace("_", " "))
            if isinstance(value, list):
                parts.extend(str(v) for v in value)
            elif value is not None:
                parts.append(str(value))
    if school.get("summary_rating") is not None:
        parts.append(f"summary rating {school['summary_rating']}")
    reviews = school.get("reviews_text") or []
    parts.extend(str(r)[:240] for r in reviews[:3])
    return " ".join(parts)


def _keyword_score(query_text: str, document: str) -> float:
    tokens = [tok for tok in _TOKEN.findall(normalize(query_text)) if tok not in _STOP and len(tok) > 2]
    if not tokens:
        return 0.0
    haystack = set(_TOKEN.findall(document.casefold()))
    hits = sum(1 for tok in tokens if tok in haystack)
    return min(0.2, 0.05 * hits)


def _vector_score(query_text: str, document: str) -> float:
    if not query_text.strip():
        return 0.0
    return min(0.2, max(0.0, cosine(embed_hash(query_text), embed_hash(document)) * 0.2))


def _need_boost(school: dict, programs: list[dict], criterion, reading: str | None) -> float:
    need = criterion.need
    if need == "after_care":
        onsite = field_meets(school, "after_care")
        support = program_support(school, programs, ["after school", "after-school", "homework help", "afterschool"])
        live = support == "live"
        if (reading or "on_site") == "nearby_ok":
            score = 5.0 if (onsite or live) else 0.0
            if onsite:
                score += 0.5
            return score
        return 5.5 if onsite else 0.0
    if need == "stem":
        return 5.0 if field_meets(school, "stem") else 0.0
    if need and field_meets(school, need):
        return 2.0
    return 0.0


def passes_hard_filters(school: dict, criteria: list) -> bool:
    for criterion in criteria:
        if criterion.kind == "location" and criterion.value:
            if str(school.get("city") or "").casefold() != str(criterion.value).casefold():
                return False
        elif criterion.kind == "grade" and criterion.value:
            if criterion.value not in (school.get("level_codes") or []):
                return False
        elif criterion.kind == "school_type" and criterion.value:
            if school.get("entity_type") != criterion.value:
                return False
    return True


def search_schools(
    schools: list[dict],
    programs: list[dict],
    criteria: list,
    query_text: str = "",
    readings: dict | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Return hard-filter matches, best boost first.

    `limit` trims by boost score only. Missing data does not remove a school
    ahead of that trim. Pass limit=None to keep every school that matches
    location, grade, and type.
    """
    readings = readings or {}
    # Build the DSL even though the local engine applies it itself, so a bad
    # filter shows up in tests and in logs.
    build_query(criteria, query_text)
    matched = []
    for school in schools:
        if not passes_hard_filters(school, criteria):
            continue
        document = search_text_for(school)
        # Capped so free-text similarity cannot flip a need boost.
        score = min(0.15, _keyword_score(query_text, document) + _vector_score(query_text, document))
        for criterion in criteria:
            if criterion.kind != "need":
                continue
            reading = readings.get(criterion.id) or criterion.resolved_reading
            score += _need_boost(school, programs, criterion, reading)
        city = next((c.value for c in criteria if c.kind == "location"), None)
        distance = distance_from_city(school, city)
        school["_distance_miles"] = distance
        matched.append((score, school.get("name") or "", school))
    matched.sort(key=lambda row: (-row[0], row[1]))
    if limit is not None:
        matched = matched[:limit]
    return [row[2] for row in matched]
