"""Read facts out of the mock school websites. The HTML is the source, not a side file."""

from __future__ import annotations

import json
import re
from functools import lru_cache

from runtime_config import SYNTHETIC_DIR

_BLOCK = re.compile(
    r'<script id="school-facts" type="application/json">(.*?)</script>',
    re.DOTALL,
)


def _slug(school_id: str) -> str:
    digits = "".join(ch for ch in school_id if ch.isdigit())
    return digits or school_id.replace(" ", "_")


@lru_cache(maxsize=1)
def _index() -> dict[str, dict]:
    folder = SYNTHETIC_DIR / "websites"
    found: dict[str, dict] = {}
    if not folder.exists():
        return found
    for path in folder.glob("*.html"):
        text = path.read_text(encoding="utf-8")
        match = _BLOCK.search(text)
        if not match:
            continue
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        school_id = payload.get("school_id")
        if school_id:
            payload["_file"] = path.name
            found[school_id] = payload
    return found


def website_facts(school_id: str) -> list[dict]:
    payload = _index().get(school_id) or {}
    return list(payload.get("facts") or [])


def website_file(school_id: str) -> str | None:
    payload = _index().get(school_id)
    if not payload:
        return None
    return payload.get("_file")


def clear_website_cache() -> None:
    _index.cache_clear()
