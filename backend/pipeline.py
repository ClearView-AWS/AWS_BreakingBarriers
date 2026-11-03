"""One parent turn: route, extract, search, evidence, score, one question, blocks."""

from __future__ import annotations

from catalog import glossary, needs
from agent.explainer import model_summaries, public_summary
from agent.extractor import extract
from agent.router import route_message, school_reference, term_from_question
from clarify.clarifier import choose_question
from contracts import Block, Criterion, Engine, EngineStep, TurnResponse
from evidence.engine import evaluate_criterion
from evidence.scorer import score_school
from evidence.why_not import explain_absence
from funding.estimator import estimate_cost
from gaps.inbox import add_question
from gaps.ses_mailer import send_school_question
from mapping.mapper import normalize
from search.corpus import known_cities, load_programs, load_schools
from search.engine import search_schools
from search.geo import distance_from_city

_LEVELS = {"p": "pre-k", "e": "elementary", "m": "middle", "h": "high"}


def turn(state: dict, payload: dict) -> TurnResponse:
    engine = Engine()
    response = _turn(state, payload, engine)
    return response.model_copy(update={"engine": engine})


def _record(engine: Engine, step_name: str, step: EngineStep) -> None:
    setattr(engine, step_name, step.engine)
    if step.error:
        engine.errors.append(step.error)


def _turn(state: dict, payload: dict, engine: Engine) -> TurnResponse:
    session = _session(state, payload.get("session_id"))
    message = (payload.get("message") or "").strip()
    action = payload.get("action")
    if not action and message:
        action, step = route_message(message, bool(session["criteria"]))
        _record(engine, "route", step)
    action = action or "refresh"

    if payload.get("criteria") is not None:
        session["criteria"] = payload["criteria"]

    if action in {"new_search", "refine"} and message:
        incoming, step = extract(message, known_cities())
        _record(engine, "extract", step)
        if action == "new_search" and not session["criteria"]:
            session["criteria"] = [item.model_dump() for item in incoming]
        else:
            session["criteria"] = _merge(session["criteria"], incoming)

    _apply_answer(session, payload.get("answer") or {}, state)
    _apply_feedback(session, payload.get("feedback") or {})

    criteria = [Criterion(**row) for row in session["criteria"]]
    schools = load_schools()
    programs = load_programs()
    _stamp_distances(schools, criteria)

    if action == "compare" or _wants(action, "compare"):
        return _compare(session, criteria, schools, programs, state, payload, message)
    if action == "why_not":
        return _why_not(session, criteria, schools, programs, state, message)
    if action == "define":
        return _define(session, criteria, message)
    if action == "cost":
        return _cost(session, criteria, schools, programs, state, message, payload)
    if action == "school_detail":
        return _detail(session, criteria, schools, programs, state, message, payload)
    if action == "save":
        return _save(session, criteria, schools, programs, state, payload, message)
    if action == "ask_school":
        return _ask(session, criteria, schools, programs, state, payload, engine)

    response = _search_response(session, criteria, schools, programs, state, message or "Showing your current search.", engine)
    if action == "new_search":
        response.route = "new_search"
    elif action in {"refine", "refresh", "feedback"}:
        response.route = "refine"
    return response


def _session(state: dict, session_id: str | None) -> dict:
    if session_id and session_id in state["sessions"]:
        return state["sessions"][session_id]
    from store import new_session

    return new_session(state)


def _merge(existing: list[dict], incoming: list[Criterion]) -> list[dict]:
    rows = [dict(row) for row in existing]
    next_index = 1 + max([_id_number(row.get("id")) for row in rows] or [0])

    def replace_kind(kind: str, item: Criterion) -> None:
        nonlocal next_index
        for row in rows:
            if row.get("kind") == kind:
                kept_id = row["id"]
                row.clear()
                row.update(item.model_dump())
                row["id"] = kept_id
                return
        dumped = item.model_dump()
        dumped["id"] = f"c{next_index}"
        next_index += 1
        rows.append(dumped)

    for item in incoming:
        if item.kind in {"location", "grade", "school_type"}:
            replace_kind(item.kind, item)
            continue
        match = None
        for row in rows:
            if item.need and row.get("need") == item.need:
                match = row
                break
            if item.need is None and row.get("need") is None and row.get("text") == item.text:
                match = row
                break
        if match:
            kept_id = match["id"]
            resolved = match.get("resolved_reading")
            match.clear()
            match.update(item.model_dump())
            match["id"] = kept_id
            if resolved and not item.resolved_reading:
                match["resolved_reading"] = resolved
            continue
        dumped = item.model_dump()
        dumped["id"] = f"c{next_index}"
        next_index += 1
        rows.append(dumped)
    return rows


