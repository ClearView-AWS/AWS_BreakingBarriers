"""FastAPI entry point. The browser renders the blocks this returns."""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import observability
from gaps.inbox import grouped_inbox, reply_to_question
from pipeline import checklist_for, turn
from contracts import Criterion
from runtime_config import BEDROCK_ENABLED, INDEX_ON_START, OPENSEARCH_URL, REPO_ROOT
from search.corpus import load_schools
from store import State, backend_name

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

INDEX_STATUS: dict = {"state": "off" if not (OPENSEARCH_URL and INDEX_ON_START) else "pending"}


def _index_on_start() -> None:
    """In AWS, build the OpenSearch indexes once if they are missing. Runs in the
    background so the health check passes while it works; until it finishes,
    searches fall back to the local engine and the request log says so."""
    if INDEX_STATUS["state"] != "pending":
        return

    def run() -> None:
        import sys

        sys.path.insert(0, str(REPO_ROOT / "data" / "index"))
        try:
            from indexer import ensure_indexes

            INDEX_STATUS.update(state="running")
            INDEX_STATUS.update(state="ready", **ensure_indexes())
        except Exception as exc:
            log.exception("index on start failed")
            INDEX_STATUS.update(state="error", error=str(exc)[:300])

    threading.Thread(target=run, name="index-on-start", daemon=True).start()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _index_on_start()
    yield


app = FastAPI(title="Guided School Search", version="0.1.0", lifespan=_lifespan)
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
    return {
        "ok": True,
        "schools": len(load_schools()),
        "state_backend": backend_name(),
        "bedrock": BEDROCK_ENABLED,
        "opensearch": bool(OPENSEARCH_URL),
        "index": INDEX_STATUS,
    }


@app.post("/api/turn")
def post_turn(body: TurnIn, response: Response) -> dict:
    payload = body.model_dump()
    trace = observability.start_trace(
        "turn",
        session_id_in=body.session_id,
        message=body.message,
        action=body.action,
        answer=body.answer,
        feedback=body.feedback,
    )
    response.headers["X-Trace-Id"] = trace["trace_id"]
    try:
        with State() as state:
            result = turn(state, payload)
            out = result.model_dump()
    except Exception as exc:
        observability.emit(error=f"{type(exc).__name__}: {exc}"[:500])
        raise
    observability.emit(
        session_id=result.session_id,
        route=result.route,
        criteria=[
            {k: v for k, v in c.items() if v not in (None, [], {}, "")}
            for c in out.get("criteria") or []
        ],
        assumption=result.assumption,
        blocks=[block.type for block in result.blocks],
        results=_result_ids(out),
    )
    out["trace_id"] = trace["trace_id"]
    return out


def _result_ids(out: dict) -> list[dict]:
    rows = []
    for block in out.get("blocks") or []:
        for school in (block.get("payload") or {}).get("schools") or []:
            if isinstance(school, dict) and school.get("id"):
                rows.append({"id": school["id"], "match": school.get("match"), "verified": school.get("verified")})
    return rows[:15]


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


# Serve the built frontend when it is present (one container can host the whole
# demo). In AWS, CloudFront serves the same build from S3 instead.
_DIST = REPO_ROOT / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="web")
