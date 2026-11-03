"""Session, saves, feedback, and inbox state.

Two backends behind one interface:

* ``STATE_TABLE`` set: DynamoDB, one table, keys ``pk`` / ``sk``. This is what
  runs in AWS, so saved lists survive a restart or a new task.
* ``STATE_TABLE`` unset: a JSON file at ``data/runtime/state.json``
  (``GS_STATE_PATH`` overrides it), for laptops and tests.

Callers see the same dict either way: ``state["sessions"]``, ``state["inbox"]``
and ``state["overlays"]``. With DynamoDB, ``state["sessions"]`` loads a session
only when it is looked up, and only items that changed are written back.

Table layout (single-table design):

=====================  ====================  ==========================================
pk                     sk                    holds
=====================  ====================  ==========================================
``SESSION#<id>``       ``META``              criteria, asked questions, notes (JSON)
``SESSION#<id>``       ``SAVED#<school>``    one saved school, ``position`` keeps order
``SESSION#<id>``       ``FEEDBACK#<00000>``  one thumbs up / down with its reason
``INBOX``              ``<question id>``     one question to a school, ``seq`` keeps order
``OVERLAY``            ``<school id>``       the school's own answers (school_reported)
=====================  ====================  ==========================================
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from runtime_config import AWS_REGION, RUNTIME_DIR

_LOCK = threading.Lock()


def _path() -> Path:
    override = os.environ.get("GS_STATE_PATH")
    if override:
        return Path(override)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR / "state.json"


def _empty() -> dict:
    return {"sessions": {}, "inbox": [], "overlays": {}}


def _table_name() -> str:
    # Read at call time so tests can switch backends with monkeypatch.setenv.
    return os.environ.get("STATE_TABLE", "").strip()


def backend_name() -> str:
    return "dynamodb" if _table_name() else "json"


# --------------------------------------------------------------------------- JSON file


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


# --------------------------------------------------------------------------- sessions


def new_session(state: dict) -> dict:
    session = {
        "id": uuid.uuid4().hex[:12],
        "criteria": [],
        "asked": [],
        "saved": [],
        "feedback": [],
    }
    state["sessions"][session["id"]] = session
    return session


def get_session(state: dict, session_id: str | None) -> dict:
    if session_id and session_id in state["sessions"]:
        return state["sessions"][session_id]
    return new_session(state)


# --------------------------------------------------------------------------- DynamoDB


def _dumps(value) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _session_parts(session: dict) -> tuple[dict, list, list]:
    meta = {k: v for k, v in session.items() if k not in {"saved", "feedback"}}
    return meta, list(session.get("saved") or []), list(session.get("feedback") or [])


def _snapshot(session: dict) -> dict:
    meta, saved, feedback = _session_parts(session)
    return {"meta": _dumps(meta), "saved": list(saved), "feedback": [_dumps(f) for f in feedback]}


def _query_all(table, pk: str) -> list[dict]:
    from boto3.dynamodb.conditions import Key

    items: list[dict] = []
    kwargs = {"KeyConditionExpression": Key("pk").eq(pk), "ConsistentRead": True}
    while True:
        page = table.query(**kwargs)
        items.extend(page.get("Items") or [])
        if "LastEvaluatedKey" not in page:
            return items
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def _load_session(table, session_id: str) -> dict | None:
    items = _query_all(table, f"SESSION#{session_id}")
    meta = next((row for row in items if row["sk"] == "META"), None)
    if meta is None:
        return None
    session = json.loads(meta["body"])
    saved = sorted((row for row in items if row["sk"].startswith("SAVED#")), key=lambda r: int(r.get("position", 0)))
    feedback = sorted((row for row in items if row["sk"].startswith("FEEDBACK#")), key=lambda r: r["sk"])
    session["saved"] = [row["school_id"] for row in saved]
    session["feedback"] = [json.loads(row["body"]) for row in feedback]
    session.setdefault("id", session_id)
    return session


class _DynamoSessions(dict):
    """Looks sessions up in DynamoDB the first time they are asked for."""

    def __init__(self, table):
        super().__init__()
        self._table = table
        self._missing: set[str] = set()
        self.originals: dict[str, dict] = {}

    def _fetch(self, session_id) -> bool:
        if not isinstance(session_id, str):
            return False
        if dict.__contains__(self, session_id):
            return True
        if session_id in self._missing:
            return False
        session = _load_session(self._table, session_id)
        if session is None:
            self._missing.add(session_id)
            return False
        dict.__setitem__(self, session_id, session)
        self.originals[session_id] = _snapshot(session)
        return True

    def __contains__(self, session_id) -> bool:
        return self._fetch(session_id)

    def __getitem__(self, session_id):
        if not self._fetch(session_id):
            raise KeyError(session_id)
        return dict.__getitem__(self, session_id)

    def get(self, session_id, default=None):
        return self[session_id] if session_id in self else default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=4)
def _table(table_name: str):
    import boto3

    return boto3.resource("dynamodb", region_name=AWS_REGION).Table(table_name)


class DynamoState:
    def __init__(self, table_name: str):
        self.table = _table(table_name)

    def load(self) -> dict:
        sessions = _DynamoSessions(self.table)
        inbox_rows = sorted(_query_all(self.table, "INBOX"), key=lambda r: int(r.get("seq", 0)))
        inbox = [json.loads(row["body"]) for row in inbox_rows]
        overlays = {row["sk"]: json.loads(row["body"]) for row in _query_all(self.table, "OVERLAY")}
        self._inbox_before = {item["id"]: _dumps(item) for item in inbox}
        self._overlays_before = {key: _dumps(value) for key, value in overlays.items()}
        return {"sessions": sessions, "inbox": inbox, "overlays": overlays}

    def save(self, state: dict) -> None:
        sessions = state["sessions"]
        originals = getattr(sessions, "originals", {})
        with self.table.batch_writer(overwrite_by_pkeys=["pk", "sk"]) as batch:
            for session_id, session in dict.items(sessions):
                self._save_session(batch, session_id, session, originals.get(session_id))
            for seq, item in enumerate(state.get("inbox") or []):
                body = _dumps(item)
                if self._inbox_before.get(item["id"]) != body:
                    batch.put_item(Item={"pk": "INBOX", "sk": item["id"], "seq": seq, "body": body, "updated": _now()})
            for school_id, overlay in (state.get("overlays") or {}).items():
                body = _dumps(overlay)
                if self._overlays_before.get(school_id) != body:
                    batch.put_item(Item={"pk": "OVERLAY", "sk": school_id, "body": body, "updated": _now()})

    @staticmethod
    def _save_session(batch, session_id: str, session: dict, before: dict | None) -> None:
        pk = f"SESSION#{session_id}"
        after = _snapshot(session)
        before = before or {"meta": None, "saved": [], "feedback": []}
        if after["meta"] != before["meta"]:
            batch.put_item(Item={"pk": pk, "sk": "META", "body": after["meta"], "updated": _now()})
        if after["saved"] != before["saved"]:
            for school_id in set(before["saved"]) - set(after["saved"]):
                batch.delete_item(Key={"pk": pk, "sk": f"SAVED#{school_id}"})
            for position, school_id in enumerate(after["saved"]):
                batch.put_item(Item={"pk": pk, "sk": f"SAVED#{school_id}", "school_id": school_id, "position": position})
        if after["feedback"] != before["feedback"]:
            start = len(before["feedback"])
            if after["feedback"][:start] != before["feedback"]:
                # An earlier entry changed: rewrite the whole list.
                for index in range(start):
                    batch.delete_item(Key={"pk": pk, "sk": f"FEEDBACK#{index:05d}"})
                start = 0
            for index in range(start, len(after["feedback"])):
                batch.put_item(Item={"pk": pk, "sk": f"FEEDBACK#{index:05d}", "body": after["feedback"][index]})


# --------------------------------------------------------------------------- entry point


class State:
    """``with State() as state:`` loads, yields the dict, and saves on success."""

    def __enter__(self) -> dict:
        self._lock = _LOCK
        self._lock.acquire()
        try:
            table = _table_name()
            self._dynamo = DynamoState(table) if table else None
            self.data = self._dynamo.load() if self._dynamo else load_state()
        except Exception:
            self._lock.release()
            raise
        return self.data

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                if self._dynamo:
                    self._dynamo.save(self.data)
                else:
                    save_state(self.data)
        finally:
            self._lock.release()
