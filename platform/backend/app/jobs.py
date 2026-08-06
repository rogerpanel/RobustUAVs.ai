"""The job plane: parameterised runs executed off the request thread.

Structurally this is `backend/task_queue.py` from RobustIDPS.ai — an in-process
queue on a worker thread, durable state in the database, live progress in
memory, and a polling endpoint. That design is chosen over Celery for the same
reason it was there: it has no broker to deploy, which means a conference demo
has one fewer thing that can fail on the day.

What is new here is the **parameter/hyperparameter split**. A demo is only
persuasive if the audience can see which knob moved, so every runner declares
its two schemas separately:

    params        what the experiment IS      (theta grid, topology, mapping)
    hyperparams   how it was COMPUTED         (seeds, policies, tolerances)

The frontend renders them as two distinct panels. Varying a hyperparameter and
getting the same answer is a robustness claim; varying a parameter and getting
a different answer is a finding. Conflating them in one blob of JSON would make
that distinction invisible.
"""
from __future__ import annotations

import datetime as dt
import logging
import queue
import threading
import traceback
import uuid
from typing import Any, Callable

from .db import Run, SessionLocal, init_db

log = logging.getLogger("robustuavs.jobs")

# run_id -> {"progress": int, "message": str}. Supplements the DB so a polling
# client sees sub-second movement without a write per percent.
_progress: dict[str, dict] = {}
_cancel: set[str] = set()

_q: "queue.Queue[tuple[str, Callable, dict]]" = queue.Queue()
_worker: threading.Thread | None = None
_worker_lock = threading.Lock()


# --------------------------------------------------------------------------
# Runner registry
# --------------------------------------------------------------------------

class Runner:
    """One kind of run, with its two schemas and its execution function."""

    def __init__(self, kind: str, title: str, description: str,
                 params: dict, hyperparams: dict,
                 fn: Callable[..., Any], provenance: str = "simulation"):
        self.kind = kind
        self.title = title
        self.description = description
        self.params = params
        self.hyperparams = hyperparams
        self.fn = fn
        self.provenance = provenance

    def schema(self) -> dict:
        return {"kind": self.kind, "title": self.title,
                "description": self.description,
                "params": self.params, "hyperparams": self.hyperparams,
                "provenance": self.provenance}

    def defaults(self) -> tuple[dict, dict]:
        return ({k: v["default"] for k, v in self.params.items()},
                {k: v["default"] for k, v in self.hyperparams.items()})


RUNNERS: dict[str, Runner] = {}


def register(runner: Runner) -> Runner:
    RUNNERS[runner.kind] = runner
    return runner


# --------------------------------------------------------------------------
# Progress and cancellation, visible to a running function
# --------------------------------------------------------------------------

class Cancelled(Exception):
    """Raised inside a runner when the client cancels it."""


def report(run_id: str, progress: int, message: str = "") -> None:
    """Called from inside a runner. Also the cancellation checkpoint.

    Cancellation is cooperative: a runner that never reports progress cannot be
    cancelled. That is an acceptable trade for not killing threads mid-write.
    """
    if run_id in _cancel:
        raise Cancelled()
    _progress[run_id] = {"progress": max(0, min(int(progress), 100)),
                         "message": message}


def cancel(run_id: str) -> bool:
    _cancel.add(run_id)
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.run_id == run_id).first()
        if run and run.status == "queued":
            # Never started, so mark it terminal now rather than waiting for a
            # checkpoint that will never come.
            run.status, run.finished_at = "cancelled", dt.datetime.utcnow()
            db.commit()
            return True
        return bool(run and run.status == "running")
    finally:
        db.close()


# --------------------------------------------------------------------------
# Worker
# --------------------------------------------------------------------------

