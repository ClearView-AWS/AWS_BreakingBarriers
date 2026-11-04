"""OpenSearch DSL from needs and criteria.

Hard filters are only location, grade level, and school type.
Everything else is a should-clause boost, so a missing field cannot drop a school.
"""

from __future__ import annotations

from typing import Any

from catalog import needs


def build_query(
    criteria: list,
    query_text: str = "",
    size: int = 100,
    *,
    vector: list[float] | None = None,
) -> dict[str, Any]:
    filters: list[dict] = []
    should: list[dict] = []
    for criterion in criteria:
        kind = getattr(criterion, "kind", None) or criterion.get("kind")
        value = getattr(criterion, "value", None) if not isinstance(criterion, dict) else criterion.get("value")
        need = getattr(criterion, "need", None) if not isinstance(criterion, dict) else criterion.get("need")
        if kind == "location" and value:
            filters.append({"term": {"city_untokenized": str(value).casefold().replace(" ", "")}})
        elif kind == "grade" and value:
            filters.append({"term": {"level_codes": value}})
        elif kind == "school_type" and value:
            filters.append({"term": {"entity_type": value}})
        elif kind == "need" and need and need in needs():
            for field, boost in (needs()[need].get("search_boost") or {}).items():
                clause = _boost_clause(field, boost)
                if clause:
                    should.append(clause)
    if query_text.strip():
        should.append(
            {
                "multi_match": {
                    "query": query_text,
                    "fields": ["search_text^2", "name^3"],
                    "type": "best_fields",
                }
            }
        )
        if vector:
            should.append(
                {
                    "knn": {
                        "embedding": {
                            "vector": vector,
                            "k": size,
                        }
                    }
                }
            )
    query: dict[str, Any] = {"bool": {}}
    if filters:
        query["bool"]["filter"] = filters
    if should:
        query["bool"]["should"] = should
        query["bool"]["minimum_should_match"] = 0
    else:
        query = {"match_all": {}}
    return {"size": size, "query": query}


def _boost_clause(field: str, boost: dict) -> dict | None:
    if not isinstance(boost, dict):
        return None
    if "gte" in boost:
        return {"range": {field: {"gte": boost["gte"], "boost": 2}}}
    if "lte" in boost:
        return {"range": {field: {"lte": boost["lte"], "boost": 2}}}
    if "terms" in boost:
        return {"terms": {field: boost["terms"], "boost": 2}}
    if boost.get("exists"):
        return {"exists": {"field": field, "boost": 2}}
    if "eq" in boost:
        return {"term": {field: {"value": boost["eq"], "boost": 2}}}
    return None


def hard_filter_fields(query: dict) -> list[str]:
    filters = query.get("query", {}).get("bool", {}).get("filter", [])
    names = []
    for clause in filters:
        term = clause.get("term") or {}
        names.extend(term.keys())
    return names
