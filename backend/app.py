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
        criteria = [Criterion(**row) for row in session.get("criteria") or []]
        items = checklist_for(session, criteria, load_schools(), _programs(), state)
        saved = []
        by_id = {school["id"]: school for school in load_schools()}
        for school_id in session.get("saved") or []:
            school = by_id.get(school_id)
            if school:
                saved.append({"id": school_id, "name": school["name"], "city": school.get("city")})
        return {
            "session_id": session_id,
            "criteria": session.get("criteria") or [],
            "saved": saved,
            "checklist": items,
            "asked": session.get("asked") or [],
        }


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
