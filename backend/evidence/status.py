"""Operators and freshness rules for one field."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from runtime_config import FRESH_MONTHS, TODAY

_TIME = re.compile(
    r"(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?",
    re.IGNORECASE,
)


def parse_date(value: object) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def months_before(day: date, months: int) -> date:
    month = day.month - months
    year = day.year
    while month <= 0:
        month += 12
        year -= 1
    # Clamp the day for short months.
    last = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][
        month - 1
    ]
    return date(year, month, min(day.day, last))


def is_fresh(when: date | None, today: date | None = None) -> bool:
    if when is None:
        return False
    today = today or TODAY
    return when >= months_before(today, FRESH_MONTHS)


def unwrap(value: object) -> object:
    if isinstance(value, list):
        if len(value) == 1:
            return value[0]
        return value
    return value


def as_list(value: object) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def parse_clock(value: object) -> int | None:
    """Minutes from midnight."""
    value = unwrap(value)
    if not isinstance(value, str):
        return None
    match = _TIME.search(value.strip())
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").lower().replace(".", "")
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    if not meridiem and hour <= 7:
        # "6:00" on an after-school field means evening.
        hour += 12
    return hour * 60 + minute


def _number(value: object) -> float | None:
    value = unwrap(value)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").replace("$", ""))
        except ValueError:
            return None
    return None


def _boolish(value: object) -> bool | None:
    value = unwrap(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"true", "yes"}:
            return True
        if lowered in {"false", "no"}:
            return False
    return None


def _comparison(op: str) -> tuple[str, str] | None:
    """Parse '>= 8', '>=:8', '== true', '==:true' into (operator, argument)."""
    text = (op or "").strip()
    for token in (">=", "<=", "==", ">", "<"):
        if text.startswith(token):
            return token, text[len(token) :].lstrip(" :\t")
    return None


def op_matches(op: str | None, value: object, params: dict | None = None) -> bool:
    if not op:
        return False
    params = params or {}
    compared = _comparison(op)
    if compared:
        name, arg = compared
        if name == "==" and arg in {"true", "false"}:
            found = _boolish(value)
            return found is not None and found == (arg == "true")
        number = _number(value)
        if number is None:
            return False
        try:
            target = float(arg)
        except ValueError:
            return False
        if name == ">=":
            return number >= target
        if name == "<=":
            return number <= target
        if name == ">":
            return number > target
        if name == "<":
            return number < target
        return number == target

    parts = op.split(":", 1)
    name = parts[0].strip()
    arg = parts[1].strip() if len(parts) > 1 else ""

    tokens = [t.strip().casefold() for t in arg.split(",") if t.strip()]
    values = [str(v).strip().casefold() for v in as_list(value)]

    if name == "in":
        return any(v in tokens for v in values)
    if name == "contains_any":
        return any(v in tokens or any(tok in v for tok in tokens) for v in values)
    if name == "nonempty":
        return len(values) > 0 and any(v for v in values)
    if name == "truthy":
        flag = _boolish(value)
        if flag is not None:
            return flag
        return len([v for v in values if v not in {"", "false", "0", "none"}]) > 0
    if name in {"time_covers", "time_within", "time_before"}:
        clock = parse_clock(value)
        target = _target_minutes(params)
        if clock is None or target is None:
            return False
        window = int(arg or "30") if name == "time_within" else 30
        if name == "time_covers":
            return clock >= target
        if name == "time_within":
            return target - window <= clock < target
        return clock < target - window
    return False


def _target_minutes(params: dict) -> int | None:
    until = params.get("until")
    if until:
        parsed = parse_clock(str(until))
        if parsed is not None:
            return parsed
    # With no clock from the parent, "has after-school care" means care until 5:00 or later.
    return 17 * 60


def apply_rule(rule: dict, value: object, params: dict | None = None) -> str | None:
    """Map a present value to a status. None means this rule does not apply."""
    if value is None or value == [] or value == "":
        return None
    if op_matches(rule.get("confirmed"), value, params):
        return "confirmed"
    if op_matches(rule.get("partial"), value, params):
        return "partial"
    if rule.get("fails") and op_matches(rule.get("fails"), value, params):
        return "needs_attention"
    if rule.get("confirmed"):
        return "needs_attention"
    return None


def downgrade_for_age(status: str | None, confidence: str | None, as_of: date | None, today: date | None = None) -> str | None:
    """Confirmed requires medium/high confidence and data newer than 18 months."""
    if status != "confirmed":
        return status
    if confidence in {"unknown", "low"}:
        return "partial"
    if not is_fresh(as_of, today):
        return "partial"
    return status


_RANK = {"confirmed": 3, "partial": 2, "needs_attention": 1, "unknown": 0}


def better(left: str | None, right: str | None) -> str | None:
    if left is None:
        return right
    if right is None:
        return left
    return left if _RANK[left] >= _RANK[right] else right


# ---------- answers from the school itself ----------

# How long a call, email reply, or staff answer counts unless needs.yaml sets max_age_days.
DEFAULT_MAX_AGE_DAYS = 365


def max_age_days(need_id: str | None) -> int:
    from catalog import needs

    spec = needs().get(need_id or "") or {}
    return int(spec.get("max_age_days") or DEFAULT_MAX_AGE_DAYS)


def answer_expired(need_id: str | None, answered: object, today: date | None = None) -> bool:
    """True when a school's own answer is older than the need allows. No date counts as expired."""
    when = parse_date(answered)
    if when is None:
        return True
    return (today or TODAY) - when > timedelta(days=max_age_days(need_id))


def stale_note(answered: object) -> str:
    when = parse_date(answered)
    return f"Reported {when.isoformat() if when else 'earlier'}, may be out of date."
