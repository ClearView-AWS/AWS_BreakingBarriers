"""A conversation on top of the search pipeline.

`chat_turn` wraps `pipeline.turn` so the parent can keep talking:

- Every message and tap is kept in the session's history, so the chat can show it.
- References resolve against what the parent is looking at: a school's name, an
  ordinal ("the second one", "#3"), a pronoun ("it", "that school") or the whole
  list ("these", "any of them").
- A follow-up question about schools ("does the second one have after-school care?",
  "can my son get into Beauclerc?") is answered in the chat, in code, from that
  school's evidence. Every sentence cites its source and goes through the citation
  validator, as for cards. Results stay where they are.
- Everything else (new criteria, a new city, compare, why-not, define, cost, save)
  goes to `pipeline.turn` unchanged, with ordinals and pronouns turned into
  school IDs first.
- A turn that leaves the results as they were doesn't post the same list again.

Reading the message: with Bedrock on and schools on screen, the fast model returns
a small plan (intent, which schools by their on-screen ref, topic, need). Code checks
every field against what is shown and the catalog; anything off falls back to the
rules below. The model never answers: every fact still comes from code, with a citation.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from agent.citations import allowed_citations, strip_cites, validate_text
from agent.localize import localize_response
from agent.translate import to_english
from catalog import needs
from contracts import Criterion, EngineStep, EvidenceRecord
from enrollment.access import getting_in
from evidence.engine import evaluate_criterion
from mapping.mapper import _phrase_in, map_phrase, mapping_is_ambiguous, normalize
from pipeline import _find_by_name, _overlays_for, _session, _stamp_distances, turn
from search.corpus import known_cities, load_programs, load_schools

log = logging.getLogger(__name__)

HISTORY_LIMIT = 40
MAX_RESULTS_ANSWERED = 8

_QUESTION_START = re.compile(
    r"^(does|do|is|are|can|could|will|would|which|what|when|where|how|has|have|any|am|should)\b"
)
_SEARCH_WORDS = re.compile(
    # Plural levels only: "does Beauclerc middle school have a bus?" is still about Beauclerc.
    r"\b(show me|find|search|look for|looking for|i need|we need|i want|we want|instead|also need|"
    r"elementary schools|middle schools|high schools|pre k)\b"
)
_ACCESS_WORDS = re.compile(
    r"\b(get in|get into|getting in|apply|application|applications|deadline|deadlines|lottery|enroll|enrol|"
    r"enrollment|admission|admissions|admit|zoned|zone|seats?|waitlist|wait list|accepted|eligible|"
    r"eligibility|chances?|odds|spot)\b"
)
_ODDS_WORDS = re.compile(r"\b(chances?|odds|likely|will (we|he|she|they|my \w+) get|get a spot)\b")
_DISTANCE_WORDS = re.compile(r"\b(how far|distance|how close|miles away|commute)\b")
# "Is it public or private?" Magnet is left out: it is a need with its own evidence.
_TYPE_WORDS = re.compile(r"\b(public|private|charter|kind of school|type of school)\b")
_RESULTS_SCOPE = re.compile(
    r"\b(these|those|any of them|all of them|of them|which ones|which of|each of|the results|they|them|their)\b"
)
_SINGULAR = re.compile(r"\b(it|its|it s|this school|that school|this one|that one|the school)\b")
_ORDINAL_WORDS = {
    "first": 1, "1st": 1, "top": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
    "fifth": 5, "5th": 5, "sixth": 6, "6th": 6, "seventh": 7, "7th": 7, "eighth": 8, "8th": 8,
}
_ORDINAL = re.compile(r"\b(first|1st|top|second|2nd|third|3rd|fourth|4th|fifth|5th|sixth|6th|seventh|7th|eighth|8th|last)\s+(one|school|result|choice|pick)\b")
_NUMBERED = re.compile(r"(?:#|\bnumber\s|\bno\s)(\d)\b")
_FIRST_N = re.compile(r"\b(?:first|top)\s+(two|three|2|3)\b")
_HASH_NUMBER = re.compile(r"#\s*(\d)\b")


def _normalized(message: str) -> str:
    """normalize() drops "#", so "does #2 have a bus?" becomes "does number 2 …" first."""
    return normalize(_HASH_NUMBER.sub(r"number \1", message))
# Words that appear in many school names, so they can't identify one school on their own.
_GENERIC = {
    "school", "schools", "academy", "middle", "elementary", "high", "charter", "stem", "day", "preparatory",
    "prep", "institute", "the", "of", "and", "christian", "public", "senior", "junior", "k", "8", "center",
}
# Follow-up phrasings that the needs catalog doesn't list word for word.
_NEED_ALIASES = {
    "after school": "after_care",
    "aftercare": "after_care",
    "buses": "transportation",
    "tuition free": "low_cost",
    "free": "low_cost",
    "class sizes": "small_classes",
    # "Is it religious?" asks the same thing as the non-religious need, from the other side.
    "religious": "non_religious",
    "religion": "non_religious",
    "faith based": "non_religious",
}
_FREE = re.compile(r"\b(tuition free|free)\b")
_DEFINE = re.compile(r"\bwhat is\b|\bwhat s\b|\bdefine\b|\bmeaning of\b")
_WHY_NOT = re.compile(r"\bwhy isn t\b|\bwhy isnt\b|\bwhy not\b|\bhow come\b")
# Routes `pipeline.turn` takes school_ids for. Patterns mirror agent/router.py.
_ID_ROUTES = [
    ("compare", re.compile(r"\bcompare\b|\bversus\b|\bvs\b|\bside by side\b")),
    ("cost", re.compile(r"\bscholarship\b|\btuition\b|\bhow much\b|\bcost\b")),
    ("save", re.compile(r"\bsave\b|\bshortlist\b|\badd to (my )?list\b")),
    ("school_detail", re.compile(r"\btell me (more )?about\b|\bdetails on\b|\bprofile\b|\bmore about\b")),
]
_TAP_TEXT = {
    "save": "You saved {names}.",
    "compare": "You compared {names}.",
    "school_detail": "You opened {names}.",
    "cost": "You asked about cost at {names}.",
}


# --- entry point -------------------------------------------------------------

def chat_turn(state: dict, payload: dict) -> dict:
    """One conversational turn. Returns the turn's response plus `history`."""
    session = _session(state, payload.get("session_id"))
    payload = {**payload, "session_id": session["id"]}
    history = session.setdefault("history", [])
    focus = session.setdefault("focus", {"results": [], "all": [], "school": None})
    written = (payload.get("message") or "").strip()
    schools = load_schools()
    by_id = {school["id"]: school for school in schools}

    tap = None
    if written:
        # The chat keeps the parent's own words; everything below reads the English.
        _remember(history, "parent", "message", written)
    else:
        tap = _tap_text(payload, by_id)
        if tap:
            _remember(history, "parent", "event", tap)

    reading = to_english(written) if written else None
    message = reading.text.strip() if reading else ""
    if reading and reading.language:
        session["language"] = reading.language
    if reading:
        payload = {**payload, "message": message, "_translated": True, "_language": reading.language}

    plan, step = _interpret(session, message, schools, by_id) if message and not payload.get("action") else (None, None)
    if plan is not None and plan.intent == "ask_about":
        response = _answer(state, session, message, plan, schools, by_id)
    else:
        if plan is not None and plan.intent:
            payload = {**payload, **plan.pipeline_payload}
        response = turn(state, payload).model_dump()
    _record_route(response, plan, step)
    if reading and reading.error:
        engine = response.setdefault("engine", {"route": None, "extract": None, "explain": None, "errors": []})
        engine.setdefault("errors", []).append(reading.error)
    # The reply follows the language of the parent's latest typed message; taps keep it.
    language = session.get("language")
    response["language"] = language
    response["read_from"] = reading.language if reading and reading.language not in (None, "en") else None

    _fold_unchanged(response, focus, payload, message)
    _update_focus(focus, response)
    reply = _reply_text(response, by_id)
    if reply:
        _remember(history, "agent", "message", reply, route=response.get("route"), school_ids=response.get("_school_ids") or [])
    response.pop("_school_ids", None)
    response["history"] = history[-HISTORY_LIMIT:]
    # This turn's tap line, so the chat can show it in the parent's language.
    response["tap"] = tap
    # Last: translate what the parent reads. The stored history stays English.
    return localize_response(response, language)


