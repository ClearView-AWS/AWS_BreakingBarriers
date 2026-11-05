"""Call guardrails: spacing, office hours, caps, do-not-call, staff answer path."""

from __future__ import annotations

import pytest

from gaps import phone
from gaps.inbox import add_question, reply_to_question
from search.corpus import load_schools

TIDEWATER = "School fl-180001"


def _school(school_id: str = TIDEWATER) -> dict:
    return next(row for row in load_schools() if row["id"] == school_id)


@pytest.fixture()
def state() -> dict:
    return {"sessions": {}, "inbox": [], "overlays": {}, "calls": {}, "do_not_call": []}


@pytest.fixture(autouse=True)
def voice_off(monkeypatch):
    for key in ("VOICE_ENABLED", "VOICE_INSTANCE_ID", "VOICE_FLOW_ID", "VOICE_SOURCE", "VOICE_VERIFIED_TO"):
        monkeypatch.delenv(key, raising=False)
    # Demo ships with enforce_limits: false; these tests exercise the guardrails.
    original = phone.call_limits

    def limited():
        return {**original(), "enforce_limits": True, "min_days_between_calls": 7, "global_daily_cap": 20}

    monkeypatch.setattr(phone, "call_limits", limited)


def test_do_not_call_blocks_and_falls_back_to_email(state, monkeypatch):
    school = _school()
    add_question(state, school, "after_care", "What time does after-school care end?", "s1")
    monkeypatch.setattr(phone, "_in_business_hours", lambda *a, **k: True)
    phone.set_do_not_call(state, school["id"], True)
    call = phone.start_call(state, school)
    assert call["status"] == "blocked"
    assert "not to be called" in call["fallback_reason"]
    assert phone.public(call)["fallback_reason"]


def test_recent_call_blocks_another(state, monkeypatch):
    school = _school()
    add_question(state, school, "after_care", "What time does after-school care end?", "s1")
    monkeypatch.setattr(phone, "_in_business_hours", lambda *a, **k: True)
    # Pretend a real call already went out today.
    state["calls"]["prior"] = {
        "id": "prior",
        "school_id": school["id"],
        "status": "completed",
        "contact_id": "c-1",
        "created": "2026-11-03T15:00:00+00:00",
    }
    call = phone.start_call(state, school)
    assert call["status"] == "blocked"
    assert "last" in call["fallback_reason"]


def test_max_questions_per_call(state, monkeypatch):
    school = _school()
    for need in ("after_care", "extended_day", "before_care", "stem", "sports", "music"):
        add_question(state, school, need, f"About {need}?", "s1")
    monkeypatch.setattr(phone, "why_blocked", lambda *a, **k: None)
    original = phone.call_limits
    monkeypatch.setattr(phone, "call_limits", lambda: {**original(), "max_questions_per_call": 3, "enforce_limits": False})
    call = phone.start_call(state, school)
    assert len(call["questions"]) == 3
    assert call["status"] == "off"


def test_demo_does_not_block_repeat_or_after_hours(state, monkeypatch):
    """On-stage default: enforce_limits false → always dial-ready (status off without Connect)."""
    school = _school()
    add_question(state, school, "after_care", "What time does after-school care end?", "s1")
    monkeypatch.setattr(phone, "call_limits", lambda: {"enforce_limits": False, "max_questions_per_call": 5})
    state["calls"]["prior"] = {
        "id": "prior",
        "school_id": school["id"],
        "status": "completed",
        "contact_id": "c-1",
        "created": "2026-11-04T15:00:00+00:00",
    }
    call = phone.start_call(state, school)
    assert call["status"] == "off"
    assert call.get("fallback_reason") == "Voice calling is off; questions go by email."


def test_outside_office_hours(state, monkeypatch):
    school = _school()
    add_question(state, school, "after_care", "What time does after-school care end?", "s1")
    monkeypatch.setattr(phone, "_in_business_hours", lambda *a, **k: False)
    call = phone.start_call(state, school)
    assert call["status"] == "blocked"
    assert "office hours" in call["fallback_reason"]


def test_daily_cap(state, monkeypatch):
    school = _school()
    add_question(state, school, "after_care", "What time does after-school care end?", "s1")
    monkeypatch.setattr(phone, "_in_business_hours", lambda *a, **k: True)
    monkeypatch.setattr(phone, "_placed_today", lambda _state: 20)
    call = phone.start_call(state, school)
    assert call["status"] == "blocked"
    assert "Daily call limit" in call["fallback_reason"]


def test_staff_answer_uses_same_overlay_path(state):
    school = _school()
    item = add_question(state, school, "after_care", "What time does after-school care end?", "s1")
    answered = reply_to_question(state, item["id"], "Care ends at 6 PM.", "18:00", channel="staff")
    assert answered["status"] == "answered"
    overlay = state["overlays"][TIDEWATER]["osp.after_school_until"]
    assert overlay["value"] == "18:00" and overlay["channel"] == "staff" and overlay["answered_at"]
