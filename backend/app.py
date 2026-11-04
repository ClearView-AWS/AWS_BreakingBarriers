"""FastAPI entry point. The browser renders the blocks this returns."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from gaps.inbox import grouped_inbox, reply_to_question
from pipeline import checklist_for, turn
from contracts import Criterion
from search.corpus import load_schools
from store import State

app = FastAPI(title="Guided School Search", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TurnIn(BaseModel):
    session_id: str | None = None
    message: str | None = None
    action: str | None = None
    school_ids: list[str] = Field(default_factory=list)
    criteria: list[dict] | None = None
    answer: dict | None = None
    # Batch answers from the brief questions UI: {"q1": "Must-have", ...}
    answers: dict | None = None
    feedback: dict | None = None
    need: str | None = None
    # "Yes, it's my zoned school" on a public card: {"school_id": "...", "value": true}.
    zoned: dict | None = None
    # M2/M3 UI events: brief_* | skip_to_results | answers_submitted
    # | pin_selected | pins_compared | area_changed
    event: str | None = None
    # area_changed: { "center": [lat, lon], "radius_mi": 5 }
    area: dict | None = None


class ReplyIn(BaseModel):
    text: str
    value: str | None = None


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "schools": len(load_schools())}


class UiTextIn(BaseModel):
    language: str
    strings: dict[str, str]


@app.post("/api/ui-text")
def ui_text(body: UiTextIn) -> dict:
    """The frontend's buttons, tabs and labels in the parent's language. Cached per language."""
    from agent.translate import translate_ui

    strings, error = translate_ui(body.strings, body.language)
    return {"language": body.language, "strings": strings, "error": error}


@app.post("/api/turn")
def post_turn(body: TurnIn) -> dict:
    with State() as state:
        response = turn(state, body.model_dump())
        return response.model_dump()


@app.get("/api/session/{session_id}")
def get_session(session_id: str) -> dict:
    with State() as state:
        session = state["sessions"].get(session_id)
        if not session:
            return {"error": "unknown session"}
        from enrollment.access import by_deadline, getting_in

        criteria = [Criterion(**row) for row in session.get("criteria") or []]
        items = checklist_for(session, criteria, load_schools(), _programs(), state)
        saved = []
        by_id = {school["id"]: school for school in load_schools()}
        grade = next((c.value for c in criteria if c.kind == "grade" and c.value), None)
        zoned = set(session.get("zoned") or [])
        for school_id in session.get("saved") or []:
            school = by_id.get(school_id)
            if school:
                access = getting_in(school, grade, zoned, (state.get("overlays") or {}).get(school_id) or {})
                saved.append({"id": school_id, "name": school["name"], "city": school.get("city"),
                              "access": access, "days_left": access["days_left"]})
        # The saved list reads as a to-do list: the soonest open deadline first.
        saved = by_deadline(saved)
        from agent.localize import localize_response

        # In the parent's language, like the chat (the session remembers it).
        return localize_response(
            {
                "session_id": session_id,
                "criteria": session.get("criteria") or [],
                "saved": saved,
                "checklist": items,
                "asked": session.get("asked") or [],
            },
            session.get("language"),
        )


@app.post("/api/chat")
def post_chat(body: TurnIn) -> dict:
    """Same body as /api/turn. Keeps the conversation history and answers follow-up questions."""
    from agent.conversation import chat_turn

    with State() as state:
        return chat_turn(state, body.model_dump())


def _programs():
    from search.corpus import load_programs

    return load_programs()


@app.get("/api/inbox")
def get_inbox() -> dict:
    with State() as state:
        return {"items": grouped_inbox(state)}


@app.post("/api/inbox/{question_id}/reply")
def post_reply(question_id: str, body: ReplyIn) -> dict:
    with State() as state:
        item = reply_to_question(state, question_id, body.text, body.value)
        if not item:
            return {"error": "unknown question"}
        return {"item": item}


@app.get("/api/schools/{school_id}")
def get_school(school_id: str) -> dict:
    for school in load_schools():
        if school["id"] == school_id or str(school.get("school_id")) == school_id:
            return {
                "id": school["id"],
                "name": school["name"],
                "city": school.get("city"),
                "entity_type": school.get("entity_type"),
                "level_codes": school.get("level_codes"),
            }
    return {"error": "unknown school"}


# ---------- Parent community ----------

from community import service as community  # noqa: E402
from community.tags import suggest_tags  # noqa: E402


class PostIn(BaseModel):
    school_id: str
    persona: str = "parent_a"
    kind: str = "question"
    text: str
    needs: list[str] = Field(default_factory=list)
    origin: str = "community"
    session_id: str | None = None


class CommunityReplyIn(BaseModel):
    persona: str = "parent_a"
    text: str
    answer: dict | None = None


class VoteIn(BaseModel):
    persona: str = "parent_a"


class TextIn(BaseModel):
    text: str


class DraftIn(BaseModel):
    school_id: str
    need: str


def _school(school_id: str) -> dict | None:
    for school in load_schools():
        if school["id"] == school_id or str(school.get("school_id")) == school_id:
            return school
    return None


@app.get("/api/community/personas")
def community_personas() -> dict:
    return {"personas": community.PERSONAS}


@app.get("/api/community/schools")
def community_schools(q: str | None = None) -> dict:
    """The Community tab's home: active schools, or any school whose name matches `q`."""
    with State() as state:
        return {"schools": community.schools_index(state, load_schools(), q)}


