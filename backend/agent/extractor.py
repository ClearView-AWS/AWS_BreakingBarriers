"""Turn a parent message into criteria. Phrase matching is code; Bedrock may draft the same JSON."""

from __future__ import annotations

import re

from catalog import needs
from contracts import Ambiguity, Criterion, MappingInfo
from mapping.mapper import map_phrase, normalize

AMBIGUOUS_CITIES = {
    "springfield",
    "portland",
    "columbus",
    "greenville",
    "franklin",
    "clinton",
    "madison",
    "georgetown",
}

_GRADE = [
    (r"\bmiddle schools?\b", "m", "middle school"),
    (r"\bescuela intermedia\b", "m", "escuela intermedia"),
    (r"\bjunior high\b", "m", "junior high"),
    (r"\belementary schools?\b", "e", "elementary school"),
    (r"\bescuela primaria\b", "e", "escuela primaria"),
    (r"\bhigh schools?\b", "h", "high school"),
    (r"\bescuela secundaria\b", "h", "escuela secundaria"),
    (r"\bpreparatoria\b", "h", "preparatoria"),
    (r"\bpre k\b|\bprek\b|\bpreschool\b|\bpreescolar\b", "p", "pre-k"),
    (r"\belementary\b", "e", "elementary"),
    (r"\bmiddle\b", "m", "middle"),
]
_TYPE = [
    (r"\bcharter\b", "charter", "charter"),
    (r"\bprivate\b", "private", "private"),
    (r"\bpublic\b", "public", "public"),
]
_UNMAPPED = [
    (r"\bhow liberal\b", "how liberal"),
    (r"\bhow conservative\b", "how conservative"),
    (r"\bliberal\b", "liberal"),
    (r"\bconservative\b", "conservative"),
    (r"\bpolitic\w*\b", "politics"),
]
_AVOID = ("not", "no", "without", "avoid", "dont", "don't")
_REQUIRE = ("must", "required", "need", "needs")
_PREFER = ("prefer", "ideally", "bonus")
_UNTIL = re.compile(r"\buntil (\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b")


def extract(text: str, cities: list[str] | None = None) -> list[Criterion]:
    """Code builds the criteria; Bedrock can only add phrases the rules missed.

    Each phrase the model drafts goes through the same rules, so it comes back
    as a city, grade, type or a need from needs.yaml, never as raw model text.
    A drafted phrase the rules cannot map is dropped (the full message already
    went through the unmapped-phrase checks).
    """
    from agent.bedrock_client import maybe_bedrock_criteria

    cities = cities or []
    found = _rules(text, cities)
    drafted = maybe_bedrock_criteria(text)
    if drafted:
        found = _add_drafted(found, drafted, cities)
    return _with_ids(found)


def _criterion_key(criterion: Criterion) -> tuple:
    if criterion.kind == "need":
        return ("need", criterion.need or normalize(criterion.text))
    return (criterion.kind,)


def _add_drafted(found: list[Criterion], drafted: list[Criterion], cities: list[str]) -> list[Criterion]:
    keys = {_criterion_key(c) for c in found}
    out = list(found)
    for item in drafted:
        for mapped in _rules(item.text, cities):
            if mapped.kind == "need" and not mapped.need:
                continue
            key = _criterion_key(mapped)
            if key in keys:
                continue
            keys.add(key)
            if mapped.kind == "need" and item.strength in {"require", "prefer", "avoid"}:
                mapped = mapped.model_copy(update={"strength": item.strength})
            out.append(mapped)
    return out


def _with_ids(criteria: list[Criterion]) -> list[Criterion]:
    numbered = []
    for index, criterion in enumerate(criteria, start=1):
        numbered.append(criterion.model_copy(update={"id": f"c{index}"}))
    return numbered


