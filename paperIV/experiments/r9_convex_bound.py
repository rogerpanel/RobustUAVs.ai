#!/usr/bin/env python3
"""Certified stealth budget with the model-based residual detector (D3) included.

r8_analytic_bound.py bounds the attack-only deviation of every stealthy attack by
an LP that keeps only the jump rule (D1), the anchor gate and the saturation
alarm (D_sat); D2-D4 were dropped as "not convex". D3 is convex after all: its
CUSUM g_k = max(0, g_{k-1} + r_k^2 - (1 + kappa)) stays below theta_3 for all k
if and only if, for every window [i, k],

    sum_{j=i..k} r_j^2  <=  theta_3 + (1 + kappa) (k - i + 1),

and the observer residual r = r^a + r^b is linear in the attack offsets d (r^a)
plus a benign part r^b. By the triangle inequality in the window's l2 norm,
"no D3 alarm" implies the second-order-cone constraint

    || r^a_W ||_2  <=  sqrt(theta_3 + (1 + kappa) |W|) + || r^b_W ||_2 ,

for every window W. We keep the windows of a few lengths (any subset is valid:
fewer constraints can only enlarge the feasible set) and bound ||r^b_W|| by an
empirical quantile on the calibration missions, as r8 does for its margins.

Attacker class (identical to r8): any causal, adaptive sequence of GNSS position
offsets d_j, one per GNSS epoch, chosen with full knowledge of the model, the
noise realisation and every threshold; the attacker cannot alter the IMU, the
actuators or the trusted anchor fix. Scope as r8: unsaturated missions (D_sat),
constant loss of effectiveness, no GNSS outage, benign margins at (1 - eps/m)
quantiles so the bound holds with probability >= 1 - eps over benign noise,
jointly for every attack in the class.

Output: results/r9_convex_bound.csv (provenance = physics_model)
Usage:  python3 r9_convex_bound.py [--quick] [--anchors 5,10,20] [--fpr 0.01,0.05]
"""
from __future__ import annotations

import argparse
import csv
import json

import cvxpy as cp
import numpy as np

from constants import *  # noqa: F401,F403
import run_pilot as RP
from sim import simulate

RES = RP.RES
DTG = DT * GNSS_EVERY


