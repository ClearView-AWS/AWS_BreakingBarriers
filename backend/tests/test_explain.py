"""Model-written text keeps only sentences whose numbers appear in what they cite."""

from __future__ import annotations

from agent.citations import known_numbers, number_claims, validate_model_text

FACTS = {
    "osp.after_school_until": known_numbers(["17:30", "After-school care is only partly supported: 5:30 PM."]),
    "osp.school_sub_type": known_numbers(["STEM"]),
    "osp.tuition": known_numbers([12000]),
}
PARENT = known_numbers(["18:00"])


def test_fabricated_time_is_dropped():
    text = "After-school care runs until 7:00 PM, so it covers your 6 PM pickup [[cite:osp.after_school_until]]."
    assert validate_model_text(text, FACTS, PARENT) == ""


def test_true_time_and_parent_time_are_kept():
    text = "After-school care ends at 5:30 PM, before your 6 PM pickup [[cite:osp.after_school_until]]."
    assert validate_model_text(text, FACTS, PARENT) == text


def test_number_must_come_from_the_cited_path():
    # 12,000 is real tuition, but this sentence cites the after-school field.
    text = "Care costs $12,000 a year [[cite:osp.after_school_until]]."
    assert validate_model_text(text, FACTS, PARENT) == ""
    cited = "Tuition is $12,000 a year [[cite:osp.tuition]]."
    assert validate_model_text(cited, FACTS, PARENT) == cited


def test_derived_numbers_are_not_trusted():
    text = "Care ends 30 minutes before your pickup [[cite:osp.after_school_until]]."
    assert validate_model_text(text, FACTS, PARENT) == ""


def test_unknown_citation_and_uncited_sentences_are_dropped():
    text = "It is a STEM school [[cite:osp.made_up]]. Families love it."
    assert validate_model_text(text, FACTS, PARENT) == ""


def test_only_the_bad_sentence_is_dropped():
    good = "It is a STEM school [[cite:osp.school_sub_type]]."
    bad = "Care runs until 8 PM [[cite:osp.after_school_until]]."
    assert validate_model_text(f"{good} {bad}", FACTS, PARENT) == good


def test_clock_time_without_meridiem_reads_both_ways():
    assert number_claims("ends at 5:30") == [{"t:05:30", "t:17:30"}]
    assert number_claims("ends at 17:30") == [{"t:17:30"}]


# Sonnet-written card summaries, end to end through the turn. No AWS calls.
import json
import re

import pytest

import agent.bedrock_client as bc
from agent.prompts import EXPLAIN_SYSTEM

QUERY = "Elementary school in Jacksonville with after-school care until 6pm"


@pytest.fixture
def cards(monkeypatch):
    """Run a search turn where only the explain step uses the fake model."""
    from store import _empty
    from testing_helpers import search_turn

    def run(explain):
        def answer(model_id, system, user):
            assert system == EXPLAIN_SYSTEM, "route and extract stay on the rules here"
            return explain(json.loads(user))

        monkeypatch.setattr(bc, "enabled", lambda: True)
        monkeypatch.setattr(bc, "converse", answer)
        monkeypatch.setattr(bc, "maybe_bedrock_route", lambda text, has_session: (None, bc.EngineStep(engine="rules")))
        monkeypatch.setattr(bc, "maybe_bedrock_criteria", lambda text, cities: (None, bc.EngineStep(engine="rules")))
        response = search_turn(_empty(), {"message": QUERY}).model_dump()
        results = next(b for b in response["blocks"] if b["type"] == "results")["payload"]
        return results["schools"] + results["missed"], response["engine"]

    return run


def _care_note(card: dict) -> str | None:
    # A card can get its after-care status from parent posts instead of the profile field
    # (community evidence). Those cards have no profile time to quote, so tests skip them.
    return next((row["note"] for row in card["evidence"] if (row.get("source") or {}).get("path") == "osp.after_school_until"), None)


def test_true_model_sentence_replaces_code_summary(cards):
    def explain(inputs):
        out = {}
        for card in inputs:
            note = next((r["note"] for r in card["evidence"] if r["cite"] == "osp.after_school_until"), None)
            if note is None:
                continue
            time = re.search(r"\d{1,2}:\d{2} [AP]M", note).group(0)
            out[card["id"]] = f"Care runs until {time}, and you need 6 PM [[cite:osp.after_school_until]]."
        return json.dumps(out)

    shown, engine = cards(explain)
    assert engine["explain"] == "bedrock"
    for card in shown:
        if _care_note(card) is None:
            continue
        time = re.search(r"\d{1,2}:\d{2} [AP]M", _care_note(card)).group(0)
        assert card["summary"] == f"Care runs until {time}, and you need 6 PM."


def test_unknown_must_have_stays_on_the_card(cards):
    from store import _empty
    from testing_helpers import search_turn

    response = search_turn(_empty(), {"message": QUERY + " and strong STEM"}).model_dump()
    results = next(b for b in response["blocks"] if b["type"] == "results")["payload"]
    unknown = [c for c in results["schools"] if any(r["status"] == "unknown" for r in c["evidence"])]
    assert unknown, "the demo query has schools with unknown after-school care"
    for card in unknown:
        row = next(r for r in card["evidence"] if r["status"] == "unknown")
        assert row["source"] is None and row["missing_paths"] == ["osp.after_school_until"]
        assert "After-school care is unknown" in card["summary"]


def test_fabricated_time_keeps_the_code_summary(cards):
    honest, _ = cards(lambda inputs: json.dumps({}))
    code_text = {card["id"]: card["summary"] for card in honest}

    shown, engine = cards(lambda inputs: json.dumps({c["id"]: "Care runs until 11:45 PM [[cite:osp.after_school_until]]." for c in inputs}))
    assert engine["explain"] == "rules_fallback"
    assert "fact check" in engine["errors"][0]
    assert {card["id"]: card["summary"] for card in shown} == code_text


def test_reply_without_json_keeps_the_code_summary(cards):
    shown, engine = cards(lambda inputs: "Here are some great schools!")
    assert engine["explain"] == "rules_fallback"
    assert engine["errors"][0].startswith("bedrock explain returned no JSON object")
    assert all("[[cite:" not in card["summary"] for card in shown)


def test_half_cited_summary_keeps_the_code_summary(cards):
    """One citation at the very end: the check would cut the fact and keep the filler."""
    honest, _ = cards(lambda inputs: json.dumps({}))
    code_text = {card["id"]: card["summary"] for card in honest}

    filler = "No other evidence was provided for this school."
    shown, engine = cards(
        lambda inputs: json.dumps({c["id"]: f"It has the care you need. {filler} [[cite:osp.after_school_until]]" for c in inputs})
    )
    assert all(filler not in card["summary"] for card in shown)
    assert {card["id"]: card["summary"] for card in shown} == code_text
    assert engine["explain"] == "rules_fallback"


def test_model_sees_filter_names(cards):
    seen = []

    def explain(inputs):
        seen.extend(row["text"] for card in inputs for row in card["criteria"])
        return json.dumps({})

    cards(explain)
    assert "After-school care until 6:00 PM" in seen
