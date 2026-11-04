"""Map data on the results block: the search center and nearby-program pins."""

from __future__ import annotations

import evidence.engine as engine
from search.corpus import load_programs
from search.geo import miles_between
from store import _empty
from testing_helpers import results_payload, search_turn

CARE = "Elementary school in Seattle with after-school care until 6pm"
NEARBY_OK = CARE + ", a nearby program is fine"


def _results(message: str) -> dict:
    response = search_turn(_empty(), {"message": message})
    return results_payload(response)


def _cards(results: dict) -> dict[str, dict]:
    return {card["id"]: card for card in results["schools"] + results["gaps"] + results["missed"]}


def _links(results: dict) -> list[dict]:
    return [link for pin in results["programs"] for link in pin["links"]]


def test_results_carry_the_search_center():
    assert _results(CARE)["center"] == [47.6062, -122.3321]


def test_program_pins_match_confirmed_program_evidence_on_shown_cards():
    results = _results(NEARBY_OK)
    assert results["programs"], "the demo city has programs within a mile of some elementary schools"
    cards = _cards(results)
    programs = {str(program["id"]): program for program in load_programs()}
    for pin in results["programs"]:
        program = programs[pin["id"]]
        assert (pin["lat"], pin["lon"]) == (program["_lat"], program["_lon"])
        for link in pin["links"]:
            card = cards[link["school_id"]]  # every pinned school is on screen
            row = next(r for r in card["evidence"] if r["criterion_id"] == link["criterion_id"])
            assert row["status"] == "confirmed"
            assert row["source"]["type"] == "program" and row["source"]["path"] == f"programs/{pin['id']}"
            assert abs(miles_between((card["lat"], card["lon"]), (pin["lat"], pin["lon"])) - link["miles"]) < 0.06


def test_no_program_pins_unless_the_parent_accepts_a_nearby_program():
    assert _results(CARE)["programs"] == []


def test_programs_farther_than_a_mile_do_not_count(monkeypatch):
    assert engine.PROGRAM_RADIUS_MILES == 1.0
    assert all(link["miles"] <= 1.0 for link in _links(_results(NEARBY_OK)))

    # The radius is what keeps farther programs out: widen it and they come back.
    monkeypatch.setattr(engine, "PROGRAM_RADIUS_MILES", 3.0)
    assert any(link["miles"] > 1.0 for link in _links(_results(NEARBY_OK)))