def _execute(run_id: str, fn: Callable, kwargs: dict) -> None:
    db = SessionLocal()
    started = dt.datetime.utcnow()
    try:
        run = db.query(Run).filter(Run.run_id == run_id).first()
        if run is None or run.status == "cancelled":
            return
        run.status, run.started_at = "running", started
        db.commit()

        result = fn(run_id=run_id, **kwargs)

        run = db.query(Run).filter(Run.run_id == run_id).first()
        run.status, run.result, run.progress = "done", result, 100
        run.message = "complete"
    except Cancelled:
        run = db.query(Run).filter(Run.run_id == run_id).first()
        if run:
            run.status, run.message = "cancelled", "cancelled by client"
    except Exception as exc:  # noqa: BLE001 - a failed run must not kill the worker
        log.exception("run %s failed", run_id)
        run = db.query(Run).filter(Run.run_id == run_id).first()
        if run:
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=6)}"
            run.message = str(exc)[:400]
    finally:
        run = db.query(Run).filter(Run.run_id == run_id).first()
        if run:
            run.finished_at = dt.datetime.utcnow()
            run.duration_s = round(
                (run.finished_at - (run.started_at or started)).total_seconds(), 3)
            db.commit()
        db.close()
        _cancel.discard(run_id)
        _progress.pop(run_id, None)


def _loop() -> None:
    while True:
        run_id, fn, kwargs = _q.get()
        try:
            _execute(run_id, fn, kwargs)
        finally:
            _q.task_done()


def start_worker() -> None:
    global _worker
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            init_db()
            _worker = threading.Thread(target=_loop, daemon=True,
                                       name="robustuavs-jobs")
            _worker.start()
            log.info("job worker started")


# --------------------------------------------------------------------------
# Submission and queries
# --------------------------------------------------------------------------

def submit(kind: str, params: dict, hyperparams: dict, label: str = "",
           session: str = "anon") -> dict:
    runner = RUNNERS.get(kind)
    if runner is None:
        raise KeyError(kind)

    # Merge over declared defaults so a client may send only what it changed —
    # and so an unknown key is rejected rather than silently ignored, which
    # would let a demo believe it varied something it did not.
    p_def, h_def = runner.defaults()
    unknown = (set(params) - set(p_def)) | (set(hyperparams) - set(h_def))
    if unknown:
        raise ValueError(f"unknown settings for '{kind}': {sorted(unknown)}")
    merged_p, merged_h = {**p_def, **params}, {**h_def, **hyperparams}

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    db = SessionLocal()
    try:
        row = Run(session=session, run_id=run_id, kind=kind, label=label or runner.title,
                  status="queued", params=merged_p, hyperparams=merged_h,
                  provenance=runner.provenance)
        db.add(row)
        db.commit()
        payload = row.to_dict()
    finally:
        db.close()

    start_worker()
    _q.put((run_id, runner.fn, {"params": merged_p, "hyperparams": merged_h}))
    return payload


def get(run_id: str) -> dict | None:
    db = SessionLocal()
    try:
        row = db.query(Run).filter(Run.run_id == run_id).first()
        if row is None:
            return None
        out = row.to_dict()
        live = _progress.get(run_id)
        if live and out["status"] == "running":
            out["progress"], out["message"] = live["progress"], live["message"]
        return out
    finally:
        db.close()


def recent(limit: int = 25, kind: str | None = None,
           session: str | None = None) -> list[dict]:
    """Most recent runs, scoped to one session when given.

    `session=None` means every run, which is what a maintainer inspecting the
    deployment wants. The HTTP layer always passes a session, so a visitor sees
    only their own.
    """
    db = SessionLocal()
    try:
        q = db.query(Run).order_by(Run.created_at.desc())
        if session:
            q = q.filter(Run.session == session)
        if kind:
            q = q.filter(Run.kind == kind)
        rows = q.limit(limit).all()
        out = []
        for r in rows:
            d = r.to_dict()
            live = _progress.get(r.run_id)
            if live and d["status"] == "running":
                d["progress"], d["message"] = live["progress"], live["message"]
            # The list view drops the result blob; a sweep result is large and
            # the client fetches it per-run.
            d.pop("result", None)
            out.append(d)
        return out
    finally:
        db.close()


def queue_status() -> dict:
    return {"queued": _q.qsize(),
            "worker_alive": bool(_worker and _worker.is_alive()),
            "in_flight": len(_progress),
            "runners": sorted(RUNNERS)}
