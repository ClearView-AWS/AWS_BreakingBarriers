"""Prompts used only when Bedrock is enabled. The model never assigns truth."""

ROUTER_SYSTEM = """Classify the parent's message as one route:
new_search, refine, compare, school_detail, define, why_not, cost, save, feedback.
Reply with only the route name."""

EXTRACT_SYSTEM = """Extract school-search criteria from the parent's message.
Reply with a JSON array. Each item has text, strength (require|prefer|avoid),
and optional params. Do not decide which school facts are true.
Do not invent schools. If a phrase is vague politics, set text to that phrase
and strength to prefer."""

EXPLAIN_SYSTEM = """Write one or two sentences a parent can read.
Use only the evidence JSON. End every sentence with [[cite:PATH]] where PATH
is an evidence source path from the JSON. Do not add facts that are not in the JSON."""
