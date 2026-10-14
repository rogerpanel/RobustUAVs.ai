#!/usr/bin/env python3
"""R6 -- vector certificates: where the closed forms stop (Remark 1).

Each aircraft carries a horizontal and a vertical protection level
(rho_h, rho_v); each task a horizontal and a vertical alert limit
(alpha_h, alpha_v). Eligibility is dominance: rho_h <= alpha_h and
rho_v <= alpha_v. The graph is no longer nested, so Lemma 1 and the
closed-form margin do not apply. We compare, per instance:

  * exact maximum coverage (Hopcroft-Karp) against the scalar surrogate
    rho~ = max(rho_h, rho_v / c), alpha~ = min(alpha_h, alpha_v / c), with
    c the median vertical/horizontal ratio. The surrogate graph is a subgraph
    of the true one (sound), so the surrogate can only lose coverage;
  * exact worst-case deficiency after b adversarial collapses (brute force
    over all b-subsets, each with a maximum matching) against the closed form
    of Prop. 3 on the surrogate, which upper-bounds it;
  * the wall time of the brute force as N grows.

The vertical/horizontal ratio is lognormal around 1.5 (VDOP typically exceeds
HDOP) with dispersion sigma; sigma = 0 is the perfectly correlated case.
Vertical alert limits {3, 6, 12, 25} m are an assumption.
Output: results/r6_vector.csv
"""
from __future__ import annotations

import csv
import itertools
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from certcmdp.certificate import OUT, KAPPA, ALERT_LIMITS  # noqa: E402
from certcmdp import combinatorics as C  # noqa: E402

V_LIMITS = (3.0, 6.0, 12.0, 25.0)   # vertical alert limits, m          [assumption]
RATIO_MED = 1.5                     # median rho_v / rho_h               [assumption]


def instance(rng, N, M, sigma):
    rho_h = KAPPA * rng.exponential(1.2, N)
    rho_v = rho_h * RATIO_MED * np.exp(sigma * rng.standard_normal(N))
    k = rng.integers(0, len(ALERT_LIMITS), M)
    # vertical limit drawn independently of the horizontal one
    a_h = np.asarray(ALERT_LIMITS)[k]
    a_v = np.asarray(V_LIMITS)[rng.integers(0, len(V_LIMITS), M)]
    return rho_h, rho_v, a_h, a_v


def exact_elig(rho_h, rho_v, a_h, a_v):
    return (rho_h[:, None] <= a_h[None, :]) & (rho_v[:, None] <= a_v[None, :])


def surrogate(rho_h, rho_v, a_h, a_v, c=RATIO_MED):
    return np.maximum(rho_h, rho_v / c), np.minimum(a_h, a_v / c)


def worst_brute(el, b):
    N, M = el.shape
    worst = 0
    for S in itertools.combinations(range(N), b):
        keep = np.ones(N, bool); keep[list(S)] = False
        worst = max(worst, M - C.brute_max_matching(el[keep]))
    return worst


def main(n=400, seed=6):
    rng = np.random.default_rng(seed)
    rows = []
    for N in (8, 12, 16, 20):
        M = (2 * N) // 3
        for sigma in (0.0, 0.25, 0.5, 1.0):
            lost, lost_frac, nested_frac = [], [], []
            gap = {b: [] for b in (1, 2, 3)}
            t_brute = {b: [] for b in (1, 2, 3)}
            t_closed = []
            for _ in range(n):
                rh, rv, ah, av = instance(rng, N, M, sigma)
                el = exact_elig(rh, rv, ah, av)
                rs, as_ = surrogate(rh, rv, ah, av)
                el_s = rs[:, None] <= as_[None, :]
                assert not (el_s & ~el).any()            # surrogate is sound
                cov = C.brute_max_matching(el)
                cov_s = M - C.deficiency(rs, as_)
                lost.append(cov - cov_s); lost_frac.append((cov - cov_s) / M)
                # is the exact graph nested (a chain graph) anyway?
                nb = [frozenset(np.flatnonzero(r)) for r in el]
                nested_frac.append(all(a <= b or b <= a for a, b in itertools.combinations(nb, 2)))
                for b in (1, 2, 3):
                    t0 = time.perf_counter()
                    wb = worst_brute(el, b)
                    t_brute[b].append(time.perf_counter() - t0)
                    t0 = time.perf_counter()
                    ws = C.worst_case_deficiency(rs, as_, b)
                    t_closed.append(time.perf_counter() - t0)
                    assert ws >= wb                       # closed form on surrogate bounds it
                    gap[b].append(ws - wb)
            row = {"N": N, "M": M, "sigma": sigma, "instances": n,
                   "frac_exact_graph_nested": float(np.mean(nested_frac)),
                   "coverage_lost_mean": float(np.mean(lost)),
                   "coverage_lost_max": int(max(lost)),
                   "coverage_lost_frac_mean": float(np.mean(lost_frac)),
                   "frac_instances_with_loss": float(np.mean(np.asarray(lost) > 0))}
            for b in (1, 2, 3):
                row[f"worst_gap_b{b}_mean"] = float(np.mean(gap[b]))
                row[f"worst_gap_b{b}_max"] = int(max(gap[b]))
                row[f"brute_ms_b{b}_median"] = 1e3 * float(np.median(t_brute[b]))
            row["closed_form_ms_median"] = 1e3 * float(np.median(t_closed))
            row["provenance"] = "sim"
            rows.append(row)
            print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}, flush=True)
    with (OUT / "r6_vector.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
