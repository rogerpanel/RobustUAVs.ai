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
  D_sat (saturation alarm, revised stack): no alarm  =>  |u_raw| < U_MAX at every
      step, so the attack-only raw command |u^a_k| <= U_MAX + max_k |u^b_k|.
Benign terms are bounded by their (1 - eps/3) quantiles on the E1 calibration
missions, so the bound holds with probability at least 1 - eps over the benign
noise (eps = 0.01), jointly over every attack.

Scope: (i) unsaturated missions only -- the revised stack enforces this with
D_sat; for the first two constraint sets saturation is simply ignored;
(ii) actuator loss of effectiveness held constant at a value in {1, 0.9, 0.8,
0.7} (worst reported), not switched mid-mission; (iii) no GNSS outage -- this is
NOT proved: an outage changes the filter, and outage missions are covered only
by the empirical check in e4_revised.py; (iv) maximised over every control step
(coarse grid plus local refinement) and over attack onset (d is free from t = 0);
(v) the benign margins are empirical quantiles of the calibration missions.

Output: results/r8_analytic_bound.csv (provenance = physics_model)
Search over the evaluation step k: a coarse grid every --stride control steps,
then every step within +-stride of the coarse maximum. A HiGHS numerical
failure is reported as "unsolved", never as a number.

Usage:  python3 r8_analytic_bound.py [--quick] [--par 4] [--stride 10]
"""
from __future__ import annotations

import argparse
import csv
import json

import numpy as np
from multiprocessing import Pool

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
    P_rows, Z_rows, A_rows, A_var, U_rows = [], [], [], [], []
    for k in range(N_STEPS):
        u_raw = -KP * xh[0] - KD * xh[1]
        U_rows.append(u_raw.copy())
        u = u_raw * loe
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
    return np.array(P_rows), np.array(Z_rows), np.array(A_rows), np.array(A_var), np.array(U_rows)


def bound(anchor, loe, c1, ca_scale, use_d1=True, stride=5, cu=None):
    P, Z, A, Av, Ur = response_rows(anchor, loe)
    n = Z.shape[1]
    G, h = [], []
    if use_d1 and c1 is not None:
        J = Z[1:] - Z[:-1]
        G += [J, -J]; h += [np.full(len(J), c1)] * 2
    if len(A):
        lim = np.sqrt(Av) * ca_scale
        G += [A, -A]; h += [lim, lim]
    if cu is not None:                          # saturation alarm: |u_raw^a| <= U_MAX + benign margin
        G += [Ur, -Ur]; h += [np.full(len(Ur), cu)] * 2
    G = np.vstack(G) if G else np.zeros((0, n)); h = np.concatenate(h) if h else np.zeros(0)
    if anchor is None and not use_d1:
        return float("inf"), -1

    def solve(k):
        r = linprog(-P[k], A_ub=G, b_ub=h, bounds=[(None, None)] * n, method="highs")
        if r.status == 3 or (r.status == 4 and anchor is None and not use_d1):
            return float("inf")
        if r.status in (2, 4):
            # d = 0 is always feasible, so "infeasible" is HiGHS presolve's
            # infeasible-OR-unbounded verdict, or a numerical failure. Re-solve
            # inside two boxes |d| <= B: a finite optimum does not move when B
            # grows tenfold, an unbounded one scales with B.
            v = []
            for B in (1e4, 1e5):
                rb = linprog(-P[k], A_ub=G, b_ub=h, bounds=[(-B, B)] * n, method="highs")
                if rb.status != 0:
                    break
                v.append(-rb.fun)
            if len(v) == 2:
                if v[1] > 5 * max(v[0], 1e-9):
                    return float("inf")
                if abs(v[1] - v[0]) <= 1e-6 * max(1.0, abs(v[0])):
                    return v[0]
        if r.status != 0:                       # numerical failure: never silently dropped
            raise RuntimeError(f"HiGHS status {r.status} at k={k} (anchor={anchor}, loe={loe}, D1={use_d1})")
        return -r.fun
    ks = list(range(stride, N_STEPS, stride)) + [N_STEPS - 1]
    vals = {}
    for k in ks:
        vals[k] = solve(k)
        if not np.isfinite(vals[k]):            # unbounded at one step: the supremum is infinite
            return float("inf"), k
    kbest = max(vals, key=lambda k: vals[k])
    for k in range(max(1, kbest - stride), min(N_STEPS, kbest + stride + 1)):   # refine
        if k not in vals:
            vals[k] = solve(k)
    kbest = max(vals, key=lambda k: vals[k])
    return float(vals[kbest]), kbest


def _job(args):
    fpr, Ta, cset, loe, c1, ca_scale, stride, cu = args
    use_d1 = cset >= 1
    try:
        b, kb = bound(Ta, loe, c1, ca_scale, use_d1, stride=stride, cu=cu if cset == 2 else None)
    except RuntimeError as e:                   # report the cell as unsolved rather than guess
        print(f"UNSOLVED {e}", flush=True)
        b, kb = float("nan"), -1
    return fpr, Ta, cset, loe, b, kb


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--quick", action="store_true")
    ap.add_argument("--eps", type=float, default=0.01)
    ap.add_argument("--par", type=int, default=4)
    ap.add_argument("--anchors", default="5,10,20,none", help="re-anchoring intervals, 'none' = no anchor")
    ap.add_argument("--out", default="r8_analytic_bound.csv")
    ap.add_argument("--stride", type=int, default=10, help="coarse grid in control steps, then +-stride refine")
    a = ap.parse_args()
    js = json.loads((RES / "e1_calibration.json").read_text())
    stack = {float(k): v for k, v in js["stack"].items()}
    single = {float(k): v for k, v in js["single"].items()}
    thA = js["anchor"]
    N = 1000 if a.quick else 4000
    ben = simulate(N, 1001, w20=RP.wind(N, 1001))            # the E1 calibration missions
    q1 = float(np.quantile(ben["S1"], 1 - a.eps / 3))       # three benign margins, eps/3 each
    qA = float(np.quantile(ben["SA"], 1 - a.eps / 3))
    qu = float(np.quantile(ben["umax"], 1 - a.eps / 3))
    cu = U_MAX + qu
    ca_scale = np.sqrt(thA) + np.sqrt(qA)
    emp = {float(r["fpr"]): float(r["delta_adv_cal_m"]) for r in csv.DictReader((RES / "e4_delta_adv.csv").open())}
    r1 = RES / "r1_delta_adv.csv"
    emp_r1 = {float(r["fpr"]): float(r["delta_pooled_m"]) for r in csv.DictReader(r1.open())} if r1.exists() else {}
    rows = []
    loes = (1.0, 0.7) if a.quick else (1.0, 0.9, 0.8, 0.7)
    anchors = (5.0, None) if a.quick else tuple(None if x.strip() == "none" else float(x)
                                                 for x in a.anchors.split(","))
    stride = 20 if a.quick else a.stride
    LAB = {0: "anchor gate only (every stack)", 1: "anchor gate + D1 (stacks D1, ALL)",
           2: "anchor gate + D1 + D_sat (revised stack)"}
    jobs = [(fpr, Ta, cs, loe, (stack[fpr]["D1"] + q1) if cs >= 1 else None, ca_scale, stride, cu)
            for fpr in RP.OPS for Ta in anchors for cs in (0, 1, 2) for loe in loes]
    with Pool(a.par) as pool:
        res = []
        for r_ in pool.imap_unordered(_job, jobs):
            res.append(r_)
            print(f"[{len(res)}/{len(jobs)}] fpr={r_[0]} Ta={r_[1]} set={r_[2]} loe={r_[3]} -> {r_[4]:.3f}", flush=True)
    for fpr in RP.OPS:
        for Ta in anchors:
            for cs in (0, 1, 2):
                use_d1 = cs >= 1
                cand = [(b, loe, kb) for f_, t_, d_, loe, b, kb in res if (f_, t_, d_) == (fpr, Ta, cs)]
                if any(np.isnan(b) for b, _, _ in cand):
                    worst = (float("nan"), None, None)
                else:
                    worst = max(cand, key=lambda x: x[0])
                th1 = stack[fpr]["D1"] if use_d1 else None
                e = emp.get(fpr, float("nan"))
                fin = np.isfinite(worst[0])
                rows.append({"fpr": fpr, "T_anchor_s": Ta if Ta else "none (C2' violated)", "constraints": LAB[cs],
                             "theta_D1": round(th1, 4) if th1 else "", "S1_benign_q": round(q1, 4),
                             "theta_anchor": round(thA, 4), "SA_benign_q": round(qA, 4),
                             "umax_benign_q": round(qu, 4) if cs == 2 else "", "eps": a.eps,
                             "delta_lp_m": round(worst[0], 3) if fin else ("unsolved" if np.isnan(worst[0]) else "inf"),
                             "worst_loe": worst[1], "argmax_t_s": round(worst[2] * DT, 2) if fin else "",
                             "stride_steps": stride,
                             "delta_emp_pilot_m": e, "delta_emp_r1_m": emp_r1.get(fpr, ""),
                             "ratio_lp_to_emp": round(worst[0] / max(e, emp_r1.get(fpr, 0.0)), 3) if fin else "",
                             "provenance": "physics_model"})
                print({k: rows[-1][k] for k in ("fpr", "T_anchor_s", "constraints", "delta_lp_m", "worst_loe",
                                                "ratio_lp_to_emp")}, flush=True)
    with (RES / a.out).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
