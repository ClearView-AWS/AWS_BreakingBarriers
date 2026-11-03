"""Build one evidence record per school and criterion from fields, reviews, programs, and websites."""

from __future__ import annotations

from datetime import date
from typing import Any

from catalog import funding_rules, needs
from contracts import Conflict, EvidenceRecord, Source
from evidence.reviews import review_status
from evidence.status import (
    apply_rule,
    as_list,
    better,
    downgrade_for_age,
    op_matches,
    parse_clock,
    parse_date,
    unwrap,
)
from gaps.websites import website_facts
from runtime_config import TODAY
from search.geo import miles_between

RELIGIOUS_WORDS = (
    "christian",
    "catholic",
    "jewish",
    "islamic",
    "islam",
    "baptist",
    "lutheran",
    "episcopal",
    "adventist",
    "jesuit",
    "hebrew",
)
PROGRAM_RADIUS_MILES = 3.0


def get_path(document: dict, path: str) -> Any:
    current: Any = document
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _overlay_value(overlays: dict | None, path: str) -> dict | None:
    if not overlays:
        return None
    found = overlays.get(path)
    return found if isinstance(found, dict) else None


def _signal_meta(school: dict, rule: dict, overlay: dict | None) -> tuple[str | None, date | None]:
    if overlay:
        confidence = overlay.get("confidence") or "high"
        return confidence, parse_date(overlay.get("as_of")) or TODAY
    signal_name = rule.get("signal")
    signal = get_path(school, signal_name) if signal_name else None
    if isinstance(signal, dict):
        confidence = signal.get("confidence")
        as_of = parse_date(signal.get("source_generated_at"))
        return (str(confidence) if confidence else "medium"), as_of or parse_date(school.get("created"))
    source = rule.get("source") or "state_data"
    # Profile fields without their own confidence still come from a named source.
    default_confidence = "high" if source == "state_data" else "medium"
    return default_confidence, parse_date(school.get("created")) or TODAY


def _cite(path: str, sentence: str) -> str:
    if f"[[cite:{path}]]" in sentence:
        return sentence
    return f"{sentence} [[cite:{path}]]"


def _clock_label(value: object) -> str:
    minutes = parse_clock(value)
    if minutes is None:
        return str(unwrap(value))
    hour, minute = divmod(minutes, 60)
    suffix = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{hour12}:{minute:02d} {suffix}"


def _programs_for(school: dict, programs: list[dict], phrases: list[str]) -> tuple[list[dict], list[dict]]:
    live: list[dict] = []
    stale: list[dict] = []
    origin = (school.get("_lat"), school.get("_lon"))
    if origin[0] is None:
        return live, stale
    needles = [p.casefold() for p in phrases]
    for program in programs:
        plat, plon = program.get("_lat"), program.get("_lon")
        if plat is None or miles_between(origin, (plat, plon)) > PROGRAM_RADIUS_MILES:
            continue
        blob = " ".join(
            [
                str(program.get("name") or ""),
                str(program.get("description") or ""),
                " ".join(program.get("tag_names") or []),
                str(program.get("program_type") or ""),
            ]
        ).casefold()
        if needles and not any(needle in blob for needle in needles):
            continue
        if _program_is_live(program):
            live.append(program)
        else:
            stale.append(program)
    return live, stale


def _program_is_live(program: dict, today: date | None = None) -> bool:
    today = today or TODAY
    instances = program.get("instances") or []
    if not instances:
        return False
    future = False
    for instance in instances:
        end = parse_date(instance.get("end_date")) or parse_date(instance.get("start_date"))
        status = str(instance.get("status") or "").casefold()
        if status == "past":
            continue
        if end is None or end >= today:
            future = True
    return future


def _reading_allows_program(criterion, need: dict) -> bool:
    if not need.get("program_fill"):
        return False
    ambiguities = need.get("ambiguities") or []
    if not ambiguities:
        return True
    reading = criterion.resolved_reading or ambiguities[0].get("default")
    return reading == "nearby_ok"


