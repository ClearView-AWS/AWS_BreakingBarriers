"""Who may do what on the public API, and how often.

The product has no login, so anyone can search, chat, and use "Have AI call" from the browser.
What a stranger with curl should not be able to do freely:

- Staff actions (answering for a school, opting a school out of calls, replying to the inbox,
  posting as school staff) need the staff code: `X-Staff-Key` must match GS_STAFF_KEY.
  Infra stores it in Secrets Manager — that path is for forging school-reported facts, not for dialing.
- Every route that runs a model, places a call or writes state is rate limited per client IP
  and in total, so a terminal script can't drain the Bedrock / Connect budget or spam dials.

With GS_STAFF_KEY unset (local dev, tests) every caller counts as staff.
"""

from __future__ import annotations

import hmac
import os
import threading
import time
from collections import deque

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

STAFF_HEADER = "x-staff-key"
MAX_BODY_BYTES = 64 * 1024

# (per client IP, all clients together) requests per window, by route group.
LIMITS: dict[str, tuple[int, int, int]] = {
    # group: (per_ip, global, window_seconds)
    "ai": (30, 300, 60),  # routes that may call Bedrock or Translate
    "call": (3, 20, 3600),  # outbound phone calls
    "write": (30, 300, 60),  # community, FAQ and inbox writes
}

_AI_ROUTES = {"/api/chat", "/api/turn", "/api/assist", "/api/ui-text"}


def staff_key() -> str | None:
    return os.environ.get("GS_STAFF_KEY") or None


def is_staff(request: Request) -> bool:
    key = staff_key()
    if not key:
        return True
    given = request.headers.get(STAFF_HEADER) or ""
    return hmac.compare_digest(given.encode(), key.encode())


def require_staff(request: Request) -> None:
    if not is_staff(request):
        raise HTTPException(status_code=401, detail="Staff code required.")


def client_ip(request: Request) -> str:
    """The viewer's address. CloudFront sets CloudFront-Viewer-Address; the ALB only accepts
    CloudFront (infra), so a caller can't forge it by skipping CloudFront."""
    viewer = request.headers.get("cloudfront-viewer-address")
    if viewer:
        # "203.0.113.7:46532" or "[2001:db8::1]:46532"
        return viewer.rsplit(":", 1)[0].strip("[]")
    forwarded = [part.strip() for part in (request.headers.get("x-forwarded-for") or "").split(",") if part.strip()]
    if forwarded:
        # The ALB appends the address it saw; anything to its left is client-supplied.
        return forwarded[-1]
    return request.client.host if request.client else "unknown"


def route_group(method: str, path: str) -> str | None:
    if method != "POST":
        return None
    if path in _AI_ROUTES:
        return "ai"
    if path == "/api/calls":
        return "call"
    if path.startswith(("/api/community/", "/api/faq", "/api/inbox/", "/api/schools/")):
        return "write"
    return None


class RateLimiter:
    """Sliding-window counts in process memory. One Fargate task serves the demo, so
    per-process counts are the real counts; with more tasks each enforces its own share."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()
        self.enabled = os.environ.get("GS_RATE_LIMITS", "1") != "0"

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def allow(self, group: str, ip: str, staff: bool = False) -> bool:
        """Count one request. Staff skip the per-IP limit but still count toward the total."""
        if not self.enabled:
            return True
        per_ip, total, window = LIMITS[group]
        now = time.monotonic()
        keys = [((group, "*"), total)] + ([] if staff else [((group, ip), per_ip)])
        with self._lock:
            windows = []
            for key, limit in keys:
                hits = self._hits.setdefault(key, deque())
                while hits and now - hits[0] >= window:
                    hits.popleft()
                if len(hits) >= limit:
                    return False  # refused requests use no budget
                windows.append(hits)
            for hits in windows:
                hits.append(now)
        return True


limiter = RateLimiter()


async def guard(request: Request, call_next):
    """Body-size cap and rate limits for every request. Registered in app.py."""
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse({"error": "Request too large."}, status_code=413)
    group = route_group(request.method, request.url.path)
    if group and not limiter.allow(group, client_ip(request), staff=staff_key() is not None and is_staff(request)):
        return JSONResponse({"error": "Too many requests. Try again in a minute."}, status_code=429)
    return await call_next(request)
