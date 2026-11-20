#!/usr/bin/env python3
"""Mismatch between the proved linear loop and PX4 on the flown attacks (PX4_PREREG.md, E6).

The stealth budget delta_cert is PROVED for the reduced-order linear loop (r8/r10), and PX4 is
only MEASURED. This script measures how far PX4 departs from that linear loop on the very
offset sequences the PX4 attacks applied, and turns the departure into a stated, statistical
(not proved) term:

  for every attacked PX4 mission with a flown twin in the same run,
    e_px4(t)  = e_attack(t) - e_twin(t)          attack-only cross-track deviation in PX4
    d(t)      = the offset the patched GNSS module applied (logged at 20 Hz)
    e_lin(t)  = P d                              the linear loop's attack-only position for the
                                                 same offsets (r8_analytic_bound.response_rows,
                                                 same re-anchoring interval, LoE 1)
    M         = sup_{t >= t0} |e_px4(t) - e_lin(t)|   pointwise mismatch after the attack onset
  and whether d satisfies the stealth constraints of the proved bound in the linear loop
  (D1 jump rule, anchor gate, saturation alarm, with the finite-sample corrected margins of
  results/r10_bound_conf.csv). For such a d, sup|e_lin| <= delta_cert(T_a) by the proof, hence

    sup|e_px4| <= delta_cert(T_a) + M.

M_ub is a distribution-free upper confidence bound on the (1 - eps) quantile of M (order
statistic, confidence 1 - delta), over the population of attacks that were flown: it is a
statement about those attacker classes, NOT a worst case over every attack, and it includes the
replay floor (two flights of one benign mission differ by up to 1.5 m). Subsets: every attack,
and the attacks undetected by the bound's stack (D1 + anchor gate, 5 % FPR).

Runs: 5 s re-anchoring: e1 (naive offsets), e2 (transferred attackers), e3eval2 (PX4-optimised);
1 s: ta1. e4neg (no anchor) is reported separately: the linear bound is infinite there.
Outputs: results/px4/px4_mismatch.csv (per mission), px4_mismatch_summary.csv.
Usage: python3 p4_mismatch.py [--complete] [--eps 0.05,0.01] [--delta 0.05]
"""
from __future__ import annotations

import argparse
import csv
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import p4_analyze as A  # noqa: E402
import r8_analytic_bound as R8  # noqa: E402
from scipy.stats import binom  # noqa: E402
from constants import DT, GNSS_EVERY, N_STEPS, U_MAX  # noqa: E402

def order_index(n, q, alpha):
    """Smallest k (1-based) with P(Bin(n, q) >= k) <= alpha: X_(k) >= x_q with prob. >= 1 - alpha
    (the same rule as r10_confidence_bound.py, repeated here so this script needs only results files)."""
    k = int(binom.ppf(1 - alpha, n, q)) + 1
    while k > 1 and binom.sf(k - 2, n, q) <= alpha:
        k -= 1
    while binom.sf(k - 1, n, q) > alpha:
        k += 1
    if k > n:
        raise ValueError(f"n = {n} is too small for q = {q}, alpha = {alpha}")
    return k


def need(path):
    if not path.exists():
        raise SystemExit(f"missing {path}: update the checkout with "
                         f"git checkout FETCH_HEAD -- paperIV/experiments paperIV/results/{path.name}")
    return path


RUNS = {5.0: [("e1", "e1"), ("e2", "e2"), ("e3eval2", "e3eval")],
        1.0: [("ta1", "ta1_e1"), ("ta1", "ta1_e2"), ("ta1", "ta1_e3")],
        None: [("e4neg", "e4neg")]}


@lru_cache(maxsize=None)
def linear(anchor):
    """Response rows of the linear loop (LoE 1) and the corrected constraint data of the bound."""
    P, Z, Az, Av, Ur = R8.response_rows(anchor, 1.0)
    return P, Z, Az, Av, Ur


@lru_cache(maxsize=None)
def bound_row(anchor):
    rows = [r for r in csv.DictReader(open(need(A.RES / "r10_bound_conf.csv")))
            if float(r["T_anchor_s"]) == anchor and float(r["loe"]) == 1.0]
    return rows[0] if rows else None


def constraint_limits():
    import json
    js = json.loads(need(A.RES / "e1_calibration.json").read_text())
    r = bound_row(5.0)
    th1 = {float(k): v for k, v in js["stack"].items()}[float(r["fpr"])]["D1"]
    c1 = th1 + float(r["margin_S1_cor"])
    ca = np.sqrt(js["anchor"]) + np.sqrt(float(r["margin_SA_cor"]))
    cu = U_MAX + float(r["margin_umax_cor"])
    return c1, ca, cu


def offsets_at_epochs(t, d):
    """Offset of GNSS epoch j: the linear loop adds d_j to the position after control step 2j,
    i.e. at time (2j + 1) DT."""
    n_ep = (N_STEPS + GNSS_EVERY - 1) // GNSS_EVERY
    te = (GNSS_EVERY * np.arange(n_ep) + 1) * DT
    return np.interp(te, t, d, left=0.0, right=float(d[-1]))


