"""Replies in the parent's language: translated last, in one call, without touching the facts. No AWS calls."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

import agent.translate as translate
from agent.conversation import chat_turn
from store import _empty

SPANISH = "Busco una escuela primaria en Jacksonville con cuidado después de clases hasta las 6"
SPANISH_EN = "I'm looking for an elementary school in Jacksonville with after-school care until 6pm"
ENGLISH = "elementary school in jacksonville with after-school care until 6pm"


class FakeTranslate:
    """Reading: maps known messages to (English, language). Replies: upper-cases everything outside
    translate="no" spans and drops the space after a span, the way the real service does."""

    def __init__(self, fail_replies: bool = False):
        self.fail_replies = fail_replies
        self.documents = 0

    def translate_text(self, Text: str, SourceLanguageCode: str, TargetLanguageCode: str, **_):
        known = {SPANISH: (SPANISH_EN, "es"), ENGLISH: (ENGLISH, "en")}
        english, language = known[Text]
        return {"TranslatedText": english, "SourceLanguageCode": language, "TargetLanguageCode": "en"}

    def translate_document(self, Document: dict, SourceLanguageCode: str, TargetLanguageCode: str, **_):
        if self.fail_replies:
            raise RuntimeError("ThrottlingException")
        self.documents += 1
        html = Document["Content"].decode("utf-8")
        parts = re.split(r'(<span translate="no">.*?</span>\s?|<[^>]+>)', html)
        out = []
        for part in parts:
            if part.startswith('<span translate="no">'):
                out.append(part.rstrip())  # the real service drops this space
            elif part.startswith("<"):
                out.append(part)
            else:
                out.append(part.upper())
        return {"TranslatedDocument": {"Content": "".join(out).encode("utf-8")}}


@pytest.fixture
def fake(monkeypatch):
    def install(**kwargs) -> FakeTranslate:
        client = FakeTranslate(**kwargs)
        monkeypatch.setattr(translate, "TRANSLATE_ENABLED", True)
        monkeypatch.setattr(translate, "_client", lambda: client)
        translate._CACHE.clear()
        return client

    return install


def _results(response: dict) -> dict:
    return next(block["payload"] for block in response["blocks"] if block["type"] == "results")


def test_a_spanish_message_gets_a_spanish_reply_without_touching_the_facts(fake):
    client = fake()
    state = _empty()
    response = chat_turn(state, {"message": SPANISH})

    assert client.documents == 1, "the whole reply is one call"
    assert response["language"] == "es" and response["read_from"] == "es"
    card = _results(response)["schools"][0]
    assert card["summary"] and card["summary"] == card["summary"].upper().replace(card["name"].upper(), card["name"])
    # Facts and names are untouched.
    assert card["name"] != card["name"].upper()
    assert all(row["status"] in {"confirmed", "partial", "needs_attention", "unknown"} for row in card["evidence"])
    assert all(row["note"] != row["note"].upper() for row in card["evidence"] if row["note"])
    # The chip shows the filter in Spanish; the parent's words stay as read.
    care = next(c for c in response["criteria"] if c.get("need") == "after_care")
    assert care["label"] == care["label"].upper() and care["text"] != care["text"].upper()
    # The stored conversation stays English for the model and the chat's history diffing.
    session = state["sessions"][response["session_id"]]
    assert session["history"][0]["text"] == SPANISH
    assert all(entry["text"] != entry["text"].upper() for entry in session["history"] if entry["role"] == "agent")


def test_kept_names_get_their_space_back(fake):
    fake()
    out, error = translate.from_english(["Arlington STEM Academy is a charter."], "es", keep_names=["Arlington STEM Academy"])
    assert error is None
    assert out == ["Arlington STEM Academy IS A CHARTER."]


def test_taps_keep_the_language_and_english_switches_back(fake):
    fake()
    state = _empty()
    first = chat_turn(state, {"message": SPANISH})
    school = _results(first)["schools"][0]

    tapped = chat_turn(state, {"session_id": first["session_id"], "action": "save", "school_ids": [school["id"]]})
    assert tapped["language"] == "es" and tapped["read_from"] is None
    assert tapped["tap"] and tapped["tap"] == tapped["tap"].upper().replace(school["name"].upper(), school["name"])
    assert state["sessions"][first["session_id"]]["history"][-2]["text"].startswith("You saved")

    back = chat_turn(state, {"session_id": first["session_id"], "message": ENGLISH})
    assert back["language"] == "en"
    assert _results(back)["schools"][0]["summary"] != _results(back)["schools"][0]["summary"].upper()


def test_a_failed_reply_translation_answers_in_english(fake):
    fake(fail_replies=True)
    response = chat_turn(_empty(), {"message": SPANISH})
    card = _results(response)["schools"][0]
    assert card["summary"] != card["summary"].upper()
    assert any(error.startswith("translate reply failed") for error in response["engine"]["errors"])


def test_off_means_no_calls_and_english(monkeypatch):
    monkeypatch.setattr(translate, "TRANSLATE_ENABLED", False)
    monkeypatch.setattr(translate, "_client", lambda: (_ for _ in ()).throw(AssertionError("no AWS calls")))
    response = chat_turn(_empty(), {"message": ENGLISH})
    assert response["language"] is None and response["read_from"] is None


def test_ui_text_keeps_placeholders(fake):
    fake()
    from app import app

    reply = TestClient(app).post(
        "/api/ui-text",
        json={"language": "es", "strings": {"show_all": "Show all {total}", "discussed": "{n} parents discussed {need} here", "save": "Save"}},
    ).json()
    assert reply["error"] is None
    assert reply["strings"] == {"show_all": "SHOW ALL {total}", "discussed": "{n} PARENTS DISCUSSED {need} HERE", "save": "SAVE"}
