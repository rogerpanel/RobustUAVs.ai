"""The kernel as a local HTTP service, so it runs in its own process (and, deployed
properly, as its own user) rather than inside the agent it guards.

    ACTFILTER_POLICY=policy.json ACTFILTER_AUDIT=audit.jsonl \\
        uvicorn actfilter.service:app --host 127.0.0.1 --port 8765

    POST /v1/decide   {"session": "...", "tool": "...", "args": {...}}  -> decision
    POST /v1/observe  {"session": "...", "model": "...", "observation": {...}}
    GET  /v1/health   GET /v1/stats   GET /v1/audit/verify

Bind it to loopback or a unix socket only: it trusts whoever can reach it to be the
host's hook, not the model.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import audit as auditmod
from .core import Reject
from .policy import load


class DecideIn(BaseModel):
    session: str = Field(default="default", max_length=200)
    tool: str = Field(max_length=200)
    args: Any = None


class ObserveIn(BaseModel):
    session: str = Field(default="default", max_length=200)
    model: str
    observation: dict


def create_app(policy_path: str, audit_path: str | None = None) -> FastAPI:
    log = auditmod.AuditLog(audit_path) if audit_path else None
    kernel = load(policy_path, log)
    app = FastAPI(title="actfilter", version="0.1")

    @app.get("/v1/health")
    def health():
        return {"ok": True, "models": sorted(kernel.models), "tools": sorted(kernel.tools),
                "passthrough": sorted(kernel.passthrough)}

    @app.post("/v1/decide")
    def decide(body: DecideIn):
        return kernel.decide(body.session, body.tool, body.args if body.args is not None else {}).to_dict()

    @app.post("/v1/observe")
    def observe(body: ObserveIn):
        try:
            return kernel.observe(body.session, body.model, body.observation)
        except Reject as e:
            raise HTTPException(422, str(e))

    @app.get("/v1/stats")
    def stats():
        return {"decisions": dict(kernel.stats)}

    @app.get("/v1/audit/verify")
    def verify():
        if not audit_path:
            return {"ok": True, "records": 0, "broken_at": None, "note": "no audit log configured"}
        return auditmod.verify(audit_path)

    app.state.kernel = kernel
    return app


app = (create_app(os.environ["ACTFILTER_POLICY"], os.environ.get("ACTFILTER_AUDIT"))
       if os.environ.get("ACTFILTER_POLICY") else None)
