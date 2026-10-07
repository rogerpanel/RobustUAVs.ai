#!/usr/bin/env python3
"""The arithmetic of the per-flight-hour quantifier (Paper II, Props. 3-4).

(a) Rate lift L_rate.  With f decisions per second, each hazardous with
    probability p, independent: lambda = 3600 f p per flight hour.  With k-of-k
    temporal confirmation under a two-state Markov error process of persistence
    rho = P(err_t | err_{t-1}), hazardous runs of length >= k start at rate
    3600 f p (1-rho) rho^(k-1) (k >= 2); rho = p recovers independence.
(b) Zero-failure demonstration.  Under a Poisson failure model, observing zero
    failures in T hours rejects lambda >= lambda_0 at confidence 1-a iff
    T >= ln(1/a) / lambda_0.  At a = 0.05 this is the "rule of three".
(c) The SORA 2.5 Annex E test-hour ladder (30/300/3000/30000 h, 95 %) read
    through (b).
(d) Frame-level testing buys no economy: demonstrating p <= p* per frame needs
    ln(1/a)/p* frames = the same flight hours as (b).

Outputs: ../results/rate_requirements.csv, rate_correlation.csv,
         sora_ladder.csv, test_economy.csv
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

R = Path(__file__).resolve().parent.parent / "results"
R.mkdir(exist_ok=True)

TARGETS = [1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-9]
RATES = [1, 5, 10, 30, 60, 100]
ALPHA = 0.05


def per_decision_requirement(lam, f, k=1, rho=None):
    """Largest per-decision hazard probability p meeting lam per hour."""
    if k == 1:
        return lam / (3600.0 * f)
    # solve 3600 f p (1-rho) rho^(k-1) = lam for p, with rho given (Markov)
    if rho is None:                       # independence: run start ~ p(1-p) p^(k-1) ~ p^k
        return (lam / (3600.0 * f)) ** (1.0 / k)
    return lam / (3600.0 * f * (1 - rho) * rho ** (k - 1))


def zero_failure_hours(lam, a=ALPHA):
    return math.log(1 / a) / lam


def main():
    rows = []
    for lam in TARGETS:
        for f in RATES:
            rows.append({"lambda_per_h": lam, "f_hz": f,
                         "p_star_k1": per_decision_requirement(lam, f),
                         "p_star_k3_indep": per_decision_requirement(lam, f, k=3),
                         "decisions_per_h": 3600 * f})
    with open(R / "rate_requirements.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    # correlation: f=30 Hz, lam=1e-4/h, k=3 confirmation, persistence rho
    corr = []
    for rho in [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 2/3, 0.7, 0.8, 0.9, 0.95, 0.99, 0.999]:
        if rho == 0.0:
            p = per_decision_requirement(1e-4, 30, k=3)          # independence limit
        else:
            p = per_decision_requirement(1e-4, 30, k=3, rho=rho)
        corr.append({"rho": rho, "p_star": min(p, 1.0),
                     "gain_vs_k1": min(p, 1.0) / per_decision_requirement(1e-4, 30),
                     "gain_bound_markov": 3 ** 3 / 2 ** 2})
    with open(R / "rate_correlation.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(corr[0].keys())); w.writeheader(); w.writerows(corr)

    ladder = []
    for sail, hours in (("I", 30), ("II", 300), ("III", 3000), ("IV", 30000)):
        lam = math.log(1 / ALPHA) / hours
        ladder.append({"sail": sail, "hours": hours, "implied_lambda": lam,
                       "nearest_decade": 10 ** round(math.log10(lam)),
                       "rule_of_three_hours": 3 / 10 ** round(math.log10(lam))})
    with open(R / "sora_ladder.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ladder[0].keys())); w.writeheader(); w.writerows(ladder)

    econ = []
    for lam in TARGETS:
        for f in (10, 30):
            p = per_decision_requirement(lam, f)
            frames = math.log(1 / ALPHA) / p
            econ.append({"lambda_per_h": lam, "f_hz": f, "p_star": p, "frames_needed": frames,
                         "frame_hours": frames / (3600 * f), "flight_hours_direct": zero_failure_hours(lam),
                         "years_at_24_7": zero_failure_hours(lam) / 8766})
    with open(R / "test_economy.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(econ[0].keys())); w.writeheader(); w.writerows(econ)
    return rows, corr, ladder, econ


if __name__ == "__main__":
    rows, corr, ladder, econ = main()
    print("p* at 30 Hz, 1e-4/h:", per_decision_requirement(1e-4, 30))
    for r in ladder:
        print(r)
    for r in corr:
        print(r)
    for r in econ:
        if r["f_hz"] == 30:
            print(r)
