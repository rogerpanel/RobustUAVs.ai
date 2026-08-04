"""RobustUAVs.ai control plane.

A read-mostly API over the committed research results, the model registry, and
the certificate engine, plus the copilot. Design authority:
docs/platform_architecture.md.

Run:
    uvicorn app.main:app --reload --port 8000     # from platform/backend/
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import auth, copilot, db, registry, results, runners  # noqa: F401
from . import jobs
from .cache import cache
from .llm import provider_status

app = FastAPI(
    title="RobustUAVs.ai",
    version="0.1.0",
    description="End-to-end UAV security: cross-layer benchmark and composed "
                "network-to-navigation certificate.",
)

# The mobile client is served from a different origin during development and
# from the same origin in production behind Caddy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081", "http://localhost:19006",
                   "https://robustuavs.ai", "https://www.robustuavs.ai"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    jobs.start_worker()


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "models": len(registry.REGISTRY),
        "copilot_tools": len(copilot.TOOLS),
        "result_files": len(results.available()),
        "providers": provider_status(),
        "database": db.backend_name(),
        "cache": cache.status(),
        "auth": auth.status(),
        "jobs": jobs.queue_status(),
    }


# -------------------------------------------------------------------- runs --

class RunRequest(BaseModel):
    kind: str
    label: str = ""
    # Two dicts, never one. Which of the two a value lives in is the
    # difference between "we found something" and "it is robust to how we
    # computed it", and the API must not blur that.
    params: dict = {}
    hyperparams: dict = {}


@app.get("/api/runners", tags=["runs"])
def api_runners() -> dict:
    return {"runners": runners.schemas()}


@app.post("/api/runs", tags=["runs"])
def api_submit(req: RunRequest, _=Depends(auth.require_write)) -> dict:
    try:
        return jobs.submit(req.kind, req.params, req.hyperparams, req.label)
    except KeyError:
        raise HTTPException(404, {"error": f"no runner '{req.kind}'",
                                  "available": sorted(jobs.RUNNERS)})
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/runs", tags=["runs"])
def api_runs(limit: int = Query(25, ge=1, le=200),
             kind: str | None = Query(None)) -> dict:
    return {"runs": jobs.recent(limit=limit, kind=kind)}


@app.get("/api/runs/{run_id}", tags=["runs"])
def api_run(run_id: str) -> dict:
    run = jobs.get(run_id)
    if run is None:
        raise HTTPException(404, f"no run '{run_id}'")
    return run


@app.post("/api/runs/{run_id}/cancel", tags=["runs"])
def api_cancel(run_id: str, _=Depends(auth.require_write)) -> dict:
    if jobs.get(run_id) is None:
        raise HTTPException(404, f"no run '{run_id}'")
    return {"run_id": run_id, "cancelling": jobs.cancel(run_id)}


# ---------------------------------------------------------------- registry --

@app.get("/api/models", tags=["registry"])
def api_models(category: str | None = Query(None)) -> dict:
    return {"categories": registry.categories(),
            "models": registry.list_models(category)}


@app.get("/api/models/{model_id}", tags=["registry"])
def api_model(model_id: str):
    m = registry.get_model(model_id)
    if m is None:
        raise HTTPException(404, f"no model '{model_id}'")
    return m


# ----------------------------------------------------------------- results --

_RESULT_ENDPOINTS = {
    "operating-curve": results.operating_curve,
    "operating-curve-perseed": results.operating_curve_perseed,
    "certified-floor": results.certified_floor,
    "certified-window": results.certified_window,
    "delta-calibration": results.whelan_calibration,
    "mcr-anchor": results.mcr_anchor,
    "ingest-stats": results.ingest_stats,
    "provenance": results.provenance_distribution,
    "dominance": results.wilcoxon,
    "pairings": results.pairings,
}


@app.get("/api/results", tags=["results"])
def api_results_index() -> dict:
    return {"endpoints": sorted(_RESULT_ENDPOINTS),
            "files": results.available()}


@app.get("/api/results/{name}", tags=["results"])
def api_result(name: str) -> dict:
    fn = _RESULT_ENDPOINTS.get(name)
    if fn is None:
        raise HTTPException(404, {"error": f"no result '{name}'",
                                  "available": sorted(_RESULT_ENDPOINTS)})
    try:
        return {"name": name, "rows": fn()}
    except results.ResultUnavailable as exc:
        # 503, not 404: the endpoint exists, the data has not been produced
        # in this deployment. The distinction matters to the client.
        raise HTTPException(503, {"error": str(exc), "unavailable": exc.name})


# ------------------------------------------------------------ certificates --

class StalenessRequest(BaseModel):
    theta_s: float
    n_malicious_hops: int = 2
    margin_m: float = 10.0
    # The result is parametric in this; the client must be able to flip it,
    # and the response always echoes which mapping produced the verdict.
    mapping: str = "ekf"


@app.post("/api/certify/staleness", tags=["certificates"])
def api_certify_staleness(req: StalenessRequest) -> dict:
    out = copilot.call("certify_staleness", **req.model_dump())
    if "error" in out:
        raise HTTPException(400, out)
    return out


# ----------------------------------------------------------------- copilot --

class Ask(BaseModel):
    question: str


@app.get("/api/copilot/tools", tags=["copilot"])
def api_tools() -> dict:
    return {"tools": copilot.TOOLS, "count": len(copilot.TOOLS)}


@app.post("/api/copilot/tool/{name}", tags=["copilot"])
def api_tool(name: str, params: dict | None = None) -> dict:
    out = copilot.call(name, **(params or {}))
    if "error" in out and "unknown tool" in str(out.get("error", "")):
        raise HTTPException(404, out)
    return out


@app.post("/api/copilot/ask", tags=["copilot"])
async def api_ask(body: Ask) -> dict:
    if not body.question.strip():
        raise HTTPException(400, "question must not be empty")
    return await copilot.answer(body.question)
