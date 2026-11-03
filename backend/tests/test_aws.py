"""AWS paths without AWS: DynamoDB state (moto), the per-request log, and the OpenSearch query."""

from __future__ import annotations

import io
import json
import logging

import pytest

boto3 = pytest.importorskip("boto3")
moto = pytest.importorskip("moto")

import observability
import store
from contracts import Criterion
from search import opensearch_client
from search.corpus import load_programs, load_schools
from search.engine import passes_hard_filters, search_schools

TABLE = "gs-guided-state-test"


@pytest.fixture
def dynamo_table(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with moto.mock_aws():
        boto3.client("dynamodb", region_name="us-east-1").create_table(
            TableName=TABLE,
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        monkeypatch.setenv("STATE_TABLE", TABLE)
        store._table.cache_clear()
        yield
        store._table.cache_clear()


def _restart():
    """What a new process sees: no cached table handle, nothing in memory."""
    store._table.cache_clear()


def test_saved_list_and_feedback_survive_restart(dynamo_table):
    from pipeline import turn

    with store.State() as state:
        first = turn(state, {"message": "Middle school in Jacksonville"})
    jax = [s for s in load_schools() if passes_hard_filters(s, [Criterion(id="l", text="", kind="location", value="Jacksonville")])]
    picks = [jax[0]["id"], jax[1]["id"]]
    with store.State() as state:
        turn(state, {"session_id": first.session_id, "action": "save", "school_ids": picks})
    with store.State() as state:
        turn(state, {"session_id": first.session_id, "action": "feedback", "feedback": {"vote": "up", "school_id": picks[0]}})

    _restart()
    assert store.backend_name() == "dynamodb"
    with store.State() as state:
        assert first.session_id in state["sessions"]
        session = state["sessions"][first.session_id]
        assert session["saved"] == picks
        assert session["feedback"] == [{"vote": "up", "school_id": picks[0]}]
        assert session["criteria"], "criteria should persist too"
        session["saved"].remove(picks[0])

    _restart()
    with store.State() as state:
        assert state["sessions"][first.session_id]["saved"] == [picks[1]]
        assert "nope" not in state["sessions"]


def test_inbox_and_school_answer_survive_restart(dynamo_table):
    from gaps.inbox import add_question, reply_to_question

    school = load_schools()[0]
    with store.State() as state:
        item = add_question(state, school, "after_care", "Until when does after-care run?", "s1")
        add_question(state, school, "after_care", "Until when does after-care run?", "s2")
    _restart()
    with store.State() as state:
        assert state["inbox"][0]["parent_count"] == 2
        reply_to_question(state, item["id"], "Until 6 pm", "18:00")
    _restart()
    with store.State() as state:
        assert state["inbox"][0]["status"] == "answered"
        assert state["overlays"][school["id"]]["osp.after_school_until"]["value"] == "18:00"


def test_turn_writes_one_traceable_log_line(monkeypatch, tmp_path):
    monkeypatch.setenv("GS_STATE_PATH", str(tmp_path / "state.json"))
    from fastapi.testclient import TestClient

    from app import app

    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    logger = logging.getLogger("gs.turn")
    logger.addHandler(handler)
    try:
        response = TestClient(app).post(
            "/api/turn", json={"message": "Middle school in Jacksonville with STEM and after-school care."}
        )
    finally:
        logger.removeHandler(handler)
    assert response.status_code == 200
    body = response.json()
    assert response.headers["X-Trace-Id"] == body["trace_id"]
    lines = [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]
    line = next(row for row in lines if row.get("trace_id") == body["trace_id"])
    assert line["event"] == "turn"
    assert line["session_id"] == body["session_id"]
    needs = {c.get("need") for c in line["criteria"]}
    assert {"stem", "after_care"} <= needs
    assert line["searches"], "every search the turn ran is logged"
    query = line["searches"][-1]["query"]
    assert {"term": {"city_untokenized": "jacksonville"}} in query["query"]["bool"]["filter"]
    assert "duration_ms" in line


def test_opensearch_query_has_hard_filters_and_knn():
    criteria = [
        Criterion(id="l", text="", kind="location", value="Jacksonville"),
        Criterion(id="g", text="", kind="grade", value="m"),
        Criterion(id="n", text="stem", kind="need", need="stem", strength="require"),
    ]
    body = opensearch_client.query_body(criteria, "robotics club", [0.1] * 256)
    bool_query = body["query"]["bool"]
    assert {"term": {"level_codes": "m"}} in bool_query["filter"]
    assert any("knn" in clause for clause in bool_query["should"])
    assert observability.trim_vectors(body)["query"]["bool"]["should"][1]["knn"]["embedding"]["vector"] == "<vector dim=256>"


def test_school_missing_from_index_is_kept_and_logged(monkeypatch):
    criteria = [Criterion(id="l", text="", kind="location", value="Jacksonville")]
    schools = load_schools()
    expected = [s["id"] for s in schools if passes_hard_filters(s, criteria)]
    # Pretend the index only has the first school.
    monkeypatch.setattr(
        "search.engine.search_candidates",
        lambda c, q: ({expected[0]: 3.0}, {"opensearch": "on", "query": {}}),
    )
    observability.start_trace("test")
    found = search_schools(schools, load_programs(), criteria, "robotics", limit=None)
    trace = observability.emit()
    assert sorted(s["id"] for s in found) == sorted(expected)
    assert trace["searches"][0]["not_in_index"][0] in expected[1:]
