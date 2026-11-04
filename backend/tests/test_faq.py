"""FAQ sidebar: ordering by asks, one ask per parent, safety, and duplicates."""

from __future__ import annotations

import faq


def _state() -> dict:
    return {"sessions": {}, "inbox": [], "overlays": {}}


def test_starting_questions_have_answers_and_sources_and_no_asks():
    rows = faq.list_faq(_state())
    assert rows and all(row["answer"] and row["source"] for row in rows)
    assert all(row["asked"] == 0 for row in rows)


def test_asks_count_once_per_parent_and_sort_first():
    state = _state()
    last = faq.list_faq(state)[-1]["id"]
    faq.toggle_ask(state, last, "parent_a")
    faq.toggle_ask(state, last, "parent_b")
    top = faq.list_faq(state, "parent_a")[0]
    assert top["id"] == last and top["asked"] == 2 and top["asked_by_me"]
    faq.toggle_ask(state, last, "parent_a")
    assert next(r for r in faq.list_faq(state) if r["id"] == last)["asked"] == 1


def test_added_question_is_unanswered_and_counts_its_asker():
    state = _state()
    result = faq.add_question(state, "parent_a", "Can I filter by bus routes?")
    assert result["ok"] and not result["existing"]
    row = next(r for r in faq.list_faq(state) if r["id"] == result["id"])
    assert row["added"] and row["answer"] is None and row["asked"] == 1


def test_same_question_adds_an_ask_instead_of_a_copy():
    state = _state()
    first = faq.add_question(state, "parent_a", "Can I filter by bus routes?")
    again = faq.add_question(state, "parent_b", "can i filter by bus routes")
    assert again["existing"] and again["id"] == first["id"]
    assert len([r for r in faq.list_faq(state) if r["added"]]) == 1
    assert next(r for r in faq.list_faq(state) if r["id"] == first["id"])["asked"] == 2


def test_personal_information_is_blocked():
    state = _state()
    result = faq.add_question(state, "parent_a", "Email me at parent@example.com about tuition")
    assert not result["ok"]
    assert not [r for r in faq.list_faq(state) if r["added"]]


def test_similar_finds_a_starting_question():
    ids = faq.similar(_state(), "what does the match percentage mean")
    assert ids and ids[0] == "match_score"
