"""Persistence: SQLite for development, PostgreSQL for production.

Mirrors `backend/database.py` in RobustIDPS.ai — one SQLAlchemy declarative
base, one `DATABASE_URL` switching the driver, and `get_db()` as a FastAPI
dependency. The schema here is much smaller because this platform is
read-mostly: the only durable state is the record of runs, which must survive a
restart so a conference demo can be resumed rather than re-executed.

There is deliberately no User table. Authentication is bearer-token only with no
registration surface (see auth.py), so there is nothing to persist about a
caller.
"""
from __future__ import annotations

import datetime as dt
import os
from typing import Iterator

from sqlalchemy import (JSON, Column, DateTime, Float, Integer, String, Text,
                        create_engine)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./robustuavs.db")

# check_same_thread is a SQLite-only concern: the job runner touches the session
# from a worker thread. Postgres needs no equivalent.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True,
                       future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False,
                            expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Run(Base):
    """One parameterised execution: a sweep, a certification, or a composition.

    `params` and `hyperparams` are separated on purpose. Parameters describe
    *what the experiment is* (topology, delay mode, theta grid) and belong in
    the paper's method description; hyperparameters describe *how it was
    computed* (seeds, sample counts, tolerances) and belong in its
    reproducibility statement. Keeping them apart means a demo can vary one
    without implying it varied the other.
    """

    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(40), unique=True, index=True, nullable=False)
    kind = Column(String(40), nullable=False, index=True)
    # Which visitor submitted this. Not a credential -- see app/sessions.py.
    session = Column(String(64), default="anon", index=True)
    label = Column(String(200), default="")

    status = Column(String(20), default="queued", index=True)  # queued|running|done|failed|cancelled
    progress = Column(Integer, default=0)
    message = Column(String(400), default="")

    params = Column(JSON, default=dict)
    hyperparams = Column(JSON, default=dict)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)

    # Every run records where its numbers may be trusted from, so a result
    # pulled out of the DB months later still carries its evidence class.
    provenance = Column(String(30), default="simulation")

    created_at = Column(DateTime, default=dt.datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    duration_s = Column(Float, nullable=True)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id, "kind": self.kind, "label": self.label,
            "status": self.status, "progress": self.progress,
            "message": self.message, "params": self.params or {},
            "hyperparams": self.hyperparams or {}, "result": self.result,
            "error": self.error, "provenance": self.provenance,
            "created_at": _iso(self.created_at),
            "started_at": _iso(self.started_at),
            "finished_at": _iso(self.finished_at),
            "duration_s": self.duration_s,
        }


def _iso(v: dt.datetime | None) -> str | None:
    return v.isoformat() + "Z" if v else None


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    # SQLite created before `session` existed will not gain the column from
    # create_all, which only creates missing tables. One idempotent ALTER is
    # cheaper than a migration framework for a single additive column.
    try:
        with engine.begin() as conn:
            cols = {r[1] for r in conn.exec_driver_sql("PRAGMA table_info(runs)")}
            if cols and "session" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE runs ADD COLUMN session VARCHAR(64) DEFAULT 'anon'")
    except Exception:
        # Postgres path, or a backend without PRAGMA. create_all handles a
        # fresh database; an existing one is the operator's to migrate.
        pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def backend_name() -> str:
    return "postgresql" if DATABASE_URL.startswith("postgres") else "sqlite"
