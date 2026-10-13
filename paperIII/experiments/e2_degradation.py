#!/usr/bin/env python3
"""E2 -- coverage as certificates degrade (RQ2) and the population lift.

(a) Binary collapse. A fraction phi of N agents loses its certificate
    (rho -> inf; in the data, one undetected relay-delay episode moves rho by
    KAPPA * hidden residual >= 20 m, i.e. past every alert limit). Compare the
    measured maximum coverage under random collapse and under the optimal
    adversary with the bounds of Lemma 1 / Prop. 3.
(b) Graded degradation. A fraction phi of agents dead-reckons for tau seconds
    (rho += KAPPA * tau). Compare random and brute-force-worst subsets with the
    graded bound of Prop. 4.
(c) Population lift. Predict P(full coverage) for a fleet of size N from the
    per-agent stationary level distribution, assuming agents are independent
    (the lift's evidence obligation), and compare with simulation under
    (i) independent degradation and (ii) spatially correlated jammers.
Outputs: results/e2_collapse.csv, e2_graded.csv, e2_lift.csv, e2_fleet_sizing.csv
"""
from __future__ import annotations

import csv
import itertools
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from certcmdp.certificate import (OUT, ALERT_LIMITS, KAPPA, residual_pools,  # noqa: E402
                                  CertificateProcess, ThreatProfile)
from certcmdp import combinatorics as C  # noqa: E402
from certcmdp.env import CertSwarm, EnvConfig  # noqa: E402

PHIS = np.round(np.arange(0, 0.85, 0.05), 2)


def write(name, rows):
    with (OUT / name).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def graded_bound(rho, alpha, b, shift):
    """Prop. 4: deficiency after ANY b agents' rho grows by `shift` is at most
    max_k (k - max(n_k - b, n_k(rho + shift)))^+ ."""
    n = C.count_profile(rho, alpha)
    ns = C.count_profile(rho + shift, alpha)
    k = np.arange(1, len(n) + 1)
    return int(max(0, (k - np.maximum(n - b, ns)).max(initial=0)))


_SNAP = {}


def base_fleet(rng, N, M):
    """A fleet caught at a random instant of an operation: certificates drawn
    from the stationary state of the certificate process (benign floor from the
    measured hop pool, dead-reckoning and relay episodes per ThreatProfile with
    jam_rate=0.03), so agents are heterogeneous, as in flight."""
    if N not in _SNAP:
        cp = CertificateProcess(4000, N, ThreatProfile(jam_rate=0.03), np.random.default_rng(11))
        for _ in range(300):
            cp.step(1.0)
        _SNAP[N] = cp.rho().copy()
    rho = _SNAP[N][rng.integers(len(_SNAP[N]))]
    alpha = np.sort(rng.choice(ALERT_LIMITS, M))
    return rho, alpha


def part_a(rng, N=12, M=8, reps=400):
    rows = []
    for phi in PHIS:
        b = int(math.ceil(phi * N - 1e-9))
        rnd, wc, d0s = [], [], []
        for _ in range(reps):
            rho, alpha = base_fleet(rng, N, M)
            d0 = C.deficiency(rho, alpha)
            S = rng.choice(N, b, replace=False)
            r2 = rho.copy(); r2[S] = np.inf
            rnd.append(M - C.deficiency(r2, alpha))
            wc.append(M - C.worst_case_deficiency(rho, alpha, b))
            d0s.append(M - d0)
        rows.append({"phi": phi, "b": b, "N": N, "M": M,
                     "cov_nominal": np.mean(d0s),
                     "cov_random": np.mean(rnd), "cov_random_p05": np.percentile(rnd, 5),
                     "cov_worst": np.mean(wc),
                     "bound_generic": max(0.0, np.mean(d0s) - b)})
    return rows


def part_b(rng, N=10, M=6, reps=150):
    rows = []
    for tau in (0.5, 1.0, 2.0):
        shift = KAPPA * tau
        for phi in PHIS[::2]:
            b = int(round(phi * N))
            rnd, wc, bd = [], [], []
            for _ in range(reps):
                rho, alpha = base_fleet(rng, N, M)
                S = rng.choice(N, b, replace=False)
                r2 = rho.copy(); r2[S] += shift
                rnd.append(M - C.deficiency(r2, alpha))
                worst = M
                for T in itertools.combinations(range(N), b):
                    r3 = rho.copy(); r3[list(T)] += shift
                    worst = min(worst, M - C.deficiency(r3, alpha))
                wc.append(worst)
                bd.append(M - graded_bound(rho, alpha, b, shift))
            rows.append({"tau_s": tau, "shift_m": round(shift, 3), "phi": phi, "b": b,
                         "cov_random": np.mean(rnd), "cov_worst": np.mean(wc),
                         "cov_bound": np.mean(bd),
                         "bound_violations": int(np.sum(np.asarray(wc) < np.asarray(bd))),
                         "bound_tight_frac": float(np.mean(np.asarray(wc) == np.asarray(bd)))})
    return rows


