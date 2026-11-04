"""Decide whether one question is worth asking. The model only words it later."""

from __future__ import annotations

from catalog import needs, unmapped_offers
from contracts import Criterion

GRADE_OPTIONS = [
    ("p", "Pre-K"),
    ("e", "Elementary"),
    ("m", "Middle"),
    ("h", "High"),
]
CITY_OPTIONS = ["Seattle"]  # the only city with schools in this prototype


def _top_ids(search_fn, criteria: list[Criterion], readings: dict) -> list[str]:
    rows = search_fn(criteria, readings)
    return [row["id"] if isinstance(row, dict) else row for row in rows][:10]


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)


def choose_question(
    criteria: list[Criterion],
    asked: set[str],
    search_fn,
    scored: list[dict] | None = None,
) -> dict | None:
    """Return the first question that applies, or None.

    search_fn(criteria, readings) -> ranked school dicts or ids.
    scored is the current top evidence list, used for the unknown-must check.
    """
    locations = [c for c in criteria if c.kind == "location"]
    grades = [c for c in criteria if c.kind == "grade"]

    if not locations and "q:location" not in asked:
        return {
            "id": "q:location",
            "reason": "missing_location",
            "text": "Which city should I search?",
            "options": [{"id": city, "label": city} for city in CITY_OPTIONS],
        }
    if any(c.ambiguities and c.kind == "location" for c in locations) and "q:location_ambiguity" not in asked:
        city = locations[0].value
        return {
            "id": "q:location_ambiguity",
            "reason": "ambiguous_location",
            "text": f"{city} is in more than one state. This prototype only has Seattle schools in Washington. Search Washington?",
            "options": [
                {"id": "washington", "label": "Yes, Washington"},
                {"id": "other", "label": "A different state"},
            ],
        }
    if not grades and "q:grade" not in asked:
        return {
            "id": "q:grade",
            "reason": "missing_grade",
            "text": "Which grades do you need?",
            "options": [{"id": code, "label": label} for code, label in GRADE_OPTIONS],
        }

    # Ambiguous criteria: ask only when the two readings change the top 10.
    candidates = []
    for criterion in criteria:
        if criterion.kind != "need" or not criterion.ambiguities:
            continue
        if criterion.resolved_reading:
            continue
        question_id = f"q:amb:{criterion.id}"
        if question_id in asked:
            continue
        ambiguity = criterion.ambiguities[0]
        option_ids = ambiguity.option_ids or []
        if len(option_ids) < 2:
            continue
        sets = []
        for option_id in option_ids:
            readings = {criterion.id: option_id}
            # Temporarily score this reading without writing it onto the criterion.
            probe = criterion.model_copy(update={"resolved_reading": option_id})
            probed = [probe if item.id == criterion.id else item for item in criteria]
            sets.append(set(_top_ids(search_fn, probed, readings)))
        overlap = _jaccard(sets[0], sets[1])
        if overlap < 0.6:
            candidates.append((criterion.strength == "require", -overlap, question_id, criterion, ambiguity))
    if candidates:
        candidates.sort(key=lambda row: (row[0], row[1]), reverse=True)
        _, _, question_id, criterion, ambiguity = candidates[0]
        labels = ambiguity.options
        return {
            "id": question_id,
            "reason": "ambiguous_reading",
            "criterion_id": criterion.id,
            "text": ambiguity.question or f"Which reading of {criterion.text} should I use?",
            "options": [
                {"id": option_id, "label": label}
                for option_id, label in zip(ambiguity.option_ids, labels)
            ],
            "assumption": _assumption(criterion, ambiguity),
        }

    top = (scored or [])[:10]
    if top:
        for criterion in criteria:
            if criterion.strength != "require" or criterion.kind != "need":
                continue
            question_id = f"q:unknown:{criterion.id}"
            if question_id in asked:
                continue
            unknown = 0
            for school in top:
                evidence = _evidence_for(school, criterion.id)
                if evidence is None or evidence.get("status") == "unknown":
                    unknown += 1
            if unknown / len(top) >= 0.3:
                spec = needs().get(criterion.need or "", {})
                template = spec.get("ask_if_unknown") or "This is unknown for {n} of these schools. Is it a must-have?"
                return {
                    "id": question_id,
                    "reason": "unknown_require",
                    "criterion_id": criterion.id,
                    "text": template.replace("{n}", str(unknown)),
                    "options": [
                        {"id": "keep", "label": "Keep it as a must-have"},
                        {"id": "prefer", "label": "Make it a preference"},
                        {"id": "ask_schools", "label": "Ask the schools"},
                    ],
                }

    for criterion in criteria:
        if criterion.need is not None or criterion.kind != "need":
            continue
        question_id = f"q:unmapped:{criterion.id}"
        if question_id in asked:
            continue
        offers = unmapped_offers()
        return {
            "id": question_id,
            "reason": "unmapped",
            "criterion_id": criterion.id,
            "text": (
                f"I don't rate schools on \"{criterion.text}\". "
                "I can look at needs the data actually supports."
            ),
            "options": [{"id": need_id, "label": label} for need_id, label in offers],
        }
    return None


def _assumption(criterion: Criterion, ambiguity) -> str:
    default = ambiguity.default
    label = "the first option"
    if default and default in ambiguity.option_ids:
        label = ambiguity.options[ambiguity.option_ids.index(default)]
    return f"I assumed {label.lower()} for {criterion.text}. Change it?"


def _evidence_for(school: dict, criterion_id: str) -> dict | None:
    for row in school.get("evidence") or []:
        if isinstance(row, dict) and row.get("criterion_id") == criterion_id:
            return row
        if hasattr(row, "criterion_id") and row.criterion_id == criterion_id:
            return row.model_dump()
    return None
