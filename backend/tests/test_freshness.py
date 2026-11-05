"""School-reported answers age out: Partial note, requeue, answered_at on the card."""

from __future__ import annotations

from datetime import date

import pytest

from contracts import Criterion
from evidence.engine import evaluate_criterion
from evidence.status import answer_expired, max_age_days, stale_note
from gaps.inbox import add_question, reply_to_question, requeue_stale
from search.corpus import load_schools

TIDEWATER = "School fl-180001"


@pytest.fixture()
def school() -> dict:
    return next(row for row in load_schools() if row["id"] == TIDEWATER)


def test_after_care_ages_out_faster_than_default():
    assert max_age_days("after_care") == 180
    assert max_age_days("stem") == 365
    assert answer_expired("after_care", "2025-01-01", today=date(2026, 11, 3))
    assert not answer_expired("after_care", "2026-06-01", today=date(2026, 11, 3))


def test_stale_overlay_is_partial_with_as_of(school):
    overlays = {
        "osp.after_school_until": {
            "value": "18:00",
            "as_of": "2025-01-01",
            "answered_at": "2025-01-01T12:00:00+00:00",
            "confidence": "high",
            "source": "school_reported",
            "channel": "call",
        }
    }
    criterion = Criterion(id="c1", text="after-school care", need="after_care", strength="require", params={}, kind="need")
    record = evaluate_criterion(school, criterion, [], overlays)
    assert record.status == "partial"
    assert record.stale is True
    assert record.answered_at
    assert "may be out of date" in record.note
    assert stale_note("2025-01-01") in record.note


def test_fresh_overlay_still_confirms(school):
    overlays = {
        "osp.after_school_until": {
            "value": "18:00",
            "as_of": "2026-10-01",
            "answered_at": "2026-10-01T12:00:00+00:00",
            "confidence": "high",
            "source": "school_reported",
            "channel": "staff",
        }
    }
    criterion = Criterion(id="c1", text="after-school care", need="after_care", strength="require", params={}, kind="need")
    record = evaluate_criterion(school, criterion, [], overlays)
    assert record.status == "confirmed"
    assert record.stale is False
    assert record.answered_at


def test_requeue_stale_opens_the_question_again(school):
    state = {"sessions": {}, "inbox": [], "overlays": {}, "calls": {}}
    add_question(state, school, "after_care", "What time does after-school care end?", "s1")
    reply_to_question(state, state["inbox"][0]["id"], "Until 6.", "18:00", channel="email")
    state["overlays"][TIDEWATER]["osp.after_school_until"]["as_of"] = "2025-01-01"
    added = requeue_stale(state, today=date(2026, 11, 3))
    assert len(added) == 1
    assert added[0]["status"] == "open" and added[0]["need"] == "after_care"
    assert added[0]["parent_count"] == 0
    # Idempotent: already open.
    assert requeue_stale(state, today=date(2026, 11, 3)) == []