def program_support(school: dict, programs: list[dict], phrases: list[str]) -> str:
    """'live', 'stale', or 'none' for programs near the school."""
    live, stale = _programs_for(school, programs, phrases)
    if live:
        return "live"
    if stale:
        return "stale"
    return "none"


def evaluate_criterion(
    school: dict,
    criterion,
    programs: list[dict] | None = None,
    overlays: dict | None = None,
    today: date | None = None,
) -> EvidenceRecord:
    today = today or TODAY
    programs = programs or []
    need_id = criterion.need
    if criterion.kind == "distance":
        return _distance_evidence(school, criterion, today)
    if not need_id or need_id not in needs():
        return EvidenceRecord(
            school_id=school["id"],
            criterion_id=criterion.id,
            status="unknown",
            value=None,
            note="This phrase is not backed by a field yet.",
        )
    spec = needs()[need_id]
    handler = spec.get("handler")
    if handler == "low_cost":
        return _low_cost(school, criterion, today)
    if handler == "non_religious":
        return _non_religious(school, criterion, today)

    params = dict(criterion.params or {})
    best_status = None
    best_path = None
    best_value = None
    best_source = None
    best_confidence = None
    best_as_of = None
    conflict = None

    facts = website_facts(school["id"])
    website_by_path = {fact["path"]: fact for fact in facts}

    for rule in spec.get("evidence") or []:
        path = rule["field"]
        if path == "reviews":
            continue
        overlay = _overlay_value(overlays, path)
        if overlay is not None:
            value = overlay.get("value")
            source_type = "school_reported"
        else:
            value = get_path(school, path)
            source_type = rule.get("source") or "state_data"
        status = apply_rule(rule, value, params)
        confidence, as_of = _signal_meta(school, rule, overlay)
        status = downgrade_for_age(status, confidence, as_of, today)
        site = website_by_path.get(path)
        if site and value is not None and str(unwrap(site.get("value"))) != str(unwrap(value)):
            conflict = Conflict(
                path=path,
                profile_value=unwrap(value) if not isinstance(value, list) else value,
                website_value=site.get("value"),
                as_of=site.get("as_of"),
            )
        if status is None and site and overlay is None:
            site_status = apply_rule(rule, site.get("value"), params)
            if site_status == "confirmed":
                # A school website never confirms. It can only support.
                site_status = "partial"
            if site_status == "partial":
                status = "partial"
                value = site.get("value")
                source_type = "school_website"
                confidence = "medium"
                as_of = parse_date(site.get("as_of")) or today
                path = path
        if status is None:
            continue
        if better(status, best_status) == status and status != best_status:
            best_status = status
            best_path = path
            best_value = unwrap(value) if not isinstance(value, list) else value
            best_source = source_type
            best_confidence = confidence
            best_as_of = as_of
        elif best_status is None:
            best_status = status
            best_path = path
            best_value = unwrap(value) if not isinstance(value, list) else value
            best_source = source_type
            best_confidence = confidence
            best_as_of = as_of

    review_ids: list[str] = []
    reviewed = review_status(school, list(spec.get("review_topics") or []), today)
    if reviewed:
        review_ids = reviewed["review_ids"]
        if reviewed["status"] == "needs_attention" and best_status != "confirmed":
            best_status = "needs_attention"
            best_path = reviewed["review_ids"][0]
            best_source = "parent_reviews"
            best_confidence = "medium"
            best_as_of = parse_date(reviewed.get("newest"))
            best_value = f"{reviewed['topic']}: {reviewed['negative']:.0f} negative-weighted"
        elif reviewed["status"] == "partial" and best_status not in {"confirmed", "needs_attention"}:
            best_status = "partial"
            best_path = reviewed["review_ids"][0]
            best_source = "parent_reviews"
            best_confidence = "medium"
            best_as_of = parse_date(reviewed.get("newest"))
            best_value = f"{reviewed['topic']}: mostly positive"

    phrases = list(spec.get("program_match") or [])
    live, stale = _programs_for(school, programs, phrases) if spec.get("program_fill") else ([], [])
    program_note = ""
    if _reading_allows_program(criterion, spec) and live and best_status in {None, "unknown", "partial", "needs_attention"}:
        program = live[0]
        # The parent accepted a nearby program, and a current program record meets it.
        if best_status != "confirmed":
            best_status = "confirmed"
            best_path = f"programs/{program.get('id')}"
            best_source = "program"
            best_confidence = "high"
            best_as_of = today
            best_value = program.get("name")
            program_note = f"Nearby program: {program.get('name')}."
    elif stale and best_status in {None, "unknown"}:
        program = stale[0]
        program_note = "A nearby program's only sessions are in the past, so it does not count."
        best_path = f"programs/{program.get('id')}"
        best_source = "program"
        best_confidence = "low"
        best_as_of = today
        best_value = program.get("name")

    if best_status is None:
        best_status = "unknown"

    note = _note(spec.get("label") or need_id, best_status, best_value, best_path, program_note, conflict)
    source = None
    if best_path:
        source = Source(
            type=best_source or "state_data",
            path=best_path,
            as_of=best_as_of.isoformat() if best_as_of else None,
            confidence=best_confidence,
        )
    return EvidenceRecord(
        school_id=school["id"],
        criterion_id=criterion.id,
        status=best_status,
        value=_display_value(best_value),
        source=source,
        note=note,
        conflict=conflict,
        review_ids=review_ids,
    )


