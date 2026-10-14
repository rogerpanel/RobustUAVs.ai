"""R3 -- certificate process driven by measured GNSS staleness traces.

Same interface as CertificateProcess (`rho()`, `step(dt, jam_mask)`). Each
aircraft replays, from a random offset and cyclically, a GNSS staleness trace
extracted from a measured PX4 flight (results/r3_staleness_traces.csv, written
by r3_extract_traces.py). This replaces the Poisson jamming and sensor-fault
onsets of the synthetic process.

Relay channel. The runbook asked for per-packet residual time series from the
hop ledger. The ledger holds one packet per simulation run (2,496 runs, 8 per
scenario cell), so there is no temporal sequence to replay. The relay channel
therefore keeps the synthetic episode model: assumed onset rate, measured
jump magnitudes (sum of H undetected residuals) and measured benign floor.
Spatial jammers still force dead reckoning on top (as in E2), so common-cause
dependence can be added to traces that are independent by construction.

rho = KAPPA * (benign + relay + dr_spatial) + KAPPA * staleness_trace
"""
from __future__ import annotations

import csv
from dataclasses import replace
from functools import lru_cache

import numpy as np

from .certificate import KAPPA, OUT, CertificateProcess, ThreatProfile

TRACE_CSV = OUT / "r3_staleness_traces.csv"


@lru_cache(maxsize=None)
def staleness_traces(labels: tuple[str, ...] | None = None):
    if not TRACE_CSV.exists():
        raise FileNotFoundError(f"{TRACE_CSV} missing: run r3_extract_traces.py on the staged corpus")
    by = {}
    with TRACE_CSV.open() as fh:
        for r in csv.DictReader(fh):
            if labels and r["label"] not in labels:
                continue
            by.setdefault(r["flight"], []).append(float(r["staleness_s"]))
    tr = tuple(np.asarray(v) for v in by.values() if len(v) > 10)
    if not tr:
        raise ValueError("no usable staleness traces")
    return tr


class TraceProcess:
    def __init__(self, B: int, N: int, prof: ThreatProfile, rng: np.random.Generator,
                 labels: tuple[str, ...] | None = None):
        self.B, self.N, self.p, self.rng = B, N, prof, rng
        # relay episodes, benign floor and spatial dead reckoning; no Poisson jamming/faults
        self.inner = CertificateProcess(B, N, replace(prof, jam_rate=0.0, fault_rate=0.0), rng)
        self.st = staleness_traces(labels)
        self.fi = rng.integers(0, len(self.st), (B, N))
        self.fo = np.array([[rng.integers(0, self.st[f].size) for f in row] for row in self.fi])
        self.n_up_jumps = self.inner.n_up_jumps
        self._read()

    def _read(self):
        self.stale = np.array([[self.st[f][o % self.st[f].size] for f, o in zip(fr, orow)]
                               for fr, orow in zip(self.fi, self.fo)])

    def rho(self):
        return self.inner.rho() + KAPPA * self.stale

    def step(self, dt: float, jam_mask: np.ndarray | None = None):
        self.inner.step(dt, jam_mask=jam_mask)
        self.fo += max(1, int(round(dt / 0.5)))       # traces are on a 0.5 s grid
        self._read()
        return self.rho()