def _id_number(value: str | None) -> int:
    if not value or not value.startswith("c"):
        return 0
    try:
        return int(value[1:])
    except ValueError:
        return 0


def _apply_answer(session: dict, answer: dict, state: dict) -> None:
    if not answer:
        return
    question_id = answer.get("question_id") or ""
    option = answer.get("option_id")
    session.setdefault("asked", [])
    if question_id and question_id not in session["asked"]:
        session["asked"].append(question_id)
    criteria = session["criteria"]
    if question_id == "q:location" and option:
        criteria.append(
            Criterion(id="tmp", text=option, kind="location", value=option, strength="require").model_dump()
        )
        _rekey(criteria)
    elif question_id == "q:grade" and option:
        label = _LEVELS.get(option, option)
        criteria.append(
            Criterion(id="tmp", text=label, kind="grade", value=option, strength="require").model_dump()
        )
        _rekey(criteria)
    elif question_id == "q:location_ambiguity" and option == "other":
        session["note"] = "This prototype only includes Florida schools, so I kept the Florida reading."
    elif question_id.startswith("q:amb:"):
        criterion_id = question_id.split(":")[-1]
        for row in criteria:
            if row["id"] == criterion_id:
                row["resolved_reading"] = option
    elif question_id.startswith("q:unknown:"):
        criterion_id = question_id.split(":")[-1]
        for row in criteria:
            if row["id"] == criterion_id and option == "prefer":
                row["strength"] = "prefer"
            if row["id"] == criterion_id and option == "ask_schools":
                session["pending_ask_need"] = row.get("need")
    elif question_id.startswith("q:unmapped:"):
        criterion_id = question_id.split(":")[-1]
        spec = needs().get(option or "")
        for row in criteria:
            if row["id"] == criterion_id and spec:
                row["need"] = option
                row["text"] = spec.get("label") or option
                row["strength"] = "prefer"
                row["ambiguities"] = []


def _rekey(criteria: list[dict]) -> None:
    for index, row in enumerate(criteria, start=1):
        if not str(row.get("id") or "").startswith("c") or row["id"] == "tmp":
            row["id"] = f"c{index}"


def _apply_feedback(session: dict, feedback: dict) -> None:
    if not feedback:
        return
    session.setdefault("feedback", []).append(feedback)
    if feedback.get("vote") == "down" and feedback.get("reason") == "too_far":
        school_id = feedback.get("school_id")
        school = _by_id(load_schools()).get(school_id)
        criteria = [Criterion(**row) for row in session["criteria"]]
        _stamp_distances(load_schools(), criteria)
        distance = None
        if school:
            city = next((c.value for c in criteria if c.kind == "location"), None)
            distance = distance_from_city(school, city)
        limit = max(2.0, round((distance or 8) - 1, 1))
        updated = False
        for row in session["criteria"]:
            if row.get("kind") == "distance":
                row.setdefault("params", {})["max_miles"] = limit
                row["text"] = f"Within {limit:g} miles"
                updated = True
        if not updated:
            session["criteria"].append(
                Criterion(
                    id="tmp",
                    text=f"Within {limit:g} miles",
                    kind="distance",
                    strength="prefer",
                    params={"max_miles": limit},
                ).model_dump()
            )
            _rekey(session["criteria"])


def _stamp_distances(schools: list[dict], criteria: list[Criterion]) -> None:
    city = next((c.value for c in criteria if c.kind == "location"), None)
    for school in schools:
        school["_distance_miles"] = distance_from_city(school, city)


def _overlays_for(state: dict, school_id: str) -> dict:
    return (state.get("overlays") or {}).get(school_id) or {}


