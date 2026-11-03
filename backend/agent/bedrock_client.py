"""Bedrock Converse calls. Disabled unless BEDROCK_ENABLED=1, and never required."""

from __future__ import annotations

import json
import logging

from runtime_config import BEDROCK_ENABLED

log = logging.getLogger(__name__)


def enabled() -> bool:
    return BEDROCK_ENABLED


def converse(model_id: str, system: str, user: str) -> str:
    import boto3

    from catalog import models

    client = boto3.client("bedrock-runtime", region_name=models().get("region", "us-east-1"))
    response = client.converse(
        modelId=model_id,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
    )
    blocks = response["output"]["message"]["content"]
    return "".join(block.get("text", "") for block in blocks)


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


def maybe_bedrock_criteria(text: str, cities: list[str]) -> list[dict] | None:
    """Return the model's raw draft items, or None to use the rules extractor.

    The items are untrusted. The extractor validates each one against the
    catalog and builds the criteria in code.
    """
    if not enabled():
        return None
    try:
        from catalog import models
        from agent.prompts import extract_system

        raw = converse(models()["fast_model"], extract_system(cities), text)
        start, end = raw.find("["), raw.rfind("]")
        if start < 0 or end < 0:
            log.warning("bedrock extract returned no JSON array: %r", raw[:200])
            return None
        payload = json.loads(raw[start : end + 1])
        if not isinstance(payload, list):
            log.warning("bedrock extract returned %s, not a list", type(payload).__name__)
            return None
        return [item for item in payload if isinstance(item, dict)]
    except Exception as exc:
        log.warning("bedrock extract failed: %s", exc)
        return None
