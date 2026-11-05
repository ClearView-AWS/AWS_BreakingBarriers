"""Calling a school: one call per school, answers checked in code before a card changes."""

from __future__ import annotations

import pytest

from gaps import phone
from gaps.inbox import add_question
from search.corpus import load_schools

TIDEWATER = "School fl-180001"


def _school(school_id: str) -> dict:
    return next(row for row in load_schools() if row["id"] == school_id)


@pytest.fixture()
def state() -> dict:
    return {"sessions": {}, "inbox": [], "overlays": {}, "calls": {}}


@pytest.fixture(autouse=True)
def voice_off(monkeypatch):
    for key in ("VOICE_ENABLED", "VOICE_INSTANCE_ID", "VOICE_FLOW_ID", "VOICE_SOURCE", "VOICE_VERIFIED_TO", "VOICE_TABLE", "GS_DYNAMODB_TABLE"):
        monkeypatch.delenv(key, raising=False)
    # Guardrails are covered in test_call_limits; keep these tests on the dial path.
    monkeypatch.setattr(phone, "why_blocked", lambda *args, **kwargs: None)


@pytest.mark.parametrize(
    ("text", "evening", "expected"),
    [
        ("6 PM", True, "18:00"),
        ("6:30pm", True, "18:30"),
        ("18:00", True, "18:00"),
        ("until 6", True, "18:00"),
        ("7:15", False, "07:15"),
        ("7 in the morning", True, "07:00"),
        ("we don't have that", True, None),
    ],
)
def test_parse_time(text, evening, expected):
    assert phone.parse_time(text, evening=evening) == expected


def test_one_call_asks_every_open_question_for_the_school(state):
    school = _school(TIDEWATER)
    add_question(state, school, "after_care", "What time does after-school care end?", "s1")
    add_question(state, school, "extended_day", "What time does the school day end?", "s2")
    call = phone.start_call(state, school)
    assert [q["id"] for q in call["questions"]] == ["after_care", "extended_day"]
    assert call["parent_count"] == 2
    assert "automated AI assistant" in call["opening"] and "transcribe" in call["opening"]
    # Without VOICE_ENABLED and a verified number nothing is dialed.
    assert call["status"] == "off"
    assert "VOICE_VERIFIED_TO" not in str(phone.public(call))


def _finished_call(state, answers, transcript, consent=True):
    school = _school(TIDEWATER)
    add_question(state, school, "after_care", "What time does after-school care end?", "s1")
    call = phone.start_call(state, school)
    call["status"] = "in_call"
    call["contact_id"] = "c-1"
    record = {"status": "completed", "consent": consent, "answers": answers, "transcript": transcript}
    return call, record


def test_checked_answer_updates_the_card(state, monkeypatch):
    transcript = [
        {"who": "agent", "text": "What time does after-school care end?"},
        {"who": "school", "text": "Care runs until 6 PM, right here on campus."},
    ]
    call, record = _finished_call(state, {"after_care": {"value": "6 PM", "quote": "until 6 PM, right here on campus"}}, transcript)
    monkeypatch.setattr(phone, "_read_record", lambda _id: record)
    monkeypatch.setattr(phone, "_disconnected", lambda _id: True)
    done = phone.refresh_call(state, call["id"])
    assert done["status"] == "completed"
    assert done["answers"][0]["value"] == "18:00"
    overlay = state["overlays"][TIDEWATER]["osp.after_school_until"]
    assert overlay["value"] == "18:00" and overlay["source"] == "school_reported"
    assert state["inbox"][0]["status"] == "answered"


def test_answer_nobody_said_is_dropped(state, monkeypatch):
    transcript = [{"who": "school", "text": "Sorry, I'd have to check on that."}]
    call, record = _finished_call(state, {"after_care": {"value": "18:00", "quote": "care ends at six"}}, transcript)
    monkeypatch.setattr(phone, "_read_record", lambda _id: record)
    monkeypatch.setattr(phone, "_disconnected", lambda _id: True)
    done = phone.refresh_call(state, call["id"])
    assert done["answers"] == []
    assert TIDEWATER not in state["overlays"]
    assert state["inbox"][0]["status"] == "open"


def test_declined_transcript_keeps_nothing(state, monkeypatch):
    transcript = [{"who": "school", "text": "No, please don't record this. Care ends at 6."}]
    call, record = _finished_call(state, {"after_care": {"value": "18:00", "quote": "Care ends at 6"}}, transcript, consent=False)
    monkeypatch.setattr(phone, "_read_record", lambda _id: record)
    monkeypatch.setattr(phone, "_disconnected", lambda _id: True)
    done = phone.refresh_call(state, call["id"])
    assert done["status"] == "declined"
    assert done["transcript"] == [] and done["answers"] == []
    assert TIDEWATER not in state["overlays"]


def test_hang_up_before_answers(state, monkeypatch):
    call, _ = _finished_call(state, {}, [])
    monkeypatch.setattr(phone, "_read_record", lambda _id: None)
    monkeypatch.setattr(phone, "_disconnected", lambda _id: True)
    assert phone.refresh_call(state, call["id"])["status"] == "no_answer"
