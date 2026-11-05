"""Distance helpers. Hard filters never use distance; scoring does."""

from __future__ import annotations

import math

CITY_CENTROIDS = {
    "jacksonville": (30.3322, -81.6557),
    "miami": (25.7617, -80.1918),
    "orlando": (28.5383, -81.3792),
    "tampa": (27.9506, -82.4572),
    "tallahassee": (30.4383, -84.2807),
    # Washington (OSPI public corpus) — city centroids for distance scoring only.
    "seattle": (47.6062, -122.3321),
    "tacoma": (47.2529, -122.4443),
    "spokane": (47.6588, -117.4260),
    "bellevue": (47.6101, -122.2015),
    "vancouver": (45.6387, -122.6615),
    "kent": (47.3809, -122.2348),
    "redmond": (47.6740, -122.1215),
    "everett": (47.9789, -122.2021),
    "federal way": (47.3223, -122.3126),
    "yakima": (46.6021, -120.5059),
    "olympia": (47.0379, -122.9007),
    "bellingham": (48.7519, -122.4787),
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


def distance_from_point(school: dict, center: tuple[float, float] | None) -> float | None:
    """Straight-line miles from a map search point (never a home address)."""
    if not center or school.get("_lat") is None:
        return None
    return miles_between((school["_lat"], school["_lon"]), center)