def _score_school(school, criteria, programs, state) -> dict | None:
    rows = []
    records = []
    for criterion in criteria:
        if criterion.kind == "need" and not criterion.need:
            continue
        if criterion.kind not in {"need", "distance"}:
            continue
        record = evaluate_criterion(school, criterion, programs, _overlays_for(state, school["id"]))
        records.append(record)
        rows.append((criterion.strength, record))
    if not rows and not any(c.kind in {"location", "grade", "school_type"} for c in criteria):
        return None
    scored = score_school(rows)
    summary = public_summary(records, school)
    return {
        "id": school["id"],
        "name": school["name"],
        "city": school.get("city"),
        "state": school.get("state"),
        "entity_type": school.get("entity_type"),
        "level_codes": school.get("level_codes") or [],
        "match": scored["match"],
        "verified": scored["verified"],
        "coverage": scored["coverage"],
        "missed_must": scored["missed_must"],
        "summary": summary,
        "distance_miles": None if school.get("_distance_miles") is None else round(school["_distance_miles"], 1),
        "lat": school.get("_lat"),
        "lon": school.get("_lon"),
        "evidence": [record.model_dump() for record in records],
        "tuition": (school.get("osp") or {}).get("tuition"),
        "saved": False,
    }


def _search_response(session, criteria, schools, programs, state, message: str, engine: Engine) -> TurnResponse:
    readings = {row.id: row.resolved_reading for row in criteria if row.resolved_reading}

    def search_fn(probe, probe_readings):
        return search_schools(schools, programs, probe, message, probe_readings, limit=10)

    matched = search_schools(schools, programs, criteria, message, readings, limit=None)
    scored_rows = []
    for school in matched:
        card = _score_school(school, criteria, programs, state)
        if card:
            card["saved"] = school["id"] in session.get("saved", [])
            scored_rows.append(card)
    scored_rows.sort(key=lambda row: (-row["match"], -row["coverage"], row["name"]))
    main = [row for row in scored_rows if not row["missed_must"]][:8]
    missed = [row for row in scored_rows if row["missed_must"]][:6]
    if main or missed:
        summaries, step = model_summaries(main + missed, _by_id(schools), criteria)
        _record(engine, "explain", step)
        for row in main + missed:
            row["summary"] = summaries.get(row["id"], row["summary"])
    shown = {row["id"] for row in main}
    gaps = []
    for row in scored_rows:
        if row["id"] in shown or row["missed_must"]:
            continue
        if any(item["status"] == "unknown" for item in row["evidence"]):
            gaps.append(row)
        if len(gaps) == 2:
            break

    question = choose_question(criteria, set(session.get("asked") or []), search_fn, scored_rows[:10])
    assumption = session.get("note")
    if question:
        session.setdefault("asked", [])
        if question["id"] not in session["asked"]:
            session["asked"].append(question["id"])
        assumption = question.get("assumption") or assumption

    if session.get("pending_ask_need"):
        _ask_unknowns(session, main + missed, state)
        session["pending_ask_need"] = None

    grade = next((c for c in criteria if c.kind == "grade"), None)
    city = next((c for c in criteria if c.kind == "location"), None)
    grade_label = _LEVELS.get(grade.value, "matching") if grade else "matching"
    city_label = f" in {city.value}" if city else ""
    lead = f"Here are {len(main)} {grade_label} schools{city_label}."
    if missed:
        noun = "school" if len(missed) == 1 else "schools"
        verb = "stays" if len(missed) == 1 else "stay"
        lead += f" {len(missed)} {noun} missed a must-have and {verb} listed underneath."
    if assumption:
        lead += f" {assumption}"
    if not main and not missed:
        lead = f"No schools matched the location, grade, and school type{city_label}."

    blocks = [
        Block(type="message", payload={"text": lead}),
        Block(type="criteria", payload={"items": [c.model_dump() for c in criteria]}),
    ]
    if question:
        blocks.append(Block(type="question", payload=question))
    blocks.append(
        Block(
            type="results",
            payload={
                "schools": main,
                "missed": missed,
                "gaps": gaps,
                "matched_count": len(scored_rows),
            },
        )
    )
    grid_schools = (main + missed)[:4]
    if grid_schools:
        blocks.append(Block(type="evidence_grid", payload=_grid(grid_schools, criteria)))
    return TurnResponse(
        session_id=session["id"],
        route="refine" if session.get("criteria") else "new_search",
        criteria=criteria,
        blocks=blocks,
        assumption=assumption,
    )


