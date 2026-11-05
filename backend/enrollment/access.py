"""Getting in: how admission works at a school, what to do next, and by when.

It reuses the evidence statuses so the frontend draws it like any criterion, but it
is never part of match or coverage. It checks the school's own answer first, then
school data, then enrollment_rules.yaml. It explains admission; it never estimates
a family's chances or promises a seat. Applicant and seat counts are shown as the
school reported them, with their date.
"""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from typing import Any

import yaml

from agent.citations import strip_cites, validate_text
from evidence.status import months_before, parse_date
from runtime_config import CONFIG_DIR, TODAY
from school_state import school_state

LABELS = {
    "confirmed": "Open to you",
    "partial": "Apply by a date",
    "needs_attention": "Needs attention",
    "unknown": "Unknown",
}
DEFAULT_HOW = {"public": "zoned", "charter": "lottery", "private": "application"}
HOW_SENTENCE = {
    "zoned": "This is a zoned neighborhood school",
    "choice": "Admission is through the district's school choice process",
    "lottery": "Admission is by application, with a lottery if there are more applicants than seats",
    "application": "Admission is by application to the school",
}
LEVEL_GRADES = {
    "p": ["PK"],
    "e": ["K", "1", "2", "3", "4", "5"],
    "m": ["6", "7", "8"],
    "h": ["9", "10", "11", "12"],
}
OPEN_SEATS_MONTHS = 6  # a school's report of open seats counts for 6 months
STALE_DEADLINE_DAYS = 365  # an older deadline is probably last cycle's, so it counts as unknown
PLACEHOLDER_DEADLINE_DAYS = 548  # more than 18 months ahead (like the sample's 1/1/2050) is a placeholder


@lru_cache(maxsize=1)
def enrollment_rules() -> dict[str, Any]:
    return yaml.safe_load((CONFIG_DIR / "enrollment_rules.yaml").read_text())


