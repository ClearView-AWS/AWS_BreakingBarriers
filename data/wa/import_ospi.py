"""Build school documents from public OSPI Washington Report Card CSVs.

Reads enrollment (school × grade) and optional graduation (school × cohort × group),
writes `schools.json` in this folder in the shape Guided Search already loads.

Run from the repo root:
  python data/wa/import_ospi.py

Raw CSVs stay local (large). Commit the generated `schools.json` for demos.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENROLLMENT = HERE / "Report_Card_Enrollment_2025-26_School_Year_-_Final_20261104.csv"
GRADUATION = HERE / "Report_Card_Graduation_2024-25_20261104.csv"
OUT = HERE / "schools.json"

# District name → city parents type. Anything else strips "School District…".
DISTRICT_CITY = {
    "Seattle School District No. 1": "Seattle",
    "Tacoma School District": "Tacoma",
    "Spokane School District": "Spokane",
    "Lake Washington School District": "Redmond",
    "Kent School District": "Kent",
    "Vancouver School District": "Vancouver",
    "Federal Way School District": "Federal Way",
    "Evergreen School District (Clark)": "Vancouver",
    "Northshore School District": "Bothell",
    "Puyallup School District": "Puyallup",
    "Edmonds School District": "Edmonds",
    "Highline School District": "Burien",
    "Bethel School District": "Spanaway",
    "Central Valley School District": "Spokane Valley",
    "Kennewick School District": "Kennewick",
    "Bellevue School District": "Bellevue",
    "Renton School District": "Renton",
    "Everett School District": "Everett",
    "Yakima School District": "Yakima",
    "Olympia School District": "Olympia",
    "Bellingham School District": "Bellingham",
    "Issaquah School District": "Issaquah",
    "Mukilteo School District": "Mukilteo",
    "Auburn School District": "Auburn",
    "Clover Park School District": "Lakewood",
    "Richland School District": "Richland",
    "Pasco School District": "Pasco",
}

TYPE_MAP = {
    "P": "public",
    "A": "public",  # alternative
    "R": "public",  # re-engagement
    "S": "public",
    "T": "public",  # tribal affiliated
    "Y": "public",
    "V": "public",
    "C": "public",
    "J": "public",
    "I": "public",
    "Q": "public",
    "Z": "public",
    "N": "private",
    "X": "private",
}

GRADE_TO_LEVEL = {
    "Pre-Kindergarten": "e",
    "Transition to Kindergarten": "e",
    "Half-Day Kindergarten": "e",
    "Kindergarten": "e",
    "1st Grade": "e",
    "2nd Grade": "e",
    "3rd Grade": "e",
    "4th Grade": "e",
    "5th Grade": "e",
    "6th Grade": "m",
    "7th Grade": "m",
    "8th Grade": "m",
    "9th Grade": "h",
    "10th Grade": "h",
    "11th Grade": "h",
    "12th Grade": "h",
}

_DISTRICT_SUFFIX = re.compile(
    r"\s+(School District(?:\s+No\.\s*\d+)?|Public Schools|Schools)\s*$",
    re.I,
)


def _int(value: object) -> int:
    text = str(value or "").replace(",", "").strip()
    if not text or text.upper() in {"N/A", "NULL", "SUPPRESSED"}:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _float(value: object) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text or text.upper() in {"N/A", "NULL"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def city_from_district(district: str) -> str:
    if district in DISTRICT_CITY:
        return DISTRICT_CITY[district]
    cleaned = _DISTRICT_SUFFIX.sub("", district or "").strip()
    return cleaned or "Washington"


def level_codes(grades: set[str]) -> list[str]:
    codes = {GRADE_TO_LEVEL[g] for g in grades if g in GRADE_TO_LEVEL}
    order = ["e", "m", "h"]
    return [c for c in order if c in codes]


def load_graduation(path: Path) -> dict[str, dict]:
    """SchoolOrganizationId → four-year All Students graduation stats."""
    if not path.exists():
        return {}
    out: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        for row in csv.DictReader(handle):
            if row.get("OrganizationLevel") != "School":
                continue
            if row.get("Cohort") != "Four Year":
                continue
            if row.get("StudentGroup") != "All Students":
                continue
            sid = (row.get("SchoolOrganizationId") or row.get("SchoolOrganizationID") or "").strip()
            if not sid:
                continue
            rate = _float(row.get("GraduationRate"))
            out[sid] = {
                "graduation_rate": rate,
                "graduates": _int(row.get("Graduate")),
                "final_cohort": _int(row.get("FinalCohort")),
                "school_year": row.get("SchoolYear"),
            }
    return out


def load_enrollment(path: Path) -> dict[str, dict]:
    if not path.exists():
        raise SystemExit(f"Missing enrollment CSV: {path}")
    by_school: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        for row in csv.DictReader(handle):
            if row.get("OrganizationLevel") != "School":
                continue
            sid = (row.get("SchoolOrganizationID") or row.get("SchoolOrganizationId") or "").strip()
            if not sid:
                continue
            grade = (row.get("GradeLevel") or "").strip()
            rec = by_school.setdefault(
                sid,
                {
                    "SchoolOrganizationID": sid,
                    "SchoolCode": row.get("SchoolCode") or "",
                    "SchoolName": row.get("SchoolName") or "",
                    "DistrictName": row.get("DistrictName") or "",
                    "County": row.get("County") or "",
                    "CurrentSchoolType": row.get("CurrentSchoolType") or "P",
                    "SchoolYear": row.get("SchoolYear") or "",
                    "grades": set(),
                    "has_all_grades": False,
                    "all_students": 0,
                    "ell": 0,
                    "low_income": 0,
                    "highly_capable": 0,
                    "swd": 0,
                },
            )
            if grade and grade != "All Grades":
                rec["grades"].add(grade)
            n = _int(row.get("All Students"))
            if grade == "All Grades":
                rec["has_all_grades"] = True
                rec["all_students"] = n
                rec["ell"] = _int(row.get("English Language Learners"))
                rec["low_income"] = _int(row.get("Low Income"))
                rec["highly_capable"] = _int(row.get("Highly Capable"))
                rec["swd"] = _int(row.get("Students with Disabilities"))
            elif not rec["has_all_grades"]:
                rec["all_students"] += n
    return by_school


def rating_from_grad(rate: float | None) -> int | None:
    """Map 0–1 graduation rate onto the 1–10 summary_rating scale used by needs.yaml."""
    if rate is None:
        return None
    return max(1, min(10, int(round(rate * 10))))


def to_document(rec: dict, grad: dict | None) -> dict | None:
    name = (rec.get("SchoolName") or "").strip()
    if not name:
        return None
    enrollment = int(rec.get("all_students") or 0)
    if enrollment <= 0:
        return None
    sid = rec["SchoolOrganizationID"]
    city = city_from_district(rec.get("DistrictName") or "")
    levels = level_codes(rec.get("grades") or set())
    if not levels:
        levels = ["e", "m", "h"]
    entity = TYPE_MAP.get(rec.get("CurrentSchoolType") or "P", "public")
    ell_n = int(rec.get("ell") or 0)
    gifted_n = int(rec.get("highly_capable") or 0)
    low_income_n = int(rec.get("low_income") or 0)
    swd_n = int(rec.get("swd") or 0)

    doc: dict = {
        "id": f"School wa-{sid}",
        "school_id": int(sid) if str(sid).isdigit() else sid,
        "document_type": "School",
        "entity_type": entity,
        "level_codes": levels,
        "name": name,
        "sortable_name": name.casefold(),
        "city": city,
        "city_untokenized": city.casefold().replace(" ", ""),
        "county": rec.get("County") or "",
        "state": "WA",
        "street": "",
        "zipcode": "",
        "enrollment": enrollment,
        "ell": ell_n > 0,
        "gifted_talented": gifted_n > 0,
        "osp": {
            "coed": ["coed"],
            "boarding": ["day"],
            "admission_type": ["zoned"],
            "wa_report_card": {
                "school_code": rec.get("SchoolCode"),
                "district": rec.get("DistrictName"),
                "school_year": rec.get("SchoolYear"),
                "school_type_code": rec.get("CurrentSchoolType"),
                "ell_students": ell_n,
                "low_income_students": low_income_n,
                "highly_capable_students": gifted_n,
                "students_with_disabilities": swd_n,
            },
        },
        "_source": "ospi_report_card",
        "_synthetic": False,
    }
    if grad and grad.get("graduation_rate") is not None:
        rate = grad["graduation_rate"]
        doc["osp"]["wa_report_card"]["graduation_rate_4yr"] = rate
        doc["osp"]["wa_report_card"]["graduates_4yr"] = grad.get("graduates")
        rating = rating_from_grad(rate)
        if rating is not None and "h" in levels:
            doc["summary_rating"] = rating
            doc["test_scores_rating"] = rating
    return doc


def main() -> int:
    enrollment = load_enrollment(ENROLLMENT)
    graduation = load_graduation(GRADUATION)
    schools: list[dict] = []
    for sid, rec in sorted(enrollment.items(), key=lambda item: item[1].get("SchoolName") or ""):
        doc = to_document(rec, graduation.get(sid))
        if doc:
            schools.append(doc)
    OUT.write_text(json.dumps(schools, indent=2) + "\n")
    cities = sorted({s["city"] for s in schools})
    print(f"Wrote {len(schools)} schools → {OUT.relative_to(HERE.parent.parent)}")
    print(f"Cities (sample): {', '.join(cities[:12])}{'…' if len(cities) > 12 else ''}")
    print(f"With 4yr graduation rating: {sum(1 for s in schools if s.get('summary_rating'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
