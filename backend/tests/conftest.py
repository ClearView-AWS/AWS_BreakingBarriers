"""Shared test setup. Rate limits are off unless a test turns them on (test_security.py)."""

import pytest

import security


@pytest.fixture(autouse=True)
def _no_rate_limits(monkeypatch):
    monkeypatch.delenv("GS_STAFF_KEY", raising=False)
    monkeypatch.setattr(security.limiter, "enabled", False)
    security.limiter.reset()
    yield
    security.limiter.reset()
