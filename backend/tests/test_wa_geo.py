"""WA OSPI schools get map pins from city centroids when latlon is missing."""

from __future__ import annotations

from search.corpus import clear_corpus_cache, load_schools
from search.geo import attach_coordinates


def test_seattle_schools_get_approx_coordinates():
    clear_corpus_cache()
    seattle = [s for s in load_schools() if s.get("city") == "Seattle" and "m" in (s.get("level_codes") or [])]
    assert seattle
    placed = [s for s in seattle if s.get("_lat") is not None and s.get("_lon") is not None]
    assert len(placed) == len(seattle)
    assert all(s.get("_approx_geo") for s in placed)
    # Pins are near Seattle, not stacked on one point.
    lats = {round(s["_lat"], 4) for s in placed}
    lons = {round(s["_lon"], 4) for s in placed}
    assert len(lats) > 1 and len(lons) > 1
    assert all(47.4 < s["_lat"] < 47.8 for s in placed)
    assert all(-122.5 < s["_lon"] < -122.1 for s in placed)


def test_approx_is_stable_for_same_id():
    school = {"id": "School wa-101143", "city": "Seattle", "name": "Aki Kurose Middle School"}
    a = attach_coordinates(dict(school))
    b = attach_coordinates(dict(school))
    assert (a["_lat"], a["_lon"]) == (b["_lat"], b["_lon"])