def _grid(cards: list[dict], criteria: list[Criterion]) -> dict:
    columns = [c for c in criteria if c.kind in {"need", "distance"} and (c.kind == "distance" or c.need)]
    cells = {}
    for card in cards:
        cells[card["id"]] = {}
        by_id = {row["criterion_id"]: row for row in card["evidence"]}
        for column in columns:
            cells[card["id"]][column.id] = by_id.get(column.id)
    return {
        "schools": [{"id": card["id"], "name": card["name"]} for card in cards],
        "criteria": [{"id": column.id, "text": column.text, "strength": column.strength} for column in columns],
        "cells": cells,
    }


def _ask_unknowns(session, cards, state) -> None:
    need_id = session.get("pending_ask_need")
    if not need_id:
        return
    by_id = _by_id(load_schools())
    for card in cards:
        for row in card["evidence"]:
            if row["status"] != "unknown":
                continue
            criterion = next((item for item in session["criteria"] if item["id"] == row["criterion_id"]), None)
            if not criterion or criterion.get("need") != need_id:
                continue
            school = by_id.get(card["id"])
            if not school:
                continue
            question = needs().get(need_id, {}).get("visit_question") or f"Can you confirm {criterion.get('text')}?"
            item = add_question(state, school, need_id, question, session["id"])
            item["email"] = send_school_question(item)


def _compare(session, criteria, schools, programs, state, payload, message) -> TurnResponse:
    ids = list(payload.get("school_ids") or [])
    if len(ids) < 2 and message:
        ids = _ids_from_text(message, schools)
    chosen = [_by_id(schools)[sid] for sid in ids if sid in _by_id(schools)][:2]
    cards = []
    for school in chosen:
        card = _score_school(school, criteria, programs, state) or {
            "id": school["id"],
            "name": school["name"],
            "evidence": [],
            "match": None,
            "verified": "0 of 0",
        }
        cards.append(card)
    narrative = " ".join(card.get("summary") or card["name"] for card in cards)
    blocks = [
        Block(type="message", payload={"text": "Side by side, using the same evidence rules."}),
        Block(type="criteria", payload={"items": [c.model_dump() for c in criteria]}),
        Block(type="comparison", payload={"schools": cards, "narrative": narrative}),
        Block(type="evidence_grid", payload=_grid(cards, criteria)),
    ]
    costs = [estimate_cost(school) for school in chosen if school.get("entity_type") == "private"]
    if costs:
        blocks.append(Block(type="cost", payload={"schools": costs}))
    return TurnResponse(session_id=session["id"], route="compare", criteria=criteria, blocks=blocks)


def _why_not(session, criteria, schools, programs, state, message) -> TurnResponse:
    name = school_reference(message or "") or message
    found = _find_by_name(name, schools)
    if not found:
        blocks = [Block(type="message", payload={"text": f"I couldn't find a school matching \"{name}\"."})]
        return TurnResponse(session_id=session["id"], route="why_not", criteria=criteria, blocks=blocks)
    school = found[0]
    matched = search_schools(schools, programs, criteria, message, limit=None)
    ranked = []
    for item in matched:
        card = _score_school(item, criteria, programs, state)
        if card:
            ranked.append(card)
    ranked.sort(key=lambda row: (-row["match"], -row["coverage"], row["name"]))
    # Rank across the full filtered set, missed group included, so the parent
    # can see where a weak school actually sits.
    explanation = explain_absence(
        school,
        criteria,
        programs,
        _overlays_for(state, school["id"]),
        [row["id"] for row in ranked],
    )
    blocks = [
        Block(type="why_not", payload=explanation),
        Block(type="criteria", payload={"items": [c.model_dump() for c in criteria]}),
    ]
    return TurnResponse(session_id=session["id"], route="why_not", criteria=criteria, blocks=blocks, assumption=explanation.get("change"))


def _define(session, criteria, message) -> TurnResponse:
    term = term_from_question(message)
    entry = _glossary_entry(term)
    if not entry:
        blocks = [Block(type="message", payload={"text": f"I don't have a definition for \"{term}\" in the framework notes."})]
    else:
        blocks = [
            Block(
                type="definition",
                payload={
                    "term": entry["term"],
                    "title": entry["title"],
                    "text": " ".join(entry["text"].split()),
                    "cite": entry["cite_path"],
                },
            )
        ]
    return TurnResponse(session_id=session["id"], route="define", criteria=criteria, blocks=blocks)


