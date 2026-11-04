"""Shared helpers for tests that need a completed (post-brief) search."""

from __future__ import annotations

from pipeline import turn


def search_turn(state: dict, payload: dict):
    """Run a turn; if the brief gate holds results back, skip to results once.

    Route/extract engine steps are taken from the first (understanding) turn; explain
    comes from the search turn.
    """
    response = turn(state, payload)
    if any(block.type == "results" for block in response.blocks):
        return response
    second = turn(state, {"session_id": response.session_id, "event": "skip_to_results", "action": "refresh"})
    first_engine = response.engine
    second_engine = second.engine
    merged = second_engine.model_copy(
        update={
            "route": first_engine.route or second_engine.route,
            "extract": first_engine.extract or second_engine.extract,
            "errors": list(first_engine.errors) + [err for err in second_engine.errors if err not in first_engine.errors],
        }
    )
    return second.model_copy(update={"engine": merged})


def results_payload(response) -> dict:
    return next(block.payload for block in response.blocks if block.type == "results")
