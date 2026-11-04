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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
    feedback: dict | None = None
    need: str | None = None
    # "Yes, it's my zoned school" on a public card: {"school_id": "...", "value": true}.
    zoned: dict | None = None


class ReplyIn(BaseModel):
    text: str
    value: str | None = None


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "schools": len(load_schools())}


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
        return {
            "session_id": session_id,
            "criteria": session.get("criteria") or [],
            "saved": saved,
            "checklist": items,
            "asked": session.get("asked") or [],
        }


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
