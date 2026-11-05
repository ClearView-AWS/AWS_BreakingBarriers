"""Load the untouched sample plus generated schools and programs."""

from __future__ import annotations

import json
from functools import lru_cache

from runtime_config import INCLUDE_WA, SAMPLE_DIR, SYNTHETIC_DIR, WA_DIR
from search.geo import attach_coordinates, parse_latlon


def _read_json(path) -> list:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return data if isinstance(data, list) else []


@lru_cache(maxsize=1)
def load_schools() -> list[dict]:
    schools = _read_json(SAMPLE_DIR / "schools_sample.json")
    schools += _read_json(SYNTHETIC_DIR / "schools.json")
    # Public OSPI Washington Report Card schools (optional; see data/wa/).
    if INCLUDE_WA:
        schools += _read_json(WA_DIR / "schools.json")
    for school in schools:
        attach_coordinates(school)
        school.setdefault("city_untokenized", str(school.get("city") or "").casefold().replace(" ", ""))
    return schools


@lru_cache(maxsize=1)
def load_programs() -> list[dict]:
    programs = _read_json(SAMPLE_DIR / "programs_sample.json")
    programs += _read_json(SYNTHETIC_DIR / "programs.json")
    for program in programs:
        point = parse_latlon(program.get("latlon"))
        if point:
            program["_lat"], program["_lon"] = point
        else:
            program["_lat"], program["_lon"] = None, None
    return programs


def clear_corpus_cache() -> None:
    load_schools.cache_clear()
    load_programs.cache_clear()


def known_cities() -> list[str]:
    cities = {school.get("city") for school in load_schools() if school.get("city")}
    cities.update({"Jacksonville", "Miami", "Orlando", "Tampa", "Tallahassee", "St. Petersburg"})
    cities.update({"Seattle", "Tacoma", "Spokane", "Bellevue", "Vancouver", "Kent", "Redmond", "Everett"})
    return sorted(cities, key=len, reverse=True)
