#!/usr/bin/env python3
"""E3 -- real-time ceiling of the projection layer (RQ4).

Wall-clock latency of (i) the closed-form feasibility certificate (deficiency
and coverage margin), (ii) unweighted greedy nested projection, (iii) the
exact lexicographic projection (Hungarian, scipy), (iv) a generic
Hopcroft-Karp maximum matching on the same graph, for N agents and M = N/2
tasks. Hardware is recorded in the CSV. Output: results/e3_latency.csv
(R8: `--board pi5` writes results/e3_latency_pi5.csv on a companion computer).
"""
from __future__ import annotations

import csv
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from certcmdp.certificate import OUT, ALERT_LIMITS, KAPPA  # noqa: E402
from certcmdp import combinatorics as C  # noqa: E402


def timeit(fn, reps):
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return np.asarray(ts) * 1e3


def cpu_model():
    """CPU model string (runbook: record the CPU with every latency run)."""
    try:
        lines = Path("/proc/cpuinfo").read_text().splitlines()
        # x86 reports "model name"; ARM boards report "Model" (Pi) or "Hardware".
        # The bare "model" field is a numeric family code and must not be used.
        for key in ("model name", "Model", "Hardware"):
            for line in lines:
                k = line.split(":", 1)[0].strip()
                if k == key and ":" in line:
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def main(board=""):
    rng = np.random.default_rng(0)
    cpu = cpu_model()
    rows = []
    for N in (12, 25, 50, 100, 250, 500, 1000, 2000, 5000, 10000, 100000):
        M = max(1, N // 2)
        reps = 200 if N <= 1000 else (20 if N <= 10000 else 5)
        rho = KAPPA * rng.exponential(1.0, N)
        alpha = rng.choice(ALERT_LIMITS, M)
        algs = {
            "closed_form_check": lambda: (C.deficiency(rho, alpha), C.coverage_margin(rho, alpha)),
            "gnp_fast": lambda: C.nested_greedy_fast(rho, alpha),
        }
        if N <= 2000:
            elig = rho[:, None] <= alpha[None, :]
            prop = rng.integers(-1, M, N)
            algs["lexicographic_hungarian"] = lambda: C.lexicographic_projection(elig, prop)
        if N <= 10000:
            elig2 = rho[:, None] <= alpha[None, :]
            algs["hopcroft_karp"] = lambda: C.brute_max_matching(elig2)
        for name, fn in algs.items():
            fn()
            t = timeit(fn, reps)
            rows.append({"N": N, "M": M, "algorithm": name, "reps": reps,
                         "p50_ms": float(np.median(t)), "p99_ms": float(np.percentile(t, 99)),
                         "max_ms": float(t.max()), "cpu": cpu, "threads": os.cpu_count()})
            print(rows[-1])
    out = OUT / (f"e3_latency_{board}.csv" if board else "e3_latency.csv")
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default="", help="R8: board name, e.g. pi5 or orin_nano")
    main(ap.parse_args().board)
