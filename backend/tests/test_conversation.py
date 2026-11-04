"""Follow-up turns in one session (issues #7 and #12). Rules engine only; no AWS calls."""

from __future__ import annotations

from pipeline import turn
from store import _empty
from testing_helpers import search_turn

FIRST = "Elementary school in Seattle with after-school care until 6pm"


def _follow_up(message: str, **payload) -> dict:
    state = _empty()
    session_id = search_turn(state, {"message": FIRST}).session_id
    return turn(state, {"message": message, "session_id": session_id, **payload}).model_dump()


def _criteria(response: dict) -> set[tuple]:
    return {(c["kind"], c.get("value") or c.get("need")) for c in response["criteria"]}


def test_new_query_replaces_the_old_criteria():
    response = _follow_up("High school in Seattle with sports")
    assert response["route"] == "new_search"
    assert _criteria(response) == {("grade", "h"), ("location", "Seattle"), ("need", "sports")}


def test_new_search_action_replaces_the_old_criteria():
    response = _follow_up("High school in Seattle with sports", action="new_search")
    assert ("need", "after_care") not in _criteria(response)


def test_partial_follow_ups_still_refine():
    city = _follow_up("what about in Seattle instead?")
    assert city["route"] == "refine"
    assert _criteria(city) == {("grade", "e"), ("location", "Seattle"), ("need", "after_care")}
    grade = _follow_up("actually, middle school")
    assert grade["route"] == "refine"
    assert _criteria(grade) == {("grade", "m"), ("location", "Seattle"), ("need", "after_care")}


def test_naming_a_school_opens_its_detail():
    response = _follow_up("tell me more about Cascade Bend Institute")
    assert response["route"] == "school_detail"
    detail = next(b["payload"] for b in response["blocks"] if b["type"] == "school_detail")
    assert detail["school"]["name"] == "Cascade Bend Institute"


def test_question_about_a_school_answers_it_without_changing_the_search():
    response = _follow_up("does Cascade Bend Institute have STEM?")
    assert response["route"] == "school_detail"
    assert ("need", "stem") not in _criteria(response), "asking about one school does not add a filter"
    detail = next(b["payload"] for b in response["blocks"] if b["type"] == "school_detail")
    statuses = {row["criterion_id"]: row["status"] for row in detail["card"]["evidence"]}
    assert "stem" in [row.get("need") for row in detail["asked"]]
    assert all(row["id"] in statuses for row in detail["asked"])
    answer = next(b["payload"]["text"] for b in response["blocks"] if b["type"] == "message")
    assert "STEM" in answer


def test_route_and_extract_run_at_the_same_time(monkeypatch):
    """Route waits for extract to start. Run one after the other, route would time out first."""
    import json
    import threading

    import agent.bedrock_client as bc
    from agent.prompts import EXPLAIN_SYSTEM, ROUTER_SYSTEM

    extract_started = threading.Event()
    overlapped = []

    def answer(model_id, system, user):
        if system == ROUTER_SYSTEM:
            overlapped.append(extract_started.wait(timeout=5))
            return "new_search"
        if system == EXPLAIN_SYSTEM:
            return "{}"
        extract_started.set()
        return json.dumps([{"kind": "grade", "value": "e", "text": "elementary"}])

    monkeypatch.setattr(bc, "enabled", lambda: True)
    monkeypatch.setattr(bc, "converse", answer)
    # First message may stop at the brief gate; extract/route still ran.
    response = turn(_empty(), {"message": FIRST}).model_dump()

    assert overlapped == [True]
    assert response["engine"]["route"] == "bedrock"
    assert response["engine"]["extract"] == "bedrock"
