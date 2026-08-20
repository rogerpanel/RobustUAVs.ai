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

from . import auth, copilot, db, registry, results, runners, sessions  # noqa: F401
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
def health(session: str = Depends(sessions.session_id)) -> dict:
    return {
        "session": session,
        "rate": sessions.rate_state(session),
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
def api_submit(req: RunRequest, _=Depends(auth.require_write),
               session: str = Depends(sessions.session_id)) -> dict:
    try:
        return jobs.submit(req.kind, req.params, req.hyperparams, req.label,
                           session=session)
    except KeyError:
        raise HTTPException(404, {"error": f"no runner '{req.kind}'",
                                  "available": sorted(jobs.RUNNERS)})
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/runs", tags=["runs"])
def api_runs(limit: int = Query(25, ge=1, le=200),
             kind: str | None = Query(None),
             session: str = Depends(sessions.session_id)) -> dict:
    # Scoped to the caller. Two visitors driving the platform at once each see
    # their own history rather than a shared stream.
    return {"runs": jobs.recent(limit=limit, kind=kind, session=session),
            "session": session}


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
    # A visitor may supply their own provider key rather than spend the
    # deployment's shared allowance. It is used for that one request and never
    # stored, logged or echoed back.
    provider: str | None = None
    api_key: str | None = None


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
async def api_ask(body: Ask,
                  session: str = Depends(sessions.session_id)) -> dict:
    if not body.question.strip():
        raise HTTPException(400, "question must not be empty")
    # Only the shared key is metered. A visitor spending their own key is not
    # consuming a resource this deployment pays for.
    if not body.api_key:
        sessions.check_rate(session, "llm")
    return await copilot.answer(body.question,
                                provider=body.provider, api_key=body.api_key)


# ------------------------------------------------- UAV / Aerial Defense --
#
# The Chapter 6 operator surface, ported from robustidps.ai's `uav` plugin.
# Reads live from the committed results, so a page whose result file is absent
# returns 503 through the same ResultUnavailable path as everything else
# rather than inventing a number to fill the panel.

from . import uav  # noqa: E402


@app.get("/api/uav/overview", tags=["uav"])
def api_uav_overview() -> dict:
    return uav.overview()


@app.get("/api/uav/ew-bench/curves", tags=["uav"])
def api_uav_curves() -> dict:
    return uav.ew_curves()


@app.get("/api/uav/ew-bench/operating-point", tags=["uav"])
def api_uav_operating_point(js_db: float = Query(20.0, ge=0, le=40)) -> dict:
    return uav.ew_operating_point(js_db)


@app.get("/api/uav/certificates", tags=["uav"])
def api_uav_certificates() -> dict:
    return uav.certificates()


@app.get("/api/uav/swarm/snapshots", tags=["uav"])
def api_uav_swarm() -> dict:
    return uav.swarm_snapshots()


@app.get("/api/uav/gnss/sky", tags=["uav"])
def api_uav_gnss(seed: int | None = None,
                 n_spoofed: int = Query(2, ge=0, le=12),
                 spoof_strength: float = Query(0.82, ge=0.0, le=1.0),
                 js_db: float = Query(0.0, ge=0.0, le=40.0),
                 n_sats: int = Query(9, ge=4, le=12)) -> dict:
    return uav.gnss_sky(seed, n_spoofed, spoof_strength, js_db, n_sats)


@app.get("/api/uav/fleet/catalog", tags=["uav"])
def api_uav_fleet_catalog() -> dict:
    return uav.attack_catalogue_fleet()


class GnssRun(BaseModel):
    n_sats: int = 9
    n_spoofed: int = 2
    js_db: float = 0.0
    mapping: str = "ekf"
    detect_threshold_m: float = 8.0
    dt_s: float = 1.0


@app.get("/api/uav/gnss/run", tags=["uav"])
def api_gnss_run(session: str = Depends(sessions.session_id)) -> dict:
    return uav.gnss_run_state(session)


@app.post("/api/uav/gnss/run/step", tags=["uav"])
def api_gnss_run_step(body: GnssRun,
                      session: str = Depends(sessions.session_id)) -> dict:
    return uav.gnss_run_step(session, body.dt_s)


@app.post("/api/uav/gnss/run/reset", tags=["uav"])
def api_gnss_run_reset(body: GnssRun,
                       session: str = Depends(sessions.session_id)) -> dict:
    return uav.gnss_run_reset(session, body.n_sats, body.n_spoofed, body.js_db,
                              body.mapping, body.detect_threshold_m)


@app.get("/api/uav/perception/catalog", tags=["uav"])
def api_uav_attack_catalog() -> dict:
    return uav.attack_catalog()


@app.get("/api/uav/dossier", tags=["uav"])
def api_uav_dossier() -> dict:
    return uav.dossier()


class MissionPlan(BaseModel):
    text: str
    format: str = "text"


@app.post("/api/uav/mission-plan/review", tags=["uav"])
def api_uav_mission_plan(body: MissionPlan) -> dict:
    return uav.review_mission_plan(body.text, body.format)


class FleetStep(BaseModel):
    session: str = "demo"
    attacks: dict[str, str] | None = None
    js_db: float | None = None
    dt_s: float = 1.0
    corridor_m: float | None = None
    mapping: str | None = None


class FleetReset(BaseModel):
    session: str = "demo"
    n: int = 4
    corridor_m: float = 10.0
    mapping: str = "ekf"
    js_db: float = 10.0


@app.get("/api/uav/fleet", tags=["uav"])
def api_uav_fleet(session: str = Depends(sessions.session_id)) -> dict:
    # Keyed on the visitor, not on a shared "demo" string: two people flying
    # the fleet at once were previously stepping the same simulation.
    return uav.fleet_state(session)


@app.post("/api/uav/fleet/step", tags=["uav"])
def api_uav_fleet_step(body: FleetStep,
                       session: str = Depends(sessions.session_id)) -> dict:
    return uav.fleet_step(session, body.attacks, body.js_db, body.dt_s,
                          body.corridor_m, body.mapping)


@app.post("/api/uav/fleet/reset", tags=["uav"])
def api_uav_fleet_reset(body: FleetReset,
                        session: str = Depends(sessions.session_id)) -> dict:
    return uav.fleet_reset(session, body.n, body.corridor_m,
                           body.mapping, body.js_db)


# ------------------------------------------------------------ evaluation --
#
# The analysis surface: robustness, ablations, ROC, statistics, calibration,
# federated learning. Every endpoint reads committed results; `calibration`
# deliberately reports that it cannot be computed and says exactly what input
# is missing, rather than returning a surrogate curve.

from . import evaluation  # noqa: E402


@app.get("/api/eval/robustness", tags=["evaluation"])
def api_eval_robustness() -> dict:
    return evaluation.robustness()


@app.get("/api/eval/ablations", tags=["evaluation"])
def api_eval_ablations() -> dict:
    return evaluation.ablations()


@app.get("/api/eval/roc", tags=["evaluation"])
def api_eval_roc() -> dict:
    return evaluation.roc()


@app.get("/api/eval/statistics", tags=["evaluation"])
def api_eval_statistics() -> dict:
    return evaluation.statistics()


@app.get("/api/eval/calibration", tags=["evaluation"])
def api_eval_calibration() -> dict:
    return evaluation.calibration()


@app.get("/api/eval/federated", tags=["evaluation"])
def api_eval_federated() -> dict:
    return evaluation.federated()


@app.get("/api/eval/interface", tags=["evaluation"])
def api_eval_interface() -> dict:
    """Is gamma a constant? The interface characterisation campaign's answer."""
    return evaluation.interface_stability()


@app.get("/api/eval/mission-distribution", tags=["evaluation"])
def api_eval_mission_distribution() -> dict:
    """What MCR's dependence on the mission distribution actually costs."""
    return evaluation.mission_distribution()


# ---------------------------------------------------------------- upload --
#
# Bring-your-own-data. The file is streamed and sampled rather than loaded:
# a 1 GB CSV read whole is several GB resident, and this host has already been
# taken down once by a memory spike. Nothing is retained.

from fastapi import File, UploadFile  # noqa: E402

from . import upload as upload_mod  # noqa: E402


@app.post("/api/upload/analyse", tags=["upload"])
async def api_upload_analyse(file: UploadFile = File(...),
                             session: str = Depends(sessions.session_id)) -> dict:
    sessions.check_rate(session, "upload")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1 << 20)          # 1 MiB at a time
        if not chunk:
            break
        total += len(chunk)
        if total > upload_mod.MAX_BYTES:
            chunks.append(chunk[:upload_mod.MAX_BYTES - (total - len(chunk))])
            break
        chunks.append(chunk)
    name = file.filename or "upload.csv"
    if not name.lower().endswith((".csv", ".tsv", ".txt")):
        raise HTTPException(
            415, f"'{name}': only delimited text is supported today. "
                 "ULOG, PCAP and Parquet are the obvious next formats and are "
                 "not implemented — see docs/idps_transfer_map.md.")
    return upload_mod.analyse_csv(iter(chunks), filename=name)


class FlyRequest(BaseModel):
    summary: dict
    corridor_m: float = 10.0
    mapping: str = "ekf"
    n_malicious_hops: int = 2


class CompareRequest(BaseModel):
    summaries: list[dict]
    corridor_m: float = 10.0
    mapping: str = "ekf"
    n_malicious_hops: int = 2


@app.post("/api/upload/compare", tags=["upload"])
def api_upload_compare(body: CompareRequest) -> dict:
    if len(body.summaries) > 4:
        raise HTTPException(400, "at most four datasets can be compared at once")
    return upload_mod.compare(body.summaries, body.corridor_m, body.mapping,
                              body.n_malicious_hops)


@app.post("/api/upload/fly", tags=["upload"])
def api_upload_fly(body: FlyRequest) -> dict:
    return upload_mod.fly(body.summary, body.corridor_m, body.mapping,
                          body.n_malicious_hops)
