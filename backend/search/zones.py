"""Demo attendance areas for the map.

The data has no real attendance boundaries, so each zoned public school gets a
demo area: the part of the map closer to it than to any other zoned public
school of the same level in its city, capped at MAX_MILES from the school.
Every area is labeled as a demo and points to the district's official zone
lookup. Charter and private schools take any address, so they get no area.
"""

from __future__ import annotations

import math
from functools import lru_cache

from enrollment.access import DEFAULT_HOW, _first, enrollment_rules
from search.corpus import load_schools

MAX_MILES = 3.0
MILES_PER_DEGREE = 69.0
CAP_SIDES = 32

DEMO_NOTE = "Demo area from the nearest zoned school. Not the official zone."
OPEN_NOTE = "Open to families from any address. No attendance area."
CHOICE_NOTE = "Admission by application or lottery. No attendance area."


def _how(school: dict) -> str:
    rules = enrollment_rules()["rules"]
    typed = _first((school.get("osp") or {}).get("admission_type"))
    return typed if typed in rules else DEFAULT_HOW.get(school.get("entity_type"), "application")


def _zoned(school: dict) -> bool:
    return school.get("entity_type") == "public" and _how(school) == "zoned" and school.get("_lat") is not None


def _clip(polygon: list[tuple[float, float]], a: float, b: float, c: float) -> list[tuple[float, float]]:
    """Keep the part of a convex polygon where a*x + b*y <= c."""
    out: list[tuple[float, float]] = []
    for i, current in enumerate(polygon):
        previous = polygon[i - 1]
        inside_now = a * current[0] + b * current[1] <= c
        inside_before = a * previous[0] + b * previous[1] <= c
        if inside_now != inside_before:
            dx, dy = current[0] - previous[0], current[1] - previous[1]
            t = (c - a * previous[0] - b * previous[1]) / (a * dx + b * dy)
            out.append((previous[0] + t * dx, previous[1] + t * dy))
        if inside_now:
            out.append(current)
    return out


def _cell(school: dict, peers: list[dict]) -> list[list[float]]:
    lat0, lon0 = school["_lat"], school["_lon"]
    scale = math.cos(math.radians(lat0))
    # Work in miles around the school so the cap is round and the split is fair.
    def to_xy(lat: float, lon: float) -> tuple[float, float]:
        return ((lon - lon0) * scale * MILES_PER_DEGREE, (lat - lat0) * MILES_PER_DEGREE)

    polygon = [
        (MAX_MILES * math.cos(2 * math.pi * k / CAP_SIDES), MAX_MILES * math.sin(2 * math.pi * k / CAP_SIDES))
        for k in range(CAP_SIDES)
    ]
    for peer in peers:
        px, py = to_xy(peer["_lat"], peer["_lon"])
        if px == 0 and py == 0:
            continue
        # Points closer to the school (origin) than to the peer: px*x + py*y <= (px^2 + py^2) / 2.
        polygon = _clip(polygon, px, py, (px * px + py * py) / 2)
        if not polygon:
            break
    return [[round(lat0 + y / MILES_PER_DEGREE, 5), round(lon0 + x / (scale * MILES_PER_DEGREE), 5)] for x, y in polygon]


@lru_cache(maxsize=1)
def _by_id() -> dict[str, dict]:
    return {school["id"]: school for school in load_schools()}


@lru_cache(maxsize=4096)
def zone_for(school_id: str) -> dict | None:
    school = _by_id().get(school_id)
    if not school:
        return None
    district = (enrollment_rules().get("districts") or {}).get(school.get("city")) or {}
    base = {
        "school_id": school_id,
        "district": district.get("name"),
        "locator_url": district.get("locator_url"),
    }
    if not _zoned(school):
        open_to_all = school.get("entity_type") in {"charter", "private"}
        return {**base, "kind": "open" if open_to_all else "choice", "polygon": None,
                "note": OPEN_NOTE if open_to_all else CHOICE_NOTE}
    levels = set(school.get("level_codes") or [])
    peers = [
        other for other in _by_id().values()
        if other["id"] != school_id
        and other.get("city") == school.get("city")
        and _zoned(other)
        and levels & set(other.get("level_codes") or [])
    ]
    return {**base, "kind": "demo_area", "polygon": _cell(school, peers), "note": DEMO_NOTE}


def zones_for(school_ids: list[str]) -> list[dict]:
    return [zone for zone in (zone_for(school_id) for school_id in school_ids[:60]) if zone]