def response_rows(anchor, loe):
    """Attack-only rows (in the GNSS-epoch offsets d) of: position p at each control
    step, GNSS measurement z and D3 residual r at each epoch, anchor innovation
    at each anchor (with its variance), and the raw command u_raw at each step."""
    n_ep = (N_STEPS + GNSS_EVERY - 1) // GNSS_EVERY
    I = np.eye(n_ep)
    p = np.zeros(n_ep); v = np.zeros(n_ep); xh = np.zeros((3, n_ep))
    po = np.zeros(n_ep); vo = np.zeros(n_ep)                 # D3 observer
    dt = DT
    F = np.array([[1, dt, -0.5 * dt * dt], [0, 1, -dt], [0, 0, 1]])
    Bu = np.array([0.5 * dt * dt, dt, 0.0])
    Q = np.diag([0.25 * dt ** 4 * KF_QV, dt * dt * KF_QV, dt * KF_QB])
    Pk = np.diag([1.0, 0.1, 0.02 ** 2])
    anchor_every = None if anchor is None else int(round(anchor / dt))
    P_rows, Z_rows, R_rows, A_rows, A_var, U_rows = [], [], [], [], [], []
    for k in range(N_STEPS):
        u_raw = -KP * xh[0] - KD * xh[1]
        U_rows.append(u_raw.copy())
        a = u_raw * loe - C_DRAG * v
        v = v + a * dt
        p = p + v * dt
        xh = F @ xh + np.outer(Bu, a)
        Pk = F @ Pk @ F.T + Q
        vo = vo + (u_raw - C_DRAG * vo) * dt                 # observer uses the command
        po = po + vo * dt
        if k % GNSS_EVERY == 0:
            z = p + I[k // GNSS_EVERY]
            Z_rows.append(z.copy())
            S = Pk[0, 0] + KF_R
            K = Pk[:, 0] / S
            xh = xh + np.outer(K, z - xh[0])
            Pk = Pk - np.outer(K, Pk[0, :])
            r3 = z - po
            R_rows.append(r3.copy())
            po = po + 0.3 * r3
            vo = vo + 0.2 * r3 / DTG
        if anchor_every and k > 0 and (k % anchor_every == 0 or k == N_STEPS - 1):
            S = Pk[0, 0] + SIG_ANCHOR ** 2
            nu = p - xh[0]
            A_rows.append(nu.copy()); A_var.append(S)
            K = Pk[:, 0] / S
            xh = xh + np.outer(K, nu)
            Pk = Pk - np.outer(K, Pk[0, :])
        P_rows.append(p.copy())
    return (np.array(P_rows), np.array(Z_rows), np.array(R_rows), np.array(A_rows),
            np.array(A_var), np.array(U_rows))


def windows(n, L):
    s = max(1, L // 4)
    starts = list(range(0, n - L + 1, s))
    if starts and starts[-1] != n - L:
        starts.append(n - L)
    return starts


def benign_window_norms(r3b, Ls):
    """Per mission, the largest l2 norm of the benign residual over windows of each length."""
    r = np.nan_to_num(r3b)
    c = np.concatenate([np.zeros((r.shape[0], 1)), np.cumsum(r * r, axis=1)], axis=1)
    out = {}
    for L in Ls:
        e = np.sqrt(np.maximum(c[:, L:] - c[:, :-L], 0.0))
        out[L] = e.max(axis=1)
    return out


def bound(anchor, loe, c1, ca_scale, cu, d3, stride):
    P, Z, R, A, Av, U = response_rows(anchor, loe)
    n = Z.shape[1]
    d = cp.Variable(n)
    cons = []
    if c1 is not None:
        J = Z[1:] - Z[:-1]
        cons += [cp.abs(J @ d) <= c1]
    if len(A):
        cons += [cp.abs(A @ d) <= np.sqrt(Av) * ca_scale]
    if cu is not None:
        cons += [cp.abs(U @ d) <= cu]
    if d3 is not None:
        th3, kappa, margins = d3
        for L, mL in margins.items():
            lim = np.sqrt(th3 + (1.0 + kappa) * L) + mL
            for i in windows(n, L):
                cons.append(cp.norm(R[i:i + L] @ d, 2) <= lim)
    c = cp.Parameter(n)
    prob = cp.Problem(cp.Maximize(c @ d), cons)

    def solve(k):
        c.value = P[k]
        prob.solve(solver=cp.CLARABEL)
        if prob.status in ("unbounded", "unbounded_inaccurate"):
            return float("inf")
        if prob.status not in ("optimal", "optimal_inaccurate"):
            raise RuntimeError(f"status {prob.status} at k={k}")
        return float(prob.value)

    ks = list(range(stride, N_STEPS, stride)) + [N_STEPS - 1]
    vals = {k: solve(k) for k in ks}
    if any(not np.isfinite(x) for x in vals.values()):
        return float("inf"), -1
    kb = max(vals, key=vals.get)
    for k in range(max(1, kb - stride), min(N_STEPS, kb + stride + 1)):
        if k not in vals:
            vals[k] = solve(k)
    kb = max(vals, key=vals.get)
    return vals[kb], kb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--eps", type=float, default=0.01)
    ap.add_argument("--anchors", default="5,10,20")
    ap.add_argument("--fpr", default="")
    ap.add_argument("--lengths", default="1,5,10,20,50,100")
    ap.add_argument("--stride", type=int, default=20)
    ap.add_argument("--out", default="r9_convex_bound.csv")
    a = ap.parse_args()
    js = json.loads((RES / "e1_calibration.json").read_text())
    stack = {float(k): v for k, v in js["stack"].items()}
    thA = js["anchor"]
    Ls = [int(x) for x in a.lengths.split(",")]
    N = 1000 if a.quick else 4000
    ben = simulate(N, 1001, w20=RP.wind(N, 1001), record_r3=True)    # the E1 calibration missions
    m = 3 + len(Ls)                                                   # margins share eps
    q = 1 - a.eps / m
    q1 = float(np.quantile(ben["S1"], q)); qA = float(np.quantile(ben["SA"], q))
    qu = float(np.quantile(ben["umax"], q))
    wn = benign_window_norms(ben["r3"], Ls)
    margins = {L: float(np.quantile(wn[L], q)) for L in Ls}
    ca_scale = np.sqrt(thA) + np.sqrt(qA)
    cu = U_MAX + qu
    fprs = [float(x) for x in a.fpr.split(",")] if a.fpr else list(RP.OPS)
    anchors = [float(x) for x in a.anchors.split(",")]
    loes = (1.0, 0.7) if a.quick else (1.0, 0.9, 0.8, 0.7)
    stride = 40 if a.quick else a.stride
    rows = []
    for fpr in fprs:
        th1, th3 = stack[fpr]["D1"], stack[fpr]["D3"]
        for Ta in anchors:
            for label, use3 in (("anchor + D1 + D_sat (r8 revised stack)", False),
                                ("anchor + D1 + D3 + D_sat", True)):
                best = (-1.0, None, None)
                for loe in loes:
                    b, kb = bound(Ta, loe, th1 + q1, ca_scale, cu,
                                  (th3, CUSUM_KAPPA, margins) if use3 else None, stride)
                    if b > best[0]:
                        best = (b, loe, kb)
                rows.append({"fpr": fpr, "T_anchor_s": Ta, "constraints": label,
                             "theta_D1": round(th1, 4), "theta_D3": round(th3, 4),
                             "eps": a.eps, "window_lengths": a.lengths if use3 else "",
                             "delta_cert_m": round(best[0], 3) if np.isfinite(best[0]) else "inf",
                             "worst_loe": best[1],
                             "argmax_t_s": round(best[2] * DT, 2) if best[2] and best[2] > 0 else "",
                             "provenance": "physics_model"})
                print(rows[-1], flush=True)
    with (RES / a.out).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
