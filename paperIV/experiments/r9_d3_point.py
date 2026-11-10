#!/usr/bin/env python3
"""Does the CUSUM detector (D3) tighten the proved budget? Point evaluation of r9_convex_bound.

Same constraints as r8 (D1 + anchor gate + D_sat; T_a = 5 s, LoE 1.0, 1 % FPR, eps = 0.01, margins
at the 1 - eps/m quantiles of 1,000 calibration missions, m = 3 + number of window lengths), with and
without the D3 second-order-cone constraints (window lengths 1, 5, 10, 20, 50, 100), at five
evaluation times. Output: results/r9_d3_point.csv (provenance = physics_model)
"""
import csv
import json
import sys
import time
from pathlib import Path

import cvxpy as cp
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r9_convex_bound as B  # noqa: E402
from constants import DT, N_STEPS, U_MAX, CUSUM_KAPPA  # noqa: E402
import run_pilot as RP  # noqa: E402
from sim import simulate  # noqa: E402

js = json.loads((B.RES / "e1_calibration.json").read_text())
stack = {float(k): v for k, v in js["stack"].items()}
thA = js["anchor"]; Ls = [1, 5, 10, 20, 50, 100]; eps = 0.01; q = 1 - eps / (3 + len(Ls))
ben = simulate(1000, 1001, w20=RP.wind(1000, 1001), record_r3=True)
q1 = np.quantile(ben["S1"], q); qA = np.quantile(ben["SA"], q); qu = np.quantile(ben["umax"], q)
wn = B.benign_window_norms(ben["r3"], Ls); margins = {L: float(np.quantile(wn[L], q)) for L in Ls}
fpr = 0.01; th1, th3 = stack[fpr]["D1"], stack[fpr]["D3"]
P, Z, R, A, Av, U = B.response_rows(5.0, 1.0); n = Z.shape[1]
rows = []
for use3 in (False, True):
    d = cp.Variable(n)
    cons = [cp.abs((Z[1:] - Z[:-1]) @ d) <= th1 + q1, cp.abs(A @ d) <= np.sqrt(Av) * (np.sqrt(thA) + np.sqrt(qA)),
            cp.abs(U @ d) <= U_MAX + qu]
    if use3:
        for L, mL in margins.items():
            lim = np.sqrt(th3 + (1 + CUSUM_KAPPA) * L) + mL
            for i in B.windows(n, L):
                cons.append(cp.norm(R[i:i + L] @ d, 2) <= lim)
    for k in (int(58.35 / DT), int(30 / DT), int(10 / DT), int(5.0 / DT) + 10, N_STEPS - 1):
        t0 = time.time(); prob = cp.Problem(cp.Maximize(P[k] @ d), cons); prob.solve(solver=cp.CLARABEL)
        print(f"D3={use3} t={k * DT:.2f}s value={prob.value:.3f} status={prob.status} ({time.time() - t0:.1f}s)", flush=True)
        rows.append({"T_anchor_s": 5.0, "loe": 1.0, "fpr": fpr, "eps": eps, "theta_D3": round(th3, 3),
                     "constraints": "anchor gate + D1 + D_sat" + (" + D3 (SOC)" if use3 else ""),
                     "eval_t_s": round(k * DT, 2), "delta_m": round(float(prob.value), 3), "status": prob.status,
                     "provenance": "physics_model"})
with open(B.RES / "r9_d3_point.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
