"""Review support for a criterion. Reviews never confirm a need."""

from __future__ import annotations

from datetime import date, datetime

from runtime_config import REVIEW_FULL_WEIGHT_YEARS, TODAY


def _parse_date(value: str | None) -> date | None:
    if not value or not isinstance(value, str):
        return None
    raw = value[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _weight(when: date | None, today: date) -> float:
    if when is None:
        return 1.0
    try:
        cutoff = today.replace(year=today.year - REVIEW_FULL_WEIGHT_YEARS)
    except ValueError:
        cutoff = today.replace(month=2, day=28, year=today.year - REVIEW_FULL_WEIGHT_YEARS)
    return 0.5 if when < cutoff else 1.0


def topic_tally(school: dict, topic: str, today: date | None = None) -> dict:
    """Weighted positive/negative counts for one review topic."""
    today = today or TODAY
    positive = 0.0
    negative = 0.0
    raw = 0
    ids: list[str] = []
    dates: list[date] = []
    for index, review in enumerate(school.get("reviews_full") or []):
        sentiments = review.get("sentiments") or []
        matched = [s for s in sentiments if s.get("topic") == topic]
        if not matched:
            continue
        raw += 1
        when = _parse_date(review.get("created_date"))
        if when:
            dates.append(when)
        weight = _weight(when, today)
        # One review contributes once, using its strongest polarity on this topic.
        polarities = [str(s.get("sentiment_enum") or "") for s in matched]
        review_id = f"reviews_full[{index}]"
        ids.append(review_id)
        if "negative" in polarities and "positive" not in polarities:
            negative += weight
        elif "positive" in polarities and "negative" not in polarities:
            positive += weight
    return {
        "positive": positive,
        "negative": negative,
        "raw": raw,
        "review_ids": ids,
        "newest": max(dates).isoformat() if dates else None,
    }


def review_status(school: dict, topics: list[str], today: date | None = None) -> dict | None:
    """Return a partial or needs-attention signal, or None when reviews are too thin."""
    if not topics:
        return None
    best = None
    for topic in topics:
        tally = topic_tally(school, topic, today)
        if tally["raw"] < 2:
            continue
        status = None
        if tally["negative"] >= 3 and tally["negative"] > tally["positive"]:
            status = "needs_attention"
        elif tally["positive"] >= 2 and tally["positive"] > tally["negative"]:
            status = "partial"
        if status is None:
            continue
        candidate = {**tally, "status": status, "topic": topic}
        if best is None:
            best = candidate
            continue
        rank = {"needs_attention": 2, "partial": 1}
        if rank[status] > rank[best["status"]]:
            best = candidate
    return best
