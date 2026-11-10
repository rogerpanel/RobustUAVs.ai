#!/usr/bin/env python3
"""Proved worst-case undetected deviation versus the re-anchoring interval T_a.

Same linear programme as r8_analytic_bound.py (D1 jump rule + anchor gate + saturation alarm,
benign margins at the 1 - eps/3 calibration quantiles, eps = 0.01, stride 20 steps, 1 % FPR
stack thresholds), evaluated for T_a in {0.5, 1, 2, 3, 5, 10} s and LoE in {1.0, 0.7}.
Output: results/r8_bound_vs_anchor.csv (provenance = physics_model)
"""
import csv
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r8_analytic_bound as R8  # noqa: E402
from constants import DT, U_MAX  # noqa: E402
import run_pilot as RP  # noqa: E402
from sim import simulate  # noqa: E402

EPS, FPR = 0.01, 0.01
js = json.loads((R8.RES / "e1_calibration.json").read_text())
stack = {float(k): v for k, v in js["stack"].items()}
thA = js["anchor"]
ben = simulate(4000, 1001, w20=RP.wind(4000, 1001))
q1 = float(np.quantile(ben["S1"], 1 - EPS / 3))
qA = float(np.quantile(ben["SA"], 1 - EPS / 3))
qu = float(np.quantile(ben["umax"], 1 - EPS / 3))


def job(args):
    Ta, loe = args
    b, kb = R8.bound(Ta, loe, stack[FPR]["D1"] + q1, np.sqrt(thA) + np.sqrt(qA), True, stride=20, cu=U_MAX + qu)
    return Ta, loe, b, kb


if __name__ == "__main__":
    jobs = [(Ta, loe) for Ta in (0.5, 1.0, 2.0, 3.0, 5.0, 10.0) for loe in (1.0, 0.7)]
    rows = []
    with Pool(4) as p:
        for Ta, loe, b, kb in p.imap_unordered(job, jobs):
            print(f"Ta={Ta} loe={loe} delta_cert={b:.2f} m at t={kb * DT:.2f}s", flush=True)
            rows.append({"fpr": FPR, "eps": EPS, "T_anchor_s": Ta, "loe": loe,
                         "constraints": "anchor gate + D1 + D_sat", "delta_cert_m": round(b, 3),
                         "argmax_t_s": round(kb * DT, 2), "stride_steps": 20, "provenance": "physics_model"})
    rows.sort(key=lambda r: (r["T_anchor_s"], -r["loe"]))
    with open(R8.RES / "r8_bound_vs_anchor.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
