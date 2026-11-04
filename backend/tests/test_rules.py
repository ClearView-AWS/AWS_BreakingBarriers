"""Deterministic rules: scoring, evidence, search filters, and the demo turn."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("GS_STATE_PATH", str(Path(__file__).resolve().parents[2] / "data" / "runtime" / "test-state.json"))

from agent.citations import validate_text
from agent.extractor import extract
from agent.router import route_message
from contracts import Criterion, EvidenceRecord, Source
from evidence.engine import evaluate_criterion
from evidence.reviews import topic_tally
from evidence.scorer import score_school, status_value
from evidence.status import apply_rule, downgrade_for_age, parse_date
from pipeline import turn
from search.corpus import clear_corpus_cache, known_cities, load_programs, load_schools
from search.engine import passes_hard_filters, search_schools
from search.query import build_query, hard_filter_fields
from store import State, load_state


@pytest.fixture(autouse=True)
def clean_state():
    path = Path(os.environ["GS_STATE_PATH"])
    if path.exists():
        path.unlink()
    yield
    if path.exists():
        path.unlink()


def _criterion(**kwargs) -> Criterion:
    base = dict(id="c1", text="stem", need="stem", strength="require", kind="need")
    base.update(kwargs)
    return Criterion(**base)


def test_score_formula_and_avoid_inversion():
    rows = [
        ("require", EvidenceRecord(school_id="s", criterion_id="a", status="confirmed", source=Source(type="state_data", path="summary_rating", confidence="high"))),
        ("prefer", EvidenceRecord(school_id="s", criterion_id="b", status="unknown")),
    ]
    scored = score_school(rows)
    assert scored["match"] == pytest.approx(3.5 / 4, abs=1e-4)
    assert scored["verified"] == "1 of 2"
    assert status_value("confirmed", "avoid") == 0.0
    assert status_value("needs_attention", "avoid") == 1.0
    assert status_value("unknown", "avoid") == 0.5
    assert status_value("partial", "avoid") == pytest.approx(0.4)


def test_stale_confirmed_becomes_partial():
    assert downgrade_for_age("confirmed", "high", parse_date("2026-07-15")) == "confirmed"
    assert downgrade_for_age("confirmed", "unknown", parse_date("2026-07-15")) == "partial"
    assert downgrade_for_age("confirmed", "high", parse_date("2020-01-01")) == "partial"
    assert downgrade_for_age("needs_attention", "high", parse_date("2020-01-01")) == "needs_attention"


def test_old_reviews_count_half():
    school = {
        "reviews_full": [
            {"created_date": "2014-01-01", "sentiments": [{"topic": "STEM / Coding", "sentiment_enum": "positive"}]},
            {"created_date": "2015-01-01", "sentiments": [{"topic": "STEM / Coding", "sentiment_enum": "positive"}]},
            {"created_date": "2025-01-01", "sentiments": [{"topic": "STEM / Coding", "sentiment_enum": "positive"}]},
        ]
    }
    tally = topic_tally(school, "STEM / Coding")
    assert tally["raw"] == 3
    assert tally["positive"] == pytest.approx(2.0)


def test_reviews_do_not_confirm():
    school = {
        "id": "School fl-1",
        "name": "Review Only",
        "created": "2026-02-01",
        "reviews_full": [
            {"created_date": "2025-01-01", "sentiments": [{"topic": "STEM / Coding", "sentiment_enum": "positive"}]},
            {"created_date": "2025-06-01", "sentiments": [{"topic": "STEM / Coding", "sentiment_enum": "positive"}]},
        ],
    }
    record = evaluate_criterion(school, _criterion(), programs=[])
    assert record.status == "partial"
    assert record.source is not None and record.source.type == "parent_reviews"


def test_missing_field_stays_in_results():
    rated = {"id": "a", "name": "Rated", "city": "Jacksonville", "level_codes": ["m"], "summary_rating": 9, "created": "2026-01-01"}
    missing = {"id": "b", "name": "Unrated", "city": "Jacksonville", "level_codes": ["m"], "created": "2026-01-01"}
    criteria = [
        Criterion(id="c1", text="Jacksonville", kind="location", value="Jacksonville", strength="require"),
        Criterion(id="c2", text="middle school", kind="grade", value="m", strength="require"),
        _criterion(id="c3", text="top school", need="high_performing", strength="prefer"),
    ]
    found = search_schools([rated, missing], [], criteria, limit=None)
    assert {school["id"] for school in found} == {"a", "b"}
    assert passes_hard_filters(missing, criteria)


def test_query_filters_are_only_location_grade_and_type():
    criteria = [
        Criterion(id="c1", text="Jacksonville", kind="location", value="Jacksonville", strength="require"),
        Criterion(id="c2", text="middle school", kind="grade", value="m", strength="require"),
        Criterion(id="c3", text="charter", kind="school_type", value="charter", strength="require"),
        _criterion(need="high_performing", strength="prefer"),
    ]
    query = build_query(criteria, "middle school")
    assert set(hard_filter_fields(query)) == {"city_untokenized", "level_codes", "entity_type"}
    assert "summary_rating" not in str(query["query"]["bool"].get("filter"))


def test_citation_validator_drops_uncited_sentences():
    kept = validate_text(
        "STEM is confirmed. [[cite:osp.school_sub_type]] The campus feels joyful.",
        {"osp.school_sub_type"},
    )
    assert "joyful" not in kept
    assert "confirmed" in kept


def test_extractor_demo_query():
    found, _ = extract(
        "Middle school in Jacksonville with STEM and after-school care. Money is tight.",
        known_cities(),
    )
    by_need = {item.need or item.kind: item for item in found}
    assert by_need["grade"].value == "m"
    assert by_need["location"].value == "Jacksonville"
    assert by_need["stem"].strength == "require"
    assert by_need["after_care"].strength == "require"
    assert by_need["after_care"].ambiguities
    assert by_need["low_cost"].strength == "prefer"


def test_negation_and_liberal_and_spanish():
    religious, _ = extract("elementary school in Orlando, not religious", known_cities())
    assert any(item.need == "non_religious" and item.strength == "require" for item in religious)
    liberal, _ = extract("How liberal are middle schools in Jacksonville?", known_cities())
    assert any(item.need is None and "liberal" in item.text for item in liberal)
    spanish, _ = extract("escuela intermedia en Jacksonville con ciencias", known_cities())
    assert any(item.kind == "grade" and item.value == "m" for item in spanish)
    assert any(item.need == "stem" for item in spanish)


def test_demo_turn_asks_before_search_then_skip_keeps_gaps():
    clear_corpus_cache()
    with State() as state:
        first = turn(
            state,
            {"message": "Middle school in Jacksonville with STEM and after-school care. Money is tight."},
        )
        assert not any(block.type == "results" for block in first.blocks)
        questions = next(block.payload for block in first.blocks if block.type == "questions")
        assert questions["skip_label"] == "Just show me results"
        assert 1 <= len(questions["items"]) <= 3
        question = questions["items"][0]
        assert question["reason"] == "ambiguous_reading"
        assert "after-school" in question["text"]
        assert len(question["options"]) == 2
        assert question.get("default")
        brief = next(block.payload for block in first.blocks if block.type == "brief")
        assert brief["approved"] is False

        response = turn(state, {"session_id": first.session_id, "event": "skip_to_results", "action": "refresh"})
    results = next(block.payload for block in response.blocks if block.type == "results")
    assert results["schools"]
    assert results["missed"]
    assert results["gaps"]
    unknown = results["gaps"][0]
    assert any(row["status"] == "unknown" for row in unknown["evidence"])
    # A require failure stays visible instead of being deleted.
    assert all(card["id"] not in {row["id"] for row in results["schools"]} for card in results["missed"])
    approved = next(block.payload for block in response.blocks if block.type == "brief")
    assert approved["approved"] is True


def test_thin_request_asks_for_city_and_grade_before_results():
    clear_corpus_cache()
    with State() as state:
        first = turn(state, {"message": "STEM schools with after-school care"})
        assert not any(block.type == "results" for block in first.blocks)
        questions = next(block.payload for block in first.blocks if block.type == "questions")
        reasons = [item["reason"] for item in questions["items"]]
        assert "missing_location" in reasons
        assert len(questions["items"]) <= 3

        approved = turn(state, {"session_id": first.session_id, "event": "brief_approved", "action": "refresh"})
        # Approving without answering leaves location unset, so still no hard-filter match required —
        # but the gate is open and a results block is returned.
        assert any(block.type == "results" for block in approved.blocks)


def test_why_not_mariner_is_the_grade_filter():
    clear_corpus_cache()
    with State() as state:
        from testing_helpers import search_turn

        first = search_turn(
            state,
            {"message": "Middle school in Jacksonville with STEM and after-school care. Money is tight."},
        )
        second = turn(
            state,
            {"session_id": first.session_id, "message": "Why isn't Mariner Elementary here?"},
        )
    payload = next(block.payload for block in second.blocks if block.type == "why_not")
    assert payload["filtered_out"] is True
    assert "elementary" in payload["text"].lower() or "pre-k" in payload["text"].lower()


def test_liberal_followup_offers_data_backed_needs():
    clear_corpus_cache()
    with State() as state:
        from testing_helpers import search_turn

        first = search_turn(
            state,
            {"message": "Middle school in Jacksonville with STEM and after-school care. Money is tight."},
        )
        second = turn(state, {"session_id": first.session_id, "message": "How liberal are these schools?"})
    question = next(block.payload for block in second.blocks if block.type == "question")
    labels = [option["label"].lower() for option in question["options"]]
    assert question["reason"] == "unmapped"
    assert any("inclusion" in label for label in labels)
    assert any("restorative" in label for label in labels)


def test_cost_does_not_promise_an_award():
    clear_corpus_cache()
    schools = load_schools()
    private = next(school for school in schools if school["name"] == "Riverside Preparatory Middle")
    with State() as state:
        from testing_helpers import search_turn

        first = search_turn(state, {"message": "Middle school in Jacksonville"})
        response = turn(
            state,
            {"session_id": first.session_id, "action": "cost", "school_ids": [private["id"]]},
        )
    cost = next(block.payload for block in response.blocks if block.type == "cost")
    estimate = cost["schools"][0]
    assert estimate["net"] is None
    assert estimate["tuition"]
    blob = str(estimate)
    assert "You may qualify" in blob
    assert "fldoe.org" in blob
    assert "15200" in blob or "15,200" in blob


def test_save_builds_a_visit_checklist_for_unknowns():
    clear_corpus_cache()
    schools = load_schools()
    beau = next(school for school in schools if school["name"] == "Beauclerc STEM Middle")
    with State() as state:
        from testing_helpers import search_turn

        first = search_turn(
            state,
            {"message": "Middle school in Jacksonville with STEM and after-school care. Money is tight."},
        )
        saved = turn(state, {"session_id": first.session_id, "action": "save", "school_ids": [beau["id"]]})
    checklist = next(block.payload for block in saved.blocks if block.type == "checklist")
    assert beau["id"] in checklist["school_ids"]
    assert any(item["need"] == "after_care" for item in checklist["items"])


def test_school_reply_confirms_the_gap():
    clear_corpus_cache()
    schools = load_schools()
    beau = next(school for school in schools if school["name"] == "Beauclerc STEM Middle")
    with State() as state:
        from testing_helpers import search_turn

        first = search_turn(
            state,
            {"message": "Middle school in Jacksonville with STEM and after-school care. Money is tight."},
        )
        turn(
            state,
            {
                "session_id": first.session_id,
                "action": "ask_school",
                "school_ids": [beau["id"]],
                "need": "after_care",
            },
        )
        inbox = state["inbox"]
        assert len(inbox) == 1
        from gaps.inbox import reply_to_question

        reply_to_question(state, inbox[0]["id"], "Care runs until 6pm.", "18:00")
        refreshed = turn(state, {"session_id": first.session_id, "action": "refresh"})
    cards = []
    for block in refreshed.blocks:
        if block.type == "results":
            cards.extend(block.payload["schools"])
            cards.extend(block.payload["gaps"])
            cards.extend(block.payload["missed"])
    beau_card = next(card for card in cards if card["id"] == beau["id"])
    care = next(row for row in beau_card["evidence"] if row["criterion_id"] and _need(first, row) )
    # Find the after-care row by source path after the reply.
    care_rows = [row for row in beau_card["evidence"] if row.get("source") and "after_school" in row["source"]["path"]]
    assert care_rows
    assert care_rows[0]["status"] == "confirmed"
    assert care_rows[0]["source"]["type"] == "school_reported"


def _need(response, row) -> bool:
    return True


def test_routes():
    assert route_message("What is CTE?", False)[0] == "define"
    assert route_message("Why isn't Bayside listed?", True)[0] == "why_not"
    assert route_message("compare Tidewater and Riverside", True)[0] == "compare"
