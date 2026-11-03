"""Getting in: status rules, sources, and that it stays out of match and coverage."""

from __future__ import annotations

from datetime import date

from enrollment.access import by_deadline, getting_in
from pipeline import turn
from search.corpus import load_schools

TODAY = date(2026, 11, 3)
BY_NAME = {school["name"]: school for school in load_schools()}


def _school(**osp) -> dict:
    return {"id": "School test", "name": "Test Charter", "entity_type": "charter", "city": "Jacksonville",
            "created": "2026-02-01T12:00:00-05:00", "osp": osp}


def test_demo_schools_get_each_status():
    expected = {
        "Beauclerc STEM Middle": ("partial", "Lottery · apply by Jan 15 (73 days left)"),
        "Riverside Preparatory Middle": ("partial", "Application · apply by Feb 1 (90 days left)"),
        "Tidewater STEM Charter": ("confirmed", "Open seats for 6th grade"),
        "Arlington STEM Academy": ("needs_attention", "Deadline passed Oct 1 · ask about mid-year openings"),
        "Northside STEM Middle": ("needs_attention", "Waitlist only for 6th grade · ask about openings"),
        "Landmark Christian Middle": ("unknown", "Ask about open seats"),
        "St. Johns STEM Middle": ("unknown", "Is this your zoned school?"),
    }
    for name, (status, line) in expected.items():
        record = getting_in(BY_NAME[name], "m", today=TODAY)
        assert (record["status"], record["line"]) == (status, line), name


def test_reported_counts_are_shown_as_reported_with_their_date():
    record = getting_in(BY_NAME["Beauclerc STEM Middle"], "m", today=TODAY)
    assert record["detail"] == "Last year: 210 applicants for 90 sixth-grade seats"
    assert record["detail_source"] == "School-reported, Mar 2026"
    assert "[[cite:osp.applicants_last_year]]" in record["note"]


def test_deadline_boundaries():
    due_today = getting_in(_school(application_deadline_date=["11/3/2026"]), today=TODAY)
    assert (due_today["status"], due_today["days_left"]) == ("partial", 0)
    passed = getting_in(_school(application_deadline_date=["1/15/2026"]), today=TODAY)
    assert passed["status"] == "needs_attention"
    stale = getting_in(_school(application_deadline_date=["10/1/2025"]), today=TODAY)
    assert stale["status"] == "unknown"  # more than a year old: probably last cycle's
    placeholder = getting_in(_school(application_deadline_date=["1/1/2050"]), today=TODAY)
    assert placeholder["status"] == "unknown" and placeholder["deadline"] is None


def test_open_seats_count_for_six_months_only():
    fresh = getting_in(_school(seats_by_grade=[{"grade": "6", "open_seats": 5, "waitlist": False, "as_of": "2026-06-01"}]), "m", today=TODAY)
    old = getting_in(_school(seats_by_grade=[{"grade": "6", "open_seats": 5, "waitlist": False, "as_of": "2026-04-01"}]), "m", today=TODAY)
    other_grade = getting_in(_school(seats_by_grade=[{"grade": "9", "open_seats": 5, "waitlist": False, "as_of": "2026-10-01"}]), "m", today=TODAY)
    assert fresh["status"] == "confirmed"
    assert old["status"] == "unknown"
    assert other_grade["status"] == "unknown"


def test_the_schools_own_answer_wins_over_its_profile():
    school = _school(application_deadline_date=["10/1/2026"])
    answer = {"osp.seats_by_grade": {"value": [{"grade": "6", "open_seats": 3, "waitlist": False, "as_of": "2026-11-02"}], "as_of": "2026-11-02"}}
    record = getting_in(school, "m", overlays=answer, today=TODAY)
    assert record["status"] == "confirmed"
    assert record["source"]["type"] == "school_reported"


def test_every_line_has_an_official_link_and_type_defaults_by_entity():
    for school in load_schools():
        record = getting_in(school, today=TODAY)
        assert record["official"]["url"].startswith("https://"), school["id"]
        assert record["note"], school["id"]  # at least the cited sentence on how admission works
    sample_public = getting_in(BY_NAME["Harbor Point Elementary School"], today=TODAY)
    assert sample_public["how"] == "zoned" and sample_public["zoned_prompt"]


def test_saved_list_puts_the_soonest_open_deadline_first():
    rows = [
        {"name": "Passed", "days_left": -33},
        {"name": "Feb", "days_left": 90},
        {"name": "Unknown", "days_left": None},
        {"name": "Jan", "days_left": 73},
    ]
    assert [row["name"] for row in by_deadline(rows)] == ["Jan", "Feb", "Passed", "Unknown"]


def test_the_api_passes_the_zoned_tap_through():
    from app import TurnIn

    body = TurnIn(session_id="s1", action="refresh", zoned={"school_id": "School fl-180011"})
    assert body.model_dump()["zoned"] == {"school_id": "School fl-180011"}


def test_zoned_tap_stores_only_the_school_id_and_never_moves_the_match():
    state = {"sessions": {}, "inbox": [], "overlays": {}}
    first = turn(state, {"message": "Middle school in Jacksonville with STEM", "action": "new_search"})
    cards = next(block.payload for block in first.blocks if block.type == "results")["schools"]
    target = next(card for card in cards if card["access"]["zoned_prompt"])
    second = turn(state, {"session_id": first.session_id, "zoned": {"school_id": target["id"]}, "action": "refresh"})
    after = {card["id"]: card for block in second.blocks if block.type == "results" for card in block.payload["schools"]}
    assert after[target["id"]]["access"]["status"] == "confirmed"
    assert after[target["id"]]["match"] == target["match"]
    assert after[target["id"]]["verified"] == target["verified"]
    assert state["sessions"][first.session_id]["zoned"] == [target["id"]]
    assert all(row["criterion_id"] != "access" for row in after[target["id"]]["evidence"])