def _display_value(value: Any) -> Any:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return value


def _note(label: str, status: str, value: Any, path: str | None, extra: str, conflict: Conflict | None) -> str:
    word = {
        "confirmed": "confirmed",
        "partial": "only partly supported",
        "needs_attention": "a miss",
        "unknown": "unknown",
    }[status]
    if status == "unknown":
        sentence = f"{label} is unknown in the school profile"
        if extra:
            sentence = f"{sentence}; {extra.rstrip('.')}"
        sentence += "."
        if path:
            return _cite(path, sentence)
        return sentence
    shown = _display_value(value)
    if path and ("after_school" in path or (isinstance(shown, str) and parse_clock(shown))):
        shown = _clock_label(shown)
    sentence = f"{label} is {word}"
    if shown not in (None, ""):
        sentence += f": {shown}"
    if extra:
        sentence += f"; {extra.rstrip('.')}"
    if conflict:
        sentence += (
            f"; the school website says {conflict.website_value}, which does not match the profile"
        )
    sentence += "."
    if path:
        return _cite(path, sentence)
    return sentence


def _low_cost(school: dict, criterion, today: date) -> EvidenceRecord:
    entity = school.get("entity_type")
    label = "Low cost"
    if entity in {"public", "charter"}:
        note = _cite(
            "entity_type",
            f"{label} is confirmed: {entity} schools in this data are tuition-free.",
        )
        return EvidenceRecord(
            school_id=school["id"],
            criterion_id=criterion.id,
            status="confirmed",
            value="tuition-free",
            source=Source(type="state_data", path="entity_type", as_of=_as_of(school, today), confidence="high"),
            note=note,
        )
    if entity == "private":
        tuition = unwrap(get_path(school, "osp.tuition"))
        rule = funding_rules()["fes_eo"]
        if tuition:
            tuition_text = f"listed tuition is ${tuition} [[cite:osp.tuition]]"
        else:
            tuition_text = "tuition is not listed on the profile"
        note = (
            f"{label} is only partly supported; {tuition_text}; "
            f"you may qualify for the {rule['name']}; "
            f"the scholarship funding organization sets the award, so this is not a promised amount "
            f"[[cite:{rule['cite_path']}]]."
        )
        return EvidenceRecord(
            school_id=school["id"],
            criterion_id=criterion.id,
            status="partial",
            value=tuition,
            source=Source(
                type="funding_rule",
                path=rule["cite_path"],
                as_of="2026-03-01",
                confidence="medium",
            ),
            note=note,
        )
    return EvidenceRecord(
        school_id=school["id"],
        criterion_id=criterion.id,
        status="unknown",
        note=f"{label} is unknown because the school type is missing.",
    )


