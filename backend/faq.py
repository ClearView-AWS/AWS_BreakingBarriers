"""The FAQ sidebar: starting questions with answers, plus questions parents add.

Questions are sorted by how many parents asked them. A parent counts once per
question. Added questions pass the same safety check as community posts and
stay unanswered until someone from the team writes an answer into faq.yaml.
"""

from __future__ import annotations

import re
from datetime import date

from catalog import _load
from community.safety import check_post

MAX_CHARS = 200
_WORD = re.compile(r"[a-z0-9]+")
_SKIP = {"the", "a", "an", "is", "are", "do", "does", "what", "how", "can", "i", "my", "this", "it", "of", "to", "in", "for", "and", "or", "me", "you"}


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.casefold()) if w not in _SKIP}


def _key(text: str) -> str:
    return " ".join(_WORD.findall(text.casefold()))


def _store(state: dict) -> dict:
    return state.setdefault("faq", {"added": [], "askers": {}})


def _entries(state: dict) -> list[dict]:
    store = _store(state)
    rows = [{"id": key, **row, "added": False} for key, row in _load("faq.yaml").items()]
    rows += [{**row, "added": True} for row in store["added"]]
    return rows


def list_faq(state: dict, persona: str | None = None) -> list[dict]:
    askers = _store(state)["askers"]
    out = []
    for order, row in enumerate(_entries(state)):
        who = askers.get(row["id"]) or []
        out.append({
            "id": row["id"],
            "question": row["question"],
            "answer": row.get("answer"),
            "source": row.get("source"),
            "added": row["added"],
            "asked": len(who),
            "asked_by_me": bool(persona and persona in who),
            "_order": order,
        })
    out.sort(key=lambda row: (-row["asked"], row["_order"]))
    for row in out:
        row.pop("_order")
    return out


def similar(state: dict, text: str, limit: int = 3) -> list[str]:
    """Ids of questions that share most of their words with the text."""
    wanted = _words(text)
    if not wanted:
        return []
    scored = []
    for row in _entries(state):
        have = _words(row["question"])
        overlap = len(wanted & have) / max(1, min(len(wanted), len(have)))
        if overlap >= 0.6:
            scored.append((overlap, row["id"]))
    return [row_id for _, row_id in sorted(scored, reverse=True)[:limit]]


def toggle_ask(state: dict, faq_id: str, persona: str) -> dict:
    if faq_id not in {row["id"] for row in _entries(state)}:
        return {"ok": False, "message": "Unknown question."}
    who = _store(state)["askers"].setdefault(faq_id, [])
    if persona in who:
        who.remove(persona)
    else:
        who.append(persona)
    return {"ok": True, "asked": len(who), "asked_by_me": persona in who}


def add_question(state: dict, persona: str, text: str) -> dict:
    text = " ".join((text or "").split())[:MAX_CHARS]
    if len(_words(text)) < 2:
        return {"ok": False, "message": "Write a short question first."}
    safety = check_post(text)
    if not safety["ok"]:
        return {"ok": False, "safety": safety, "message": safety["message"]}
    store = _store(state)
    same = next((row for row in _entries(state) if _key(row["question"]) == _key(text)), None)
    if same:
        who = store["askers"].setdefault(same["id"], [])
        if persona not in who:
            who.append(persona)
        return {"ok": True, "id": same["id"], "existing": True}
    faq_id = f"q_{len(store['added']) + 1}"
    store["added"].append({"id": faq_id, "question": text, "answer": None, "source": None,
                           "created_at": date.today().isoformat()})
    store["askers"][faq_id] = [persona]
    return {"ok": True, "id": faq_id, "existing": False}
