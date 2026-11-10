#!/usr/bin/env python3
"""Proved stealth budget with a finite-sample confidence correction on the benign margins.

r8_bound_vs_anchor.py bounds every benign term by the empirical (1 - eps/3) quantile of N
calibration missions, so "probability >= 1 - eps over the benign noise" holds only in the
large-sample limit. Here each margin is instead a distribution-free upper confidence bound on
that quantile: the order statistic X_(k) of the N calibration values, with k the smallest index
such that

    P( Bin(N, q) >= k ) <= delta / 3,          q = 1 - eps / 3,

so that P( X_(k) >= x_q ) >= 1 - delta/3 for any continuous distribution. By a union bound over
the three margins (jump rule, anchor gate, raw command), with confidence at least 1 - delta over
the calibration sample, every margin dominates its quantile, and the LP bound then holds with
probability at least 1 - eps over the benign noise, jointly for every attack in the class.

Output: results/r10_bound_conf.csv (provenance = physics_model): for each T_a and LoE, the bound
with the empirical margins (as r8) and with the corrected margins.
Usage:  python3 r10_confidence_bound.py [--delta 0.05]
"""
import argparse
import csv
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy.stats import binom

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r8_analytic_bound as R8  # noqa: E402
from constants import DT, U_MAX  # noqa: E402
import run_pilot as RP  # noqa: E402
from sim import simulate  # noqa: E402

EPS, FPR, N = 0.01, 0.01, 4000
TAS, LOES = (0.5, 1.0, 2.0, 3.0, 5.0, 10.0), (1.0, 0.7)


def order_index(n, q, alpha):
    """Smallest k (1-based) with P(Bin(n, q) >= k) <= alpha: X_(k) >= x_q with prob. >= 1 - alpha."""
    k = int(binom.ppf(1 - alpha, n, q)) + 1
    while k > 1 and binom.sf(k - 2, n, q) <= alpha:      # sf(k-2) = P(Bin >= k-1)
        k -= 1
    while binom.sf(k - 1, n, q) > alpha:
        k += 1
    if k > n:
        raise ValueError(f"n = {n} is too small for q = {q}, alpha = {alpha}")
    return k


def margins(delta):
    ben = simulate(N, 1001, w20=RP.wind(N, 1001))          # the E1 calibration missions, as in r8
    q = 1 - EPS / 3
    k = order_index(N, q, delta / 3)
    out = {"k": k, "n": N, "q": q}
    for name, key in (("S1", "S1"), ("SA", "SA"), ("umax", "umax")):
        x = np.sort(ben[key])
        out[name] = {"empirical": float(np.quantile(ben[key], q)), "corrected": float(x[k - 1])}
    return out


def job(args):
    Ta, loe, m, which = args
    js = json.loads((R8.RES / "e1_calibration.json").read_text())
    th1 = {float(k_): v for k_, v in js["stack"].items()}[FPR]["D1"]
    thA = js["anchor"]
    c1 = th1 + m["S1"][which]
    ca = np.sqrt(thA) + np.sqrt(m["SA"][which])
    cu = U_MAX + m["umax"][which]
    b, kb = R8.bound(Ta, loe, c1, ca, True, stride=20, cu=cu)
    return Ta, loe, which, b, kb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delta", type=float, default=0.05)
    ap.add_argument("--par", type=int, default=4)
    a = ap.parse_args()
    m = margins(a.delta)
    print(f"order statistic k = {m['k']} of n = {N} (q = {m['q']:.5f}, delta/3 = {a.delta / 3:.4f}); "
          f"empirical index ~ {int(np.ceil(m['q'] * N))}", flush=True)
    for s in ("S1", "SA", "umax"):
        print(f"  margin {s}: empirical {m[s]['empirical']:.4f} -> corrected {m[s]['corrected']:.4f}", flush=True)
    jobs = [(Ta, loe, m, w) for Ta in TAS for loe in LOES for w in ("empirical", "corrected")]
    res = {}
    with Pool(a.par) as p:
        for Ta, loe, w, b, kb in p.imap_unordered(job, jobs):
            res[(Ta, loe, w)] = (b, kb)
            print(f"Ta={Ta} loe={loe} {w}: {b:.3f} m at t={kb * DT:.2f} s", flush=True)
    rows = []
    for Ta in TAS:
        for loe in LOES:
            be, ke = res[(Ta, loe, "empirical")]; bc, kc = res[(Ta, loe, "corrected")]
            rows.append({"fpr": FPR, "eps": EPS, "delta": a.delta, "n_cal": N, "order_k": m["k"],
                         "T_anchor_s": Ta, "loe": loe, "constraints": "anchor gate + D1 + D_sat",
                         "delta_cert_empirical_m": round(be, 3), "delta_cert_corrected_m": round(bc, 3),
                         "argmax_t_corrected_s": round(kc * DT, 2), "stride_steps": 20,
                         "margin_S1_emp": round(m["S1"]["empirical"], 4), "margin_S1_cor": round(m["S1"]["corrected"], 4),
                         "margin_SA_emp": round(m["SA"]["empirical"], 4), "margin_SA_cor": round(m["SA"]["corrected"], 4),
                         "margin_umax_emp": round(m["umax"]["empirical"], 4), "margin_umax_cor": round(m["umax"]["corrected"], 4),
                         "provenance": "physics_model"})
    with open(R8.RES / "r10_bound_conf.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
