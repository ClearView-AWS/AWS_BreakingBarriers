"""Load needs, funding rules, glossary, and model ids."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import yaml

from runtime_config import CONFIG_DIR


def _load(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be a mapping")
    return data


@lru_cache(maxsize=1)
def needs() -> dict[str, dict[str, Any]]:
    return _load("needs.yaml")


@lru_cache(maxsize=1)
def funding_rules() -> dict[str, dict[str, Any]]:
    return _load("funding_rules.yaml")


@lru_cache(maxsize=1)
def glossary() -> dict[str, dict[str, Any]]:
    return _load("glossary.yaml")


@lru_cache(maxsize=1)
def models() -> dict[str, Any]:
    """Model ids from models.yaml. Env vars win, so a sandbox can swap ids without a code change."""
    data = _load("models.yaml")
    overrides = {
        "fast_model": "FAST_MODEL_ID",
        "strong_model": "STRONG_MODEL_ID",
        "embed_model": "EMBED_MODEL_ID",
        "region": "AWS_REGION",
    }
    for key, env in overrides.items():
        value = os.environ.get(env, "").strip()
        if value:
            data[key] = value
    return data


def unmapped_offers() -> list[tuple[str, str]]:
    out = []
    for need_id, spec in needs().items():
        if spec.get("offer_when_unmapped"):
            out.append((need_id, spec.get("label") or need_id))
    return out
