#!/usr/bin/env python3
"""E4 -- dynamics of the projection layer under a moving certificate.

(a) Hysteresis sweep (Thm 2): acquisition needs rho <= alpha - h, holding
    needs rho <= alpha. Record forced releases, all reassignments, certified
    coverage and inter-epoch exposure; check forced_i <= TV+_i / h per agent.
(b) Look-ahead sweep (Thm 3): acquisition needs rho + kappa*H <= alpha.
    Exposure (feasible at decision, infeasible before the next epoch) must be
    explained entirely by upward jumps when H >= dt.
(c) Misreporting (Prop. 6): f agents report rho = 0. Reported deficiency
    differs from the true one by at most f; violations come only from liars.
Policy: a fixed heuristic proposer (keep current task, else nearest), so the
sweep isolates the allocation layer. Outputs: results/e4_hysteresis.csv,
e4_lookahead.csv, e4_liars.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from certcmdp.certificate import OUT, KAPPA, ALERT_LIMITS  # noqa: E402
from certcmdp import combinatorics as C  # noqa: E402
from certcmdp.env import CertSwarm, EnvConfig  # noqa: E402


def write(name, rows):
    with (OUT / name).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def heuristic(env):
    d = np.linalg.norm(env.site[:, None] - env.pos[:, :, None], axis=-1)
    near = d.argmin(-1)
    return np.where(env.assign >= 0, env.assign, near)


def run(eta=0.0, H=0.0, Hkeep=0.0, seeds=(0, 1, 2, 3), B=16, T=300, dt=0.5):
    agg = {"forced": [], "switches": [], "r_cert": [], "exposure": [], "exp_nojump": [],
           "bound_ok": [], "viol": [], "cov_ratio": []}
    for s in seeds:
        T = int(round(150.0 / dt))
        env = CertSwarm(B, EnvConfig(dt=dt, horizon=T), seed=100 + s)
        env.reset()
        tv = np.zeros((B, env.cfg.N))
        forced = np.zeros((B, env.cfg.N))
        for t in range(T):
            prev = env.assign.copy()
            prop = heuristic(env)
            ex = env.allocate(prop, "project", eta=eta, lookahead=KAPPA * H,
                              keep_lookahead=KAPPA * Hkeep)
            # forced release: held j at t-1, rho now > alpha_j
            bidx = np.arange(B)[:, None]
            a_prev = np.where(prev >= 0, env.alpha[bidx, np.maximum(prev, 0)], np.inf)
            forced += (prev >= 0) & (env.rho > a_prev)
            rho0 = env.rho.copy()
            jumps0 = env.cert.n_up_jumps.copy()
            _, info, _ = env.step(ex)
            tv += np.maximum(env.rho - rho0, 0)
            jumped = env.cert.n_up_jumps > jumps0
            a_ex = np.where(ex >= 0, env.alpha[bidx, np.maximum(ex, 0)], np.inf)
            expo = (ex >= 0) & (rho0 <= a_ex) & (env.rho > a_ex)
            agg["exposure"].append(expo.sum() / (B * env.cfg.N))
            agg["exp_nojump"].append((expo & ~jumped).sum())
            agg["switches"].append(info["switches"].mean() / env.cfg.N)
            agg["r_cert"].append(info["r_cert"].mean())
            agg["viol"].append(info["viol"].sum())
            agg["cov_ratio"].append(np.mean(info["assigned_feasible"] / np.maximum(info["bound"], 1)))
        if eta > 0:   # Thm 2 with h_min = eta * min alert limit
            agg["bound_ok"].append(float(np.mean(forced <= tv / (eta * min(ALERT_LIMITS)) + 1)))
        agg["forced"].append(forced.mean() / T)
    return {
        "forced_per_agent_step": float(np.mean(agg["forced"])),
        "switches_per_agent_step": float(np.mean(agg["switches"])),
        "r_cert": float(np.mean(agg["r_cert"])),
        "assigned_over_bound": float(np.mean(agg["cov_ratio"])),
        "exposure_per_agent_step": float(np.mean(agg["exposure"])),
        "exposure_without_jump": int(np.sum(agg["exp_nojump"])),
        "violations": int(np.sum(agg["viol"])),
        "thm2_bound_holds_frac": (float(np.mean(agg["bound_ok"])) if agg["bound_ok"] else ""),
    }


def liars(n=4000, seed=4):
    rng = np.random.default_rng(seed)
    rows = []
    for f in range(0, 5):
        dev, viol_nonliar, viol_liar, maxdev = [], 0, 0, 0
        for _ in range(n):
            N, M = 12, 8
            rho = KAPPA * rng.exponential(1.2, N)
            alpha = rng.choice(ALERT_LIMITS, M)
            L = rng.choice(N, f, replace=False)
            rep = rho.copy(); rep[L] = 0.0
            dd = abs(C.deficiency(rep, alpha) - C.deficiency(rho, alpha))
            dev.append(dd); maxdev = max(maxdev, dd)
            a = C.nested_greedy_fast(rep, alpha)
            bad = np.array([a[i] >= 0 and rho[i] > alpha[a[i]] for i in range(N)])
            isl = np.zeros(N, bool); isl[L] = True
            viol_liar += int((bad & isl).sum()); viol_nonliar += int((bad & ~isl).sum())
        rows.append({"liars_f": f, "instances": n, "mean_abs_dev_d": float(np.mean(dev)),
                     "max_abs_dev_d": maxdev, "violations_by_liars": viol_liar,
                     "violations_by_honest": viol_nonliar})
    return rows


def main():
    rows = []
    for eta in (0.0, 0.05, 0.1, 0.2, 0.3, 0.5):
        r = {"eta": eta, **run(eta=eta)}
        rows.append(r); print(r)
    write("e4_hysteresis.csv", rows)
    rows = []
    for name, H, Hk, dt in (("standard", 0.0, 0.0, 0.5), ("release_only", 0.0, 0.5, 0.5),
                            ("predictive_dt", 0.5, 0.5, 0.5), ("predictive_1s", 1.0, 0.5, 0.5),
                            ("predictive_2s", 2.0, 0.5, 0.5),
                            ("standard_5Hz", 0.0, 0.0, 0.19), ("predictive_dt_5Hz", 0.19, 0.19, 0.19)):
        r = {"config": name, "dt_s": dt, "H_s": H, "lookahead_m": round(KAPPA * H, 3),
             "keep_lookahead_m": round(KAPPA * Hk, 3),
             **run(H=H, Hkeep=Hk, dt=dt)}
        rows.append(r); print(r)
    write("e4_lookahead.csv", rows)
    lr = liars()
    write("e4_liars.csv", lr)
    for r in lr:
        print(r)


if __name__ == "__main__":
    main()
