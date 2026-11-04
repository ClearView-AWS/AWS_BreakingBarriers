"""Decide which questions are worth asking. The model only words them later."""

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
DEFAULT_CITY = "Seattle"
DEFAULT_GRADE = "m"


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
    """Return the first question that applies, or None. Kept for refine (max 1)."""
    questions = choose_questions(criteria, asked, search_fn, scored, limit=1)
    return questions[0] if questions else None


def choose_questions(
    criteria: list[Criterion],
    asked: set[str],
    search_fn,
    scored: list[dict] | None = None,
    limit: int = 3,
    *,
    include_unknown_rule: bool = True,
) -> list[dict]:
    """Return up to `limit` questions in plan order (location → grade → ambiguity → unknown → unmapped)."""
    found: list[dict] = []
    seen = set(asked)

    def take(question: dict | None) -> bool:
        if not question or question["id"] in seen:
            return len(found) >= limit
        found.append(question)
        seen.add(question["id"])
        return len(found) >= limit

    locations = [c for c in criteria if c.kind == "location"]
    grades = [c for c in criteria if c.kind == "grade"]

    if not locations and take(
        {
            "id": "q:location",
            "reason": "missing_location",
            "text": "Which city should I search?",
            "options": [{"id": city, "label": city} for city in CITY_OPTIONS],
            "default": DEFAULT_CITY,
        }
    ):
        return found

    if any(c.ambiguities and c.kind == "location" for c in locations) and take(
        {
            "id": "q:location_ambiguity",
            "reason": "ambiguous_location",
            "text": (
                f"{locations[0].value} is in more than one state. "
                "This prototype only has Seattle schools in Washington. Search Washington?"
            ),
            "options": [
                {"id": "washington", "label": "Yes, Washington"},
                {"id": "other", "label": "A different state"},
            ],
            "default": "washington",
        }
    ):
        return found

    if not grades and take(
        {
            "id": "q:grade",
            "reason": "missing_grade",
            "text": "Which grades do you need?",
            "options": [{"id": code, "label": label} for code, label in GRADE_OPTIONS],
            "default": DEFAULT_GRADE,
        }
    ):
        return found

    # Ambiguous criteria: ask only when the two readings change the top 10.
    candidates = []
    for criterion in criteria:
        if criterion.kind != "need" or not criterion.ambiguities:
            continue
        if criterion.resolved_reading:
            continue
        question_id = f"q:amb:{criterion.id}"
        if question_id in seen:
            continue
        ambiguity = criterion.ambiguities[0]
        option_ids = ambiguity.option_ids or []
        if len(option_ids) < 2:
            continue
        sets = []
        for option_id in option_ids:
            readings = {criterion.id: option_id}
            probe = criterion.model_copy(update={"resolved_reading": option_id})
            probed = [probe if item.id == criterion.id else item for item in criteria]
            sets.append(set(_top_ids(search_fn, probed, readings)))
        overlap = _jaccard(sets[0], sets[1])
        if overlap < 0.6:
            candidates.append((criterion.strength == "require", -overlap, question_id, criterion, ambiguity))
    candidates.sort(key=lambda row: (row[0], row[1]), reverse=True)
    for _, _, question_id, criterion, ambiguity in candidates:
        labels = ambiguity.options
        default = ambiguity.default if ambiguity.default in (ambiguity.option_ids or []) else (ambiguity.option_ids or [None])[0]
        if take(
            {
                "id": question_id,
                "reason": "ambiguous_reading",
                "criterion_id": criterion.id,
                "text": ambiguity.question or f"Which reading of {criterion.text} should I use?",
                "options": [
                    {"id": option_id, "label": label}
                    for option_id, label in zip(ambiguity.option_ids, labels)
                ],
                "default": default,
                "assumption": _assumption(criterion, ambiguity),
            }
        ):
            return found

    if include_unknown_rule:
        top = (scored or [])[:10]
        if top:
            for criterion in criteria:
                if criterion.strength != "require" or criterion.kind != "need":
                    continue
                question_id = f"q:unknown:{criterion.id}"
                if question_id in seen:
                    continue
                unknown = 0
                for school in top:
                    evidence = _evidence_for(school, criterion.id)
                    if evidence is None or evidence.get("status") == "unknown":
                        unknown += 1
                if unknown / len(top) >= 0.3:
                    spec = needs().get(criterion.need or "", {})
                    template = spec.get("ask_if_unknown") or "This is unknown for {n} of these schools. Is it a must-have?"
                    if take(
                        {
                            "id": question_id,
                            "reason": "unknown_require",
                            "criterion_id": criterion.id,
                            "text": template.replace("{n}", str(unknown)),
                            "options": [
                                {"id": "keep", "label": "Keep it as a must-have"},
                                {"id": "prefer", "label": "Make it a preference"},
                                {"id": "ask_schools", "label": "Ask the schools"},
                            ],
                            "default": "keep",
                        }
                    ):
                        return found

    for criterion in criteria:
        if criterion.need is not None or criterion.kind != "need":
            continue
        question_id = f"q:unmapped:{criterion.id}"
        if question_id in seen:
            continue
        offers = unmapped_offers()
        default = offers[0][0] if offers else None
        if take(
            {
                "id": question_id,
                "reason": "unmapped",
                "criterion_id": criterion.id,
                "text": (
                    f"I don't rate schools on \"{criterion.text}\". "
                    "I can look at needs the data actually supports."
                ),
                "options": [{"id": need_id, "label": label} for need_id, label in offers],
                "default": default,
            }
        ):
            return found

    return found


def apply_question_defaults(session: dict, questions: list[dict], state: dict, apply_answer) -> list[str]:
    """Apply each question's default via the pipeline answer handler. Returns assumption notes."""
    assumptions: list[str] = []
    for question in questions:
        default = question.get("default")
        options = question.get("options") or []
        if default is None and options:
            default = options[0]["id"]
        if default is None:
            continue
        apply_answer(session, {"question_id": question["id"], "option_id": default}, state)
        assumption = question.get("assumption")
        if assumption:
            assumptions.append(assumption)
        else:
            label = next((opt["label"] for opt in options if opt["id"] == default), str(default))
            assumptions.append(f"I assumed {label}.")
    return assumptions


def brief_payload(criteria: list[Criterion], *, approved: bool, assumptions: list[str] | None = None) -> dict:
    must, nice, avoid = [], [], []
    for criterion in criteria:
        if criterion.kind in {"location", "grade", "school_type"} or (
            criterion.kind == "need" and criterion.strength == "require"
        ):
            must.append(criterion.id)
        elif criterion.kind == "need" and criterion.strength == "prefer":
            nice.append(criterion.id)
        elif criterion.kind == "need" and criterion.strength == "avoid":
            avoid.append(criterion.id)
    return {
        "must": must,
        "nice": nice,
        "avoid": avoid,
        "assumptions": assumptions or [],
        "approved": approved,
    }


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
