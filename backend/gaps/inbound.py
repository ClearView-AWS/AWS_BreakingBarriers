"""Inbound parent line: speak a need, hear the top schools back.

The Connect number that calls schools can also take an inbound parent call.
Lex turns speech into text, the same pipeline.turn runs the search, and this
module turns the result into a short spoken (or SMS) summary. No new AWS
resources — see docs/inbound-voice.md.
"""

from __future__ import annotations

from typing import Any


def spoken_summary(result: Any, limit: int = 3) -> str:
    """Top schools from a pipeline turn, in at most 60 words, for TTS or SMS."""
    cards = _cards(result)[: max(0, limit)]
    if not cards:
        return "I could not find matching schools. Try a city and a grade, or ask for STEM or after-school care."
    lines = []
    for index, card in enumerate(cards, start=1):
        name = str(card.get("name") or "a school").strip()
        city = str(card.get("city") or "").strip()
        place = f"{name} in {city}" if city else name
        bit = _one_line(card)
        lines.append(f"{index}. {place}{': ' + bit if bit else ''}".strip())
    text = "Top schools. " + " ".join(lines)
    return _trim_words(text, 60)


def _cards(result: Any) -> list[dict]:
    if result is None:
        return []
    if isinstance(result, dict):
        blocks = result.get("blocks") or []
        if not blocks and result.get("schools"):
            return list(result.get("schools") or [])
    else:
        blocks = getattr(result, "blocks", None) or []
    out: list[dict] = []
    for block in blocks:
        kind = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
        payload = block.get("payload") if isinstance(block, dict) else getattr(block, "payload", None) or {}
        if kind != "results":
            continue
        for key in ("schools", "gaps", "missed"):
            for card in payload.get(key) or []:
                if isinstance(card, dict):
                    out.append(card)
        break
    return out


def _one_line(card: dict) -> str:
    summary = str(card.get("summary") or "").strip()
    if summary:
        return summary.rstrip(".")
    # Fall back to a short status from the first evidence row.
    for row in card.get("evidence") or []:
        note = str((row or {}).get("note") or "").strip()
        if note:
            return note.rstrip(".")
        status = (row or {}).get("status")
        if status:
            return str(status).replace("_", " ")
    return ""


def _trim_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    clipped = " ".join(words[:max_words]).rstrip(".,;:")
    return clipped + "."
