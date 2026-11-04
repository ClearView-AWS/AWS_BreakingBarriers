"""Session, saves, and inbox state.

A JSON file stands in for DynamoDB locally. Set GS_DYNAMODB_TABLE to use a
single DynamoDB table (pk/sk) so Fargate tasks share state across replaces.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path

from runtime_config import AWS_REGION, RUNTIME_DIR

_LOCK = threading.Lock()
DYNAMODB_TABLE = os.environ.get("GS_DYNAMODB_TABLE", "").strip()


def _path() -> Path:
    override = os.environ.get("GS_STATE_PATH")
    if override:
        return Path(override)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR / "state.json"


def _empty() -> dict:
    return {"sessions": {}, "inbox": [], "overlays": {}}


def _dynamo_table():
    import boto3

    return boto3.resource("dynamodb", region_name=AWS_REGION).Table(DYNAMODB_TABLE)


def _session_keys(table):
    from boto3.dynamodb.conditions import Key

    return table.query(KeyConditionExpression=Key("pk").eq("SESSIONS"), ProjectionExpression="sk")


def _decode_item(item: dict | None):
    if not item:
        return None
    raw = item.get("data_json")
    if raw is None:
        return item.get("data")
    return json.loads(raw)


def _load_dynamo() -> dict:
    from boto3.dynamodb.conditions import Key

    table = _dynamo_table()
    state = _empty()
    response = table.query(KeyConditionExpression=Key("pk").eq("SESSIONS"))
    for item in response.get("Items", []):
        session = _decode_item(item) or {}
        session_id = session.get("id") or item.get("sk")
        if session_id:
            state["sessions"][session_id] = session
    for meta_key, field in (("INBOX", "inbox"), ("OVERLAYS", "overlays")):
        payload = _decode_item(table.get_item(Key={"pk": "META", "sk": meta_key}).get("Item"))
        if payload is not None:
            state[field] = payload
    return state


def _save_dynamo(state: dict) -> None:
    table = _dynamo_table()
    # data_json keeps floats/bools that DynamoDB AttributeValues reject.
    existing = {item["sk"] for item in _session_keys(table).get("Items", [])}
    current = set(state.get("sessions") or {})
    with table.batch_writer() as batch:
        for session_id, session in (state.get("sessions") or {}).items():
            batch.put_item(
                Item={"pk": "SESSIONS", "sk": session_id, "data_json": json.dumps(session)}
            )
        for session_id in existing - current:
            batch.delete_item(Key={"pk": "SESSIONS", "sk": session_id})
        batch.put_item(
            Item={"pk": "META", "sk": "INBOX", "data_json": json.dumps(state.get("inbox") or [])}
        )
        batch.put_item(
            Item={
                "pk": "META",
                "sk": "OVERLAYS",
                "data_json": json.dumps(state.get("overlays") or {}),
            }
        )


def load_state() -> dict:
    if DYNAMODB_TABLE:
        try:
            return _load_dynamo()
        except Exception:
            # Fall through to the file so a missing table does not take the API down.
            pass
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
    if DYNAMODB_TABLE:
        try:
            _save_dynamo(state)
            return
        except Exception:
            pass
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