def _non_religious(school: dict, criterion, today: date) -> EvidenceRecord:
    entity = school.get("entity_type")
    subtype = [str(v).casefold() for v in as_list(get_path(school, "osp.school_sub_type"))]
    name = str(school.get("name") or "").casefold()
    religious = "religious" in subtype or any(word in name for word in RELIGIOUS_WORDS)
    if religious:
        path = "osp.school_sub_type" if "religious" in subtype else "name"
        note = _cite(path, "Non-religious is a miss: the profile shows a religious affiliation.")
        return EvidenceRecord(
            school_id=school["id"],
            criterion_id=criterion.id,
            status="needs_attention",
            value="religious",
            source=Source(type="school_reported", path=path, as_of=_as_of(school, today), confidence="high"),
            note=note,
        )
    if entity in {"public", "charter"}:
        note = _cite("entity_type", f"Non-religious is confirmed: this is a {entity} school.")
        return EvidenceRecord(
            school_id=school["id"],
            criterion_id=criterion.id,
            status="confirmed",
            value=entity,
            source=Source(type="state_data", path="entity_type", as_of=_as_of(school, today), confidence="high"),
            note=note,
        )
    if entity == "private":
        return EvidenceRecord(
            school_id=school["id"],
            criterion_id=criterion.id,
            status="unknown",
            value=None,
            note="Non-religious is unknown: the profile does not say whether this private school is religious.",
        )
    return EvidenceRecord(
        school_id=school["id"],
        criterion_id=criterion.id,
        status="unknown",
        note="Non-religious is unknown.",
    )


def _distance_evidence(school: dict, criterion, today: date) -> EvidenceRecord:
    distance = school.get("_distance_miles")
    limit = float((criterion.params or {}).get("max_miles") or 8)
    if distance is None:
        return EvidenceRecord(
            school_id=school["id"],
            criterion_id=criterion.id,
            status="unknown",
            note="Distance is unknown because the map point is missing.",
        )
    if distance <= limit:
        status = "confirmed"
    elif distance <= limit + 3:
        status = "partial"
    else:
        status = "needs_attention"
    shown = f"{distance:.1f} miles"
    note = _cite("latlon", f"Distance is {status.replace('_', ' ')}: {shown} from the search city (limit {limit:.0f} miles).")
    return EvidenceRecord(
        school_id=school["id"],
        criterion_id=criterion.id,
        status=status,
        value=round(distance, 1),
        source=Source(type="state_data", path="latlon", as_of=_as_of(school, today), confidence="high"),
        note=note,
    )


def _as_of(school: dict, today: date) -> str:
    return (parse_date(school.get("created")) or today).isoformat()


def field_meets(school: dict, need_id: str) -> bool:
    """True when a search boost should treat the need as present on the profile."""
    spec = needs().get(need_id) or {}
    if need_id == "stem":
        subtype = [str(v).casefold() for v in as_list(get_path(school, "osp.school_sub_type"))]
        clubs = [str(v).casefold() for v in as_list(get_path(school, "osp.student_clubs"))]
        if any("stem" in v or v == "science" for v in subtype):
            return True
        return any(c in {"science_club", "robotics", "coding", "math_club", "stem_club"} for c in clubs)
    if need_id == "after_care":
        return bool(as_list(get_path(school, "osp.after_school_until")))
    for rule in spec.get("evidence") or []:
        if rule.get("field") == "reviews":
            continue
        value = get_path(school, rule["field"])
        if op_matches(rule.get("confirmed"), value, {}):
            return True
    return False