@app.get("/api/community/schools/{school_id}")
def community_school(school_id: str, sort: str = "top", need: str | None = None, persona: str | None = None) -> dict:
    school = _school(school_id)
    if not school:
        return {"error": "unknown school"}
    with State() as state:
        return {
            "school": {"id": school["id"], "name": school["name"], "city": school.get("city"), "entity_type": school.get("entity_type")},
            "demand": community.demand(state, school["id"]),
            "threads": community.threads_for(state, school["id"], sort=sort, need=need, viewer=persona),
            # "Ask the school" questions waiting for an answer. Staff answer them on this page.
            "questions": community.open_questions(state, school["id"]),
        }


class QuestionAnswerIn(BaseModel):
    text: str
    value: str | None = None
    offers: bool | None = None


@app.post("/api/community/schools/{school_id}/questions/{question_id}/answer")
def community_answer_question(school_id: str, question_id: str, body: QuestionAnswerIn) -> dict:
    school = _school(school_id)
    if not school:
        return {"ok": False, "safety": {"ok": False, "findings": [], "message": "Unknown school."}}
    answer = {key: value for key, value in {"value": body.value, "offers": body.offers}.items() if value is not None}
    with State() as state:
        return community.answer_question(state, school, question_id, body.text, answer)


@app.get("/api/community/threads/{thread_id}")
def community_thread(thread_id: str, persona: str | None = None) -> dict:
    with State() as state:
        found = community.thread(state, thread_id, viewer=persona)
        return found or {"error": "unknown thread"}


@app.post("/api/community/posts")
def community_post(body: PostIn) -> dict:
    school = _school(body.school_id)
    if not school:
        return {"ok": False, "safety": {"ok": False, "findings": [], "message": "Unknown school."}}
    with State() as state:
        return community.create_thread(
            state,
            school,
            body.persona,
            body.kind,
            body.text,
            body.needs,
            origin=body.origin,
            asker=body.session_id,
        )


@app.post("/api/community/threads/{thread_id}/replies")
def community_reply(thread_id: str, body: CommunityReplyIn) -> dict:
    with State() as state:
        return community.reply(state, thread_id, body.persona, body.text, body.answer)


@app.post("/api/community/posts/{post_id}/vote")
def community_vote(post_id: str, body: VoteIn) -> dict:
    with State() as state:
        return community.vote(state, post_id, body.persona)


import faq  # noqa: E402


class FaqIn(BaseModel):
    persona: str = "parent_a"
    text: str = ""


@app.get("/api/faq")
def faq_list(persona: str | None = None, q: str | None = None) -> dict:
    with State() as state:
        return {"questions": faq.list_faq(state, persona), "similar": faq.similar(state, q) if q else []}


@app.post("/api/faq")
def faq_add(body: FaqIn) -> dict:
    with State() as state:
        result = faq.add_question(state, body.persona, body.text)
        return {**result, "questions": faq.list_faq(state, body.persona)}


@app.post("/api/faq/{faq_id}/ask")
def faq_ask(faq_id: str, body: FaqIn) -> dict:
    with State() as state:
        result = faq.toggle_ask(state, faq_id, body.persona)
        return {**result, "questions": faq.list_faq(state, body.persona)}


@app.get("/api/zones")
def zones(ids: str = "") -> dict:
    """Demo attendance areas for the schools on the map (see search/zones.py)."""
    from search.zones import zones_for

    return {"zones": zones_for([value for value in ids.split(",") if value])}


@app.post("/api/community/suggest-tags")
def community_tags(body: TextIn) -> dict:
    return {"tags": suggest_tags(body.text)}


@app.post("/api/community/draft")
def community_draft(body: DraftIn) -> dict:
    school = _school(body.school_id)
    if not school:
        return {"error": "unknown school"}
    return community.draft_question(school, body.need)


@app.post("/api/community/schools/{school_id}/digest")
def community_digest(school_id: str) -> dict:
    school = _school(school_id)
    if not school:
        return {"error": "unknown school"}
    with State() as state:
        return community.digest(state, school)


# ---------- Highlight assistant ----------

from agent.assistant import assist  # noqa: E402
from contracts import Criterion as _Criterion  # noqa: E402


class AssistIn(BaseModel):
    session_id: str | None = None
    text: str = Field(default="", max_length=2000)
    question: str = Field(default="", max_length=1000)
    school_id: str | None = None
    criterion_id: str | None = None


@app.post("/api/assist")
def post_assist(body: AssistIn) -> dict:
    """Explain highlighted text from the school's own evidence. Read-only: it never changes the session."""
    from pipeline import _score_school, _stamp_distances
    from search.corpus import load_programs

    with State() as state:
        session = state["sessions"].get(body.session_id or "") or {}
        criteria = [_Criterion(**row) for row in session.get("criteria") or []]
        card = None
        if body.school_id:
            schools = load_schools()
            _stamp_distances(schools, criteria)
            school = next((row for row in schools if row["id"] == body.school_id), None)
            if school:
                card = _score_school(school, criteria, load_programs(), state, session)
        return assist(body.text, body.question, card, criteria, body.criterion_id)
