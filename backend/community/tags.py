"""Need tags and a rough stance for posts.

Tags are the need ids in needs.yaml, so the agent can find threads by school
and need. The parent confirms the suggested tags before posting.

The stance rule is a small word list. It only decides whether a post leans
positive or negative about the tagged need; questions are always neutral.
Swap in a Bedrock Haiku call later if the word list is too blunt.
"""

from __future__ import annotations

import re

from catalog import needs
from mapping.mapper import _phrase_in, normalize

_POSITIVE = {
    "love", "loves", "loved", "great", "helpful", "recommend", "happy", "excellent",
    "amazing", "good", "wonderful", "fantastic", "supportive", "best", "thriving", "fun",
}
_NEGATIVE = {
    "bad", "terrible", "worried", "disappointed", "disappointing", "poor", "unsafe", "awful",
    "never", "frustrating", "frustrated", "chaotic", "worst", "unhappy", "struggled", "lacking",
}
_WORD = re.compile(r"[a-z']+")


def suggest_tags(text: str, limit: int = 3) -> list[dict]:
    normalized = normalize(text or "")
    hits: list[tuple[int, str]] = []
    for need_id, spec in needs().items():
        phrases = [spec.get("label") or need_id, *(spec.get("phrases") or [])]
        longest = 0
        for phrase in phrases:
            if _phrase_in(normalized, phrase):
                longest = max(longest, len(phrase))
        if longest:
            hits.append((longest, need_id))
    hits.sort(reverse=True)
    out = []
    for _, need_id in hits[:limit]:
        out.append({"need": need_id, "label": label_for(need_id)})
    return out


def label_for(need_id: str) -> str:
    return (needs().get(need_id) or {}).get("label") or need_id.replace("_", " ")


def stance(text: str, kind: str) -> str:
    if kind == "question":
        return "neutral"
    words = _WORD.findall((text or "").casefold())
    positive = sum(1 for word in words if word in _POSITIVE)
    negative = sum(1 for word in words if word in _NEGATIVE)
    if positive > negative:
        return "positive"
    if negative > positive:
        return "negative"
    return "neutral"
