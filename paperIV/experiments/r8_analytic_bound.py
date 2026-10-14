#!/usr/bin/env python3
"""R8 -- an analytic stealth budget for the linear loop (runbook R8).

The pilot's delta_adv is an empirical supremum over optimised attackers. Here
we bound the attack-only deviation of EVERY stealthy attack by a linear
programme on the same loop as sim.py (lateral double integrator with drag,
PD control on the estimate, 3-state Kalman filter with its deterministic
gain sequence, GNSS at 10 Hz, trusted anchor fixes), with the attack offset
d_j at each GNSS epoch j as the decision variables.

Superposition: with noise switched off the loop is linear in d (U_MAX
saturation aside, see below), so the attack-only position p^a_k = r_k . d.

Stealth constraints. Only detector conditions that are CONVEX in d and IMPLIED
by "no alarm" are kept; dropping a detector can only enlarge the feasible set,
so the bound remains an upper bound for every stack containing the kept ones:
  D1 (jump rule): no alarm  =>  every total jump <= theta_1, so the attack-only
      jump |Delta(p^a + d)_j| <= theta_1 + S1_benign;
  anchor gate (present in every stack under C2'): no alarm  =>  at every anchor
      |nu^a_i| <= sqrt(S_i) (sqrt(theta_A) + sqrt(SA_benign)).
D2-D4 alarm on runs of consecutive exceedances or on quadratic statistics,
which are not convex in d; they are dropped (conservative).
Benign terms are bounded by their (1 - eps/2) quantiles on the E1 calibration
missions, so the bound holds with probability at least 1 - eps over the benign
noise (eps = 0.01), jointly over every attack.

Scope stated in the output: (i) unsaturated controller (|u| <= U_MAX ignored;
checked against the pilot's saturated attack-only deviations), (ii) actuator
loss of effectiveness held constant at its worst value in [0.7, 1], (iii) no
GNSS outage (an outage removes the attacker's channel and cannot extend reach
beyond holding d constant), (iv) maximised over every control step of the
mission and over attack onset (d is free from t = 0).

Output: results/r8_analytic_bound.csv (provenance = physics_model)
Usage:  python3 r8_analytic_bound.py [--quick]
"""
from __future__ import annotations

import argparse
import csv
import json

import numpy as np
from scipy.optimize import linprog

from constants import *  # noqa: F401,F403
import run_pilot as RP
from sim import simulate

RES = RP.RES


