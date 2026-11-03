"""Parent community rules: safety, demand counts, votes, and evidence."""

from __future__ import annotations

import pytest

from community import service
from community.evidence import apply_community
from community.safety import check_post
from community.tags import stance, suggest_tags
from contracts import Criterion
from evidence.engine import evaluate_criterion
from search.corpus import load_programs, load_schools

BEAUCLERC = "School fl-180019"
CEDAR = "School fl-180100"
MARINER = "School fl-95390"


def _school(school_id: str) -> dict:
    return next(row for row in load_schools() if row["id"] == school_id)


@pytest.fixture()
def state() -> dict:
    data = {"sessions": {}, "inbox": [], "overlays": {}}
    service.ensure(data)
    return data


def _record(state: dict, school_id: str, need: str, strength: str = "require"):
    school = _school(school_id)
    criterion = Criterion(id="c1", text=need, need=need, strength=strength)
    overlays = (state.get("overlays") or {}).get(school_id) or {}
    record = evaluate_criterion(school, criterion, load_programs(), overlays)
    return apply_community(record, school, criterion, state)


@pytest.mark.parametrize(
    "text, kind",
    [
        ("My son Ethan needs after-care.", "name"),
        ("my daughter, Maya, loves robotics", "name"),
        ("Mr. Lopez is the best teacher", "name"),
        ("Leo is in 6th grade this year", "name"),
        ("Email me at parent@example.com", "email"),
        ("Call me at (904) 555-0142", "phone"),
        ("We live at 1200 Oak Grove Road", "address"),
    ],
)
def test_safety_blocks_personal_information(text, kind):
    result = check_post(text)
    assert not result["ok"]
    assert any(item["type"] == kind for item in result["findings"])


@pytest.mark.parametrize(
    "text",
    [
        "Does after-care run past 5:30?",
        "The robotics club is great for beginners.",
        "Our experience with the IEP process was good.",
        "Does the bus cover the area south of Beach Blvd?",
        "My kid loves the art teacher.",
    ],
)
def test_safety_lets_clean_posts_through(text):
    assert check_post(text)["ok"]


def test_blocked_post_is_never_published(state):
    before = len(state["community"]["posts"])
    result = service.create_thread(state, _school(BEAUCLERC), "parent_a", "question", "My son Ethan wants robotics.", ["stem"])
    assert result["ok"] is False
    assert len(state["community"]["posts"]) == before


def test_demand_counts_once_per_parent_per_month(state):
    start = service.demand_for(state, BEAUCLERC, "after_care")
    service.record_ask(state, BEAUCLERC, "after_care", "session-1", "agent")
    service.record_ask(state, BEAUCLERC, "after_care", "session-1", "agent")
    assert service.demand_for(state, BEAUCLERC, "after_care") == start + 1


def test_new_question_counts_toward_demand(state):
    start = service.demand_for(state, BEAUCLERC, "transportation")
    result = service.create_thread(state, _school(BEAUCLERC), "parent_b", "question", "Is there a bus stop near the library?", ["transportation"])
    assert result["ok"]
    assert service.demand_for(state, BEAUCLERC, "transportation") == start + 1


def test_vote_toggles(state):
    post_id = service.threads_for(state, BEAUCLERC)[0]["post_id"]
    first = service.vote(state, post_id, "parent_a")
    second = service.vote(state, post_id, "parent_a")
    assert first["voted"] is True and second["voted"] is False
    assert second["votes"] == first["votes"] - 1


def test_threads_sort_by_votes(state):
    votes = [row["votes"] for row in service.threads_for(state, BEAUCLERC)]
    assert votes == sorted(votes, reverse=True)


def test_posts_support_but_never_confirm(state):
    record = _record(state, CEDAR, "after_care")
    assert record.status == "partial"
    assert record.source.type == "community"
    assert record.source.confidence == "low"
    assert record.post_ids


def test_neutral_threads_leave_unknown(state):
    record = _record(state, BEAUCLERC, "after_care")
    assert record.status == "unknown"


def test_negative_posts_flag_without_missing_must_have(state):
    record = _record(state, MARINER, "teacher_stability")
    assert record.status in {"needs_attention", "confirmed"}
    if record.source and record.source.type == "community":
        assert record.source.confidence == "low"


def test_school_answer_confirms_and_closes_inbox(state):
    state["inbox"].append({
        "id": "q-1", "school_id": BEAUCLERC, "school_name": "Beauclerc STEM Middle", "need": "after_care",
        "question": "?", "session_ids": ["s"], "parent_count": 1, "status": "open", "replies": [],
    })
    thread_id = service.threads_for(state, BEAUCLERC, need="after_care")[0]["post_id"]
    result = service.reply(state, thread_id, "school_staff", "After-care runs until 6:00 PM on campus.", {"need": "after_care", "value": "18:00"})
    assert result["ok"] and result["post"]["verified_school"]
    assert state["inbox"][0]["status"] == "answered"
    record = _record(state, BEAUCLERC, "after_care")
    assert record.status == "confirmed"
    assert record.source.type == "school_reported"


def test_school_yes_no_answer_for_need_without_field(state):
    assert _record(state, BEAUCLERC, "foreign_language", "prefer").status == "unknown"
    created = service.create_thread(state, _school(BEAUCLERC), "parent_a", "question", "Is Spanish offered?", ["foreign_language"])
    service.reply(state, created["post"]["post_id"], "school_staff", "Yes, Spanish 1 and 2 are offered.", {"need": "foreign_language", "offers": True})
    record = _record(state, BEAUCLERC, "foreign_language", "prefer")
    assert record.status == "confirmed"
    assert record.source.path == service.school_answer_for(state, BEAUCLERC, "foreign_language")["post_id"]


def test_tags_and_stance():
    tags = [row["need"] for row in suggest_tags("Does after-school care run late? Also curious about robotics.")]
    assert "after_care" in tags and "stem" in tags
    assert stance("Is after-care good?", "question") == "neutral"
    assert stance("We love the after-care staff, very helpful.", "experience") == "positive"
