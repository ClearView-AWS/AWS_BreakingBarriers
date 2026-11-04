"""Build about 300 Seattle schools without editing GreatSchools' original sample.

The 25 sample schools (anonymized, Florida in the original) are copied to
sample_seattle.json with Seattle locations, ids, districts and addresses; their
ratings, reviews and missing fields stay as GreatSchools sent them. The original
files in Sample Data/ are not touched.

Demo schools are hand-placed so the Seattle middle-school script can show
on-site care, nearby programs, a stale program, a website conflict, and a
school with no after-care data. Random schools keep the sample's missing-data
rates. Seattle middle schools in the random set never have both STEM and
on-site care, so they cannot crowd the demo ranking.

Every generated school and program is then moved to the nearest street point
from street_points.json (Seattle arterials, see seattle_streets.py), so no pin
lands in water. That step uses no random numbers, so every other field stays the same.

Last, every generated school gets admissions fields in osp: admission_type on
all of them, and deadlines, links, requirements and seat counts at about the
sample's low rates. Demo schools get hand-set values that cover every Getting
in status. Each school draws these from its own random stream, so the fields
above never change. The 25 sample schools are not touched.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "Sample Data" / "schools_sample.json"
OUT_SAMPLE = Path(__file__).resolve().parent / "sample_seattle.json"
PROGRAM_SAMPLE = ROOT / "Sample Data" / "programs_sample.json"
OUT_SCHOOLS = Path(__file__).resolve().parent / "schools.json"
OUT_PROGRAMS = Path(__file__).resolve().parent / "programs.json"
WEB = Path(__file__).resolve().parent / "websites"
STREETS = Path(__file__).resolve().parent / "street_points.json"

# Random programs start on top of their school; move them this far away first
# so the two pins don't overlap. Well inside the plan's 1-mile program rule.
PROGRAM_OFFSET_MILES = (0.3, 0.6)

# Admissions. The sample fills admissions_url for 3 of 25 schools,
# application_requirements for 2 and application_deadline_date for 1, so the
# generated schools use about the same rates. Dates follow the sample's M/D/YYYY.
ADMISSION_TYPES = ("zoned", "choice", "lottery", "application")
URL_RATE = 0.12
REQUIREMENTS_RATE = 0.08
DEADLINE_RATE = 0.05
SEATS_RATE = 0.04
APPLICANTS_RATE = 0.04
# Ahead of the app's clock (Nov 3, 2026), already passed, and more than a year old.
DEADLINES = ["1/15/2027", "2/1/2027", "3/1/2027", "10/1/2026", "1/15/2025"]
REPORTED_ON = ["2026-03-15", "2026-08-20", "2026-09-15", "2026-10-05"]
ENTRY_GRADE = {"p": "PK", "e": "K", "m": "6", "h": "9"}

# Hand-set for the Seattle middle-school demo so each Getting in status shows up:
# apply by a date, open seats, deadline passed, waitlist only, and a stale deadline.
DEMO_ADMISSIONS = {
    "Arbor Heights STEM Middle": {
        # A district magnet lottery, so the demo's "after-care unknown" card also reads
        # "Lottery · apply by Jan 15".
        "admission_type": ["lottery"],
        "application_deadline_date": ["1/15/2027"],
        "application_requirements": ["application"],
        "applicants_last_year": [{"grade": "6", "applicants": 210, "seats": 90, "as_of": "2026-03-15"}],
    },
    "Queen Anne Preparatory Middle": {
        "admission_type": ["application"],
        "application_deadline_date": ["2/1/2027"],
        "application_requirements": ["application", "interview"],
    },
    "Cascade STEM Charter": {
        "admission_type": ["lottery"],
        "seats_by_grade": [{"grade": "6", "open_seats": 12, "waitlist": False, "as_of": "2026-09-15"}],
    },
    "Wallingford STEM Academy": {
        "admission_type": ["lottery"],
        "application_deadline_date": ["10/1/2026"],
    },
    "Rainier Beach STEM Middle": {
        "admission_type": ["lottery"],
        "seats_by_grade": [{"grade": "6", "open_seats": 0, "waitlist": True, "as_of": "2026-10-01"}],
    },
    "Evergreen Hill Christian Middle": {
        "admission_type": ["application"],
        "application_deadline_date": ["1/15/2025"],
    },
}

TARGET = 300
# Seattle neighborhoods: Northgate (leap), Wallingford (full), Ballard (on-site care),
# Arbor Heights (ask), Rainier Beach (stale program).
LEAP_POINT = (47.708, -122.325)
FULL_POINT = (47.661, -122.340)
ONSITE_POINT = (47.668, -122.383)
ASK_POINT = (47.517, -122.376)
STALE_POINT = (47.524, -122.280)
# About the old Jacksonville density of after-school programs per square mile.
PROGRAM_RATE = 0.06
# Random Seattle pins stay south of the Northgate leap cluster.
RANDOM_BOX = (47.53, 47.69, -122.39, -122.28)

# Every word sorts after "Arbor", so the demo's ask school keeps its place in ties.
ADJECTIVES = [
    "Cedar", "Fir", "Madrona", "Salmon", "Orca", "Cascade", "Evergreen", "Hemlock", "Spruce", "Maple",
    "Willow", "Heron", "Osprey", "Juniper", "Sound", "Summit", "Olympic", "Larch", "Rainier", "Sitka",
]
PLACES = [
    "Ridge", "Crossing", "Landing", "Gardens", "Shores", "Park", "Grove", "Heights", "Walk", "Point",
    "Terrace", "Commons", "Bend", "Cove", "Trace", "Meadow", "Springs", "Harbor", "Isle", "Run",
]


def main() -> None:
    sample = json.loads(SAMPLE.read_text())
    seattle_sample = _relocate_sample(sample)
    demo, demo_programs = _demo()
    random_schools, random_programs = _random(len(sample) + len(demo))
    schools = demo + random_schools
    programs = demo_programs + random_programs
    moves = _place_on_streets(seattle_sample + schools, programs, {p["id"] for p in random_programs})
    OUT_SAMPLE.write_text(json.dumps(seattle_sample, indent=2))
    for school in schools:
        _add_admissions(school)
    # The relocated sample keeps the sample's own admissions fields.
    OUT_SCHOOLS.write_text(json.dumps(schools, indent=2))
    OUT_PROGRAMS.write_text(json.dumps(programs, indent=2))
    _websites(schools)
    print(f"sample moved to Seattle {len(seattle_sample)} + synthetic {len(schools)} = {len(seattle_sample) + len(schools)} schools")
    print(f"synthetic programs {len(programs)}")
    for kind, miles in moves.items():
        miles = sorted(miles)
        print(
            f"{kind} moved to a street: median {miles[len(miles) // 2]:.2f} mi, max {miles[-1]:.2f} mi, "
            f"{sum(m > 0.2 for m in miles)} of {len(miles)} more than 0.2 mi"
        )
    types = {kind: sum(s["osp"]["admission_type"] == [kind] for s in schools) for kind in ADMISSION_TYPES}
    filled = {
        key: sum(key in s["osp"] for s in schools)
        for key in ("application_deadline_date", "admissions_url", "application_requirements", "seats_by_grade", "applicants_last_year")
    }
    print(f"admission types: {types}")
    print(f"admissions fields filled (of {len(schools)}): {filled}")


def _relocate_sample(sample: list[dict]) -> list[dict]:
    """Copy GreatSchools' sample schools to Seattle.

    Location, id, district and address change; ratings, reviews, osp answers and
    missing fields stay exactly as the sample has them. Each school starts at a
    stable random Seattle point and is then moved onto a street like the rest.
    """
    moved = []
    for original in sample:
        school = json.loads(json.dumps(original))
        number = school["school_id"]
        rng = random.Random(f"relocate-{number}")
        lat = round(rng.uniform(RANDOM_BOX[0], RANDOM_BOX[1]), 6)
        lon = round(rng.uniform(RANDOM_BOX[2], RANDOM_BOX[3]), 6)
        school["id"] = f"School wa-{number}"
        school["city"] = "Seattle"
        school["city_untokenized"] = "seattle"
        school["county"] = "King County"
        school["state"] = "WA"
        school["zipcode"] = f"981{number % 100:02d}"
        school["latlon"] = f"{lat}, {lon}"
        if "school_district_city" in school:
            school["school_district_city"] = "Seattle"
        if school.get("entity_type") == "public":
            school["school_district_name"] = "Seattle Public Schools"
        else:
            school.pop("school_district_name", None)
        osp = school.get("osp") or {}
        for key, values in list(osp.items()):
            if isinstance(values, list):
                osp[key] = ["University of Washington" if v == "Florida State University" else v for v in values]
        school["_synthetic"] = True
        school["_relocated_from"] = "Sample Data/schools_sample.json (Florida)"
        moved.append(school)
    return moved


def _add_admissions(school: dict) -> None:
    """Add osp admissions fields to one generated school.

    Demo schools take hand-set values, or the plain default for their type.
    Random schools draw from their own stream, so no other field changes.
    """
    osp = school["osp"]
    entity = school["entity_type"]
    default = {"public": "zoned", "charter": "lottery", "private": "application"}[entity]
    if school.get("_demo_role") != "random":
        osp.update(DEMO_ADMISSIONS.get(school["name"], {"admission_type": [default]}))
        return
    rng = random.Random(f"admissions-{school['id']}")
    roll = rng.random()
    if entity == "public":
        kind = "choice" if roll < 0.15 else "zoned"
    elif entity == "charter":
        kind = "application" if roll < 0.15 else "lottery"
    else:
        kind = "application"
    osp["admission_type"] = [kind]
    slug = school["name"].casefold().replace(" ", "-")
    # Draw every roll for every school, so changing one rate doesn't reshuffle the rest.
    rolls = {key: rng.random() for key in ("url", "requirements", "deadline", "seats", "applicants")}
    deadline = rng.choice(DEADLINES)
    reported = rng.choice(REPORTED_ON)
    grade = ENTRY_GRADE[school["level_codes"][0]]
    open_seats = rng.choice([0, 0, 4, 8, 15])
    applicants = rng.choice([60, 120, 180, 240])
    seats = rng.choice([40, 60, 90])
    if rolls["url"] < URL_RATE:
        osp["admissions_url"] = [f"https://www.example.org/{slug}/admissions"]
    if kind == "zoned":
        # A zoned school takes the children who live in its zone; no deadline or lottery.
        return
    if rolls["requirements"] < REQUIREMENTS_RATE:
        osp["application_requirements"] = ["application", "interview"] if kind == "application" and entity == "private" else ["application"]
    if rolls["deadline"] < DEADLINE_RATE:
        osp["application_deadline_date"] = [deadline]
    if rolls["seats"] < SEATS_RATE:
        osp["seats_by_grade"] = [{"grade": grade, "open_seats": open_seats, "waitlist": open_seats == 0, "as_of": reported}]
    if rolls["applicants"] < APPLICANTS_RATE:
        osp["applicants_last_year"] = [{"grade": grade, "applicants": applicants, "seats": seats, "as_of": "2026-03-15"}]


def _miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    hav = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 3958.7613 * 2 * math.asin(math.sqrt(hav))


def _nearest(points: list[list], lat: float, lon: float, used: set[int]) -> int:
    """Index of the closest street point not already taken by another pin."""
    scale = math.cos(math.radians(lat))
    best, best_d2 = -1, float("inf")
    for index, (plat, plon, _) in enumerate(points):
        if index in used:
            continue
        d2 = (plat - lat) ** 2 + ((plon - lon) * scale) ** 2
        if d2 < best_d2:
            best, best_d2 = index, d2
    return best


def _offset(lat: float, lon: float, seed: str) -> tuple[float, float]:
    # Its own random stream, so the main generator's draws are untouched.
    rng = random.Random(seed)
    bearing = rng.uniform(0, 2 * math.pi)
    miles = rng.uniform(*PROGRAM_OFFSET_MILES)
    dlat = miles / 69.0 * math.cos(bearing)
    dlon = miles / (69.0 * math.cos(math.radians(lat))) * math.sin(bearing)
    return lat + dlat, lon + dlon


def _place_on_streets(schools: list[dict], programs: list[dict], offset_ids: set[str]) -> dict[str, list[float]]:
    """Move every generated pin onto a real street and give it that street's name.

    Schools go first, then programs. No two pins share a street point. Returns how
    far each pin moved, in miles, for the summary line.
    """
    metros = json.loads(STREETS.read_text())["metros"]
    used: dict[str, set[int]] = {city: set() for city in metros}
    moves: dict[str, list[float]] = {"schools": [], "programs": []}
    for kind, records in (("schools", schools), ("programs", programs)):
        for record in records:
            metro = metros[record["city"]]
            lat, lon = (float(x) for x in record["latlon"].split(","))
            if record["id"] in offset_ids:
                lat, lon = _offset(lat, lon, f"program-offset-{record['id']}")
            index = _nearest(metro["points"], lat, lon, used[record["city"]])
            used[record["city"]].add(index)
            plat, plon, street = metro["points"][index]
            moves[kind].append(_miles((lat, lon), (plat, plon)))
            record["latlon"] = f"{plat}, {plon}"
            number = record.get("school_id") or record.get("program_id")
            record["street"] = f"{100 + (number * 7919) % 9800} {metro['streets'][street]}"
    return moves


def _demo() -> tuple[list[dict], list[dict]]:
    schools = []
    schools.append(_school(1, "Cascade STEM Charter", "charter", ["m"], FULL_POINT, 0.004, stem=True, care="18:00", rating=9, role="full"))
    schools.append(_school(2, "Fremont STEM Middle", "public", ["m"], FULL_POINT, 0.008, stem=True, care="17:30", rating=8, role="full"))
    schools.append(_school(3, "Wallingford STEM Academy", "charter", ["m"], FULL_POINT, 0.012, stem=True, care="18:00", rating=8, role="full"))
    schools.append(_school(4, "Ravenna Bridge Middle", "public", ["m"], FULL_POINT, 0.016, stem=True, care="17:30", rating=7, role="full"))
    schools.append(
        _school(
            5,
            "Queen Anne Preparatory Middle",
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
            "Ballard Day Middle",
            "Phinney Day Middle",
            "Greenwood Day Middle",
            "Crown Hill Day Middle",
            "Loyal Heights Day Middle",
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
        "Northgate STEM Middle",
        "Haller Lake STEM Middle",
        "Lake City STEM Middle",
        "Pinehurst STEM Middle",
        "Victory Heights STEM Middle",
        "Meadowbrook STEM Middle",
        "Maple Leaf STEM Middle",
        "Olympic Hills STEM Middle",
    ]
    for offset, name in enumerate(leap_names, start=11):
        schools.append(
            _school(offset, name, "public", ["m"], LEAP_POINT, 0.004 * (offset - 10), stem=True, care=None, rating=6, role="leap")
        )
    schools.append(_school(19, "Arbor Heights STEM Middle", "public", ["m"], ASK_POINT, 0.0, stem=True, care=None, rating=5, role="ask"))
    schools.append(_school(20, "Rainier Beach STEM Middle", "charter", ["m"], STALE_POINT, 0.0, stem=True, care=None, rating=4, role="stale"))
    schools.append(
        _school(
            21,
            "Evergreen Hill Christian Middle",
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
        _program(1, "Northgate After School STEM Lab", LEAP_POINT, live=True, end="18:00"),
        _program(2, "Lake City Homework Help Club", (LEAP_POINT[0] + 0.01, LEAP_POINT[1] - 0.01), live=True, end="18:00"),
        _program(3, "Rainier Beach After School Club", STALE_POINT, live=False, end="17:30"),
    ]
    return schools, programs


def _random(already: int) -> tuple[list[dict], list[dict]]:
    rng = random.Random(7)
    need = TARGET - already
    schools = []
    programs = []
    city, county, zip_prefix = "Seattle", "King County", "981"
    for index in range(need):
        # Keep random Seattle pins south of the Northgate leap-program cluster.
        lat = RANDOM_BOX[0] + rng.random() * (RANDOM_BOX[1] - RANDOM_BOX[0])
        lon = RANDOM_BOX[2] + rng.random() * (RANDOM_BOX[3] - RANDOM_BOX[2])
        roll = rng.random()
        entity = "charter" if roll < 0.48 else "private" if roll < 0.80 else "public"
        levels = rng.choice([["e"], ["m"], ["h"], ["p", "e"], ["e", "m"], ["m", "h"]])
        stem = rng.random() < 0.28
        care = "17:30" if rng.random() < 0.35 else None
        if "m" in levels and stem and care:
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
        # Seattle packs the random schools far tighter than the old three-metro spread,
        # so programs are rarer here, and none sit near the stale-program demo school.
        # The draw stays in place, so no other random value moves.
        near_stale = _miles((lat, lon), STALE_POINT) < 3.5
        if rng.random() < PROGRAM_RATE and not near_stale:
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
    county: str = "King County",
    city: str = "Seattle",
    zip_prefix: str = "981",
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
        "id": f"School wa-{school_id}",
        "school_id": school_id,
        "name": name,
        "sortable_name": name.casefold(),
        "document_type": "School",
        "entity_type": entity,
        "level_codes": levels,
        "city": city,
        "city_untokenized": city.casefold().replace(" ", ""),
        "county": county,
        "state": "WA",
        "street": f"{100 + number} Synthetic Avenue",
        "zipcode": f"{zip_prefix}{number % 100:02d}",
        "latlon": f"{lat}, {lon}",
        "enrollment": 280 + number * 3,
        "created": "2026-02-01T12:00:00-08:00",
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


def _program(number: int, name: str, origin: tuple[float, float], live: bool, end: str, city: str = "Seattle") -> dict:
    program_id = 880000 + number
    if live:
        start, finish, status = "2026-11-01", "2027-05-20", "upcoming"
    else:
        start, finish, status = "2024-01-08", "2024-05-20", "past"
    return {
        "id": f"Program wa-{program_id}",
        "program_id": program_id,
        "name": name,
        "description": f"After school homework help until {end} on school days.",
        "program_type": "after_school",
        "city": city,
        "state": "WA",
        "geo_state": "WA",
        "county": "King County",
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
        if role == "full" and school["name"].startswith("Cascade"):
            facts.append({"path": "osp.after_school_until", "value": "16:00", "as_of": "2026-10-01"})
        if school["name"] == "Northgate STEM Middle":
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
