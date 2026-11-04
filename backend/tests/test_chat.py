"""The chat layer (agent.conversation): history, references, follow-up answers and pass-through."""

from __future__ import annotations

import re

import pytest

from agent.citations import citations_in
from agent.conversation import HISTORY_LIMIT, chat_turn
from pipeline import turn
from search.corpus import load_schools

DEMO = "Middle school in Seattle with STEM and after-school care. Money is tight."
BY_NAME = {school["name"]: school for school in load_schools()}


class Chat:
    def __init__(self) -> None:
        self.state = {"sessions": {}, "inbox": [], "overlays": {}}
        self.session_id: str | None = None

    def send(self, message: str | None = None, **payload) -> dict:
        if message:
            payload["message"] = message
        response = chat_turn(self.state, {"session_id": self.session_id, **payload})
        self.session_id = response["session_id"]
        return response

    @property
    def session(self) -> dict:
        return self.state["sessions"][self.session_id]


def _block(response: dict, kind: str) -> dict:
    return next((b["payload"] for b in response["blocks"] if b["type"] == kind), {})


def _shown(response: dict) -> list[str]:
    return [card["id"] for card in _block(response, "results").get("schools", [])]


@pytest.fixture()
def chat() -> Chat:
    conversation = Chat()
    first = conversation.send(DEMO)
    if not _shown(first):
        conversation.send(event="skip_to_results", action="refresh")
    return conversation


def test_ordinal_follow_up_is_answered_from_evidence(chat):
    second = chat.session["focus"]["results"][1]
    response = chat.send("Does the second one have after-school care?")
    answer = _block(response, "answer")
    assert response["route"] == "ask_about"
    assert answer["school_ids"] == [second]
    assert answer["topic"] == {"kind": "need", "need": "after_care"}
    cited = _block(response, "message")["cited"]
    assert citations_in(cited)  # every shown fact carries its source
    assert "[[cite:" not in _block(response, "message")["text"]


def test_a_follow_up_keeps_the_results_and_the_criteria(chat):
    before = [dict(c) for c in chat.session["criteria"]]
    chat.send("Does the second one have a bus?")
    assert chat.session["criteria"] == before
    assert chat.session["focus"]["results"]  # still pointing at the shown list


def test_names_pronouns_and_the_whole_list_resolve(chat):
    beauclerc = BY_NAME["Arbor Heights STEM Middle"]["id"]
    named = chat.send("Can my son get into Arbor Heights?")
    assert _block(named, "answer")["school_ids"] == [beauclerc]
    pronoun = chat.send("How far is it?")
    assert _block(pronoun, "answer")["school_ids"] == [beauclerc]
    assert _block(pronoun, "answer")["topic"]["kind"] == "distance"
    whole = chat.send("Which of these are tuition-free?")
    assert _block(whole, "answer")["school_ids"] == chat.session["focus"]["results"][:8]
    assert _block(whole, "answer")["topic"]["need"] == "low_cost"


def test_getting_in_answers_never_estimate_chances(chat):
    response = chat.send("Will my son get into Arbor Heights? What are his chances?")
    message = _block(response, "message")
    assert _block(response, "answer")["topic"]["kind"] == "access"
    assert "never estimate" in (message["prompt"] or "")
    assert not re.search(r"\b(likely|probab|percent|%|odds of)\b", message["text"].casefold())
    assert "Jan 15, 2027" in message["text"]


def test_unknown_facts_offer_to_ask_the_school(chat):
    response = chat.send("Does Arbor Heights have after school care?")
    message = _block(response, "message")
    assert "isn't on file yet" in message["prompt"]
    chips = _block(response, "chips")["items"]
    assert chips[0]["payload"] == {"action": "ask_school", "school_ids": [BY_NAME["Arbor Heights STEM Middle"]["id"]], "need": "after_care"}
    # A reply that is only a prompt still shows in the chat, and "it" then means Arbor Heights.
    assert "isn't on file yet" in chat.session["history"][-1]["text"]
    follow = chat.send("Is it safe?")
    assert _block(follow, "answer")["school_ids"] == [BY_NAME["Arbor Heights STEM Middle"]["id"]]


def test_search_changes_and_other_routes_pass_through(chat):
    assert chat.send("What about Seattle instead?")["route"] == "refine"
    assert chat.send("I also need a school with arts")["route"] == "refine"
    assert chat.send("What's CTE?")["route"] == "define"
    assert chat.send("Why isn't Mariner Elementary listed?")["route"] == "why_not"


def test_ordinals_become_school_ids_for_detail_compare_and_save(chat):
    first, second = chat.session["focus"]["results"][:2]
    detail = chat.send("tell me about the first one")
    assert _block(detail, "school_detail")["school"]["id"] == first
    compare = chat.send("compare the first two")
    assert compare["route"] == "compare"
    chat.send("save the second one")
    assert chat.session["saved"] == [second]


