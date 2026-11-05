"""School tools served over MCP by the AgentCore Gateway (Lambda target).

Each tool reads the same corpus, funding rules, and glossary the app uses, and every
fact it returns carries the field path it came from.
"""

from __future__ import annotations

import json
from typing import Any

from catalog import glossary
from evidence.engine import get_path
from evidence.status import unwrap
from funding.estimator import estimate_cost
from runtime_config import CONFIG_DIR
from search.corpus import load_schools

LEVELS = {"elementary": "e", "middle": "m", "high": "h", "preschool": "p"}

FACT_PATHS = [
    "entity_type",
    "level_codes",
    "street",
    "city",
    "state",
    "zipcode",
    "enrollment",
    "summary_rating",
    "test_scores_rating",
    "student_progress_rating",
    "student_teacher_ratio",
    "osp.school_sub_type",
    "osp.after_school_until",
    "osp.student_clubs",
    "osp.admission_type",
    "osp.application_deadline_date",
    "osp.tuition",
]

# Tool schemas registered on the gateway target. infra/lib/gateway-stack.ts reads the
# same file, so the gateway and this code cannot drift.
TOOL_SCHEMAS: list[dict[str, Any]] = json.loads((CONFIG_DIR / "mcp_tools.json").read_text())


def _find(school_id: str) -> dict | None:
    for school in load_schools():
        if school["id"] == school_id or str(school.get("school_id")) == school_id:
            return school
    return None


def find_schools(city: str, level: str | None = None, school_type: str | None = None, limit: int = 5) -> dict:
    city_key = city.casefold().replace(" ", "")
    level_code = LEVELS.get((level or "").casefold(), (level or "").casefold() or None)
    kind = (school_type or "").casefold() or None
    limit = max(1, min(int(limit or 5), 20))
    rows = [
        school
        for school in load_schools()
        if school.get("city_untokenized") == city_key
        and (not level_code or level_code in (school.get("level_codes") or []))
        and (not kind or school.get("entity_type") == kind)
    ]
    rows.sort(key=lambda school: -(school.get("summary_rating") or 0))
    return {
        "count": len(rows),
        "schools": [
            {
                "school_id": school["id"],
                "name": school["name"],
                "entity_type": school.get("entity_type"),
                "level_codes": school.get("level_codes"),
                "summary_rating": school.get("summary_rating"),
            }
            for school in rows[:limit]
        ],
    }


def get_school_facts(school_id: str) -> dict:
    school = _find(school_id)
    if not school:
        return {"error": f"unknown school: {school_id}"}
    facts = []
    for path in FACT_PATHS:
        value = unwrap(get_path(school, path))
        if value not in (None, "", []):
            facts.append({"field": path, "value": value})
    return {"school_id": school["id"], "name": school["name"], "facts": facts}


def estimate_school_cost(school_id: str) -> dict:
    school = _find(school_id)
    if not school:
        return {"error": f"unknown school: {school_id}"}
    return estimate_cost(school)


def define_term(term: str) -> dict:
    key = term.casefold().strip()
    for entry_id, entry in glossary().items():
        names = {entry_id.casefold(), str(entry.get("term", "")).casefold(), str(entry.get("title", "")).casefold()}
        if key in names:
            return {
                "term": entry.get("term"),
                "title": entry.get("title"),
                "text": " ".join(str(entry.get("text") or "").split()),
                "cite": entry.get("cite_path"),
            }
    return {"error": f"no definition for {term!r}", "known_terms": sorted(e.get("term") for e in glossary().values())}


TOOLS = {
    "find_schools": find_schools,
    "get_school_facts": get_school_facts,
    "estimate_school_cost": estimate_school_cost,
    "define_term": define_term,
}


def handler(event: dict, context: Any) -> dict:
    """Lambda entry point. The gateway sends the tool arguments as the event and the
    tool name as `<target>___<tool>` in the client context."""
    full_name = context.client_context.custom["bedrockAgentCoreToolName"]
    name = full_name.split("___", 1)[-1]
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"unknown tool: {name}"}
    try:
        return tool(**(event or {}))
    except TypeError as exc:
        return {"error": f"bad arguments for {name}: {exc}"}