def _state_pack(school: dict, config: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Admission rules + checked date for the school's state (WA OSPI vs FL demo)."""
    state = school_state(school)
    pack = (config.get("by_state") or {}).get(state) or {}
    rules = pack.get("rules") or config["rules"]
    checked = pack.get("checked") or config.get("checked")
    return rules, checked


def parse_deadline(value: object) -> date | None:
    """The sample writes deadlines as M/D/YYYY; school answers may use ISO dates."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        return datetime.strptime(text, "%m/%d/%Y").date()
    except ValueError:
        return parse_date(text)


def _first(value: object) -> object:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _ordinal(grade: str) -> str:
    if grade == "PK":
        return "pre-K"
    if grade == "K":
        return "kindergarten"
    number = int(grade)
    suffix = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix} grade"


_WORDS = ["", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth"]


def _grade_adjective(grade: str) -> str:
    """'sixth-grade' as in "90 sixth-grade seats"."""
    if grade in {"PK", "K"}:
        return _ordinal(grade)
    return f"{_WORDS[int(grade)]}-grade"


def _day(when: date) -> str:
    return f"{when.strftime('%b')} {when.day}"


def _month(when: date | None) -> str:
    return f"{when.strftime('%b')} {when.year}" if when else ""


def _field(school: dict, overlays: dict, key: str) -> tuple[object, str, str | None]:
    """(value, source type, as_of). A school's own answer in its thread wins over its profile."""
    path = f"osp.{key}"
    answer = overlays.get(path)
    if isinstance(answer, dict) and answer.get("value") is not None:
        return answer["value"], "school_reported", answer.get("as_of")
    return (school.get("osp") or {}).get(key), "school_profile", None


def _rows_for_grade(rows: object, grades: list[str] | None) -> list[dict]:
    rows = [row for row in rows or [] if isinstance(row, dict)] if isinstance(rows, list) else []
    if grades is None:
        return rows
    return [row for row in rows if str(row.get("grade")) in grades]


def getting_in(
    school: dict,
    grade: str | None = None,
    zoned_ids: set[str] | None = None,
    overlays: dict | None = None,
    today: date | None = None,
) -> dict:
    """The Getting in record for one school. `grade` is a level code (p, e, m, h) or None."""
    today = today or TODAY
    overlays = overlays or {}
    config = enrollment_rules()
    rules, checked = _state_pack(school, config)
    osp = school.get("osp") or {}
    entity = school.get("entity_type")

    typed = _first(osp.get("admission_type"))
    how = typed if typed in rules else DEFAULT_HOW.get(entity, "application")
    # Pick the law that governs this school: charter schools follow the charter
    # admission law (lottery when oversubscribed), and a public school's lottery is
    # a district magnet or choice program under the school choice law.
    if entity == "charter" and how in {"lottery", "application"}:
        rule_key = "lottery"
    elif entity == "public" and how == "lottery":
        rule_key = "choice"
    else:
        rule_key = how
    rule = rules[rule_key]
    district = (config.get("districts") or {}).get(school.get("city"))
    grades = LEVEL_GRADES.get(grade) if grade else None

    how_cite = "osp.admission_type" if typed in rules else rule["cite_path"]
    allowed = {rule["cite_path"], how_cite}
    sentences = [f"{HOW_SENTENCE[how]} [[cite:{how_cite}]]."]

    seats_value, seats_type, seats_answered = _field(school, overlays, "seats_by_grade")
    deadline_value, deadline_type, deadline_answered = _field(school, overlays, "application_deadline_date")
    applicants_value, _, _ = _field(school, overlays, "applicants_last_year")

    deadline = parse_deadline(_first(deadline_value))
    if deadline and (deadline - today).days > PLACEHOLDER_DEADLINE_DAYS:
        deadline = None
    fresh_cut = months_before(today, OPEN_SEATS_MONTHS)
    fresh = [
        row
        for row in _rows_for_grade(seats_value, grades)
        if (parse_date(row.get("as_of")) or date.min) >= fresh_cut
    ]
    open_rows = [row for row in fresh if (row.get("open_seats") or 0) > 0]
    wait_rows = [row for row in fresh if row.get("waitlist") or row.get("open_seats") == 0]
    as_of_created = (parse_date(school.get("created")) or today).isoformat()

    record: dict[str, Any] = {
        "school_id": school["id"],
        "criterion_id": "access",
        "how": how,
        "how_label": rules[how]["label"],
        "deadline": None,
        "days_left": None,
        "detail": None,
        "source": {"type": "enrollment_rule", "path": rule["cite_path"], "as_of": checked, "confidence": "high"},
        "official": {
            "name": rule["official_name"],
            "url": rule["official_url"],
            "more_url": rule.get("more_url"),
            "agency": rule.get("agency"),
            "cite_path": rule["cite_path"],
            "summary": " ".join(rule["summary"].split()),
            "next_step": rule["next_step"],
        },
        "admissions_url": _first(osp.get("admissions_url")),
        "district": district,
        "zoned_prompt": False,
        "ask_open_seats": False,
    }

    pill_label: str | None = None
    if how == "zoned" and school["id"] in (zoned_ids or set()):
        status, line = "confirmed", "Your zoned school"
        record["source"] = {"type": "parent", "path": "session.zoned", "as_of": today.isoformat(), "confidence": "high"}
        allowed.add("session.zoned")
        sentences.append("You told us this is your zoned school [[cite:session.zoned]].")
    elif open_rows:
        row = open_rows[0]
        grade_name = _ordinal(str(row["grade"]))
        status, line = "confirmed", f"Open seats for {grade_name}"
        record["source"] = {"type": seats_type, "path": "osp.seats_by_grade", "as_of": row.get("as_of") or seats_answered, "confidence": "high"}
        allowed.add("osp.seats_by_grade")
        sentences.append(
            f"The school reported {row['open_seats']} open seats for {grade_name} as of "
            f"{_month(parse_date(row.get('as_of')))} [[cite:osp.seats_by_grade]]."
        )
    elif deadline and deadline >= today:
        days = (deadline - today).days
        status, line = "partial", f"{rules[how]['label']} · apply by {_day(deadline)} ({days} days left)"
        record.update(deadline=deadline.isoformat(), days_left=days)
        record["source"] = {"type": deadline_type, "path": "osp.application_deadline_date", "as_of": deadline_answered or as_of_created, "confidence": "medium"}
        allowed.add("osp.application_deadline_date")
        sentences.append(f"Applications are due {_day(deadline)}, {deadline.year} [[cite:osp.application_deadline_date]].")
    elif deadline and (today - deadline).days <= STALE_DEADLINE_DAYS:
        status, line = "needs_attention", f"Deadline passed {_day(deadline)} · ask about mid-year openings"
        record.update(deadline=deadline.isoformat(), days_left=(deadline - today).days, ask_open_seats=True)
        record["source"] = {"type": deadline_type, "path": "osp.application_deadline_date", "as_of": deadline_answered or as_of_created, "confidence": "medium"}
        allowed.add("osp.application_deadline_date")
        sentences.append(
            f"The application deadline was {_day(deadline)}, {deadline.year}, and it has passed [[cite:osp.application_deadline_date]]."
        )
    elif wait_rows:
        row = wait_rows[0]
        grade_name = _ordinal(str(row["grade"]))
        status, line = "needs_attention", f"Waitlist only for {grade_name} · ask about openings"
        record["ask_open_seats"] = True
        record["source"] = {"type": seats_type, "path": "osp.seats_by_grade", "as_of": row.get("as_of") or seats_answered, "confidence": "high"}
        allowed.add("osp.seats_by_grade")
        sentences.append(
            f"The school reported a waitlist only for {grade_name} as of {_month(parse_date(row.get('as_of')))} [[cite:osp.seats_by_grade]]."
        )
    elif how == "zoned":
        # Known admission type — not an evidence Unknown. Offer the district locator.
        status, line = "partial", "Zoned neighborhood school · check your address"
        record["zoned_prompt"] = True
        pill_label = rules[how]["label"]
    else:
        status, line = "unknown", "Ask about open seats"
        record["ask_open_seats"] = True
        old = parse_deadline(_first(deadline_value))
        if old and (today - old).days > STALE_DEADLINE_DAYS:
            allowed.add("osp.application_deadline_date")
            sentences.append(
                f"The last deadline on file, {_day(old)}, {old.year}, is more than a year old [[cite:osp.application_deadline_date]]."
            )

    applicants = _rows_for_grade(applicants_value, grades)
    if applicants:
        row = applicants[0]
        grade_label = _grade_adjective(str(row["grade"]))
        when = parse_date(row.get("as_of"))
        record["detail"] = f"Last year: {row['applicants']} applicants for {row['seats']} {grade_label} seats"
        record["detail_as_of"] = row.get("as_of")
        record["detail_source"] = f"School-reported, {_month(when)}" if when else "School-reported"
        allowed.add("osp.applicants_last_year")
        sentences.append(
            f"Last year the school reported {row['applicants']} applicants for {row['seats']} {grade_label} seats "
            f"[[cite:osp.applicants_last_year]]."
        )

    cited = validate_text(" ".join(sentences), allowed)
    record.update(
        status=status,
        label=pill_label or LABELS[status],
        line=line,
        note=cited,
        text=strip_cites(cited),
    )
    return record


def by_deadline(records: list[dict]) -> list[dict]:
    """Saved schools with the soonest open deadline first; passed and unknown ones last."""

    def key(row: dict) -> tuple:
        days = row.get("days_left")
        upcoming = days is not None and days >= 0
        return (0 if upcoming else 1, days if upcoming else 0, row.get("name") or "")

    return sorted(records, key=key)
