"""Bedrock Converse calls. Disabled unless BEDROCK_ENABLED=1, and never required."""

from __future__ import annotations

import json
import logging

from contracts import EngineStep
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


def _step(answered: bool, error: str | None) -> EngineStep:
    if answered:
        return EngineStep(engine="bedrock")
    if not enabled():
        return EngineStep(engine="rules")
    log.warning("%s", error)
    return EngineStep(engine="rules_fallback", error=error)


def maybe_bedrock_route(text: str, has_session: bool) -> tuple[str | None, EngineStep]:
    if not enabled():
        return None, _step(False, None)
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
        if raw in allowed:
            return raw, _step(True, None)
        error = f"bedrock route answer not allowed: {raw!r}"
    except Exception as exc:
        error = f"bedrock route failed: {exc}"
    return None, _step(False, error)


def maybe_bedrock_criteria(text: str, cities: list[str]) -> tuple[list[dict] | None, EngineStep]:
    """Return the model's raw draft items, or None to use the rules extractor.

    The items are untrusted. The extractor validates each one against the
    catalog and builds the criteria in code.
    """
    if not enabled():
        return None, _step(False, None)
    try:
        from catalog import models
        from agent.prompts import extract_system

        raw = converse(models()["fast_model"], extract_system(cities), text)
        start, end = raw.find("["), raw.rfind("]")
        if start < 0 or end < 0:
            return None, _step(False, f"bedrock extract returned no JSON array: {raw[:200]!r}")
        payload = json.loads(raw[start : end + 1])
        if not isinstance(payload, list):
            return None, _step(False, f"bedrock extract returned {type(payload).__name__}, not a list")
        return [item for item in payload if isinstance(item, dict)], _step(True, None)
    except Exception as exc:
        return None, _step(False, f"bedrock extract failed: {exc}")
