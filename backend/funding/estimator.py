"""Private-school cost after likely scholarships. No award amount is promised."""

from __future__ import annotations

from catalog import funding_rules
from evidence.engine import get_path
from evidence.status import unwrap


def estimate_cost(school: dict) -> dict:
    entity = school.get("entity_type")
    rules = funding_rules()
    if entity in {"public", "charter"}:
        return {
            "school_id": school["id"],
            "school_name": school["name"],
            "entity_type": entity,
            "tuition": None,
            "net": None,
            "disclaimer": "This school is tuition-free in the data. No scholarship estimate is needed.",
            "lines": [
                {
                    "wording": f"{entity.title()} school, tuition-free.",
                    "cite": "entity_type",
                    "official_url": None,
                }
            ],
        }
    tuition = unwrap(get_path(school, "osp.tuition"))
    lines = []
    for rule in rules.values():
        if "private" not in (rule.get("applies_to") or []):
            continue
        lines.append(
            {
                "name": rule["name"],
                "wording": rule["wording"],
                "eligibility": " ".join(str(rule.get("eligibility") or "").split()),
                "official_url": rule["official_url"],
                "cite": rule["cite_path"],
            }
        )
    return {
        "school_id": school["id"],
        "school_name": school["name"],
        "entity_type": entity,
        "tuition": tuition,
        "net": None,
        "disclaimer": (
            "You may qualify. Award amounts are set by the scholarship funding organization, "
            "so this screen does not subtract a dollar amount from tuition."
        ),
        "lines": lines,
    }
