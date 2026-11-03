"""Distance helpers. Hard filters never use distance; scoring does."""

from __future__ import annotations

import math

CITY_CENTROIDS = {
    "jacksonville": (30.3322, -81.6557),
    "miami": (25.7617, -80.1918),
    "orlando": (28.5383, -81.3792),
    "tampa": (27.9506, -82.4572),
    "tallahassee": (30.4383, -84.2807),
}


def miles_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 3958.7613 * 2 * math.asin(math.sqrt(hav))


def parse_latlon(value: object) -> tuple[float, float] | None:
    if not isinstance(value, str) or "," not in value:
        return None
    left, right = value.split(",", 1)
    try:
        return float(left.strip()), float(right.strip())
    except ValueError:
        return None


def attach_coordinates(school: dict) -> dict:
    point = parse_latlon(school.get("latlon"))
    if point:
        school["_lat"], school["_lon"] = point
    else:
        school["_lat"], school["_lon"] = None, None
    return school


def distance_from_city(school: dict, city: str | None) -> float | None:
    if not city or school.get("_lat") is None:
        return None
    centroid = CITY_CENTROIDS.get(city.casefold())
    if not centroid:
        return None
    return miles_between((school["_lat"], school["_lon"]), centroid)