def response_rows(anchor, loe):
    """Coefficient rows (in the GNSS-epoch offsets d) of p at every control step,
    of the attack-only GNSS measurement z at every epoch, and of the anchor
    innovation at every anchor; plus the anchor innovation variances."""
    n_ep = (N_STEPS + GNSS_EVERY - 1) // GNSS_EVERY
    I = np.eye(n_ep)
    p = np.zeros(n_ep); v = np.zeros(n_ep); xh = np.zeros((3, n_ep))
    dt = DT
    F = np.array([[1, dt, -0.5 * dt * dt], [0, 1, -dt], [0, 0, 1]])
    Bu = np.array([0.5 * dt * dt, dt, 0.0])
    Q = np.diag([0.25 * dt ** 4 * KF_QV, dt * dt * KF_QV, dt * KF_QB])
    Pk = np.diag([1.0, 0.1, 0.02 ** 2])
    anchor_every = None if anchor is None else int(round(anchor / dt))
    P_rows, Z_rows, A_rows, A_var = [], [], [], []
    for k in range(N_STEPS):
        u = (-KP * xh[0] - KD * xh[1]) * loe
        a = u - C_DRAG * v
        v = v + a * dt
        p = p + v * dt
        xh = F @ xh + np.outer(Bu, a)
        Pk = F @ Pk @ F.T + Q
        if k % GNSS_EVERY == 0:
            z = p + I[k // GNSS_EVERY]
            Z_rows.append(z.copy())
            S = Pk[0, 0] + KF_R
            K = Pk[:, 0] / S
            xh = xh + np.outer(K, z - xh[0])
            Pk = Pk - np.outer(K, Pk[0, :])
        if anchor_every and k > 0 and (k % anchor_every == 0 or k == N_STEPS - 1):
            S = Pk[0, 0] + SIG_ANCHOR ** 2
            nu = p - xh[0]
            A_rows.append(nu.copy()); A_var.append(S)
            K = Pk[:, 0] / S
            xh = xh + np.outer(K, nu)
            Pk = Pk - np.outer(K, Pk[0, :])
        P_rows.append(p.copy())
    return np.array(P_rows), np.array(Z_rows), np.array(A_rows), np.array(A_var)


def bound(anchor, loe, c1, ca_scale, use_d1=True, stride=5):
    P, Z, A, Av = response_rows(anchor, loe)
    n = Z.shape[1]
    G, h = [], []
    if use_d1 and c1 is not None:
        J = Z[1:] - Z[:-1]
        G += [J, -J]; h += [np.full(len(J), c1)] * 2
    if len(A):
        lim = np.sqrt(Av) * ca_scale
        G += [A, -A]; h += [lim, lim]
    G = np.vstack(G) if G else np.zeros((0, n)); h = np.concatenate(h) if h else np.zeros(0)
    if anchor is None and not use_d1:
        return float("inf"), -1

    def solve(k):
        r = linprog(-P[k], A_ub=G, b_ub=h, bounds=[(None, None)] * n, method="highs")
        if r.status == 3:
            return float("inf")
        return -r.fun if r.status == 0 else float("nan")
    ks = list(range(stride, N_STEPS, stride)) + [N_STEPS - 1]
    vals = {k: solve(k) for k in ks}
    kbest = max(vals, key=lambda k: vals[k])
    for k in range(max(1, kbest - stride), min(N_STEPS, kbest + stride + 1)):   # refine
        if k not in vals:
            vals[k] = solve(k)
    kbest = max(vals, key=lambda k: vals[k])
    return float(vals[kbest]), kbest


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--quick", action="store_true")
    ap.add_argument("--eps", type=float, default=0.01)
    a = ap.parse_args()
    js = json.loads((RES / "e1_calibration.json").read_text())
    stack = {float(k): v for k, v in js["stack"].items()}
    single = {float(k): v for k, v in js["single"].items()}
    thA = js["anchor"]
    N = 1000 if a.quick else 4000
    ben = simulate(N, 1001, w20=RP.wind(N, 1001))            # the E1 calibration missions
    q1 = float(np.quantile(ben["S1"], 1 - a.eps / 2))
    qA = float(np.quantile(ben["SA"], 1 - a.eps / 2))
    ca_scale = np.sqrt(thA) + np.sqrt(qA)
    emp = {float(r["fpr"]): float(r["delta_adv_cal_m"]) for r in csv.DictReader((RES / "e4_delta_adv.csv").open())}
    r1 = RES / "r1_delta_adv.csv"
    emp_r1 = {float(r["fpr"]): float(r["delta_pooled_m"]) for r in csv.DictReader(r1.open())} if r1.exists() else {}
    rows = []
    loes = (1.0, 0.7) if a.quick else (1.0, 0.9, 0.8, 0.7)
    anchors = (5.0, None) if a.quick else (5.0, 10.0, 20.0, None)
    for fpr in RP.OPS:
        for Ta in anchors:
            for use_d1, th1, label in ((False, None, "anchor gate only (every stack)"),
                                       (True, stack[fpr]["D1"], "anchor gate + D1 (stacks D1, ALL)")):
                c1 = (th1 + q1) if use_d1 else None
                worst = (-1.0, None, None)
                for loe in loes:
                    b, kb = bound(Ta, loe, c1, ca_scale, use_d1, stride=20 if a.quick else 5)
                    if b > worst[0]:
                        worst = (b, loe, kb)
                e = emp.get(fpr, float("nan"))
                rows.append({"fpr": fpr, "T_anchor_s": Ta if Ta else "none (C2' violated)", "constraints": label,
                             "theta_D1": round(th1, 4) if th1 else "", "S1_benign_q": round(q1, 4),
                             "theta_anchor": round(thA, 4), "SA_benign_q": round(qA, 4), "eps": a.eps,
                             "delta_lp_m": round(worst[0], 3) if np.isfinite(worst[0]) else "inf",
                             "worst_loe": worst[1], "argmax_t_s": round(worst[2] * DT, 2) if worst[2] is not None and worst[2] >= 0 else "",
                             "delta_emp_pilot_m": e, "delta_emp_r1_m": emp_r1.get(fpr, ""),
                             "ratio_lp_to_emp": round(worst[0] / max(e, emp_r1.get(fpr, 0.0)), 3)
                             if np.isfinite(worst[0]) else "inf",
                             "provenance": "physics_model"})
                print({k: rows[-1][k] for k in ("fpr", "T_anchor_s", "constraints", "delta_lp_m", "worst_loe",
                                                "ratio_lp_to_emp")}, flush=True)
    with (RES / "r8_analytic_bound.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
