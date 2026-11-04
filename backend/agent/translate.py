"""Read and answer the parent in any language.

In: Amazon Translate detects the language of a message (SourceLanguageCode="auto") and returns
English, so the router, the extractor and the follow-up reader (rules or Bedrock) keep working in
English. Out: the finished, fact-checked reply is translated back in one TranslateDocument call,
with school names marked translate="no". Every language Translate supports comes for free.
Off unless TRANSLATE_ENABLED=1. When it is off, or a call fails, text passes through unchanged.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from runtime_config import AWS_REGION, TRANSLATE_ENABLED

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Reading:
    """The message the pipeline reads, and the language the parent wrote in (None if unknown)."""

    text: str
    language: str | None
    error: str | None = None


@lru_cache(maxsize=1)
def _client():
    import boto3

    return boto3.client("translate", region_name=AWS_REGION)


def to_english(text: str) -> Reading:
    if not TRANSLATE_ENABLED or not text.strip():
        return Reading(text, None)
    try:
        reply = _client().translate_text(Text=text, SourceLanguageCode="auto", TargetLanguageCode="en")
    except Exception as exc:  # no access, throttled, offline: read the message as written
        error = f"translate failed: {exc}"
        log.warning("%s", error)
        return Reading(text, None, error)
    language = reply.get("SourceLanguageCode")
    if language == "en":
        # Already English: keep the parent's exact words rather than a round-tripped copy.
        return Reading(text, "en")
    return Reading(str(reply.get("TranslatedText") or text), language)


# --- out: English -> the parent's language ------------------------------------

# Translated strings, keyed by (language, English). Labels, statuses and summaries repeat a lot.
_CACHE: dict[tuple[str, str], str] = {}
_CACHE_LIMIT = 20000
# TranslateDocument takes up to 100 KB per document; stay under it.
_DOC_LIMIT = 90_000
_ITEM = re.compile(r'<p data-i="(\d+)">(.*?)</p>', re.DOTALL)
_KEEP_OPEN = '<span translate="no">'


def from_english(texts: list[str], language: str | None, keep_names: Iterable[str] = ()) -> tuple[list[str], str | None]:
    """Translate English texts into `language`, keeping the names in `keep_names` as written.

    Returns the texts in the same order, and an error string if the call failed (the texts are
    then English, so the reply is never lost).
    """
    out = list(texts)
    if not TRANSLATE_ENABLED or not language or language == "en":
        return out, None
    todo: list[str] = []
    for index, text in enumerate(texts):
        if not text or not text.strip():
            continue
        cached = _CACHE.get((language, text))
        if cached is not None:
            out[index] = cached
        elif text not in todo:
            todo.append(text)
    if not todo:
        return out, None
    try:
        translated = _translate_html(todo, language, keep_names)
    except Exception as exc:  # no access, throttled, unsupported language: answer in English
        error = f"translate reply failed: {exc}"
        log.warning("%s", error)
        return out, error
    if len(_CACHE) > _CACHE_LIMIT:
        _CACHE.clear()
    for source, result in zip(todo, translated):
        _CACHE[(language, source)] = result
    for index, text in enumerate(texts):
        if (language, text) in _CACHE:
            out[index] = _CACHE[(language, text)]
    return out, None


def _translate_html(texts: list[str], language: str, keep_names: Iterable[str]) -> list[str]:
    names = sorted({name for name in keep_names if name and name.strip()}, key=len, reverse=True)
    keep = re.compile("|".join(re.escape(html.escape(name, quote=False)) for name in names)) if names else None
    items = []
    for index, text in enumerate(texts):
        body = html.escape(text, quote=False)
        if keep:
            body = keep.sub(lambda match: f"{_KEEP_OPEN}{match.group(0)}</span>", body)
        items.append(f'<p data-i="{index}">{body}</p>')

    results = list(texts)
    for document in _documents(items):
        reply = _client().translate_document(
            Document={"Content": document.encode("utf-8"), "ContentType": "text/html"},
            SourceLanguageCode="en",
            TargetLanguageCode=language,
        )
        content = reply["TranslatedDocument"]["Content"]
        content = content.decode("utf-8") if isinstance(content, (bytes, bytearray)) else str(content)
        for match in _ITEM.finditer(content):
            results[int(match.group(1))] = _clean(match.group(2))
    return results


def _documents(items: list[str]) -> list[str]:
    """Pack the items into as few HTML documents as fit under the size limit."""
    documents, current, size = [], [], 0
    for item in items:
        length = len(item.encode("utf-8"))
        if current and size + length > _DOC_LIMIT:
            documents.append(current)
            current, size = [], 0
        current.append(item)
        size += length
    if current:
        documents.append(current)
    return ["<html><body>" + "".join(chunk) + "</body></html>" for chunk in documents]


def _clean(fragment: str) -> str:
    # Translate drops the space between a kept name and the next word ("Academy</span>está").
    fragment = re.sub(r"</span>(?=[^\s.,;:!?)\]»”’'-])", "</span> ", fragment)
    fragment = re.sub(r"(?<=[^\s(\[«“‘'-])<span", " <span", fragment)
    fragment = re.sub(r"</?span[^>]*>", "", fragment)
    return html.unescape(fragment).strip()


# --- the UI's own strings ----------------------------------------------------

_PLACEHOLDER = re.compile(r"\{([a-zA-Z_]+)\}")
_STAND_IN_BASE = 901


def translate_ui(strings: dict[str, str], language: str | None) -> tuple[dict[str, str], str | None]:
    """Translate the frontend's string table, keeping its {placeholders}.

    Placeholders become plain numbers (901, 902...) for the call, since Translate moves or splits
    markup in some languages but leaves numbers alone. A string that comes back without all its
    numbers stays English.
    """
    keys = list(strings)
    swapped, maps = [], []
    for key in keys:
        names = list(dict.fromkeys(_PLACEHOLDER.findall(strings[key])))
        mapping = {name: str(_STAND_IN_BASE + index) for index, name in enumerate(names)}
        maps.append(mapping)
        swapped.append(_PLACEHOLDER.sub(lambda match: mapping[match.group(1)], strings[key]))
    translated, error = from_english(swapped, language)
    out: dict[str, str] = {}
    for key, mapping, text in zip(keys, maps, translated):
        if any(number not in text for number in mapping.values()):
            out[key] = strings[key]
            continue
        for name, number in mapping.items():
            text = text.replace(number, "{" + name + "}", 1)
        out[key] = text
    return out, error
