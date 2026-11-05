"""Distance helpers. Hard filters never use distance; scoring does."""

from __future__ import annotations

import hashlib
import math

CITY_CENTROIDS = {
    "jacksonville": (30.3322, -81.6557),
    "miami": (25.7617, -80.1918),
    "orlando": (28.5383, -81.3792),
    "tampa": (27.9506, -82.4572),
    "tallahassee": (30.4383, -84.2807),
    # Washington (OSPI public corpus) — city centroids for distance + map pins.
    "seattle": (47.6062, -122.3321),
    "tacoma": (47.2529, -122.4443),
    "spokane": (47.6588, -117.4260),
    "spokane valley": (47.6733, -117.2394),
    "bellevue": (47.6101, -122.2015),
    "vancouver": (45.6387, -122.6615),
    "kent": (47.3809, -122.2348),
    "redmond": (47.6740, -122.1215),
    "everett": (47.9789, -122.2021),
    "federal way": (47.3223, -122.3126),
    "yakima": (46.6021, -120.5059),
    "olympia": (47.0379, -122.9007),
    "bellingham": (48.7519, -122.4787),
    "renton": (47.4829, -122.2171),
    "kirkland": (47.6815, -122.2087),
    "auburn": (47.3073, -122.2285),
    "lakewood": (47.1718, -122.5185),
    "kennewick": (46.2112, -119.1372),
    "pasco": (46.2396, -119.1006),
    "richland": (46.2857, -119.2845),
    "puyallup": (47.1854, -122.2929),
    "bothell": (47.7599, -122.2054),
    "burien": (47.4704, -122.3468),
    "edmonds": (47.8107, -122.3774),
    "issaquah": (47.5301, -122.0326),
    "marysville": (48.0518, -122.1771),
    "spanaway": (47.1040, -122.4346),
    "mukilteo": (47.9445, -122.3046),
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


def _approx_from_city(school: dict) -> tuple[float, float] | None:
    """Stable city-centroid pin when OSPI rows have no street latlon (demo map)."""
    city = str(school.get("city") or "").casefold().strip()
    centroid = CITY_CENTROIDS.get(city)
    if not centroid:
        return None
    digest = hashlib.md5(str(school.get("id") or school.get("name") or city).encode()).hexdigest()
    dlat = ((int(digest[:4], 16) % 1000) - 500) / 12_000  # ~±0.04°
    dlon = ((int(digest[4:8], 16) % 1000) - 500) / 12_000
    return centroid[0] + dlat, centroid[1] + dlon


def attach_coordinates(school: dict) -> dict:
    point = parse_latlon(school.get("latlon"))
    approx = False
    if not point:
        point = _approx_from_city(school)
        approx = point is not None
    if point:
        school["_lat"], school["_lon"] = point
        if approx:
            school["_approx_geo"] = True
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
