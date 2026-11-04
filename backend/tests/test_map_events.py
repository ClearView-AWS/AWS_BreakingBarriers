"""Map events: pin select, pin compare, search-this-area refine."""

from __future__ import annotations

from store import _empty
from testing_helpers import results_payload, search_turn
from pipeline import turn

CARE = "Middle school in Seattle with STEM and after-school care. Money is tight."


def test_pins_compared_returns_comparison():
    state = _empty()
    first = search_turn(state, {"message": CARE})
    schools = results_payload(first)["schools"]
    assert len(schools) >= 2
    ids = [schools[0]["id"], schools[1]["id"]]
    compared = turn(state, {"session_id": first.session_id, "event": "pins_compared", "school_ids": ids})
    assert compared.route == "compare"
    assert any(block.type == "comparison" for block in compared.blocks)


def test_pin_selected_opens_school_detail():
    state = _empty()
    first = search_turn(state, {"message": CARE})
    school_id = results_payload(first)["schools"][0]["id"]
    detail = turn(state, {"session_id": first.session_id, "event": "pin_selected", "school_ids": [school_id]})
    assert detail.route == "school_detail"
    assert any(block.type == "school_detail" for block in detail.blocks)


def test_area_changed_moves_search_center_and_adds_distance():
    state = _empty()
    first = search_turn(state, {"message": CARE})
    moved = turn(
        state,
        {
            "session_id": first.session_id,
            "event": "area_changed",
            "area": {"center": [47.62, -122.33], "radius_mi": 5},
        },
    )
    assert moved.route == "refine"
    results = results_payload(moved)
    assert results["center"] == [47.62, -122.33]
    assert any(row.kind == "distance" for row in moved.criteria)
    message = next(block.payload["text"] for block in moved.blocks if block.type == "message")
    assert "moved the search area" in message.lower()