def p_full_iid(N, alpha, q):
    """P(n_k >= k for all k) when each agent independently falls in level
    l (rho <= ALERT_LIMITS[l], first such) with prob q[l], q[-1] = none.
    Exact DP over agents with state = counts per level (small M only)."""
    lv = np.asarray(ALERT_LIMITS)
    need = [int((alpha <= x).sum()) for x in lv]       # tasks with alpha <= level x
    # cumulative requirement: #agents with rho<=lv[l] must be >= #tasks with alpha<=lv[l]
    # (for nested graphs with alpha on the grid, this is exactly Hall on prefixes)
    from functools import lru_cache
    cum = np.cumsum(q[:-1])
    # multinomial over levels: P(N_0..N_3, rest); condition on cumulative counts
    dist = {(): 1.0}
    probs = list(q)
    # enumerate compositions via DP on cumulative counts
    dp = np.zeros(N + 1); dp[0] = 1.0   # dp[c] = P(first l levels hold c agents) restricted to valid
    total = np.zeros(N + 1); total[0] = 1.0
    rem_p = 1.0
    # sequential binomial splitting: agents not yet in levels < l fall in level l w.p. q_l/rem
    state = {0: 1.0}
    for l in range(len(lv)):
        p_l = probs[l] / rem_p if rem_p > 1e-15 else 0.0
        new = {}
        for c, pc in state.items():
            left = N - c
            for x in range(left + 1):
                pr = math.comb(left, x) * p_l ** x * (1 - p_l) ** (left - x)
                cc = c + x
                if cc >= need[l]:
                    new[cc] = new.get(cc, 0.0) + pc * pr
        state = new
        rem_p -= probs[l]
    return float(sum(state.values()))


def part_c(seed=7, N=12, M=8, B=64, T=400):
    """Stationary per-agent level distribution and full-coverage frequency."""
    rows, sizing = [], []
    for corr in ("independent", "spatial_jammers"):
        cfg = EnvConfig(N=N, M=M, n_jammers=(3 if corr == "spatial_jammers" else 0),
                        jam_radius=260.0)
        if corr == "independent":   # same marginal stress, but per-agent and independent
            cfg.threat = ThreatProfile(jam_rate=0.03)
        env = CertSwarm(B, cfg, seed=seed)
        env.reset()
        # hold alert limits fixed across the batch to make the lift well-posed
        alpha = np.sort(np.array([2.0, 5.0, 5.0, 10.0, 10.0, 20.0, 20.0, 20.0]))[:M]
        env.alpha[:] = alpha
        # agents loiter around three operating areas, as a tasked fleet does;
        # co-location is what turns a jammer into a common-cause failure
        centres = env.rng.uniform(0.2 * cfg.L, 0.8 * cfg.L, (B, 3, 2))
        home = centres[np.arange(B)[:, None], np.arange(N)[None, :] % 3]
        levels, full = [], []
        for t in range(T):
            env.pos = home + env.rng.normal(0, 60, env.pos.shape)
            env.jam_v = 0.9 * env.jam_v + 0.1 * env.rng.normal(0, 1, env.jam_v.shape)
            sp = np.linalg.norm(env.jam_v, axis=-1, keepdims=True) + 1e-9
            env.jam = np.clip(env.jam + env.jam_v / sp * cfg.jam_speed * cfg.dt, 0, cfg.L)
            jm = env.jam_mask() if cfg.n_jammers else None
            rho = env.cert.step(cfg.dt, jam_mask=jm)
            if t < 50:
                continue
            lv = np.searchsorted(np.asarray(ALERT_LIMITS), rho, side="left")  # 0..4
            levels.append(lv.ravel())
            full.append(C.batch_deficiency(rho, alpha))
        lv = np.concatenate(levels)
        q = np.bincount(lv, minlength=len(ALERT_LIMITS) + 1) / lv.size
        dsim = np.stack(full)                       # (T', B)
        pred = p_full_iid(N, alpha, q)
        # i.i.d. Monte Carlo of the deficiency distribution with the same marginals
        mc_rng = np.random.default_rng(5)
        lvl_rho = np.r_[np.asarray(ALERT_LIMITS), 1e9]
        draws = lvl_rho[mc_rng.choice(len(q), size=(200000, N), p=q)]
        d_iid = C.batch_deficiency(draws, alpha)
        boot = np.random.default_rng(9)
        for k in range(0, 7):
            tail_sim = (dsim >= k).mean(0) if k else (dsim == 0).mean(0)   # per fleet
            bs = [tail_sim[boot.integers(0, B, B)].mean() for _ in range(2000)]
            rows.append({"dependence": corr, "N": N, "M": M, "event": ("d=0" if k == 0 else f"d>={k}"),
                         "q_le2": q[0], "q_le10": q[:3].sum(), "q_le20": q[:4].sum(),
                         "p_iid_pred": (d_iid == 0).mean() if k == 0 else (d_iid >= k).mean(),
                         "p_iid_exact": pred if k == 0 else "",
                         "p_sim": tail_sim.mean(),
                         "p_sim_lo": np.percentile(bs, 2.5), "p_sim_hi": np.percentile(bs, 97.5),
                         "n_fleets": B, "n_steps": dsim.shape[0]})
        for n in range(M, 31):
            sizing.append({"dependence": corr, "N": n, "p_full_pred_iid": p_full_iid(n, alpha, q)})
    return rows, sizing


def main():
    rng = np.random.default_rng(3)
    write("e2_collapse.csv", part_a(rng))
    write("e2_graded.csv", part_b(rng))
    lift, sizing = part_c()
    write("e2_lift.csv", lift)
    write("e2_fleet_sizing.csv", sizing)
    for r in lift:
        print(r)


if __name__ == "__main__":
    main()