def one(r, d_src, anchor, limits):
    a = A.series(d_src, r["mid"]); b = A.series(d_src, A.twin_mid(r))
    if a is None or b is None:
        return None
    t = a["t"].astype(float)
    e_px4 = a["e"].astype(float) - b["e"].astype(float)
    dep = offsets_at_epochs(t, a["d"].astype(float))
    if anchor is None:
        P = linear(None)[0]
    else:
        P, Z, Az, Av, Ur = linear(anchor)
    p_lin = P @ dep                                    # position after step k, at time (k + 1) DT
    e_lin = np.interp(t, (np.arange(N_STEPS) + 1) * DT, p_lin, left=0.0)
    t0 = r.get("attack_t0") or 0.0
    m = t >= t0
    out = {"run": d_src, "exp": r["exp"], "mid": r["mid"], "family": r["family"],
           "attacker_id": r.get("attacker_id"), "anchor_s": anchor, "t0": t0,
           "delta_px4_m": float(np.max(np.abs(e_px4[m]))), "delta_lin_m": float(np.max(np.abs(e_lin[m]))),
           "mismatch_m": float(np.max(np.abs(e_px4[m] - e_lin[m]))),
           "offset_max_m": float(np.max(np.abs(dep)))}
    if anchor is not None:
        c1, ca, cu = limits
        zj = Z @ dep
        ok1 = bool(np.all(np.abs(np.diff(zj)) <= c1))
        okA = bool(np.all(np.abs(Az @ dep) <= np.sqrt(Av) * ca)) if len(Az) else True
        okU = bool(np.all(np.abs(Ur @ dep) <= cu))
        out.update(feasible_D1=ok1, feasible_anchor=okA, feasible_sat=okU, feasible=ok1 and okA and okU)
    return out


def ub(v, eps, delta):
    """Order-statistic upper confidence bound on the (1 - eps) quantile, or None if n is too small."""
    v = np.sort(np.asarray(v, float))
    try:
        k = order_index(len(v), 1 - eps, delta)
    except ValueError:
        return None, None
    return float(v[k - 1]), k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--complete", action="store_true", help="include the reruns of deviation 4")
    ap.add_argument("--cruise", action="store_true", help="validity rule of deviation 5")
    ap.add_argument("--eps", default="0.05,0.01"); ap.add_argument("--delta", type=float, default=0.05)
    a = ap.parse_args()
    A.COMPLETE = a.complete
    A.CRUISE = a.cruise
    cal5 = A.cal_load()
    f1 = A.PX / "calibration_ta1.json"
    cal1 = __import__("json").loads(f1.read_text()) if f1.exists() else None
    limits = constraint_limits()
    per = []
    for anchor, runs in RUNS.items():
        for d, exp in runs:
            if not (A.PX / d / "missions.jsonl").exists():
                print(f"  {d}/{exp}: no missions, skipped"); continue
            cal = cal1 if anchor == 1.0 else cal5
            for r in A.rows(d, exp):
                if r["family"] == "none":
                    continue
                o = one(r, r.get("_src", d), anchor, limits)
                if o is None:
                    continue
                if cal:
                    o["undetected_D1_gate"] = not A.alarm(r, cal, "D1", 0.05, gate=anchor is not None)
                    o["undetected_ALL_gate"] = not A.alarm(r, cal, "ALL", 0.05, gate=anchor is not None)
                per.append(o)
    if not per:
        print("no attacked missions with series and twins found"); return
    A.write("px4_mismatch.csv", [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in o.items()}
                                 | {"provenance": "px4_sitl"} for o in per])
    eps = [float(x) for x in a.eps.split(",")]
    summ = []
    for anchor in (5.0, 1.0, None):
        for subset in ("all", "undetected_D1_gate"):
            S = [o for o in per if o["anchor_s"] == anchor and (subset == "all" or o.get(subset))]
            if not S:
                continue
            M = [o["mismatch_m"] for o in S]
            # one-sided form (recorded with deviation 5): sup|e_px4| <= sup|e_lin| + M+, and for offsets
            # feasible in the linear bound sup|e_lin| <= delta_cert, so only PX4 EXCEEDING the linear
            # loop matters; the pointwise M also counts the linear loop overshooting PX4.
            Mp = [max(0.0, o["delta_px4_m"] - o["delta_lin_m"]) for o in S]
            row = {"anchor_s": anchor, "subset": subset, "n": len(S),
                   "mismatch_q50_m": round(float(np.median(M)), 3),
                   "mismatch_q95_m": round(float(np.quantile(M, 0.95)), 3), "mismatch_max_m": round(max(M), 3),
                   "delta_px4_max_m": round(max(o["delta_px4_m"] for o in S), 3),
                   "delta_lin_max_m": round(max(o["delta_lin_m"] for o in S), 3)}
            if anchor is not None:
                row["share_offsets_feasible_in_linear_bound"] = round(float(np.mean([o["feasible"] for o in S])), 4)
                br = bound_row(anchor)
                row["delta_cert_corrected_m"] = float(br["delta_cert_corrected_m"]) if br else None
            row["Mplus_q50_m"] = round(float(np.median(Mp)), 3)
            row["Mplus_max_m"] = round(max(Mp), 3)
            for e in eps:
                u, k = ub(Mp, e, a.delta)
                row[f"Mplus_ub_eps{e}_m"] = None if u is None else round(u, 3)
                if anchor is not None and u is not None and row.get("delta_cert_corrected_m") is not None:
                    row[f"stat_bound_Mplus_eps{e}_m"] = round(row["delta_cert_corrected_m"] + u, 3)
            for e in eps:
                u, k = ub(M, e, a.delta)
                row[f"M_ub_eps{e}_m"] = None if u is None else round(u, 3)
                row[f"M_ub_eps{e}_order_k"] = k
                if anchor is not None and u is not None and row.get("delta_cert_corrected_m") is not None:
                    row[f"stat_bound_eps{e}_m"] = round(row["delta_cert_corrected_m"] + u, 3)
            row.update(delta=a.delta, provenance="px4_sitl")
            summ.append(row)
    A.write("px4_mismatch_summary.csv", summ)
    for row in summ:
        print("  " + ", ".join(f"{k}={v}" for k, v in row.items() if k != "provenance"))


if __name__ == "__main__":
    main()
