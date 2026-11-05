"""Florida scholarship lines show only on Florida schools, never on Washington cards."""

from __future__ import annotations

from datetime import date

from agent.citations import allowed_citations, validate_text
from catalog import funding_rules, funding_rules_for
from contracts import Criterion
from evidence.engine import evaluate_criterion
from funding.estimator import estimate_cost
from school_state import school_state
from search.corpus import load_schools

TODAY = date(2026, 11, 4)
FL_CITES = {rule["cite_path"] for rule in funding_rules().values()}
LOW_COST = Criterion(id="c1", text="low cost", need="low_cost", strength="prefer", kind="need")


def _private(state: str | None, school_id: str = "School test", tuition: int | None = 12000) -> dict:
    school = {"id": school_id, "name": "Test Academy", "entity_type": "private",
              "created": "2026-02-01T12:00:00-08:00", "osp": {}}
    if state:
        school["state"] = state
    if tuition is not None:
        school["osp"]["tuition"] = tuition
    return school


def test_every_florida_rule_is_gated_to_florida():
    assert all(rule.get("states") == ["FL"] for rule in funding_rules().values())
    assert set(funding_rules_for("FL")) == set(funding_rules())
    assert funding_rules_for("WA") == {}


def test_state_is_inferred_for_wa_rows_without_a_state_field():
    assert school_state({"id": "School wa-123"}) == "WA"
    assert school_state({"id": "x", "osp": {"wa_report_card": {}}}) == "WA"
    assert school_state({"id": "x", "state": "fl"}) == "FL"


def test_florida_private_school_keeps_its_scholarship_lines():
    cost = estimate_cost(_private("FL"))
    assert {line["cite"] for line in cost["lines"]} == FL_CITES
    assert all("fldoe.org" in line["official_url"] for line in cost["lines"])


def test_wa_private_school_gets_no_florida_lines():
    for school in (_private("WA"), _private(None, school_id="School wa-999")):
        cost = estimate_cost(school)
        assert cost["lines"] == []
        assert cost["tuition"] == 12000
        assert cost["net"] is None
        assert "Florida" not in str(cost)
        assert "financial aid" in cost["disclaimer"]


def test_wa_public_cost_view_has_no_scholarship_copy():
    seattle = next(s for s in load_schools() if s.get("city") == "Seattle" and s.get("state") == "WA")
    cost = estimate_cost(seattle)
    assert all(line["official_url"] is None for line in cost["lines"])
    assert "Florida" not in str(cost)


def test_low_cost_evidence_for_wa_private_cites_tuition_not_florida():
    record = evaluate_criterion(_private("WA"), LOW_COST, today=TODAY)
    assert record.status == "partial"
    assert record.source.path == "osp.tuition"
    assert "Family Empowerment" not in record.note
    assert not any(f"[[cite:{path}]]" in record.note for path in FL_CITES)

    missing = evaluate_criterion(_private("WA", tuition=None), LOW_COST, today=TODAY)
    assert missing.status == "unknown"
    assert missing.missing_paths == ["osp.tuition"]


def test_low_cost_evidence_for_fl_private_still_names_the_scholarship():
    record = evaluate_criterion(_private("FL"), LOW_COST, today=TODAY)
    assert record.status == "partial"
    assert record.source.type == "funding_rule"
    assert "Family Empowerment Scholarship" in record.note


def test_wa_answers_cannot_cite_a_florida_scholarship():
    school = _private("WA")
    record = evaluate_criterion(school, LOW_COST, today=TODAY)
    allowed = allowed_citations([record], school)
    assert not (allowed & FL_CITES)
    text = "You may qualify for a scholarship [[cite:funding.fes_eo]]."
    assert "fes_eo" not in validate_text(text, allowed)
    assert FL_CITES <= allowed_citations([], _private("FL"))
