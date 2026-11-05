"""Questions for schools. Many parents asking the same thing become one request."""

from __future__ import annotations

from datetime import datetime, timezone

from evidence.status import answer_expired, max_age_days
from runtime_config import TODAY


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_question(state: dict, school: dict, need_id: str, question: str, session_id: str) -> dict:
    inbox = state.setdefault("inbox", [])
    for item in inbox:
        if item["school_id"] == school["id"] and item["need"] == need_id and item["status"] == "open":
            if session_id not in item["session_ids"]:
                item["session_ids"].append(session_id)
            item["parent_count"] = len(item["session_ids"])
            return item
    item = {
        "id": f"q-{len(inbox) + 1}",
        "school_id": school["id"],
        "school_name": school["name"],
        "need": need_id,
        "question": question,
        "session_ids": [session_id],
        "parent_count": 1,
        "status": "open",
        "created": _now(),
        "email_to": f"office@{school['id'].lower().replace(' ', '-')}.example.org",
        "replies": [],
    }
    inbox.append(item)
    return item


def grouped_inbox(state: dict) -> list[dict]:
    return list(state.get("inbox") or [])


def reply_to_question(
    state: dict, question_id: str, text: str, value: str | None = None, channel: str = "email"
) -> dict | None:
    """channel says how the school answered: "email" (inbox reply), "call", or "staff"."""
    for item in state.get("inbox") or []:
        if item["id"] != question_id:
            continue
        item["replies"].append({"text": text, "at": _now(), "value": value, "channel": channel})
        item["status"] = "answered"
        item["answered_at"] = _now()
        if value:
            _apply_overlay(state, item["school_id"], item["need"], value, channel)
        return item
    return None


def _apply_overlay(state: dict, school_id: str, need_id: str, value: str, channel: str = "staff") -> None:
    path = _path_for(need_id)
    if not path:
        return
    overlays = state.setdefault("overlays", {})
    school_overlay = overlays.setdefault(school_id, {})
    school_overlay[path] = {
        "value": value,
        "as_of": TODAY.isoformat(),
        "answered_at": _now(),
        "confidence": "high",
        "source": "school_reported",
        "channel": channel,
    }


def requeue_stale(state: dict, today=None) -> list[dict]:
    """School answers older than the need's max_age_days go back in the queue as open questions."""
    from catalog import needs

    names = {item["school_id"]: item.get("school_name") for item in state.get("inbox") or []}
    answered: list[tuple[str, str, str | None]] = []
    for school_id, fields in (state.get("overlays") or {}).items():
        for path, record in (fields or {}).items():
            need_id = _need_for(path)
            if need_id and isinstance(record, dict):
                answered.append((school_id, need_id, record.get("as_of")))
    for school_id, by_need in ((state.get("community") or {}).get("school_answers") or {}).items():
        for need_id, record in (by_need or {}).items():
            answered.append((school_id, need_id, (record or {}).get("as_of")))
    added = []
    for school_id, need_id, as_of in answered:
        if not answer_expired(need_id, as_of, today):
            continue
        if any(i["school_id"] == school_id and i["need"] == need_id and i["status"] == "open" for i in state.get("inbox") or []):
            continue
        spec = needs().get(need_id) or {}
        school = {"id": school_id, "name": names.get(school_id) or school_id}
        item = add_question(state, school, need_id, spec.get("visit_question") or f"Can you tell us about {need_id}?", "freshness")
        # No parent asked this time: the old answer expired.
        item["session_ids"], item["parent_count"] = [], 0
        item["reason"] = f"Answer from {as_of or 'an unknown date'} is older than {max_age_days(need_id)} days."
        added.append(item)
    return added


def _need_for(path: str) -> str | None:
    return next((need for need, field in _PATHS.items() if field == path), None)


_PATHS = {
    "after_care": "osp.after_school_until",
    "extended_day": "osp.end_time",
    "before_care": "osp.before_school_from",
    "stem": "osp.school_sub_type",
    "low_cost": "osp.tuition",
}


def _path_for(need_id: str) -> str | None:
    return _PATHS.get(need_id)
