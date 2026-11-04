"""Classify a parent message. Rules first; Bedrock only when it is enabled."""

from __future__ import annotations

import re

from contracts import EngineStep
from mapping.mapper import normalize


def route_message(text: str, has_session: bool) -> tuple[str, EngineStep]:
    from agent.bedrock_client import maybe_bedrock_route

    drafted, step = maybe_bedrock_route(text, has_session)
    return drafted or _rules_route(text, has_session), step


def _rules_route(text: str, has_session: bool) -> str:
    normalized = normalize(text)
    if re.search(r"\bwhy isn t\b|\bwhy isnt\b|\bwhy not\b|\bhow come\b", normalized):
        return "why_not"
    if re.search(r"\bcompare\b|\bversus\b|\bvs\b|\bside by side\b", normalized):
        return "compare"
    if re.search(r"\bwhat is\b|\bwhat s\b|\bdefine\b|\bmeaning of\b", normalized):
        return "define"
    if re.search(r"\bscholarship\b|\btuition\b|\bhow much\b|\bcost\b", normalized):
        return "cost"
    if re.search(r"\bsave\b|\bshortlist\b|\badd to (my )?list\b", normalized):
        return "save"
    if re.search(r"\btoo far\b|\bthumbs\b|\bnot relevant\b", normalized):
        return "feedback"
    if re.search(r"\btell me about\b|\bdetails on\b|\bprofile\b", normalized) or _names_a_school(normalized):
        return "school_detail"
    if has_session and not _states_grade_and_place(text):
        return "refine"
    return "new_search"


def _names_a_school(normalized: str) -> bool:
    from search.corpus import load_schools

    for school in load_schools():
        name = normalize(school.get("name") or "")
        if name and re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", normalized):
            return True
    return False


def _states_grade_and_place(text: str) -> bool:
    """A follow-up that names both a grade level and a place starts a new search."""
    from agent.extractor import _rules
    from search.corpus import known_cities

    kinds = {criterion.kind for criterion in _rules(text, known_cities())}
    return {"grade", "location"} <= kinds


def term_from_question(text: str) -> str:
    normalized = normalize(text)
    match = re.search(r"(?:what is|what s|define|meaning of)\s+([a-z0-9 ]+)", normalized)
    if not match:
        return normalized
    return match.group(1).strip(" ?.")


def school_reference(text: str) -> str | None:
    normalized = normalize(text)
    patterns = [
        r"why isn t (.+?) (?:here|listed|showing|in the|on the|included)",
        r"why isnt (.+?) (?:here|listed|showing)",
        r"compare (.+?) (?:and|vs|versus|with) (.+)",
        r"tell me about (.+)",
        r"details on (.+)",
        r"how much (?:is|does) (.+?) cost",
        r"tuition (?:at|for) (.+)",
        r"save (.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return match.group(1).strip(" ?.")
    return None
