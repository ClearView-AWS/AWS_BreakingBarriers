"""Load needs, funding rules, glossary, and model ids."""

from __future__ import annotations

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


def funding_rules_for(state: str) -> dict[str, dict[str, Any]]:
    """Scholarship rules that apply in one state. A rule with no `states` list applies everywhere."""
    return {
        rule_id: rule
        for rule_id, rule in funding_rules().items()
        if not rule.get("states") or state in rule["states"]
    }


@lru_cache(maxsize=1)
def glossary() -> dict[str, dict[str, Any]]:
    return _load("glossary.yaml")


@lru_cache(maxsize=1)
def models() -> dict[str, Any]:
    return _load("models.yaml")


@lru_cache(maxsize=1)
def call_limits() -> dict[str, Any]:
    return _load("calls.yaml")


def unmapped_offers() -> list[tuple[str, str]]:
    out = []
    for need_id, spec in needs().items():
        if spec.get("offer_when_unmapped"):
            out.append((need_id, spec.get("label") or need_id))
    return out