# --- history -----------------------------------------------------------------

def _remember(history: list, role: str, kind: str, text: str, route: str | None = None, school_ids: list | None = None) -> None:
    history.append({"role": role, "kind": kind, "text": text, "route": route, "school_ids": school_ids or []})
    del history[:-HISTORY_LIMIT]


def _names(ids: list[str], by_id: dict) -> str:
    names = [by_id[sid]["name"] for sid in ids if sid in by_id]
    return " and ".join(names) if len(names) <= 2 else ", ".join(names[:-1]) + f" and {names[-1]}"


def _tap_text(payload: dict, by_id: dict) -> str | None:
    """A short line for a tap, so the chat history stays readable."""
    action = payload.get("action")
    ids = list(payload.get("school_ids") or [])
    zoned = payload.get("zoned") or {}
    feedback = payload.get("feedback") or {}
    if zoned.get("school_id") in by_id:
        name = by_id[zoned["school_id"]]["name"]
        return f"You said {name} is your zoned school." if zoned.get("value", True) else f"You said {name} is not your zoned school."
    if feedback.get("school_id") in by_id:
        name = by_id[feedback["school_id"]]["name"]
        if feedback.get("vote") == "up":
            return f"You gave {name} a thumbs up."
        reason = str(feedback.get("reason") or "").replace("_", " ")
        return f"You gave {name} a thumbs down" + (f" ({reason})." if reason else ".")
    if action == "ask_school" and ids and ids[0] in by_id:
        label = (needs().get(payload.get("need") or "") or {}).get("label") or "that"
        return f"You asked {by_id[ids[0]]['name']} about {label.lower()}."
    if action in _TAP_TEXT and ids:
        return _TAP_TEXT[action].format(names=_names(ids, by_id))
    if payload.get("answer"):
        return "You answered the question."
    if payload.get("criteria") is not None:
        return "You edited the search."
    return None


