"""Demo attendance areas: only zoned public schools get one, and it is labeled a demo."""

from __future__ import annotations

from search.corpus import load_schools
from search.zones import MAX_MILES, zone_for, zones_for
from search.geo import miles_between


def _inside(point, polygon):
    lat, lon = point
    inside = False
    for i, (lat1, lon1) in enumerate(polygon):
        lat2, lon2 = polygon[i - 1]
        if (lon1 > lon) != (lon2 > lon) and lat < (lat2 - lat1) * (lon - lon1) / (lon2 - lon1) + lat1:
            inside = not inside
    return inside


def _zoned():
    return [s for s in load_schools() if (zone_for(s["id"]) or {}).get("kind") == "demo_area"]


def test_charter_and_private_get_no_area():
    for school in load_schools():
        if school["entity_type"] in {"charter", "private"}:
            zone = zone_for(school["id"])
            assert zone["kind"] == "open" and zone["polygon"] is None


def test_area_is_labeled_demo_and_links_the_district_lookup():
    zone = zone_for(_zoned()[0]["id"])
    assert "Not the official zone" in zone["note"]
    assert "locator_url" in zone


def test_area_holds_its_school_and_stays_within_the_cap():
    for school in _zoned()[:20]:
        polygon = zone_for(school["id"])["polygon"]
        assert len(polygon) >= 3
        assert _inside((school["_lat"], school["_lon"]), polygon)
        assert all(miles_between((school["_lat"], school["_lon"]), (lat, lon)) <= MAX_MILES + 0.05 for lat, lon in polygon)


def test_areas_of_same_level_neighbors_do_not_hold_each_other():
    schools = _zoned()
    for school in schools[:20]:
        polygon = zone_for(school["id"])["polygon"]
        for other in schools:
            if other["id"] == school["id"] or other["city"] != school["city"]:
                continue
            if set(other["level_codes"]) & set(school["level_codes"]):
                assert not _inside((other["_lat"], other["_lon"]), polygon)


def test_unknown_ids_are_skipped():
    assert zones_for(["nope"]) == []
