"""Follow-up turns in one session (issues #7 and #12). Rules engine only; no AWS calls."""

from __future__ import annotations

from pipeline import turn
from store import _empty

FIRST = "Elementary school in Jacksonville with after-school care until 6pm"


def _follow_up(message: str, **payload) -> dict:
    state = _empty()
    session_id = turn(state, {"message": FIRST}).session_id
    return turn(state, {"message": message, "session_id": session_id, **payload}).model_dump()


def _criteria(response: dict) -> set[tuple]:
    return {(c["kind"], c.get("value") or c.get("need")) for c in response["criteria"]}


def test_new_query_replaces_the_old_criteria():
    response = _follow_up("High school in Miami with sports")
    assert response["route"] == "new_search"
    assert _criteria(response) == {("grade", "h"), ("location", "Miami"), ("need", "sports")}


def test_new_search_action_replaces_the_old_criteria():
    response = _follow_up("High school in Miami with sports", action="new_search")
    assert ("need", "after_care") not in _criteria(response)


def test_partial_follow_ups_still_refine():
    city = _follow_up("what about in Miami instead?")
    assert city["route"] == "refine"
    assert _criteria(city) == {("grade", "e"), ("location", "Miami"), ("need", "after_care")}
    grade = _follow_up("actually, middle school")
    assert grade["route"] == "refine"
    assert _criteria(grade) == {("grade", "m"), ("location", "Jacksonville"), ("need", "after_care")}


def test_naming_a_school_opens_its_detail():
    response = _follow_up("tell me more about Lark Harbor Academy")
    assert response["route"] == "school_detail"
    detail = next(b["payload"] for b in response["blocks"] if b["type"] == "school_detail")
    assert detail["school"]["name"] == "Lark Harbor Academy"


def test_question_about_a_school_answers_it_without_changing_the_search():
    response = _follow_up("does Lark Harbor Academy have STEM?")
    assert response["route"] == "school_detail"
    assert ("need", "stem") not in _criteria(response), "asking about one school does not add a filter"
    detail = next(b["payload"] for b in response["blocks"] if b["type"] == "school_detail")
    statuses = {row["criterion_id"]: row["status"] for row in detail["card"]["evidence"]}
    assert "stem" in [row.get("need") for row in detail["asked"]]
    assert all(row["id"] in statuses for row in detail["asked"])
    answer = next(b["payload"]["text"] for b in response["blocks"] if b["type"] == "message")
    assert "STEM" in answer
