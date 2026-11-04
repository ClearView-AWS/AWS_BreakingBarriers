"""Session, saves, and inbox state. A JSON file stands in for DynamoDB locally."""

from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path

from runtime_config import RUNTIME_DIR

_LOCK = threading.Lock()


def _path() -> Path:
    override = os.environ.get("GS_STATE_PATH")
    if override:
        return Path(override)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR / "state.json"


def _empty() -> dict:
    return {"sessions": {}, "inbox": [], "overlays": {}}


def load_state() -> dict:
    path = _path()
    if not path.exists():
        return _empty()
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return _empty()
    data.setdefault("sessions", {})
    data.setdefault("inbox", [])
    data.setdefault("overlays", {})
    return data


def save_state(state: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def new_session(state: dict) -> dict:
    session = {
        "id": uuid.uuid4().hex[:12],
        "criteria": [],
        "asked": [],
        "saved": [],
        "feedback": [],
        # M2: search runs only after the brief is approved or the parent skips questions.
        "brief_approved": False,
        "pending_questions": [],
        "assumptions": [],
    }
    state["sessions"][session["id"]] = session
    return session


def get_session(state: dict, session_id: str | None) -> dict:
    if session_id and session_id in state["sessions"]:
        return state["sessions"][session_id]
    return new_session(state)


class State:
    def __enter__(self) -> dict:
        self._lock = _LOCK
        self._lock.acquire()
        self.data = load_state()
        return self.data

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                save_state(self.data)
        finally:
            self._lock.release()
