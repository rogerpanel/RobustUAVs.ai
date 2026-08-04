"""Bearer-token auth with no registration surface.

The requirement is explicit: no login or register component yet. So this is
deliberately *not* the user/password/JWT stack RobustIDPS.ai carries. It is the
smallest thing that protects the one operation worth protecting — spending CPU
by launching a run — while leaving the read-only research surface open, because
that surface is the public artifact for a paper and gating it would defeat its
purpose.

Two modes, chosen by whether `API_TOKENS` is set:

  unset  -> OPEN. Every endpoint is public, writes included. Correct for a
            laptop demo and for a reviewer running the artifact locally.
  set     -> PROTECTED. Reads stay public; anything that launches or cancels a
            run requires `Authorization: Bearer <token>`.

The mode is reported by /api/health so it can never be a silent assumption —
a deployment that believes it is protected and is not should be able to see so
at a glance.
"""
from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import Header, HTTPException


def _tokens() -> set[str]:
    raw = os.getenv("API_TOKENS", "")
    return {t.strip() for t in raw.split(",") if t.strip()}


def is_open() -> bool:
    return not _tokens()


def mode() -> str:
    return "open" if is_open() else "bearer"


def status() -> dict:
    return {
        "mode": mode(),
        "writes_protected": not is_open(),
        "reads_public": True,
        "note": ("No API_TOKENS configured: every endpoint is public, including "
                 "run submission. Set API_TOKENS to a comma-separated list to "
                 "require a bearer token for writes."
                 if is_open() else
                 "Run submission and cancellation require a bearer token; the "
                 "read-only research surface stays public."),
    }


def require_write(authorization: Optional[str] = Header(default=None)) -> str:
    """FastAPI dependency guarding operations that consume resources."""
    tokens = _tokens()
    if not tokens:
        return "anonymous"

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            401, "This deployment requires a bearer token for write operations.",
            headers={"WWW-Authenticate": "Bearer"})

    presented = authorization.split(" ", 1)[1].strip()
    # compare_digest against each configured token: constant-time, so a caller
    # cannot learn a valid prefix from response timing.
    for t in tokens:
        if hmac.compare_digest(presented, t):
            return f"token:{t[:4]}…"
    raise HTTPException(403, "Invalid bearer token.")