def _reply_text(response: dict, by_id: dict) -> str:
    """What the agent said this turn, for the history."""
    texts = []
    for block in response.get("blocks") or []:
        payload = block.get("payload") or {}
        if block.get("type") == "message":
            # An answer can be only a prompt ("…isn't on file yet. I can ask the school."),
            # and it still has to show up in the chat.
            texts.extend(str(payload[key]) for key in ("text", "prompt") if payload.get(key))
        elif block.get("type") == "question" and payload.get("text"):
            texts.append(str(payload["text"]))
        elif block.get("type") == "school_detail":
            school = payload.get("school") or {}
            texts.append(f"Here is {school.get('name', 'the school')}.")
        elif block.get("type") in {"why_not", "definition"} and payload.get("text"):
            texts.append(str(payload["text"]))
    return " ".join(texts)


def _fingerprint(results: dict) -> str:
    """What the parent would see change on the cards. Summaries are left out: a model may reword them."""
    rows = [
        [
            group,
            card.get("id"),
            card.get("match"),
            card.get("verified"),
            [[row.get("criterion_id"), row.get("status"), str(row.get("value"))] for row in card.get("evidence") or []],
            (card.get("access") or {}).get("label"),
            (card.get("access") or {}).get("line"),
        ]
        for group in ("schools", "gaps", "missed")
        for card in results.get(group) or []
    ]
    return json.dumps(rows, default=str)


def _fold_unchanged(response: dict, focus: dict, payload: dict, message: str) -> None:
    """Don't post the same list twice. A turn that leaves the results as they were says so in one line."""
    results = next((b["payload"] for b in response.get("blocks") or [] if b.get("type") == "results"), None)
    if results is None:
        return
    mark, before = _fingerprint(results), focus.get("mark")
    focus["mark"] = mark
    if mark != before or response.get("route") == "new_search":
        return
    response["blocks"] = [b for b in response["blocks"] if b.get("type") not in {"results", "evidence_grid"}]
    response["unchanged"] = True
    if payload.get("action") == "ask_school":
        return  # its lead already says where the question went
    if message:
        text = "I couldn't turn that into a change to your search, so the results above still stand."
    elif payload.get("answer"):
        text = "Got it. That doesn't change the results above."
    elif payload.get("feedback"):
        text = "Thanks, noted. The results above didn't change."
    else:
        text = "Noted. The results above didn't change."
    if response.get("assumption"):
        text = f"{text} {response['assumption']}"
    lead = next((b for b in response["blocks"] if b.get("type") == "message"), None)
    if lead is None:
        response["blocks"].insert(0, {"type": "message", "payload": {"text": text}})
    else:
        lead["payload"] = {**lead.get("payload", {}), "text": text}


def _update_focus(focus: dict, response: dict) -> None:
    for block in response.get("blocks") or []:
        payload = block.get("payload") or {}
        if block.get("type") == "results":
            main = [card["id"] for card in payload.get("schools") or []]
            others = [card["id"] for card in (payload.get("missed") or []) + (payload.get("gaps") or [])]
            focus["results"] = main
            focus["all"] = main + [sid for sid in others if sid not in main]
        elif block.get("type") == "school_detail":
            focus["school"] = (payload.get("school") or {}).get("id") or focus.get("school")
    ids = response.get("_school_ids") or []
    if len(ids) == 1:
        focus["school"] = ids[0]


# --- references --------------------------------------------------------------

def _named(text: str, schools: list[dict], prefer: list[str]) -> list[dict]:
    """Schools named in the text: the full name, or a word only that school's name has."""
    found: list[dict] = []
    ordered = sorted(schools, key=lambda s: (s["id"] not in prefer, prefer.index(s["id"]) if s["id"] in prefer else 0))
    for school in ordered:
        name = normalize(school.get("name") or "")
        if name and _phrase_in(text, name):
            found.append(school)
    if found:
        return found
    for school in ordered:
        distinctive = [w for w in normalize(school.get("name") or "").split() if w not in _GENERIC and len(w) > 3]
        if distinctive and all(_phrase_in(text, w) for w in distinctive[:2]):
            found.append(school)
    # "Arbor Heights" names Arbor Heights STEM Middle, not every school whose only long word is "Heights".
    widest = max((min(2, len([w for w in normalize(s.get("name") or "").split() if w not in _GENERIC and len(w) > 3])) for s in found), default=0)
    found = [s for s in found if min(2, len([w for w in normalize(s.get("name") or "").split() if w not in _GENERIC and len(w) > 3])) == widest]
    # A distinctive word shared by several schools ("Cedar") doesn't identify one; keep the shown one if any.
    shown = [s for s in found if s["id"] in prefer]
    return (shown or found)[:2] if len(found) > 1 else found


