"""Map a parent phrase to a need with embeddings. Code, not the model, picks the id."""

from __future__ import annotations

import re
from dataclasses import dataclass

from catalog import needs
from mapping.embedder import cosine, embed_hash

_NON_WORD = re.compile(r"[^a-z0-9]+")

# Exact phrase hits dominate. Below this cosine, the phrase stays unmapped.
UNMAPPED_BELOW = 0.42
AMBIGUOUS_MARGIN = 0.06


@dataclass
class MapHit:
    need: str | None
    score: float
    runner_up: str | None
    margin: float


def normalize(text: str) -> str:
    lowered = (
        text.casefold()
        .replace("’", "'")
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )
    lowered = lowered.replace("-", " ")
    return _NON_WORD.sub(" ", lowered).strip()


def _phrase_in(text: str, phrase: str) -> bool:
    phrase_n = normalize(phrase)
    if not phrase_n:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase_n)}(?![a-z0-9])", text) is not None


_centroids: dict[str, list[float]] | None = None


def _centroids_for() -> dict[str, list[float]]:
    global _centroids
    if _centroids is None:
        built: dict[str, list[float]] = {}
        for need_id, spec in needs().items():
            phrases = [spec.get("label") or need_id, *(spec.get("phrases") or [])]
            vectors = [embed_hash(normalize(p)) for p in phrases]
            width = len(vectors[0])
            mean = [sum(v[i] for v in vectors) / len(vectors) for i in range(width)]
            norm = sum(x * x for x in mean) ** 0.5 or 1.0
            built[need_id] = [x / norm for x in mean]
        _centroids = built
    return _centroids


def map_phrase(text: str) -> MapHit:
    """Return the best need for a phrase that was already pulled out of the query."""
    catalog = needs()
    normalized = normalize(text)
    exact: dict[str, float] = {}
    for need_id, spec in catalog.items():
        for phrase in spec.get("phrases") or []:
            if _phrase_in(normalized, phrase):
                # Longer phrases win inside the same need; the cross-need choice is below.
                exact[need_id] = max(exact.get(need_id, 0.0), 0.62 + min(len(phrase), 40) / 200)

    vector = embed_hash(normalized)
    scored: list[tuple[float, str]] = []
    for need_id, centroid in _centroids_for().items():
        lexical = exact.get(need_id, 0.0)
        semantic = cosine(vector, centroid)
        if lexical:
            score = min(1.0, lexical + 0.1 * max(semantic, 0))
        else:
            score = semantic
        scored.append((score, need_id))
    scored.sort(reverse=True)
    if not scored:
        return MapHit(None, 0.0, None, 1.0)
    best_score, best_id = scored[0]
    runner_score, runner_id = scored[1] if len(scored) > 1 else (0.0, None)
    margin = best_score - runner_score
    if best_id not in exact and best_score < UNMAPPED_BELOW:
        return MapHit(None, round(best_score, 4), runner_id, round(margin, 4))
    return MapHit(best_id, round(best_score, 4), runner_id, round(margin, 4))


def mapping_is_ambiguous(hit: MapHit) -> bool:
    return bool(hit.need) and hit.margin < AMBIGUOUS_MARGIN and hit.score < 0.7
