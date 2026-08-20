"""Read-only access to the committed research results.

The control plane is stateless with respect to research numbers: everything it
serves traces to a file under `results/`, never to a constant typed into the
API. If a file is absent the endpoint says so rather than interpolating, which
is the same discipline the papers apply to pending data.
"""
from __future__ import annotations

import csv
import functools
import json
from pathlib import Path
from typing import Any, Optional

# platform/backend/app/results.py -> repo root
REPO = Path(__file__).resolve().parents[3]
RESULTS = REPO / "results"


class ResultUnavailable(Exception):
    """A result file the caller asked for is not present in this checkout."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(
            f"'{name}' is not available in this checkout. It is produced by the "
            f"experiment harness; see PENDING_ON_DATA.md if it is data-gated."
        )


def _path(name: str) -> Path:
    p = (RESULTS / name).resolve()
    # Refuse traversal: a request must not be able to read outside results/.
    if not str(p).startswith(str(RESULTS)):
        raise ResultUnavailable(name)
    return p


@functools.lru_cache(maxsize=64)
def read_csv(name: str) -> list[dict[str, Any]]:
    p = _path(name)
    if not p.exists():
        raise ResultUnavailable(name)
    with p.open() as fh:
        rows = list(csv.DictReader(fh))
    return [{k: _coerce(v) for k, v in r.items()} for r in rows]


@functools.lru_cache(maxsize=16)
def read_jsonl(name: str) -> list[dict]:
    p = _path(name)
    if not p.exists():
        raise ResultUnavailable(name)
    with p.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _coerce(v: Optional[str]) -> Any:
    """CSV gives strings; give the client typed JSON instead."""
    if v is None or v == "":
        return None
    for cast in (int, float):
        try:
            return cast(v)
        except (TypeError, ValueError):
            continue
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    return v


def available() -> list[str]:
    if not RESULTS.exists():
        return []
    return sorted(p.name for p in RESULTS.iterdir() if p.is_file())


# --- named accessors, so routers and copilot tools agree on filenames -------

def operating_curve() -> list[dict]:
    return read_csv("theta_operating_curve.csv")


def operating_curve_perseed() -> list[dict]:
    return read_csv("theta_operating_curve_perseed.csv")


def certified_floor() -> list[dict]:
    return read_csv("certified_floor_vs_theta.csv")


def certified_window() -> list[dict]:
    return read_csv("certified_operating_window.csv")


def ingest_stats() -> list[dict]:
    return read_csv("ingest_stats.csv")


def provenance_distribution() -> list[dict]:
    return read_csv("provenance_distribution.csv")


def whelan_calibration() -> list[dict]:
    return read_csv("whelan_delta_calibration.csv")


def gamma_campaign_bins() -> list[dict]:
    return read_csv("gamma_campaign_bins.csv")


def gamma_campaign_model() -> list[dict]:
    return read_csv("gamma_campaign_model.csv")


def gamma_stability() -> list[dict]:
    return read_csv("gamma_stability.csv")


def mission_distribution() -> list[dict]:
    return read_csv("mission_distribution.csv")


def mcr_anchor() -> list[dict]:
    return read_csv("ewbench_mcr_anchor.csv")


def wilcoxon() -> list[dict]:
    return read_csv("stats_wilcoxon.csv")


def pairings() -> list[dict]:
    return read_jsonl("pairings_poc.jsonl")
