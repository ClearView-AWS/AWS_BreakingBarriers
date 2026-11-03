"""Bedrock Converse calls. Disabled unless BEDROCK_ENABLED=1, and never required."""

from __future__ import annotations

import json
import logging
import time
from functools import lru_cache

from observability import append
from runtime_config import BEDROCK_ENABLED

log = logging.getLogger(__name__)


def enabled() -> bool:
    return BEDROCK_ENABLED


@lru_cache(maxsize=1)
def _client():
    import boto3

    from catalog import models

    return boto3.client("bedrock-runtime", region_name=models().get("region", "us-east-1"))


def converse(model_id: str, system: str, user: str, purpose: str = "") -> str:
    started = time.perf_counter()
    try:
        response = _client().converse(
            modelId=model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
        )
    except Exception as exc:
        append("bedrock", {"purpose": purpose, "model": model_id, "ok": False, "error": str(exc)[:300]})
        raise
    blocks = response["output"]["message"]["content"]
    text = "".join(block.get("text", "") for block in blocks)
    append(
        "bedrock",
        {
            "purpose": purpose,
            "model": model_id,
            "ok": True,
            "ms": round((time.perf_counter() - started) * 1000, 1),
            "usage": response.get("usage"),
            "output": text[:500],
        },
    )
    return text


def maybe_bedrock_route(text: str, has_session: bool) -> str | None:
    if not enabled():
        return None
    try:
        from catalog import models
        from agent.prompts import ROUTER_SYSTEM

        raw = converse(
            models()["fast_model"],
            ROUTER_SYSTEM,
            f"session={has_session}\nmessage={text}",
            purpose="route",
        ).strip().split()[0]
        allowed = {
            "new_search",
            "refine",
            "compare",
            "school_detail",
            "define",
            "why_not",
            "cost",
            "save",
            "feedback",
        }
        return raw if raw in allowed else None
    except Exception as exc:
        log.warning("bedrock route failed: %s", exc)
        return None


def maybe_bedrock_criteria(text: str):
    """Return None so the rules extractor stays the source of truth unless parsing works.

    When Bedrock is on, its JSON is still mapped to needs in code by the caller
    only if every item has text and strength. On any failure, return None.
    """
    if not enabled():
        return None
    try:
        from catalog import models
        from agent.prompts import EXTRACT_SYSTEM
        from contracts import Criterion

        raw = converse(models()["fast_model"], EXTRACT_SYSTEM, text, purpose="extract")
        start, end = raw.find("["), raw.rfind("]")
        if start < 0 or end < 0:
            return None
        payload = json.loads(raw[start : end + 1])
        drafted = []
        for item in payload:
            drafted.append(
                Criterion(
                    id="draft",
                    text=str(item.get("text") or ""),
                    strength=item.get("strength") or "prefer",
                    params=item.get("params") or {},
                    kind="need",
                )
            )
        return [row for row in drafted if row.text] or None
    except Exception as exc:
        log.warning("bedrock extract failed: %s", exc)
        return None
