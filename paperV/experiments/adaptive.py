"""Adaptive oracle search (A7 in the pilot naming; 'A6 oracle action-space adversary' in the
research plan's ladder). Cross-entropy method over the oracle family in attacks.py, with the
safety filter and adversarial nature in the loop. Seeds 2xxx = attacker optimisation;
evaluation always uses held-out 4xxx seeds (never re-tuned after looking at them).

objective 'violation': minimise the minimum TRUE margin (corridor or separation) over the episode
objective 'denial'   : maximise  (#aircraft missing the deadline)/N + fallback fraction
                       + 0.25 * intervention fraction   (progress-intent constrained box)
"""
from __future__ import annotations

import numpy as np

from attacks import BOX_VIOLATION, BOX_DENIAL
from episode import EpCfg, run_episode


def score(res, objective):
    if objective == "violation":
        return -min(res["min_corridor_margin"], res["min_sep_margin"])       # maximise
    N = res["N"]
    return ((N - res["n_reached_dl"]) / N + res["fallback_ticks"] / res["n_ticks"]
            + 0.25 * res["interventions"] / res["aircraft_ticks"])


def cem(N, objective, base: dict, pool=None, n_cand=8, n_elite=3, n_gen=4, n_train=2, seed=2000, log=None):
    box = BOX_VIOLATION if objective == "violation" else BOX_DENIAL
    rng = np.random.default_rng(seed + 17 * N + (0 if objective == "violation" else 1))
    mu = box.mean(1); sd = (box[:, 1] - box[:, 0]) / 2.0
    best, best_s = None, -np.inf
    for g in range(n_gen):
        C = np.clip(mu + sd * rng.standard_normal((n_cand, len(mu))), box[:, 0], box[:, 1])
        jobs = []
        for c in C:
            for s in range(n_train):
                jobs.append(EpCfg(N=N, planner=f"oracle_{objective}", theta=tuple(c), seed=seed + s, **base))
        res = (pool.map(_run, jobs) if pool else list(map(_run, jobs)))
        sc = np.array([np.mean([score(res[i * n_train + s], objective) for s in range(n_train)])
                       for i in range(n_cand)])
        order = np.argsort(-sc)
        E = C[order[:n_elite]]
        mu = E.mean(0); sd = 0.7 * E.std(0) + 0.05 * (box[:, 1] - box[:, 0])
        if sc[order[0]] > best_s:
            best_s, best = float(sc[order[0]]), C[order[0]].copy()
        if log is not None:
            for i in range(n_cand):
                log.append(dict(N=N, objective=objective, gen=g, cand=i, score=float(sc[i]),
                                theta=";".join(f"{v:.4f}" for v in C[i])))
    return best, best_s


def _run(cfg):
    r = run_episode(cfg, keep_times=False)
    return r
