"""Questions for schools. Many parents asking the same thing become one request."""

from __future__ import annotations

from datetime import datetime, timezone

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


def reply_to_question(state: dict, question_id: str, text: str, value: str | None = None) -> dict | None:
    for item in state.get("inbox") or []:
        if item["id"] != question_id:
            continue
        item["replies"].append({"text": text, "at": _now(), "value": value})
        item["status"] = "answered"
        if value:
            _apply_overlay(state, item["school_id"], item["need"], value)
        return item
    return None


def _apply_overlay(state: dict, school_id: str, need_id: str, value: str) -> None:
    path = _path_for(need_id)
    if not path:
        return
    overlays = state.setdefault("overlays", {})
    school_overlay = overlays.setdefault(school_id, {})
    school_overlay[path] = {
        "value": value,
        "as_of": TODAY.isoformat(),
        "confidence": "high",
        "source": "school_reported",
    }


def _path_for(need_id: str) -> str | None:
    return {
        "after_care": "osp.after_school_until",
        "extended_day": "osp.end_time",
        "before_care": "osp.before_school_from",
        "stem": "osp.school_sub_type",
        "low_cost": "osp.tuition",
    }.get(need_id)