def _cost(session, criteria, schools, programs, state, message, payload) -> TurnResponse:
    ids = list(payload.get("school_ids") or [])
    if not ids and message:
        ids = [school["id"] for school in _find_by_name(school_reference(message or "") or message, schools)[:1]]
    if not ids:
        # Fall back to private schools already in the filtered set.
        matched = search_schools(schools, programs, criteria, message, limit=None)
        ids = [school["id"] for school in matched if school.get("entity_type") == "private"][:3]
    by_id = _by_id(schools)
    estimates = [estimate_cost(by_id[sid]) for sid in ids if sid in by_id]
    blocks = [
        Block(type="message", payload={"text": "Likely scholarship eligibility. Not a promised award."}),
        Block(type="cost", payload={"schools": estimates}),
    ]
    return TurnResponse(session_id=session["id"], route="cost", criteria=criteria, blocks=blocks)


def _detail(session, criteria, schools, programs, state, message, payload) -> TurnResponse:
    ids = list(payload.get("school_ids") or [])
    if not ids and message:
        found = _find_by_name(school_reference(message or "") or message, schools)
        ids = [found[0]["id"]] if found else []
    if not ids:
        blocks = [Block(type="message", payload={"text": "Which school should I open?"})]
        return TurnResponse(session_id=session["id"], route="school_detail", criteria=criteria, blocks=blocks)
    school = _by_id(schools)[ids[0]]
    card = _score_school(school, criteria, programs, state)
    blocks = [
        Block(
            type="school_detail",
            payload={
                "school": _profile(school),
                "card": card,
                "reviews": _review_topics(school),
                "cost": estimate_cost(school) if school.get("entity_type") == "private" else None,
            },
        )
    ]
    return TurnResponse(session_id=session["id"], route="school_detail", criteria=criteria, blocks=blocks)


def _save(session, criteria, schools, programs, state, payload, message) -> TurnResponse:
    ids = list(payload.get("school_ids") or [])
    if not ids and message:
        ids = [school["id"] for school in _find_by_name(school_reference(message or "") or message, schools)[:1]]
    saved = session.setdefault("saved", [])
    for school_id in ids:
        if school_id not in saved:
            saved.append(school_id)
    items = checklist_for(session, criteria, schools, programs, state)
    blocks = [
        Block(type="message", payload={"text": f"Saved list has {len(saved)} schools."}),
        Block(type="checklist", payload={"school_ids": saved, "items": items}),
    ]
    return TurnResponse(session_id=session["id"], route="save", criteria=criteria, blocks=blocks)


def _ask(session, criteria, schools, programs, state, payload, engine: Engine) -> TurnResponse:
    school_id = (payload.get("school_ids") or [None])[0]
    need_id = payload.get("need")
    school = _by_id(schools).get(school_id)
    if not school or not need_id:
        blocks = [Block(type="message", payload={"text": "I need a school and a question to send."})]
        return TurnResponse(session_id=session["id"], route="save", criteria=criteria, blocks=blocks)
    question = needs().get(need_id, {}).get("visit_question") or f"Can you tell us about {need_id}?"
    item = add_question(state, school, need_id, question, session["id"])
    item["email"] = send_school_question(item)
    blocks = [
        Block(
            type="message",
            payload={
                "text": f"I grouped that question for {school['name']}. It is waiting in the school inbox ({item['parent_count']} parent{'s' if item['parent_count'] != 1 else ''})."
            },
        )
    ]
    # Re-run the search so the card still shows the unknown cell beside the button.
    response = _search_response(session, criteria, schools, programs, state, "", engine)
    response.blocks.insert(0, blocks[0])
    return response


def checklist_for(session, criteria, schools, programs, state) -> list[dict]:
    by_id = _by_id(schools)
    items = []
    for school_id in session.get("saved") or []:
        school = by_id.get(school_id)
        if not school:
            continue
        card = _score_school(school, criteria, programs, state)
        if not card:
            continue
        for row in card["evidence"]:
            if row["status"] != "unknown":
                continue
            criterion = next((item for item in criteria if item.id == row["criterion_id"]), None)
            if not criterion or not criterion.need:
                continue
            question = needs().get(criterion.need, {}).get("visit_question")
            if question:
                items.append(
                    {
                        "school_id": school_id,
                        "school_name": school["name"],
                        "criterion_id": criterion.id,
                        "need": criterion.need,
                        "question": question,
                    }
                )
    return items


