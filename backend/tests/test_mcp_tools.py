"""AgentCore Gateway tools: schemas match the code, results cite fields, the handler routes by name."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import mcp_tools
from agent.gateway import _parse


def _context(tool: str) -> SimpleNamespace:
    return SimpleNamespace(client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": f"school-data___{tool}"}))


def test_every_schema_has_a_tool_with_matching_arguments():
    assert len(mcp_tools.TOOL_SCHEMAS) >= 3
    for schema in mcp_tools.TOOL_SCHEMAS:
        params = set(inspect.signature(mcp_tools.TOOLS[schema["name"]]).parameters)
        assert set(schema["inputSchema"]["properties"]) == params
        assert set(schema["inputSchema"]["required"]) <= params


def test_find_schools_filters_on_city_level_and_type():
    result = mcp_tools.find_schools("Jacksonville", level="middle", school_type="charter", limit=3)
    assert result["count"] >= 1 and len(result["schools"]) <= 3
    assert all(row["entity_type"] == "charter" and "m" in row["level_codes"] for row in result["schools"])


def test_school_facts_name_their_source_field():
    result = mcp_tools.get_school_facts("School fl-180003")
    fields = {fact["field"]: fact["value"] for fact in result["facts"]}
    assert fields["osp.after_school_until"] == "18:00"
    assert mcp_tools.get_school_facts("nope")["error"]


def test_cost_never_subtracts_an_award():
    result = mcp_tools.estimate_school_cost("School fl-180021")
    assert result["net"] is None and "You may qualify" in result["disclaimer"]
    assert all(line["official_url"] for line in result["lines"])


def test_define_term_matches_key_term_or_title_and_lists_terms_on_a_miss():
    assert mcp_tools.define_term("cte")["title"] == "Career and Technical Education"
    assert mcp_tools.define_term("Charter school")["cite"] == "glossary.charter"
    assert "CTE" in mcp_tools.define_term("zzz")["known_terms"]


def test_handler_routes_by_gateway_tool_name():
    assert mcp_tools.handler({"term": "ESA"}, _context("define_term"))["term"] == "ESA"
    assert "unknown tool" in mcp_tools.handler({}, _context("drop_tables"))["error"]
    assert "bad arguments" in mcp_tools.handler({"nope": 1}, _context("define_term"))["error"]


def test_parse_reads_json_and_sse():
    assert _parse('{"jsonrpc":"2.0","id":1,"result":{}}')["result"] == {}
    assert _parse('event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"a":1}}\n\n')["result"] == {"a": 1}