def _ordinals(text: str, focus: dict) -> list[str]:
    results = focus.get("results") or []
    picks: list[int] = []
    first_n = _FIRST_N.search(text)
    if first_n:
        count = {"two": 2, "three": 3, "2": 2, "3": 3}[first_n.group(1)]
        picks.extend(range(1, count + 1))
    for match in _ORDINAL.finditer(text):
        picks.append(len(results) if match.group(1) == "last" else _ORDINAL_WORDS[match.group(1)])
    for match in _NUMBERED.finditer(text):
        picks.append(int(match.group(1)))
    ids = []
    for position in picks:
        if 1 <= position <= len(results) and results[position - 1] not in ids:
            ids.append(results[position - 1])
    return ids


def _strip_names(text: str, named: list[dict]) -> str:
    for school in named:
        text = text.replace(normalize(school["name"]), " ")
        for word in normalize(school["name"]).split():
            if word not in _GENERIC:
                text = re.sub(rf"\b{re.escape(word)}\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _targets(text: str, focus: dict, schools: list[dict]) -> tuple[list[str], str]:
    """(school ids, scope) where scope is 'named', 'ordinal', 'pronoun', 'results' or ''."""
    named = _named(text, schools, focus.get("all") or [])
    if named:
        return [s["id"] for s in named], "named"
    ordinal = _ordinals(text, focus)
    if ordinal:
        return ordinal, "ordinal"
    if _SINGULAR.search(text) and focus.get("school"):
        return [focus["school"]], "pronoun"
    if _RESULTS_SCOPE.search(text) and focus.get("results"):
        return list(focus["results"][:MAX_RESULTS_ANSWERED]), "results"
    return [], ""


def _resolved_route(message: str, focus: dict, schools: list[dict]) -> Plan | None:
    """Turn "compare the first two" or "save it" into school IDs for routes that take them."""
    text = _normalized(message)
    route = next((name for name, pattern in _ID_ROUTES if pattern.search(text)), None)
    if not route:
        return None
    ids, scope = _targets(text, focus, schools)
    if scope in {"ordinal", "pronoun"} or (scope == "named" and route == "compare"):
        return Plan(intent=route, ids=ids, scope=scope)
    return None


def _default_targets(session: dict, kind: str) -> tuple[list[str], str]:
    """Who a question with no school in it is about."""
    focus = session["focus"]
    if kind == "summary":
        return [], ""
    # "Is there after-school care?" right after talking about one school means that school.
    last = next((h for h in reversed(session.get("history") or []) if h["role"] == "agent"), None)
    if focus.get("school") and last and last.get("route") in {"ask_about", "school_detail"}:
        return [focus["school"]], "pronoun"
    if focus.get("results"):
        return list(focus["results"][:MAX_RESULTS_ANSWERED]), "results"
    return [], ""


# --- reading a typed message -------------------------------------------------

@dataclass
class Plan:
    """What a typed message asks for, from Bedrock's reading or the rules. Code checks both.

    `intent` is "ask_about" (answered here from evidence), a pipeline route
    (sent to `pipeline.turn` as the action), or None to let the pipeline route it.
    """

    intent: str | None
    ids: list[str] = field(default_factory=list)
    scope: str = ""
    kind: str = "summary"
    need: str | None = None
    message: str | None = None  # a clearer wording for the pipeline ("Why isn't X here?")

    @property
    def pipeline_payload(self) -> dict:
        payload: dict[str, Any] = {"action": self.intent}
        if self.ids and self.intent in _ID_INTENTS:
            payload["school_ids"] = self.ids
        if self.message:
            payload["message"] = self.message
        return payload


_ID_INTENTS = {"compare", "school_detail", "cost", "save"}
_MODEL_INTENTS = {"ask_about", "new_search", "refine", "why_not", "define", "feedback", *_ID_INTENTS}
_MODEL_TOPICS = {"need", "access", "distance", "type", "summary", "cost"}


def _interpret(session: dict, message: str, schools: list[dict], by_id: dict) -> tuple[Plan | None, EngineStep | None]:
    """Bedrock reads the message when there are schools on screen; the rules read it otherwise or on failure."""
    focus = session["focus"]
    step = None
    if focus.get("results") or focus.get("school"):
        refs = _refs(focus)
        drafted, step = maybe_bedrock_follow_up(_follow_up_context(session, message, refs, by_id))
        if drafted is not None:
            plan = _plan_from_model(drafted, message, session, refs, schools, by_id)
            if plan is not None:
                return plan, step
            error = f"bedrock follow-up plan not usable: {json.dumps(drafted)[:200]}"
            log.warning("%s", error)
            step = EngineStep(engine="rules_fallback", error=error)
    return _rules_question(session, message, schools, by_id) or _resolved_route(message, focus, schools), step


def _refs(focus: dict) -> dict[str, str]:
    """Short names for the schools on screen: "#1"… as numbered on the cards, "x1"… for the rest."""
    refs = {f"#{index}": sid for index, sid in enumerate(focus.get("results") or [], start=1)}
    others = [sid for sid in focus.get("all") or [] if sid not in refs.values()]
    refs.update({f"x{index}": sid for index, sid in enumerate(others, start=1)})
    if focus.get("school") and focus["school"] not in refs.values():
        refs["f"] = focus["school"]
    return refs


def _follow_up_context(session: dict, message: str, refs: dict[str, str], by_id: dict) -> str:
    focus = session["focus"]
    in_focus = next((ref for ref, sid in refs.items() if sid == focus.get("school")), None)
    # The current message is already the last history line; send the few before it.
    recent = [
        f"{'Parent' if h['role'] == 'parent' else 'Guide'}: {h['text'][:300]}" for h in (session.get("history") or [])[-5:-1]
    ]
    shown = [
        {"ref": ref, "name": by_id[sid]["name"], "type": by_id[sid].get("entity_type")} for ref, sid in refs.items() if sid in by_id
    ]
    return json.dumps({"shown": shown, "in_focus": in_focus, "recent": recent, "message": message})


def _plan_from_model(drafted: dict, message: str, session: dict, refs: dict[str, str], schools: list[dict], by_id: dict) -> Plan | None:
    """Check the model's reading against what is on screen and the catalog. None means use the rules."""
    focus = session["focus"]
    intent, topic, need, raw_refs = drafted.get("intent"), drafted.get("topic"), drafted.get("need"), drafted.get("schools") or []
    if intent not in _MODEL_INTENTS or not isinstance(raw_refs, list):
        return None
    if "all" in raw_refs:
        ids, scope = list(focus.get("results") or [])[:MAX_RESULTS_ANSWERED], "results"
    else:
        if any(ref not in refs for ref in raw_refs):
            return None  # a school that isn't on screen
        ids, scope = list(dict.fromkeys(refs[ref] for ref in raw_refs)), "named"
    if not ids:
        # A school named in the message but not on screen ("Can we get into Beauclerc?").
        named = _named(_normalized(message), schools, focus.get("all") or [])
        ids, scope = [s["id"] for s in named], "named" if named else ""

    if intent == "cost" or (intent == "ask_about" and topic == "cost"):
        # Tuition at a public or charter school is a fact on file; only private schools get the
        # cost view. "Which are tuition-free?" is the low-cost need, as in the rules.
        free = bool(_FREE.search(_normalized(message)))
        if not free and (not ids or any(by_id[sid].get("entity_type") == "private" for sid in ids)):
            return Plan(intent="cost", ids=ids, scope=scope)
        intent, topic, need = "ask_about", "need", "low_cost"
    if intent == "why_not" and ids:
        return Plan(intent="why_not", message=f"Why isn't {by_id[ids[0]]['name']} here?")
    if intent == "define":
        term = drafted.get("term")
        clean = isinstance(term, str) and 0 < len(term) <= 40
        return Plan(intent="define", message=f"What is {term}?" if clean else None)
    if intent != "ask_about":
        return Plan(intent=intent, ids=ids, scope=scope)

    if topic not in _MODEL_TOPICS or (topic == "need" and need not in needs()):
        return None
    if not ids:
        ids, scope = _default_targets(session, topic)
        if not ids:
            return None
    if topic == "summary" and scope == "results":
        return Plan(intent=None)  # too open for the whole list; the pipeline routes it
    return Plan(intent="ask_about", ids=ids, scope=scope, kind=topic, need=need if topic == "need" else None)


def _record_route(response: dict, plan: Plan | None, step: EngineStep | None) -> None:
    """Say who read the message. When the chat layer chose the route, the pipeline's router didn't run."""
    if step is None:
        return
    engine = response.setdefault("engine", {"route": None, "extract": None, "explain": None, "errors": []})
    if plan is not None and plan.intent:
        engine["route"] = step.engine
    if step.error:
        engine.setdefault("errors", []).append(step.error)


def maybe_bedrock_follow_up(context: str) -> tuple[dict | None, EngineStep]:
    """The model's reading of a follow-up as a dict, or None to use the rules. Untrusted until checked."""
    from agent import bedrock_client as bc

    if not bc.enabled():
        return None, EngineStep(engine="rules")
    try:
        from catalog import models

        raw = bc.converse(models()["fast_model"], follow_up_system(), context)
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end < 0:
            return None, bc._step(False, f"bedrock follow-up returned no JSON object: {raw[:200]!r}")
        payload = json.loads(raw[start : end + 1])
        if not isinstance(payload, dict):
            return None, bc._step(False, f"bedrock follow-up returned {type(payload).__name__}, not an object")
        return payload, bc._step(True, None)
    except Exception as exc:
        return None, bc._step(False, f"bedrock follow-up failed: {exc}")


def follow_up_system() -> str:
    need_lines = "\n".join(f"- {need_id}: {spec.get('label') or need_id}" for need_id, spec in needs().items())
    return f"""You read a parent's message in a school-search chat and say what they want.
You never answer the question and never state facts about schools; code does that.

The input is JSON: the schools on screen ("shown", each with a ref; "#1", "#2"... are
numbered as on the result cards), the school being discussed ("in_focus"), the last
few chat lines ("recent") and the new "message".

Reply with only a JSON object:
{{"intent": "...", "schools": [...], "topic": "...", "need": "...", "term": "..."}}

intent, one of:
- ask_about: a question about one or more schools that a fact can answer (does it have X,
  how far, how to get in, public or private, is it free). A question about the schools on
  screen is ask_about even when it names a need: "any with small classes?", "which of
  these have a bus?", "do any of them support that?" -> schools ["all"].
- refine: the parent tells you to change the search (adds, drops or changes a need,
  another city or grade: "I also need...", "only show...", "what about...", "forget the..."),
  or asks about something no topic or need covers
- new_search: a whole new search that names a grade level and a place
- compare: compare two or more schools
- school_detail: wants the full profile of one school
- cost: tuition, cost or scholarships
- save: save a school to the list
- why_not: why a school is missing from the results
- define: what a term means (put the term in "term")
- feedback: a result is wrong, too far or not relevant

schools: refs from "shown". "the second one", "#2", "number 2" -> ["#2"]. "it", "this one",
"that school" -> the in_focus ref. "these", "any of them", "which ones" -> ["all"]. A school
named in the message -> its ref. [] when no school is meant.

topic (ask_about only): need | access (getting in, applying, deadlines, lotteries, zoning,
chances) | distance | type (public, private or charter) | cost | summary (an open question
such as "tell me about it").

need (topic need only): one id from this list, or null.
{need_lines}"""


# --- follow-up answers -------------------------------------------------------

def _topic(text: str) -> tuple[str, str | None]:
    """('access' | 'distance' | 'type' | 'need' | 'summary', need id)."""
    if _ACCESS_WORDS.search(text):
        return "access", None
    if _DISTANCE_WORDS.search(text):
        return "distance", None
    if _TYPE_WORDS.search(text):
        return "type", None
    best: tuple[int, str] | None = None
    for need_id, spec in needs().items():
        for phrase in spec.get("phrases") or []:
            if _phrase_in(text, phrase) and (best is None or len(phrase) > best[0]):
                best = (len(phrase), need_id)
    for phrase, need_id in _NEED_ALIASES.items():
        if _phrase_in(text, phrase) and (best is None or len(phrase) > best[0]):
            best = (len(phrase), need_id)
    if best:
        return "need", best[1]
    hit = map_phrase(text)
    if hit.need and hit.score >= 0.6 and not mapping_is_ambiguous(hit):
        return "need", hit.need
    return "summary", None


def _is_follow_up_question(text: str, raw: str) -> bool:
    return raw.rstrip().endswith("?") or bool(_QUESTION_START.search(text))


def _rules_question(session: dict, message: str, schools: list[dict], by_id: dict) -> Plan | None:
    """The rules' reading of a question about schools, or None to let the search pipeline handle it."""
    text = _normalized(message)
    if not _is_follow_up_question(text, message) or _WHY_NOT.search(text):
        return None  # statements refine the search; "why isn't X here?" has its own explanation
    asks_cost = False
    for name, pattern in _ID_ROUTES:
        # Compare, save and the full profile have their own views. "Which are
        # tuition-free?" is a low-cost question, not a request for the cost view.
        if not pattern.search(text) or (name == "cost" and _FREE.search(text)):
            continue
        if name != "cost":
            return None
        asks_cost = True
    focus = session["focus"]
    ids, scope = _targets(text, focus, schools)
    if _DEFINE.search(text) and not ids:
        return None  # "What's CTE?" is a definition, not a question about these schools
    named = [by_id[sid] for sid in ids if scope == "named"]
    rest = _strip_names(text, named)
    # A new city or school level is a new search, even when phrased as a question.
    if _SEARCH_WORDS.search(rest) or any(_phrase_in(rest, normalize(city)) for city in known_cities()):
        return None
    kind, need_id = _topic(rest)
    if asks_cost:
        # Tuition at a public or charter school is a fact on file ("tuition-free"),
        # so answer it here. A private school still gets the scholarship cost view.
        kind, need_id = "need", "low_cost"
    if not ids:
        ids, scope = _default_targets(session, kind)
        if not ids:
            return None
    if kind == "summary" and scope == "results":
        return None  # too open for the whole list; the search handles it
    if asks_cost and any((by_id.get(sid) or {}).get("entity_type") == "private" for sid in ids):
        return None
    return Plan(intent="ask_about", ids=ids, scope=scope, kind=kind, need=need_id)


def _answer(state: dict, session: dict, message: str, plan: Plan, schools: list[dict], by_id: dict) -> dict:
    """A cited answer, in code, from each school's evidence."""
    text = _normalized(message)
    rest = _strip_names(text, [by_id[sid] for sid in plan.ids if plan.scope == "named" and sid in by_id])
    criteria = [Criterion(**row) for row in session.get("criteria") or []]
    _stamp_distances(schools, criteria)
    targets = [by_id[sid] for sid in plan.ids if sid in by_id]
    kind, need_id = plan.kind, plan.need
    if kind == "access":
        body = _answer_access(state, session, criteria, targets, asked_odds=bool(_ODDS_WORDS.search(text)))
    elif kind == "distance":
        body = _answer_distance(criteria, targets)
    elif kind == "type":
        body = _answer_type(targets, _asked_type(rest) if plan.scope == "results" else None)
    elif kind == "need" and need_id:
        body = _answer_need(state, criteria, targets, need_id)
    else:
        body = _answer_summary(state, session, criteria, targets)
    return _answer_response(session, criteria, targets, kind, need_id, body)


def _checked(notes: list[str], records: list[EvidenceRecord], school: dict) -> str:
    """One school's notes with every uncited sentence dropped."""
    allowed = allowed_citations([r for r in records if r.school_id == school["id"]], school)
    return validate_text(" ".join(notes), allowed)


def _with_name(name: str, checked: str) -> str:
    """Put the school's name in front of text that already passed the citation check.

    The name is added after the check, so a name like "St. Johns" can't be split
    into its own uncited sentence and dropped.
    """
    return f"{name}: {checked}" if checked else ""


def _label(need_id: str) -> str:
    return (needs().get(need_id) or {}).get("label") or need_id


def _lower(label: str) -> str:
    """'After-school care' -> 'after-school care', but 'CTE' and 'AP courses' stay as they are."""
    return label[0].lower() + label[1:] if len(label) > 1 and label[1].islower() else label


def _need_criterion(criteria: list[Criterion], need_id: str) -> Criterion:
    # Reuse the parent's own criterion, so its time ("until 5:30") and reading carry over.
    for criterion in criteria:
        if criterion.need == need_id:
            return criterion
    return Criterion(id="ask", text=_label(need_id), need=need_id, strength="prefer", kind="need")


def _answer_need(state: dict, criteria: list[Criterion], targets: list[dict], need_id: str) -> dict:
    criterion = _need_criterion(criteria, need_id)
    label = _label(need_id)
    programs = load_programs()
    records = [evaluate_criterion(s, criterion, programs, _overlays_for(state, s["id"])) for s in targets]
    lines, unknown = [], []
    for school, record in zip(targets, records):
        checked = _checked([record.note], records, school) if record.status != "unknown" and record.source else ""
        if checked:
            lines.append(_with_name(school["name"], checked))
        else:
            unknown.append(school)
    # One school per line when the question was about the whole list.
    cited = "\n".join(lines)
    prompt = None
    chips: list[dict] = []
    if unknown:
        names = ", ".join(s["name"] for s in unknown[:4]) + (f" and {len(unknown) - 4} more" if len(unknown) > 4 else "")
        whom = "the school" if len(unknown) == 1 else "the schools"
        prompt = f"{label} isn't on file yet for {names}. I can ask {whom} for you."
        chips += [
            {"label": f"Ask {s['name']} about {_lower(label)}", "payload": {"action": "ask_school", "school_ids": [s["id"]], "need": need_id}}
            for s in unknown[:2]
        ]
    if len(targets) == 1:
        chips.append({"label": "How do I get in?", "payload": {"message": f"How do I get into {targets[0]['name']}?"}})
    return {"cited": cited, "prompt": prompt, "chips": chips, "records": records}


def _answer_access(
    state: dict, session: dict, criteria: list[Criterion], targets: list[dict], asked_odds: bool, named: bool = True
) -> dict:
    grade = next((c.value for c in criteria if c.kind == "grade" and c.value), None)
    zoned = set(session.get("zoned") or [])
    lines, accesses, chips = [], [], []
    for school in targets[:MAX_RESULTS_ANSWERED]:
        access = getting_in(school, grade, zoned, _overlays_for(state, school["id"]))
        accesses.append(access)
        # getting_in already validated its note against its own sources.
        note = access.get("note") or ""
        if note:
            lines.append(_with_name(school["name"], note) if named else note)
    cited = "\n".join(lines)
    prompt_parts = []
    if asked_odds:
        prompt_parts.append("I can explain how admission works and by when, but I never estimate a family's chances.")
    if len(targets) == 1:
        access = accesses[0]
        line = access["line"]
        prompt_parts.append(f"Status: {access['label']} · {line}" + ("" if line.endswith(("?", ".")) else "."))
        if access.get("zoned_prompt"):
            chips.append({"label": "Yes, it's my zoned school", "payload": {"action": "refresh", "zoned": {"school_id": targets[0]["id"]}}})
            locator = (access.get("district") or {}).get("locator_url")
            if locator:
                chips.append({"label": "Find my zoned school", "href": locator})
        chips.append({"label": access["official"]["name"], "href": access["official"]["url"]})
    return {"cited": cited, "prompt": " ".join(prompt_parts) or None, "chips": chips, "records": [], "access": accesses}


def _answer_distance(criteria: list[Criterion], targets: list[dict]) -> dict:
    city = next((c.value for c in criteria if c.kind == "location" and c.value), None)
    lines = [
        _with_name(
            s["name"],
            validate_text(f"{s['_distance_miles']:.1f} miles from the center of {city}, in a straight line [[cite:latlon]].", {"latlon"}),
        )
        for s in targets
        if s.get("_distance_miles") is not None and city
    ]
    cited = "\n".join(line for line in lines if line)
    prompt = None if cited else "Tell me a city first, and I'll measure from its center."
    return {"cited": cited, "prompt": prompt, "chips": [], "records": []}


_TYPES = ("public", "private", "charter")


def _asked_type(text: str) -> str | None:
    """'private' for "which of these are private?"; None for "public or private?"."""
    asked = [word for word in _TYPES if _phrase_in(text, word)]
    return asked[0] if len(asked) == 1 else None


def _answer_type(targets: list[dict], asked: str | None = None) -> dict:
    """Public, private or charter, from the school's state record."""
    if asked and len(targets) > 1:
        return _answer_which_type(targets, asked)
    lines, unknown = [], []
    for school in targets:
        entity = school.get("entity_type")
        checked = validate_text(f"This is a {entity} school [[cite:entity_type]].", {"entity_type"}) if entity else ""
        if checked:
            lines.append(_with_name(school["name"], checked))
        else:
            unknown.append(school["name"])
    prompt = f"The school type isn't on file for {', '.join(unknown)}." if unknown else None
    chips: list[dict] = []
    if len(targets) == 1 and targets[0].get("entity_type") == "private":
        chips.append({"label": "Cost after scholarships", "payload": {"action": "cost", "school_ids": [targets[0]["id"]]}})
    if len(targets) == 1:
        chips.append({"label": "How do I get in?", "payload": {"message": f"How do I get into {targets[0]['name']}?"}})
    return {"cited": "\n".join(lines), "prompt": prompt, "chips": chips, "records": []}


def _answer_which_type(targets: list[dict], asked: str) -> dict:
    """ "Which of these are private?" names only the private ones, not every school's type."""
    matching = [s for s in targets if s.get("entity_type") == asked]
    unknown = [s["name"] for s in targets if not s.get("entity_type")]
    total = len(targets)
    if matching:
        count = f"{len(matching)} of these {total} schools " + ("is" if len(matching) == 1 else "are")
        head = f"{count} {asked} [[cite:entity_type]]."
    else:
        head = f"None of these {total} schools is {asked} [[cite:entity_type]]."
    lines = [validate_text(head, {"entity_type"})]
    lines += [_with_name(s["name"], validate_text(f"This is a {asked} school [[cite:entity_type]].", {"entity_type"})) for s in matching]
    prompt = f"The school type isn't on file for {', '.join(unknown)}." if unknown else None
    chips: list[dict] = []
    if asked == "private" and matching:
        chips.append({"label": "Cost after scholarships", "payload": {"action": "cost", "school_ids": [s["id"] for s in matching[:3]]}})
    return {"cited": "\n".join(line for line in lines if line), "prompt": prompt, "chips": chips, "records": []}


def _answer_summary(state: dict, session: dict, criteria: list[Criterion], targets: list[dict]) -> dict:
    """An open question about one school: what we know for the parent's criteria, plus Getting in."""
    school = targets[0]
    programs = load_programs()
    records = [
        evaluate_criterion(school, c, programs, _overlays_for(state, school["id"]))
        for c in criteria
        if (c.kind == "need" and c.need) or c.kind == "distance"
    ]
    notes = [r.note for r in records if r.status != "unknown" and r.source]
    access = _answer_access(state, session, criteria, [school], asked_odds=False, named=False)
    parts = [part for part in [_checked(notes, records, school), access["cited"]] if part]
    # Name the school once, at the start, rather than before every sentence.
    cited = _with_name(school["name"], " ".join(parts)) if parts else ""
    chips = [
        {"label": "Open the full profile", "payload": {"action": "school_detail", "school_ids": [school["id"]]}},
        *access["chips"],
    ]
    return {"cited": cited, "prompt": access["prompt"], "chips": chips, "records": records, "access": access.get("access")}


def _answer_response(session: dict, criteria: list[Criterion], targets: list[dict], kind: str, need_id: str | None, body: dict) -> dict:
    text = strip_cites(body["cited"])
    if not text and not body.get("prompt"):
        body["prompt"] = "I don't have anything on file about that yet."
    message: dict[str, Any] = {"text": text, "cited": body["cited"], "prompt": body.get("prompt")}
    blocks = [{"type": "message", "payload": message}]
    if body.get("chips"):
        blocks.append({"type": "chips", "payload": {"items": body["chips"]}})
    blocks.append(
        {
            "type": "answer",
            "payload": {
                "school_ids": [s["id"] for s in targets],
                "topic": {"kind": kind, "need": need_id},
                "evidence": [r.model_dump() for r in body.get("records") or []],
                "access": body.get("access"),
            },
        }
    )
    return {
        "session_id": session["id"],
        "route": "ask_about",
        "criteria": [c.model_dump() for c in criteria],
        "blocks": blocks,
        "assumption": None,
        "_school_ids": [s["id"] for s in targets],
    }
