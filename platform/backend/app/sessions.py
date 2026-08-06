"""Per-visitor session isolation, without accounts.

The artifact must be usable by several people at once — a reviewer in one
timezone, a conference audience in another — without one visitor's fleet, runs
or uploads appearing in another's. Until the paper clears double-blind review
there is deliberately no login, so the isolation cannot rest on identity.

The mechanism is a client-generated opaque id sent as `X-Session-Id`. It is not
a credential and is not treated as one: it authenticates nothing, and anyone who
guesses another id sees that session's runs. That is an acceptable exposure for
a public artifact whose entire dataset is already published, and it is exactly
the property that must NOT be relied on once accounts exist. The header is
therefore validated for shape only, and everything keyed by it is demo state —
never anything private.

What this does buy, which matters:

  * two visitors driving the fleet demo no longer fight over one simulation
  * the run list shows your runs, not a stranger's
  * an uploaded file's summary cannot leak into another visitor's copilot
  * per-session rate limiting has something to count against
"""
from __future__ import annotations

import re
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException

# 8-64 chars of url-safe id. Long enough not to collide by accident, short
# enough to log without noise. Shape only -- no attempt to prove provenance.
_VALID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

ANONYMOUS = "anon"


def session_id(x_session_id: str | None = Header(default=None)) -> str:
    """FastAPI dependency: the caller's session, or a shared anonymous bucket.

    A missing header is allowed rather than rejected. `curl` against this API is
    a supported way to use the artifact, and forcing every script to invent a
    session id would make the simple case worse to serve an isolation property
    scripts do not need.
    """
    if x_session_id is None:
        return ANONYMOUS
    if not _VALID.match(x_session_id):
        raise HTTPException(400, "X-Session-Id must be 8-64 url-safe characters")
    return x_session_id


# ------------------------------------------------------------ rate limits --
#
# The deployment can be configured with the maintainer's own Anthropic key so
# that visitors get narrated answers without supplying one. That is a standing
# invitation to burn someone else's credits, so calls that can reach a paid
# provider are counted per session and per hour.
#
# In-process and therefore per-worker: with several uvicorn workers the real
# ceiling is the limit times the worker count. Stated rather than hidden. The
# fix when it matters is Redis, which this deployment already optionally has.

_BUCKETS: dict[tuple[str, str], deque] = defaultdict(deque)

LIMITS = {
    "llm": (30, 3600),        # 30 narrated answers per hour per session
    "upload": (20, 3600),     # 20 file analyses per hour per session
}


def check_rate(session: str, bucket: str) -> None:
    """Raise 429 when a session has exhausted its allowance for `bucket`."""
    limit, window = LIMITS.get(bucket, (60, 3600))
    now = time.monotonic()
    q = _BUCKETS[(session, bucket)]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        retry = int(window - (now - q[0])) + 1
        raise HTTPException(
            429,
            detail={
                "error": f"rate limit: {limit} {bucket} calls per hour per session",
                "retry_after_s": retry,
                "note": "Supply your own provider key in the copilot's key menu "
                        "to bypass the shared allowance.",
            },
            headers={"Retry-After": str(retry)},
        )
    q.append(now)


def rate_state(session: str) -> dict:
    now = time.monotonic()
    out = {}
    for bucket, (limit, window) in LIMITS.items():
        q = _BUCKETS[(session, bucket)]
        used = sum(1 for ts in q if now - ts <= window)
        out[bucket] = {"used": used, "limit": limit, "window_s": window}
    return out


def reset_all() -> None:
    """Test hook."""
    _BUCKETS.clear()
