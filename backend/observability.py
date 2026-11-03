"""One structured log line per request, so a wrong result can be traced.

``start_trace`` opens a trace for the request, code anywhere in the turn adds
to it with ``record``, and ``emit`` writes it as a single JSON line on stdout.
On Fargate, stdout goes to CloudWatch Logs (log group ``/gs-guided/api``), where
Logs Insights can filter by ``trace_id`` or ``session_id``.

What a line holds: the parent's message, the criteria the turn extracted, the
OpenSearch query that was sent (vectors trimmed), how many hits came back, the
ranked school ids, and whether Bedrock was used or fell back.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from typing import Any

from runtime_config import TURN_LOG_ENABLED

_TRACE: contextvars.ContextVar[dict | None] = contextvars.ContextVar("gs_trace", default=None)

_logger = logging.getLogger("gs.turn")
if not _logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def start_trace(event: str, **fields: Any) -> dict:
    trace = {"event": event, "trace_id": uuid.uuid4().hex[:16], "_start": time.perf_counter(), **fields}
    _TRACE.set(trace)
    return trace


def current() -> dict | None:
    return _TRACE.get()


def record(key: str, value: Any) -> None:
    trace = _TRACE.get()
    if trace is not None:
        trace[key] = value


def append(key: str, value: Any) -> None:
    trace = _TRACE.get()
    if trace is not None:
        trace.setdefault(key, []).append(value)


def trim_vectors(value: Any) -> Any:
    """Replace long float lists (embeddings) with their length, so log lines stay readable."""
    if isinstance(value, dict):
        return {k: trim_vectors(v) for k, v in value.items()}
    if isinstance(value, list):
        if len(value) > 16 and all(isinstance(x, (int, float)) for x in value):
            return f"<vector dim={len(value)}>"
        return [trim_vectors(v) for v in value]
    return value


def emit(**fields: Any) -> dict | None:
    trace = _TRACE.get()
    if trace is None:
        return None
    trace.update(fields)
    start = trace.pop("_start", None)
    if start is not None:
        trace["duration_ms"] = round((time.perf_counter() - start) * 1000, 1)
    _TRACE.set(None)
    if TURN_LOG_ENABLED:
        _logger.info(json.dumps(trace, default=str))
    return trace
