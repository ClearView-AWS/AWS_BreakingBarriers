"""Classify a parent message. Rules first; Bedrock only when it is enabled."""

from __future__ import annotations

import re

from mapping.mapper import normalize


def route_message(text: str, has_session: bool) -> str:
    from agent.bedrock_client import maybe_bedrock_route

    drafted = maybe_bedrock_route(text, has_session)
    if drafted:
        return drafted
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
    if re.search(r"\btell me about\b|\bdetails on\b|\bprofile\b", normalized):
        return "school_detail"
    if has_session:
        return "refine"
    return "new_search"


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
