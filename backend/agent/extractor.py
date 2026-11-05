"""Turn a parent message into criteria. Phrase matching is code; Bedrock may draft the same JSON."""

from __future__ import annotations

import logging
import re

from catalog import needs
from contracts import Ambiguity, Criterion, EngineStep, MappingInfo
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
_REQUIRE = ("must", "required", "need", "needs", "gotta")
_PREFER = ("prefer", "ideally", "bonus", "nice", "plus")
_UNTIL = re.compile(r"\buntil (\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b")
_GRADE_CODES = {code for _, code, _ in _GRADE}
_TYPE_VALUES = {value for _, value, _ in _TYPE}
_STRENGTHS = {"require", "prefer", "avoid"}
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_TIMED_NEEDS = {"after_care", "extended_day"}

log = logging.getLogger(__name__)


def extract(text: str, cities: list[str] | None = None) -> tuple[list[Criterion], EngineStep]:
    from agent.bedrock_client import maybe_bedrock_criteria

    cities = cities or []
    drafted, step = maybe_bedrock_criteria(text, cities)
    if drafted is not None:
        return _with_ids(_from_draft(drafted, text, cities)), step
    return _with_ids(_rules(text, cities)), step


def _from_draft(items: list[dict], text: str, cities: list[str]) -> list[Criterion]:
    """Keep only draft items whose codes, cities and need ids exist in the catalog."""
    normalized = normalize(text)
    by_city = {city.casefold(): city.title() for city in AMBIGUOUS_CITIES}
    by_city.update({city.casefold(): city for city in cities})
    found = []
    for item in items:
        criterion = _draft_criterion(item, normalized, by_city)
        if criterion is None:
            log.warning("dropped bedrock criterion: %s", item)
            continue
        found.append(criterion)
    return _dedupe(found)


def _draft_criterion(item: dict, normalized: str, by_city: dict[str, str]) -> Criterion | None:
    kind = item.get("kind")
    value = item.get("value")
    text = str(item.get("text") or "").strip()
    if kind == "grade" and value in _GRADE_CODES:
        return Criterion(id="grade", text=text or value, kind="grade", value=value, strength="require")
    if kind == "location" and isinstance(value, str) and value.casefold() in by_city:
        return _location(by_city[value.casefold()])
    if kind == "school_type" and value in _TYPE_VALUES:
        return Criterion(id="type", text=text or value, kind="school_type", value=value, strength="require")
    if kind != "need" or not text:
        return None
    need_id = item.get("need")
    if need_id is None:
        return _unmapped(text)
    strength = item.get("strength")
    if need_id not in needs() or strength not in _STRENGTHS:
        return None
    # Prefer clear lexical markers over the model when the parent said must/prefer/avoid.
    lexical = _lexical_strength(normalized, text, need_id)
    if lexical:
        strength = lexical
    params = {}
    until = (item.get("params") or {}).get("until")
    if need_id in _TIMED_NEEDS and isinstance(until, str) and _TIME.match(until):
        params["until"] = until
    return _need(need_id, text, strength, params, _explicit_reading(normalized, need_id))


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
        found.append(_location(city))

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
        strength = _strength(normalized, start, end, needs()[need_id])
        params = {}
        if until_value and need_id in _TIMED_NEEDS:
            params["until"] = until_value
        found.append(_need(need_id, phrase, strength, params, _explicit_reading(normalized, need_id)))

    for pattern, label in _UNMAPPED:
        match = re.search(pattern, normalized)
        if not match or _overlaps(match.start(), match.end(), consumed):
            continue
        consumed.append((match.start(), match.end()))
        found.append(_unmapped(label))
    return _dedupe(found)


def _location(city: str) -> Criterion:
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
    return Criterion(
        id="location",
        text=city,
        kind="location",
        value=city,
        strength="require",
        ambiguities=ambiguities,
    )


def _need(need_id: str, phrase: str, strength: str, params: dict, reading: str | None) -> Criterion:
    spec = needs()[need_id]
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
    return Criterion(
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


def _unmapped(text: str) -> Criterion:
    return Criterion(
        id="unmapped",
        text=text,
        need=None,
        strength="prefer",
        kind="need",
        mapping=MappingInfo(score=0.0, runner_up=None, margin=0.0),
    )


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
        phrases = list(spec.get("phrases") or [])
        label = spec.get("label")
        if label and label not in phrases:
            phrases.append(label)
        for phrase in phrases:
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
    marked = _strength_from_span(normalized, start, end)
    if marked:
        return marked
    return spec.get("default_strength") or "prefer"


# Post-nominal cues only ("gifted is a plus"). A following "prefer …" starts the next need.
_AFTER_PREFER = ("plus", "bonus", "nice")
_AFTER_REQUIRE = ("required",)


def _strength_from_span(normalized: str, start: int, end: int) -> str | None:
    """Closest strength cue wins. After-side only allows post-nominal words."""
    before = normalized[max(0, start - 48) : start].split()[-6:]
    after = normalized[end : end + 32].split()[:4]
    # (distance, after-first so post-nominal beats a same-distance earlier must, rank, strength)
    candidates: list[tuple[int, int, int, str]] = []
    rank = {"avoid": 0, "require": 1, "prefer": 2}
    for index, word in enumerate(reversed(before)):
        if word in _AVOID:
            candidates.append((index, 1, rank["avoid"], "avoid"))
        elif word in _REQUIRE:
            candidates.append((index, 1, rank["require"], "require"))
        elif word in _PREFER:
            candidates.append((index, 1, rank["prefer"], "prefer"))
    for index, word in enumerate(after):
        if word in _AFTER_REQUIRE:
            candidates.append((index, 0, rank["require"], "require"))
        elif word in _AFTER_PREFER:
            candidates.append((index, 0, rank["prefer"], "prefer"))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][3]


def _lexical_strength(normalized: str, phrase: str, need_id: str) -> str | None:
    """Strength from nearby must/prefer/avoid words, or None if unmarked."""
    candidates = [phrase, *(needs().get(need_id, {}).get("phrases") or [])]
    for candidate in candidates:
        pn = normalize(candidate or "")
        if not pn:
            continue
        start = normalized.find(pn)
        if start < 0:
            continue
        marked = _strength_from_span(normalized, start, start + len(pn))
        if marked:
            return marked
    return None


def _until_param(text: str) -> str | None:
    light = text.casefold().replace("-", " ")
    match = _UNTIL.search(light)
    if not match:
        return None
    hour = int(match.group(1))
    minute = match.group(2) or "00"
    meridiem = match.group(3) or ""
    # "Until 5:30" with no am/pm is after school: the timed needs (after-school care, extended
    # day) end in the afternoon, so 1 to 11 means pm.
    if (meridiem == "pm" or not meridiem) and 1 <= hour < 12:
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
