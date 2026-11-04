"""Put a finished reply into the parent's language.

Runs last, after evidence, scoring and the fact check, so translation never touches what is true:
only the words a parent reads. IDs, paths, values, URLs, statuses and school names stay as they
are. One batched Amazon Translate call per reply (agent/translate.py).
"""

from __future__ import annotations

from typing import Any

from agent.translate import from_english

# Keys whose string values are words for the parent.
_TEXT_KEYS = {
    "text",
    "prompt",
    "label",
    "how_label",
    "line",
    "summary",
    "detail",
    "next_step",
    "change",
    "title",
    "question",
    "lines",
    "disclaimer",
    "wording",
    "esp_text",
    "zoned_prompt",
    "assumption",
    "tap",
    "window",
    "detail_source",
}
# Subtrees that are data, logs or the stored conversation, never shown as prose.
_SKIP_KEYS = {"history", "engine", "evidence", "source", "cited", "records"}
_NAME_KEYS = {"name", "school_name"}


def localize_response(response: dict, language: str | None) -> dict:
    """Translate the reply in place into `language`. English or unknown leaves it untouched."""
    if not language or language == "en":
        return response
    slots: list[tuple[Any, Any]] = []  # (container, key or index) holding one string
    names: set[str] = set()
    _collect(response, slots, names, parent_key=None)
    texts = [container[key] for container, key in slots]
    translated, error = from_english(texts, language, keep_names=names)
    for (container, key), text in zip(slots, translated):
        container[key] = text
    if error:
        engine = response.setdefault("engine", {"route": None, "extract": None, "explain": None, "errors": []})
        engine.setdefault("errors", []).append(error)
    return response


def _collect(node: Any, slots: list, names: set[str], parent_key: str | None) -> None:
    if isinstance(node, dict):
        # A criterion's `text` is the parent's own words; only its filter name is ours to translate.
        is_criterion = "strength" in node and "kind" in node
        for key, value in node.items():
            if key in _SKIP_KEYS:
                continue
            if key in _NAME_KEYS and isinstance(value, str):
                names.add(value)
                continue
            if key in _TEXT_KEYS and not (is_criterion and key != "label"):
                if isinstance(value, str) and value.strip():
                    slots.append((node, key))
                    continue
                if isinstance(value, list) and all(isinstance(item, str) for item in value):
                    slots.extend((value, index) for index, item in enumerate(value) if item.strip())
                    continue
            _collect(value, slots, names, key)
    elif isinstance(node, list):
        for item in node:
            _collect(item, slots, names, parent_key)
