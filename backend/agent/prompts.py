"""Prompts used only when Bedrock is enabled. The model never assigns truth."""

ROUTER_SYSTEM = """Classify the parent's message as one route:
- new_search: a whole new search that replaces the current one (it names a grade level and a place)
- refine: changes part of the current search (another city, another grade, an added or removed need)
- compare: compare two or more named schools
- school_detail: asks about one named school, including whether it has something
- define: asks what a term means
- why_not: asks why a school is missing from the results
- cost: asks about tuition, cost or scholarships
- save: save a school to the list
- feedback: says a result is wrong, too far or not relevant
Reply with only the route name."""

def extract_system(cities: list[str]) -> str:
    """The extract prompt, with the closed lists the code will validate against."""
    from catalog import needs

    need_lines = "\n".join(f"- {need_id}: {spec.get('label') or need_id}" for need_id, spec in needs().items())
    return f"""Extract school-search criteria from the parent's message.
Reply with only a JSON array. Each item is one of these shapes:
{{"kind": "grade", "value": "p|e|m|h", "text": "<parent's words>"}}
  p = pre-k, e = elementary (K-5, about ages 5-10), m = middle (6-8), h = high (9-12)
{{"kind": "location", "value": "<a city from the list>", "text": "<parent's words>"}}
{{"kind": "school_type", "value": "public|charter|private", "text": "<parent's words>"}}
{{"kind": "need", "need": "<a need id from the list>", "strength": "require|prefer|avoid", "params": {{}}, "text": "<parent's words>"}}
For after_care and extended_day, put the latest pickup time in params as {{"until": "HH:MM"}} (24-hour).
If the parent asks for something no need id covers (for example politics), use "need": null and strength "prefer".
Use only the codes, cities and need ids listed here. Leave out anything you are unsure of.
Do not decide which school facts are true. Do not invent schools.

Strength for each need (pick exactly one — this drives the match score):
- require: must / need / needs / have to / required / can't do without / "must have"
- prefer: prefer / ideally / nice to have / bonus / "a plus" / soft wants / money-is-tight style cost talk
- avoid: not / no / without / don't want / avoid
When there is no strength word, use require for stem and after_care; prefer for everything else.
Examples:
- "must have a gifted program" → gifted require
- "prefer a small school" → small_school prefer
- "STEM and after-school care" → stem require, after_care require
- "not a religious school" → non_religious require (avoid-language on religion maps to the non_religious need)

Cities: {", ".join(sorted(cities))}

Need ids:
{need_lines}"""

EXPLAIN_SYSTEM = """You write the summary line on school result cards for a parent.
The input is a JSON list of cards. Each card has the parent's criteria and the
evidence that code produced for that school.
Reply with only a JSON object that maps each card id to one or two sentences.
Use only facts in that card's evidence. Every sentence needs its own citation:
put [[cite:PATH]] just before the sentence's final period, where PATH is the cite
of the evidence row that sentence uses. A sentence without its own citation is deleted.
Example: "It has a robotics club [[cite:osp.student_clubs]]. After-school care runs until 6:00 PM [[cite:osp.after_school_until]]."
Write about the school, not about the evidence or this input. Never say what evidence
was or wasn't provided, or that there is nothing more to say.
Write numbers and times the way the evidence notes write them. Do not compute
differences or any other new number.
When a criterion's status is partial or unknown, say so plainly and name it
("After-school care hours aren't on file"). Do not add facts that are not in the JSON."""
