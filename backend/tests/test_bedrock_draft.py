"""Bedrock draft criteria: code validates every item against the catalog. No AWS calls."""

from __future__ import annotations

import json

import pytest

import agent.bedrock_client as bc
from agent.extractor import extract
from search.corpus import known_cities, load_programs, load_schools
from search.engine import search_schools

QUERY = "Elementary school in Jacksonville with after-school care until 6pm"


@pytest.fixture
def bedrock(monkeypatch):
    """Turn Bedrock on and answer every converse call with the given text."""

    def answer(raw: str) -> None:
        monkeypatch.setattr(bc, "enabled", lambda: True)
        monkeypatch.setattr(bc, "converse", lambda model_id, system, user: raw)

    return answer


def _fenced(items: list[dict]) -> str:
    return "```json\n" + json.dumps(items) + "\n```"


def _hits(criteria) -> list[dict]:
    return search_schools(load_schools(), load_programs(), criteria, QUERY)


def test_valid_draft_matches_rules_results(bedrock):
    rules_hits = _hits(extract(QUERY, known_cities())[0])

    bedrock(
        _fenced(
            [
                {"kind": "grade", "value": "e", "text": "my kid is 7"},
                {"kind": "location", "value": "jacksonville", "text": "Jax"},
                {"kind": "need", "need": "after_care", "strength": "require", "params": {"until": "18:00"}, "text": "can't pick up before 6"},
            ]
        )
    )
    criteria, _ = extract("my kid is 7, we live in Jax, I can't pick up before 6", known_cities())

    by_kind = {c.kind: c for c in criteria}
    assert by_kind["grade"].value == "e"
    assert by_kind["location"].value == "Jacksonville"
    assert by_kind["need"].need == "after_care"
    assert by_kind["need"].params == {"until": "18:00"}
    assert by_kind["need"].ambiguities, "after_care keeps its on-site question"
    assert [s["id"] for s in _hits(criteria)] == [s["id"] for s in rules_hits]


def test_values_outside_the_catalog_are_dropped(bedrock):
    bedrock(
        _fenced(
            [
                {"kind": "grade", "value": "elementary", "text": "elementary"},
                {"kind": "location", "value": "Atlantis", "text": "Atlantis"},
                {"kind": "school_type", "value": "boarding", "text": "boarding"},
                {"kind": "need", "need": "pony_rides", "strength": "require", "text": "ponies"},
                {"kind": "need", "need": "after_care", "strength": "must", "text": "after care"},
                {"kind": "need", "need": "stem", "strength": "prefer", "params": {"until": "18:00"}, "text": "STEM"},
                {"kind": "need", "need": "after_care", "strength": "require", "params": {"until": "6pm"}, "text": "after care"},
            ]
        )
    )
    criteria, _ = extract("anything", known_cities())

    assert [(c.kind, c.need, c.params) for c in criteria] == [
        ("need", "stem", {}),
        ("need", "after_care", {}),
    ]


def test_need_null_becomes_unmapped(bedrock):
    bedrock(_fenced([{"kind": "need", "need": None, "strength": "prefer", "text": "how liberal"}]))
    criteria, _ = extract("how liberal is it", known_cities())

    assert [(c.id, c.need, c.text) for c in criteria] == [("c1", None, "how liberal")]


def test_reply_without_json_uses_rules(bedrock):
    bedrock("Sorry, I can't help with that.")
    criteria, _ = extract(QUERY, known_cities())

    assert {c.kind for c in criteria} == {"grade", "location", "need"}


def _turn(message: str) -> dict:
    from pipeline import turn
    from store import _empty

    return turn(_empty(), {"message": message}).model_dump()["engine"]


def test_engine_rules_when_bedrock_is_off():
    assert _turn(QUERY) == {"route": "rules", "extract": "rules", "errors": []}


def test_engine_bedrock_when_claude_answers(monkeypatch):
    draft = _fenced([{"kind": "grade", "value": "e", "text": "elementary"}])
    monkeypatch.setattr(bc, "enabled", lambda: True)
    monkeypatch.setattr(bc, "converse", lambda m, system, u: "new_search" if "route" in system else draft)

    assert _turn(QUERY) == {"route": "bedrock", "extract": "bedrock", "errors": []}


def test_engine_shows_fallback_and_reason(monkeypatch):
    def expired(model_id, system, user):
        raise RuntimeError("ExpiredToken")

    monkeypatch.setattr(bc, "enabled", lambda: True)
    monkeypatch.setattr(bc, "converse", expired)

    assert _turn(QUERY) == {
        "route": "rules_fallback",
        "extract": "rules_fallback",
        "errors": ["bedrock route failed: ExpiredToken", "bedrock extract failed: ExpiredToken"],
    }


def test_engine_route_answer_outside_the_list(bedrock):
    bedrock("maybe_search")
    engine = _turn(QUERY)

    assert engine["route"] == "rules_fallback"
    assert engine["errors"][0] == "bedrock route answer not allowed: 'maybe_search'"
