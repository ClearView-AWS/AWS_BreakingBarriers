"""Edge cases of plan.md's Rules in Code: evidence status, scoring and ranking."""

from __future__ import annotations

import pytest

from contracts import Criterion, EvidenceRecord, Source
from evidence.engine import evaluate_criterion
from evidence.reviews import review_status
from evidence.scorer import is_missed_must, score_school
from evidence.status import downgrade_for_age, parse_date
from pipeline import _rank_key
from search.corpus import load_programs, load_schools

BY_NAME = {school["name"]: school for school in load_schools()}
STEM = "STEM / Coding"


def _record(status: str, confidence: str | None = "high") -> EvidenceRecord:
    source = Source(type="state_data", path="x", confidence=confidence) if confidence else None
    return EvidenceRecord(school_id="s", criterion_id="c", status=status, source=source)


def _care(reading: str | None = None) -> Criterion:
    return Criterion(id="c1", text="after-school care", need="after_care", strength="require", kind="need", resolved_reading=reading)


def _reviews(*polarities: str) -> dict:
    return {
        "reviews_full": [
            {"created_date": f"2025-0{i + 1}-01", "sentiments": [{"topic": STEM, "sentiment_enum": p}]}
            for i, p in enumerate(polarities)
        ]
    }


# Ranking --------------------------------------------------------------------

def test_ranking_uses_match_only_and_never_coverage():
    cards = [
        {"name": "Zed", "match": 0.8, "coverage": 1.0},
        {"name": "Abe", "match": 0.8, "coverage": 0.0},
        {"name": "Top", "match": 0.9, "coverage": 0.0},
    ]
    assert [card["name"] for card in sorted(cards, key=_rank_key)] == ["Top", "Abe", "Zed"]


def test_coverage_counts_confirmed_and_needs_attention_only():
    rows = [("prefer", _record(s)) for s in ("confirmed", "needs_attention", "partial", "unknown")]
    scored = score_school(rows)
    assert scored["coverage"] == 0.5
    assert scored["verified"] == "2 of 4"


# Confirmed needs medium or high confidence and data under 18 months old ------

def test_low_confidence_or_old_data_is_only_partial():
    fresh = parse_date("2026-07-15")
    assert downgrade_for_age("confirmed", "medium", fresh) == "confirmed"
    assert downgrade_for_age("confirmed", "low", fresh) == "partial"
    # The app's clock is Nov 3, 2026, so 18 months back is May 3, 2025.
    assert downgrade_for_age("confirmed", "high", parse_date("2025-05-03")) == "confirmed"
    assert downgrade_for_age("confirmed", "high", parse_date("2025-05-02")) == "partial"


# Reviews: 2+ mostly positive support, 3+ mostly negative need attention -----

def test_review_thresholds():
    assert review_status(_reviews("positive"), [STEM]) is None
    assert review_status(_reviews("positive", "positive"), [STEM])["status"] == "partial"
    assert review_status(_reviews("negative", "negative"), [STEM]) is None
    assert review_status(_reviews("negative", "negative", "negative"), [STEM])["status"] == "needs_attention"
    assert review_status(_reviews("positive", "negative", "negative", "negative"), [STEM])["status"] == "needs_attention"


# Sources that can only support ----------------------------------------------

def test_a_school_website_supports_but_never_confirms():
    record = evaluate_criterion(BY_NAME["Cedar Creek STEM Middle"], _care("on_site"), programs=[])
    assert record.status == "partial"
    assert record.source is not None and record.source.type == "school_website"


def test_a_website_that_disagrees_with_the_profile_is_flagged():
    record = evaluate_criterion(BY_NAME["Tidewater STEM Charter"], _care("on_site"), programs=[])
    assert record.conflict is not None
    assert record.conflict.website_value == "16:00"


def test_a_program_with_only_past_sessions_does_not_count():
    record = evaluate_criterion(BY_NAME["Northside STEM Middle"], _care("nearby_ok"), programs=load_programs())
    assert record.status == "unknown"
    assert "past" in record.note


# Missed a must-have needs solid evidence ------------------------------------

def test_missed_must_needs_medium_or_high_confidence():
    assert is_missed_must(_record("needs_attention", "high"), "require")
    assert is_missed_must(_record("needs_attention", "medium"), "require")
    assert not is_missed_must(_record("needs_attention", "low"), "require")
    assert not is_missed_must(_record("needs_attention", "high"), "prefer")
    assert is_missed_must(_record("confirmed", "high"), "avoid")


# Distance is computed from latlon -------------------------------------------

@pytest.mark.parametrize(
    ("miles", "status"),
    [(8.0, "confirmed"), (9.5, "partial"), (11.0, "partial"), (11.1, "needs_attention"), (None, "unknown")],
)
def test_distance_is_computed_evidence(miles, status):
    school = {"id": "s", "name": "Here", "created": "2026-02-01", "_distance_miles": miles}
    criterion = Criterion(id="c9", text="Within 8 miles", kind="distance", strength="prefer", params={"max_miles": 8})
    record = evaluate_criterion(school, criterion, programs=[])
    assert record.status == status
    if miles is not None:
        assert record.source is not None
        assert (record.source.type, record.source.path) == ("computed", "latlon")
