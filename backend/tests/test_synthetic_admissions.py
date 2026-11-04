"""Shape of the admissions fields the generator adds to synthetic schools."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHOOLS = json.loads((ROOT / "data" / "synthetic" / "schools.json").read_text())
SAMPLE = json.loads((ROOT / "Sample Data" / "schools_sample.json").read_text())
BY_NAME = {school["name"]: school for school in SCHOOLS}
TYPES = {"zoned", "choice", "lottery", "application"}


def _deadline(school: dict) -> date | None:
    value = (school["osp"].get("application_deadline_date") or [None])[0]
    return datetime.strptime(value, "%m/%d/%Y").date() if value else None


def test_every_generated_school_has_one_admission_type():
    for school in SCHOOLS:
        assert school["_synthetic"] is True
        kinds = school["osp"]["admission_type"]
        assert len(kinds) == 1 and kinds[0] in TYPES, school["id"]


def test_zoned_schools_have_no_application_data():
    for school in SCHOOLS:
        if school["osp"]["admission_type"] == ["zoned"]:
            for key in ("application_deadline_date", "application_requirements", "seats_by_grade", "applicants_last_year"):
                assert key not in school["osp"], (school["id"], key)


def test_dates_and_counts_are_well_formed():
    for school in SCHOOLS:
        _deadline(school)  # raises if not M/D/YYYY, the sample's format
        for row in school["osp"].get("seats_by_grade") or []:
            date.fromisoformat(row["as_of"])
            assert row["open_seats"] >= 0 and row["waitlist"] == (row["open_seats"] == 0)
        for row in school["osp"].get("applicants_last_year") or []:
            date.fromisoformat(row["as_of"])
            assert row["applicants"] > 0 and row["seats"] > 0


def test_demo_schools_cover_each_getting_in_case():
    arbor_heights = BY_NAME["Arbor Heights STEM Middle"]["osp"]
    assert arbor_heights["admission_type"] == ["lottery"]
    assert _deadline(BY_NAME["Arbor Heights STEM Middle"]) == date(2027, 1, 15)
    assert arbor_heights["applicants_last_year"][0] == {"grade": "6", "applicants": 210, "seats": 90, "as_of": "2026-03-15"}
    assert _deadline(BY_NAME["Queen Anne Preparatory Middle"]) == date(2027, 2, 1)
    assert BY_NAME["Cascade STEM Charter"]["osp"]["seats_by_grade"][0]["open_seats"] > 0
    assert _deadline(BY_NAME["Wallingford STEM Academy"]) == date(2026, 10, 1)
    assert BY_NAME["Rainier Beach STEM Middle"]["osp"]["seats_by_grade"][0]["waitlist"] is True
    assert _deadline(BY_NAME["Evergreen Hill Christian Middle"]) == date(2025, 1, 15)


def test_sample_schools_are_left_alone():
    for school in SAMPLE:
        assert "admission_type" not in (school.get("osp") or {}), school["id"]
