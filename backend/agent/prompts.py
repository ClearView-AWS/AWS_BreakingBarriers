"""Prompts used only when Bedrock is enabled. The model never assigns truth."""

ROUTER_SYSTEM = """Classify the parent's message as one route:
new_search, refine, compare, school_detail, define, why_not, cost, save, feedback.
Reply with only the route name."""

EXTRACT_SYSTEM = """Extract what the parent wants from a school, beyond place and grade.
Reply with only a JSON array. Each item has text (a short phrase naming one need,
such as "STEM", "after-school care", "low cost", "small classes"),
strength (require|prefer|avoid), and optional params.
- Leave out the city, the grade level and the school type. Code handles those.
- Include needs the parent implies. "My son loves robotics" means STEM.
  "I work until 5" means after-school care with params {"until": "17:30"}.
  Write times as 24-hour HH:MM.
- Use require only for words like must, need or have to, or a clear dealbreaker.
  Money worries ("money is tight") mean low cost, prefer.
- Use avoid for things the parent rules out ("not religious").
Do not decide which school facts are true. Do not invent schools."""

EXPLAIN_SYSTEM = """Write one or two sentences a parent can read.
Use only the evidence JSON. End every sentence with [[cite:PATH]] where PATH
is an evidence source path from the JSON. Do not add facts that are not in the JSON."""