def _rules(text: str, cities: list[str]) -> list[Criterion]:
    normalized = normalize(text)
    until_value = _until_param(text)
    found: list[Criterion] = []
    consumed: list[tuple[int, int]] = []

    for pattern, code, label in _GRADE:
        if re.search(pattern, normalized):
            found.append(Criterion(id="grade", text=label, kind="grade", value=code, strength="require"))
            break

    city = _find_city(normalized, cities)
    if city:
        ambiguities = []
        if city.casefold() in AMBIGUOUS_CITIES:
            ambiguities.append(
                Ambiguity(
                    kind="place",
                    options=[f"{city}, Florida", "A different state"],
                    option_ids=["florida", "other"],
                    question=f"Which {city} do you mean?",
                )
            )
        found.append(
            Criterion(
                id="location",
                text=city,
                kind="location",
                value=city,
                strength="require",
                ambiguities=ambiguities,
            )
        )

    for pattern, value, label in _TYPE:
        if re.search(pattern, normalized):
            found.append(
                Criterion(id="type", text=label, kind="school_type", value=value, strength="require")
            )
            break

    religious = re.search(r"\b(?:not|no|non|without|avoid|dont)\b(?:\s+\w+){0,3}\s+religios\w*", normalized)
    if religious:
        consumed.append((religious.start(), religious.end()))
        spec = needs()["non_religious"]
        hit = map_phrase("not religious")
        found.append(
            Criterion(
                id="non_religious",
                text=religious.group(0),
                need="non_religious",
                strength="require",
                kind="need",
                mapping=MappingInfo(score=hit.score, runner_up=hit.runner_up, margin=hit.margin),
            )
        )

    spans = _need_spans(normalized)
    for start, end, need_id, phrase in spans:
        if _overlaps(start, end, consumed):
            continue
        consumed.append((start, end))
        spec = needs()[need_id]
        strength = _strength(normalized, start, end, spec)
        params = {}
        if until_value and need_id in {"after_care", "extended_day"}:
            params["until"] = until_value
        reading = _explicit_reading(normalized, need_id)
        ambiguities = []
        if spec.get("ambiguities") and not reading:
            for item in spec["ambiguities"]:
                options = item.get("options") or []
                ambiguities.append(
                    Ambiguity(
                        kind=item.get("kind") or "definition",
                        options=[opt.get("label") for opt in options],
                        option_ids=[opt.get("id") for opt in options],
                        question=item.get("question"),
                        default=item.get("default"),
                    )
                )
        hit = map_phrase(phrase)
        found.append(
            Criterion(
                id=need_id,
                text=phrase,
                need=need_id,
                strength=strength,
                params=params,
                kind="need",
                mapping=MappingInfo(score=hit.score, runner_up=hit.runner_up, margin=hit.margin),
                ambiguities=ambiguities,
                resolved_reading=reading,
            )
        )

    for pattern, label in _UNMAPPED:
        match = re.search(pattern, normalized)
        if not match or _overlaps(match.start(), match.end(), consumed):
            continue
        consumed.append((match.start(), match.end()))
        found.append(
            Criterion(
                id="unmapped",
                text=label,
                need=None,
                strength="prefer",
                kind="need",
                mapping=MappingInfo(score=0.0, runner_up=None, margin=0.0),
            )
        )
    return _dedupe(found)


def _dedupe(found: list[Criterion]) -> list[Criterion]:
    kept: list[Criterion] = []
    index_by_key: dict[str, int] = {}
    rank = {"require": 3, "avoid": 2, "prefer": 1}
    for criterion in found:
        if criterion.kind != "need" or not criterion.need:
            kept.append(criterion)
            continue
        key = criterion.need
        if key not in index_by_key:
            index_by_key[key] = len(kept)
            kept.append(criterion)
            continue
        current = kept[index_by_key[key]]
        if rank[criterion.strength] > rank[current.strength]:
            kept[index_by_key[key]] = criterion.model_copy(
                update={"ambiguities": current.ambiguities or criterion.ambiguities}
            )
    return kept


def _find_city(normalized: str, cities: list[str]) -> str | None:
    ordered = sorted(set(cities) | AMBIGUOUS_CITIES, key=len, reverse=True)
    for city in ordered:
        token = normalize(city)
        if token and re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", normalized):
            # Keep the display name from the catalog when we have one.
            for original in cities:
                if normalize(original) == token:
                    return original
            return city.title()
    return None


def _need_spans(normalized: str) -> list[tuple[int, int, str, str]]:
    spans = []
    for need_id, spec in needs().items():
        for phrase in spec.get("phrases") or []:
            phrase_n = normalize(phrase)
            if not phrase_n:
                continue
            match = re.search(rf"(?<![a-z0-9]){re.escape(phrase_n)}(?![a-z0-9])", normalized)
            if match:
                spans.append((match.start(), match.end(), need_id, phrase_n))
    spans.sort(key=lambda row: (-(row[1] - row[0]), row[0]))
    return spans


def _overlaps(start: int, end: int, consumed: list[tuple[int, int]]) -> bool:
    return any(not (end <= left or start >= right) for left, right in consumed)


def _strength(normalized: str, start: int, end: int, spec: dict) -> str:
    before = normalized[max(0, start - 48) : start].split()[-6:]
    after = normalized[end : end + 32].split()[:4]
    if any(word in before for word in _AVOID):
        return "avoid"
    if any(word in before or word in after for word in _REQUIRE):
        return "require"
    if any(word in before for word in _PREFER):
        return "prefer"
    return spec.get("default_strength") or "prefer"


def _until_param(text: str) -> str | None:
    light = text.casefold().replace("-", " ")
    match = _UNTIL.search(light)
    if not match:
        return None
    hour = int(match.group(1))
    minute = match.group(2) or "00"
    meridiem = match.group(3) or ""
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}"


def _explicit_reading(normalized: str, need_id: str) -> str | None:
    if need_id != "after_care":
        return None
    if re.search(r"\b(on campus|at the school|on site|on-site)\b", normalized):
        return "on_site"
    if re.search(r"\b(nearby program|off campus|nearby is fine)\b", normalized):
        return "nearby_ok"
    return None