def test_pass_through_matches_the_pipeline():
    via = Chat()
    via_chat = via.send(DEMO)
    if not _shown(via_chat):
        via_chat = via.send(event="skip_to_results", action="refresh")
    state = {"sessions": {}, "inbox": [], "overlays": {}}
    direct = turn(state, {"message": DEMO})
    if not any(block.type == "results" for block in direct.blocks):
        direct = turn(state, {"session_id": direct.session_id, "event": "skip_to_results", "action": "refresh"})
    direct = direct.model_dump()
    assert via_chat["route"] == direct["route"]
    assert _shown(via_chat) == _shown(direct)


def test_history_logs_messages_and_taps_and_is_capped(chat):
    school = chat.session["focus"]["results"][0]
    chat.send(action="save", school_ids=[school])
    chat.send(action="refresh", zoned={"school_id": school})
    texts = [entry["text"] for entry in chat.session["history"]]
    assert texts[0] == DEMO
    assert any(text.startswith("You saved") for text in texts)
    assert any("is your zoned school" in text for text in texts)
    for _ in range(HISTORY_LIMIT):
        chat.send("Does the first one have a bus?")
    assert len(chat.session["history"]) == HISTORY_LIMIT


def _first_of_type(chat: Chat, entity_type: str) -> dict:
    shown = chat.session["focus"]["all"]
    by_id = {school["id"]: school for school in load_schools()}
    return next(by_id[sid] for sid in shown if by_id[sid].get("entity_type") == entity_type)


def test_public_or_private_is_answered_from_the_school_type(chat):
    school = _first_of_type(chat, "public")
    chat.send(action="school_detail", school_ids=[school["id"]])
    response = chat.send("is this one public or private")
    message = _block(response, "message")
    assert _block(response, "answer")["school_ids"] == [school["id"]]
    assert _block(response, "answer")["topic"]["kind"] == "type"
    assert message["text"] == f"{school['name']}: This is a public school."
    assert "[[cite:entity_type]]" in message["cited"]


def test_tuition_at_a_public_school_is_not_a_scholarship_estimate(chat):
    school = _first_of_type(chat, "public")
    chat.send(action="school_detail", school_ids=[school["id"]])
    response = chat.send("what is the tuition for this one")
    assert response["route"] == "ask_about"
    assert _block(response, "answer")["topic"] == {"kind": "need", "need": "low_cost"}
    assert "tuition-free" in _block(response, "message")["text"]
    assert "scholarship" not in _block(response, "message")["text"].casefold()


def test_tuition_at_a_private_school_still_opens_the_cost_view(chat):
    school = _first_of_type(chat, "private")
    chat.send(action="school_detail", school_ids=[school["id"]])
    response = chat.send("what is the tuition for this one")
    assert response["route"] == "cost"
    assert _block(response, "cost")["schools"][0]["school_id"] == school["id"]


def test_which_are_private_names_only_the_private_ones(chat):
    by_id = {school["id"]: school for school in load_schools()}
    asked = chat.session["focus"]["results"][:8]
    private = [sid for sid in asked if by_id[sid].get("entity_type") == "private"]
    response = chat.send("Which of these are private?")
    message = _block(response, "message")
    assert _block(response, "answer")["topic"]["kind"] == "type"
    for sid in asked:
        assert (by_id[sid]["name"] in message["text"]) == (sid in private)
    assert "public school" not in message["text"]
    assert citations_in(message["cited"])


def test_cost_view_for_a_public_school_says_tuition_free(chat):
    school = _first_of_type(chat, "public")
    response = chat.send(action="cost", school_ids=[school["id"]])
    text = _block(response, "message")["text"]
    assert "tuition-free" in text and "scholarship eligibility" not in text


# --- Bedrock reads the follow-up; code checks the reading -------------------------

def _model_reads(monkeypatch, reading, seen: list | None = None, extract: str = "[]") -> None:
    """Turn Bedrock on with a stub: `reading` is what the model says about the follow-up."""
    import json

    import agent.bedrock_client as bc
    from agent.conversation import follow_up_system
    from agent.prompts import EXPLAIN_SYSTEM, ROUTER_SYSTEM

    def answer(model_id, system, user):
        if system == follow_up_system():
            if seen is not None:
                seen.append(json.loads(user))
            return reading if isinstance(reading, str) else json.dumps(reading)
        if system == ROUTER_SYSTEM:
            raise AssertionError("the chat layer chose the route, so the pipeline's router should not run")
        if system == EXPLAIN_SYSTEM:
            return "{}"
        return extract

    monkeypatch.setattr(bc, "enabled", lambda: True)
    monkeypatch.setattr(bc, "converse", answer)


