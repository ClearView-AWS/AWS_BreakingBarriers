"""Expand the Florida sample to about 300 schools without editing the original 25.

Demo schools are hand-placed so the Jacksonville middle-school script can show
on-site care, nearby programs, a stale program, a website conflict, and a
school with no after-care data. Random schools keep the sample's missing-data
rates. Jacksonville middle schools in the random set never have both STEM and
on-site care, so they cannot crowd the demo ranking.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "Sample Data" / "schools_sample.json"
PROGRAM_SAMPLE = ROOT / "Sample Data" / "programs_sample.json"
OUT_SCHOOLS = Path(__file__).resolve().parent / "schools.json"
OUT_PROGRAMS = Path(__file__).resolve().parent / "programs.json"
WEB = Path(__file__).resolve().parent / "websites"

TARGET = 300
LEAP_POINT = (30.42, -81.78)
FULL_POINT = (30.33, -81.60)
ONSITE_POINT = (30.30, -81.58)
ASK_POINT = (30.20, -81.80)
STALE_POINT = (30.15, -81.50)

ADJECTIVES = [
    "Harbor", "Cedar", "Palm", "Oak", "Cypress", "Bay", "Pine", "Coral", "Willow", "Maple",
    "Lark", "Heron", "Osprey", "Marlin", "Dolphin", "Magnolia", "Sabal", "Indigo", "Citrus", "River",
]
PLACES = [
    "Ridge", "Crossing", "Landing", "Gardens", "Shores", "Park", "Grove", "Heights", "Walk", "Point",
    "Terrace", "Commons", "Bend", "Cove", "Trace", "Meadow", "Springs", "Harbor", "Isle", "Run",
]


def main() -> None:
    sample = json.loads(SAMPLE.read_text())
    demo, demo_programs = _demo()
    random_schools, random_programs = _random(len(sample) + len(demo))
    schools = demo + random_schools
    programs = demo_programs + random_programs
    OUT_SCHOOLS.write_text(json.dumps(schools, indent=2))
    OUT_PROGRAMS.write_text(json.dumps(programs, indent=2))
    _websites(schools)
    print(f"sample {len(sample)} + synthetic {len(schools)} = {len(sample) + len(schools)} schools")
    print(f"synthetic programs {len(programs)}")


def _demo() -> tuple[list[dict], list[dict]]:
    schools = []
    schools.append(_school(1, "Tidewater STEM Charter", "charter", ["m"], FULL_POINT, 0.004, stem=True, care="18:00", rating=9, role="full"))
    schools.append(_school(2, "St. Johns STEM Middle", "public", ["m"], FULL_POINT, 0.008, stem=True, care="17:30", rating=8, role="full"))
    schools.append(_school(3, "Arlington STEM Academy", "charter", ["m"], FULL_POINT, 0.012, stem=True, care="18:00", rating=8, role="full"))
    schools.append(_school(4, "Mandarin Bridge Middle", "public", ["m"], FULL_POINT, 0.016, stem=True, care="17:30", rating=7, role="full"))
    schools.append(
        _school(
            5,
            "Riverside Preparatory Middle",
            "private",
            ["m"],
            FULL_POINT,
            0.02,
            stem=True,
            care="18:00",
            rating=9,
            tuition="15200",
            role="private",
        )
    )
    for offset, name in enumerate(
        [
            "Riverview Day Middle",
            "Ortega Day Middle",
            "Avondale Day Middle",
            "Murray Hill Day Middle",
            "Lakewood Day Middle",
        ],
        start=6,
    ):
        schools.append(
            _school(
                offset,
                name,
                "public",
                ["m"],
                ONSITE_POINT,
                0.004 * (offset - 5),
                stem=False,
                care="18:00",
                rating=8,
                role="onsite",
            )
        )
    leap_names = [
        "Cedar Creek STEM Middle",
        "San Marco STEM Middle",
        "Hogan STEM Middle",
        "Kernan STEM Middle",
        "Oceanway STEM Middle",
        "Fort Caroline STEM Middle",
        "Dames Point STEM Middle",
        "Southside STEM Middle",
    ]
    for offset, name in enumerate(leap_names, start=11):
        schools.append(
            _school(offset, name, "public", ["m"], LEAP_POINT, 0.004 * (offset - 10), stem=True, care=None, rating=6, role="leap")
        )
    schools.append(_school(19, "Beauclerc STEM Middle", "public", ["m"], ASK_POINT, 0.0, stem=True, care=None, rating=5, role="ask"))
    schools.append(_school(20, "Northside STEM Middle", "charter", ["m"], STALE_POINT, 0.0, stem=True, care=None, rating=4, role="stale"))
    schools.append(
        _school(
            21,
            "Landmark Christian Middle",
            "private",
            ["m"],
            ASK_POINT,
            0.03,
            stem=False,
            care=None,
            rating=None,
            tuition="11000",
            religious=True,
            role="religious",
        )
    )
    programs = [
        _program(1, "Cedar Creek After School STEM Lab", LEAP_POINT, live=True, end="18:00"),
        _program(2, "Mandarin Homework Help Club", (LEAP_POINT[0] + 0.01, LEAP_POINT[1] - 0.01), live=True, end="18:00"),
        _program(3, "Northside After School Club", STALE_POINT, live=False, end="17:30"),
    ]
    return schools, programs


def _random(already: int) -> tuple[list[dict], list[dict]]:
    rng = random.Random(7)
    need = TARGET - already
    metros = [
        ("Jacksonville", "Duval County", 30.25, -81.60, "322"),
        ("Miami", "Miami-Dade County", 25.80, -80.22, "331"),
        ("Orlando", "Orange County", 28.52, -81.38, "328"),
    ]
    schools = []
    programs = []
    for index in range(need):
        city, county, lat, lon, zip_prefix = metros[0 if rng.random() < 0.4 else 1 if rng.random() < 0.7 else 2]
        # Keep random Jacksonville pins south of the leap-program cluster.
        if city == "Jacksonville":
            lat = 30.18 + rng.random() * 0.14
            lon = -81.80 + rng.random() * 0.28
        else:
            lat = lat + rng.uniform(-0.12, 0.12)
            lon = lon + rng.uniform(-0.12, 0.12)
        roll = rng.random()
        entity = "charter" if roll < 0.48 else "private" if roll < 0.80 else "public"
        levels = rng.choice([["e"], ["m"], ["h"], ["p", "e"], ["e", "m"], ["m", "h"]])
        stem = rng.random() < 0.28
        care = "17:30" if rng.random() < 0.35 else None
        if city == "Jacksonville" and "m" in levels and stem and care:
            care = None
        rating = None if rng.random() < 0.48 else rng.choice([3, 4, 5, 6, 7, 8, 9])
        tuition = str(rng.choice([9000, 11000, 14000, 18000])) if entity == "private" else None
        name = f"{rng.choice(ADJECTIVES)} {rng.choice(PLACES)} {rng.choice(['School', 'Academy', 'Institute'])}"
        school = _school(
            100 + index,
            name,
            entity,
            levels,
            (lat, lon),
            0.0,
            stem=stem,
            care=care,
            rating=rating,
            tuition=tuition,
            role="random",
            county=county,
            city=city,
            zip_prefix=zip_prefix,
            rng=rng,
        )
        if rng.random() >= 0.48:
            school["reviews_full"] = _reviews(name, positive=rng.random() > 0.4)
            school["reviews_text"] = [row["text"] for row in school["reviews_full"]]
            school["avg_review_rating"] = 3.8
        if rng.random() < 0.48:
            school.pop("student_teacher_ratio", None)
        schools.append(school)
        if rng.random() < 0.18 and not (city == "Jacksonville" and lat > 30.36):
            programs.append(
                _program(
                    100 + index,
                    f"{name.split()[0]} Homework Help",
                    (lat, lon),
                    live=rng.random() > 0.2,
                    end="18:00",
                    city=city,
                )
            )
    return schools, programs


def _school(
    number: int,
    name: str,
    entity: str,
    levels: list[str],
    origin: tuple[float, float],
    shift: float,
    stem: bool,
    care: str | None,
    rating: int | None,
    role: str,
    tuition: str | None = None,
    arts: bool = False,
    religious: bool = False,
    county: str = "Duval County",
    city: str = "Jacksonville",
    zip_prefix: str = "322",
    rng: random.Random | None = None,
) -> dict:
    rng = rng or random.Random(number)
    lat = round(origin[0] + shift, 6)
    lon = round(origin[1] + shift / 2, 6)
    school_id = 180000 + number
    osp: dict = {
        "coed": ["coed"],
        "boarding": ["day"],
    }
    if stem:
        osp["school_sub_type"] = ["STEM"]
        osp["student_clubs"] = ["science_club", "robotics", "math_club"]
    elif arts:
        osp["school_sub_type"] = ["arts"]
        osp["arts_visual"] = ["drawing", "painting"]
        osp["arts_music"] = ["band"]
        osp["student_clubs"] = ["art_club"]
    elif religious:
        osp["school_sub_type"] = ["religious"]
    if care:
        osp["after_school_until"] = [care]
    if entity == "public":
        osp["transportation"] = ["busses"]
    if tuition:
        osp["tuition"] = [tuition]
    if rng.random() > 0.5:
        osp["end_time"] = ["3:15 PM"]
    record = {
        "id": f"School fl-{school_id}",
        "school_id": school_id,
        "name": name,
        "sortable_name": name.casefold(),
        "document_type": "School",
        "entity_type": entity,
        "level_codes": levels,
        "city": city,
        "city_untokenized": city.casefold().replace(" ", ""),
        "county": county,
        "state": "FL",
        "street": f"{100 + number} Synthetic Avenue",
        "zipcode": f"{zip_prefix}{number % 100:02d}",
        "latlon": f"{lat}, {lon}",
        "enrollment": 280 + number * 3,
        "created": "2026-02-01T12:00:00-05:00",
        "osp": osp,
        "esp_text": [f"{name} serves families in {city}."],
        "_synthetic": True,
        "_demo_role": role,
    }
    if rating is not None:
        record["summary_rating"] = rating
        record["test_scores_rating"] = max(1, rating - 1)
        record["student_progress_rating"] = rating
    if rng.random() > 0.3:
        record["student_teacher_ratio"] = rng.choice([12, 14, 16, 18, 22])
    if role in {"full", "ask", "leap", "onsite"}:
        record["reviews_full"] = _reviews(name, positive=role != "ask", stem_topic=role == "onsite")
        record["reviews_text"] = [row["text"] for row in record["reviews_full"]]
        record["avg_review_rating"] = 4.2 if role != "ask" else 3.1
    return record


def _reviews(name: str, positive: bool, stem_topic: bool = False) -> list[dict]:
    tone = "positive" if positive else "negative"
    score = 0.97 if positive else -0.97
    stem = "STEM / Coding" if stem_topic or positive else "Teachers / Staff"
    return [
        {
            "text": f"Our child settled in at {name} and the teachers stay in touch.",
            "created_date": "2024-11-02T00:00:00-04:00",
            "overall_rating": score,
            "sentiments": [{"topic": "Teachers / Staff", "sentiment_enum": tone, "sentiment_polarity": str(score)}],
        },
        {
            "text": f"The science activities at {name} are a regular part of the week.",
            "created_date": "2025-03-18T00:00:00-04:00",
            "overall_rating": score,
            "sentiments": [{"topic": stem, "sentiment_enum": tone, "sentiment_polarity": str(score)}],
        },
        {
            "text": f"Science club is the reason we picked {name}.",
            "created_date": "2025-09-12T00:00:00-04:00",
            "overall_rating": score,
            "sentiments": [{"topic": "STEM / Coding", "sentiment_enum": "positive" if positive else "negative", "sentiment_polarity": str(score)}],
        },
    ]


def _program(number: int, name: str, origin: tuple[float, float], live: bool, end: str, city: str = "Jacksonville") -> dict:
    program_id = 880000 + number
    if live:
        start, finish, status = "2026-11-01", "2027-05-20", "upcoming"
    else:
        start, finish, status = "2024-01-08", "2024-05-20", "past"
    return {
        "id": f"Program fl-{program_id}",
        "program_id": program_id,
        "name": name,
        "description": f"After school homework help until {end} on school days.",
        "program_type": "after_school",
        "city": city,
        "state": "FL",
        "geo_state": "FL",
        "county": "Duval County" if city == "Jacksonville" else "",
        "latlon": f"{origin[0]}, {origin[1]}",
        "tag_names": ["After School", "Homework Help", "STEM"],
        "level_code": ["m"],
        "age_min_search": 10,
        "age_max_search": 14,
        "instances": [
            {
                "id": program_id,
                "start_date": start,
                "end_date": finish,
                "status": status,
                "active": live,
                "start_time": "15:30",
                "end_time": end,
            }
        ],
        "_synthetic": True,
    }


def _websites(schools: list[dict]) -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    for path in WEB.glob("*.html"):
        path.unlink()
    for school in schools:
        facts = []
        role = school.get("_demo_role")
        if role == "full" and school["name"].startswith("Tidewater"):
            facts.append({"path": "osp.after_school_until", "value": "16:00", "as_of": "2026-10-01"})
        if school["name"] == "Cedar Creek STEM Middle":
            facts.append({"path": "osp.after_school_until", "value": "18:00", "as_of": "2026-10-12"})
        payload = {"school_id": school["id"], "facts": facts}
        body = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{school['name']}</title></head>
<body>
  <p>This is a synthetic page for {school['name']} in {school['city']}. It is not a real school site.</p>
  <script id="school-facts" type="application/json">{json.dumps(payload)}</script>
</body>
</html>
"""
        slug = str(school["school_id"])
        (WEB / f"{slug}.html").write_text(body)


if __name__ == "__main__":
    main()
