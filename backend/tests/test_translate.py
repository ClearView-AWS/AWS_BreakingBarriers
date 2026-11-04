"""Amazon Translate in front of the parser: any language in, English to the pipeline. No AWS calls."""

from __future__ import annotations

import pytest

import agent.translate as translate
from agent.conversation import chat_turn
from pipeline import turn
from store import _empty

# Haitian Creole: no phrase list covers it, so only translation can make the rules read it.
CREOLE = "Mwen bezwen yon lekòl primè nan Miami ak swen apre lekòl"
CREOLE_EN = "I need an elementary school in Miami with after-school care"


class FakeTranslate:
    """Stands in for the boto3 client. `replies` maps input text to (English, language) or an exception."""

    def __init__(self, replies: dict):
        self.replies = replies
        self.calls: list[str] = []

    def translate_text(self, Text: str, SourceLanguageCode: str, TargetLanguageCode: str, **_):
        assert (SourceLanguageCode, TargetLanguageCode) == ("auto", "en")
        self.calls.append(Text)
        reply = self.replies[Text]
        if isinstance(reply, Exception):
            raise reply
        return {"TranslatedText": reply[0], "SourceLanguageCode": reply[1], "TargetLanguageCode": "en"}

    def translate_document(self, Document: dict, SourceLanguageCode: str, TargetLanguageCode: str, **_):
        # Replies are translated back; these tests only check the reading, so echo the document.
        return {"TranslatedDocument": {"Content": Document["Content"]}}


@pytest.fixture
def translate_on(monkeypatch):
    def install(replies: dict) -> FakeTranslate:
        client = FakeTranslate(replies)
        monkeypatch.setattr(translate, "TRANSLATE_ENABLED", True)
        monkeypatch.setattr(translate, "_client", lambda: client)
        return client

    return install


def _criteria(response: dict) -> dict:
    return {(c["kind"], c.get("need") or c.get("value")) for c in response["criteria"]}


def test_off_by_default_the_message_passes_through(monkeypatch):
    monkeypatch.setattr(translate, "TRANSLATE_ENABLED", False)
    assert translate.to_english(CREOLE) == translate.Reading(CREOLE, None)
    response = chat_turn(_empty(), {"message": CREOLE})
    assert ("need", "after_care") not in _criteria(response), "without translation the rules can't read Creole"
    assert response["language"] is None


def test_a_message_in_any_language_is_parsed_after_translation(translate_on):
    client = translate_on({CREOLE: (CREOLE_EN, "ht")})
    response = chat_turn(_empty(), {"message": CREOLE})

    assert client.calls == [CREOLE], "translated once, not again inside the pipeline"
    assert {("grade", "e"), ("location", "Miami"), ("need", "after_care")} <= _criteria(response)
    assert response["language"] == "ht"
    assert response["history"][0] == {"role": "parent", "kind": "message", "text": CREOLE, "route": None, "school_ids": []}


def test_english_keeps_the_parents_exact_words(translate_on):
    message = "elementary school in miami with after-school care"
    translate_on({message: ("Elementary school in Miami with after-school care.", "en")})
    assert translate.to_english(message) == translate.Reading(message, "en")


def test_a_failed_call_reads_the_message_as_written(translate_on):
    translate_on({CREOLE: RuntimeError("AccessDeniedException")})
    response = chat_turn(_empty(), {"message": CREOLE})

    assert response["language"] is None
    assert any(error.startswith("translate failed") for error in response["engine"]["errors"])
    assert response["blocks"], "the parent still gets an answer"


def test_the_search_endpoint_translates_too(translate_on):
    translate_on({CREOLE: (CREOLE_EN, "ht")})
    response = turn(_empty(), {"message": CREOLE}).model_dump()
    assert ("need", "after_care") in _criteria(response)
    assert response["language"] == "ht"