def test_model_reading_answers_wording_the_rules_miss(chat, monkeypatch):
    second = chat.session["focus"]["results"][1]
    seen: list = []
    _model_reads(monkeypatch, {"intent": "ask_about", "schools": ["#2"], "topic": "need", "need": "after_care"}, seen)
    response = chat.send("is pickup at the 2nd pick doable if I'm stuck at work till 6")
    answer = _block(response, "answer")
    assert answer["school_ids"] == [second]
    assert answer["topic"] == {"kind": "need", "need": "after_care"}
    assert citations_in(_block(response, "message")["cited"])
    assert response["engine"]["route"] == "bedrock"
    # The model sees the schools numbered as on the cards, and the message.
    shown = {row["ref"]: row["name"] for row in seen[0]["shown"]}
    assert shown["#2"] == next(s["name"] for s in load_schools() if s["id"] == second)
    assert seen[0]["message"].startswith("is pickup")


@pytest.mark.parametrize(
    "reading",
    [
        {"intent": "ask_about", "schools": ["#99"], "topic": "need", "need": "after_care"},  # not on screen
        {"intent": "ask_about", "schools": ["#2"], "topic": "need", "need": "politics"},  # not a need
        {"intent": "book_a_tour", "schools": ["#2"]},  # not an intent
        "Sure! The second school has care until 6.",  # not JSON, and the model may not state facts
    ],
)
def test_a_bad_model_reading_falls_back_to_the_rules(chat, monkeypatch, reading):
    second = chat.session["focus"]["results"][1]
    _model_reads(monkeypatch, reading)
    response = chat.send("Does the second one have after-school care?")
    assert _block(response, "answer")["school_ids"] == [second]
    assert response["engine"]["route"] == "rules_fallback"
    assert response["engine"]["errors"]
    assert "until 6" not in _block(response, "message")["text"]


def test_model_cost_question_about_a_public_school_says_tuition_free(chat, monkeypatch):
    public = _first_of_type(chat, "public")
    ref = next(f"#{i}" for i, sid in enumerate(chat.session["focus"]["results"], start=1) if sid == public["id"])
    _model_reads(monkeypatch, {"intent": "cost", "schools": [ref]})
    response = chat.send(f"how much would {ref} set us back")
    assert response["route"] == "ask_about"
    assert _block(response, "answer")["topic"] == {"kind": "need", "need": "low_cost"}


def test_model_refine_goes_to_the_pipeline_without_a_second_router_call(chat, monkeypatch):
    arts = '[{"kind": "need", "need": "arts", "strength": "prefer", "text": "art classes"}]'
    _model_reads(monkeypatch, {"intent": "refine", "schools": []}, extract=arts)
    response = chat.send("could we get some art classes in the mix too")
    assert response["route"] == "refine"
    assert any(c.get("need") == "arts" for c in response["criteria"])
    assert response["engine"]["route"] == "bedrock"


def test_model_why_not_names_the_school_for_the_pipeline(chat, monkeypatch):
    _model_reads(monkeypatch, {"intent": "why_not", "schools": []})
    response = chat.send("how come Mariner Elementary didn't show up")
    assert response["route"] == "why_not"
    assert _block(response, "why_not")["school_name"] == "Mariner Elementary School"


# --- the same list isn't posted twice ---------------------------------------------

def test_a_turn_that_changes_nothing_does_not_repeat_the_list(chat):
    shown = list(chat.session["focus"]["results"])
    response = chat.send(action="feedback", feedback={"school_id": shown[0], "vote": "up"})
    assert response["unchanged"] is True
    assert not _block(response, "results") and not _block(response, "evidence_grid")
    assert _block(response, "message")["text"].startswith("Thanks, noted.")
    assert chat.session["focus"]["results"] == shown


def test_a_typed_message_that_changes_nothing_says_so_and_keeps_its_question(chat):
    response = chat.send("How liberal are these schools?")
    assert response["unchanged"] is True
    assert _block(response, "message")["text"].startswith("I couldn't turn that into a change")
    assert "how liberal" in _block(response, "question")["text"]


def test_a_turn_that_changes_the_results_posts_them(chat):
    response = chat.send("I also need a school with arts")
    assert not response.get("unchanged")
    assert _block(response, "results")["schools"]


def test_saved_list_count_reads_naturally(chat):
    response = chat.send(action="save", school_ids=[chat.session["focus"]["results"][0]])
    assert _block(response, "message")["text"] == "Your saved list has 1 school."


def test_hash_numbers_match_the_card_numbers(chat):
    second = chat.session["focus"]["results"][1]
    response = chat.send("does #2 have a bus?")
    assert _block(response, "answer")["school_ids"] == [second]


def test_model_reading_cost_for_tuition_free_is_the_low_cost_need(chat, monkeypatch):
    _model_reads(monkeypatch, {"intent": "cost", "schools": ["all"]})
    response = chat.send("Which of these are tuition-free?")
    assert response["route"] == "ask_about"
    assert _block(response, "answer")["topic"] == {"kind": "need", "need": "low_cost"}