def _profile(school: dict) -> dict:
    osp = school.get("osp") or {}
    return {
        "id": school["id"],
        "name": school["name"],
        "city": school.get("city"),
        "state": school.get("state"),
        "street": school.get("street"),
        "zipcode": school.get("zipcode"),
        "entity_type": school.get("entity_type"),
        "level_codes": school.get("level_codes") or [],
        "summary_rating": school.get("summary_rating"),
        "student_progress_rating": school.get("student_progress_rating"),
        "test_scores_rating": school.get("test_scores_rating"),
        "enrollment": school.get("enrollment"),
        "student_teacher_ratio": school.get("student_teacher_ratio"),
        "esp_text": school.get("esp_text") or [],
        "osp": {key: value for key, value in osp.items() if key not in {"administrator_email", "facebook_url"}},
        "synthetic": bool(school.get("_synthetic")),
    }


def _review_topics(school: dict) -> list[dict]:
    buckets: dict[str, dict] = {}
    for index, review in enumerate(school.get("reviews_full") or []):
        when = str(review.get("created_date") or "")[:10]
        for sentiment in review.get("sentiments") or []:
            topic = sentiment.get("topic") or "Other"
            bucket = buckets.setdefault(
                topic,
                {"topic": topic, "positive": 0, "negative": 0, "neutral": 0, "dates": [], "quotes": []},
            )
            polarity = str(sentiment.get("sentiment_enum") or "neutral")
            if polarity not in bucket:
                polarity = "neutral"
            bucket[polarity] += 1
            if when:
                bucket["dates"].append(when)
            if len(bucket["quotes"]) < 2 and review.get("text"):
                side = polarity
                bucket["quotes"].append(
                    {"side": side, "date": when, "text": str(review["text"])[:280], "id": f"reviews_full[{index}]"}
                )
    rows = []
    for bucket in buckets.values():
        if bucket["positive"] + bucket["negative"] + bucket["neutral"] == 0:
            continue
        dates = sorted(bucket["dates"])
        rows.append(
            {
                "topic": bucket["topic"],
                "positive": bucket["positive"],
                "negative": bucket["negative"],
                "neutral": bucket["neutral"],
                "earliest": dates[0] if dates else None,
                "latest": dates[-1] if dates else None,
                "quotes": bucket["quotes"],
            }
        )
    rows.sort(key=lambda row: -(row["positive"] + row["negative"] + row["neutral"]))
    return rows


def _glossary_entry(term: str) -> dict | None:
    needle = normalize(term)
    for key, entry in glossary().items():
        names = {normalize(key), normalize(entry.get("term") or ""), normalize(entry.get("title") or "")}
        if needle in names or any(name and name in needle for name in names):
            return entry
    return None


def _by_id(schools: list[dict]) -> dict[str, dict]:
    return {school["id"]: school for school in schools}


def _find_by_name(query: str, schools: list[dict]) -> list[dict]:
    if not query:
        return []
    needle = normalize(query)
    ranked = []
    for school in schools:
        name = normalize(school.get("name") or "")
        if not name:
            continue
        if needle == name:
            ranked.append((0, school))
        elif needle in name or name in needle:
            ranked.append((1, school))
        else:
            tokens = set(needle.split())
            name_tokens = set(name.split())
            if tokens and len(tokens & name_tokens) / len(tokens) >= 0.6:
                ranked.append((2, school))
    ranked.sort(key=lambda row: row[0])
    return [school for _, school in ranked]


def _ids_from_text(message: str, schools: list[dict]) -> list[str]:
    normalized = normalize(message)
    parts = re_split_compare(normalized)
    ids = []
    for part in parts:
        found = _find_by_name(part, schools)
        if found:
            ids.append(found[0]["id"])
    return ids


def re_split_compare(normalized: str) -> list[str]:
    import re

    match = re.search(r"compare (.+)", normalized)
    text = match.group(1) if match else normalized
    pieces = re.split(r"\band\b|\bvs\b|\bversus\b|\bwith\b", text)
    return [piece.strip(" ?.") for piece in pieces if piece.strip(" ?.")]


def _wants(action: str, name: str) -> bool:
    return action == name
