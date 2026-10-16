"""A6 policy search (runbook P2.1): CEM, then CMA-ES as a second optimiser, on single-aircraft lanes.

With separation off the aircraft are decoupled, so a single-aircraft lane is the exact
one-aircraft problem and 12x cheaper; the best policy is then evaluated on full fleets.
Search missions come from block 12xxx (primary) or 13xxx (independently seeded re-search);
evaluation missions (14xxx) are never seen here.

Goals (maximised):
  G1 safety violation : - min true margin (positive only if the corridor was left)
  G2 maximal fallback : fallback steps / aircraft-steps
  G3 stealthy denial  : (1 - completed) + 0.5 (1 - progress) - 2 * stealth alarm
  G4 boundary riding  : fraction of steps with plan slack < 0.1 m - 0.5 * progress

    python3 adaptive.py --attacker A6 --goals G1,G2,G3,G4 --btot b0,b1 --margins 20 --opt cem \
        --seed-block 12000 --par 4 --out ../results/a6_search.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

try:
    from . import constants as C
    from .attacks import OracleAdversarialPlanner, DIM, N_EPOCH, hand_policies
    from .budget import level_values
    from .episode import EpisodeCfg, run_episode
except ImportError:
    import constants as C
    from attacks import OracleAdversarialPlanner, DIM, N_EPOCH, hand_policies
    from budget import level_values
    from episode import EpisodeCfg, run_episode

B_ATT_SEARCH = 14            # epochs the attacker may hijack during the search (runbook: unbounded A6)
NATURE = dict(w_mode="dryden", e_mode="vertex")   # physical wind (A1 holds), worst-case estimate offset


def quiet():
    """OSQP prints a polishing note from C even with verbose=False; silence fd 1 in workers."""
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)


@__import__("functools").lru_cache(maxsize=None)
def stealth_thresholds():
    p = C.RESULTS / "stealth_monitor.csv"
    if not p.exists():
        raise FileNotFoundError(f"{p} missing: run run_campaign.py --phase p2-budget --stage monitor first")
    rows = {(r["b_tot_level"], float(r["m"])): r for r in csv.DictReader(open(p))}
    return rows


def alarm(rec, level, m):
    thr = stealth_thresholds()[(level, float(m))]
    ti, tf = float(thr["thr_interventions"]), float(thr["thr_fallback"])
    return [int(a > ti or b > tf) for a, b in zip(rec["interventions_i"], rec["fallback_i"])]


def score(rec, goal, level, m):
    n = rec["aircraft_steps"] or 1
    prog = rec["progress_pct"] / 100.0
    if goal == "G1":
        mm = rec["min_true_margin"]
        return -mm if mm is not None and np.isfinite(mm) else 0.0
    if goal == "G2":
        return rec["fallback_steps"] / n
    if goal == "G3":
        return (1 - int(rec["completed"])) + 0.5 * (1 - prog) - 2.0 * max(alarm(rec, level, m))
    if goal == "G4":
        return rec["boundary_steps"] / n - 0.5 * prog
    raise ValueError(goal)


def _eval(job):
    theta, goal, level, b, m, seed = job
    pl = OracleAdversarialPlanner(theta, b_att=B_ATT_SEARCH, n_hijack=1)
    rec = run_episode(EpisodeCfg(n_uav=1, m=m, b_tot_level=level, b_tot_m=b, planner_obj=pl, attacker="A6", goal=goal,
                                 mission_seed=seed, **NATURE))
    return score(rec, goal, level, m), rec["violations_corridor"], rec["aircraft_steps"]


def evaluate(pool, thetas, goal, level, b, m, seeds):
    jobs = [(th, goal, level, b, m, s) for th in thetas for s in seeds]
    res = pool.map(_eval, jobs, chunksize=1)
    sc = np.array([r[0] for r in res]).reshape(len(thetas), len(seeds))
    viol = sum(r[1] for r in res); steps = sum(r[2] for r in res)
    return sc.mean(1), viol, steps


def cem(pool, goal, level, b, m, seeds, rng, cand=12, elite=4, gens=25, trace=None):
    mu = np.full(DIM, 0.5); sd = np.full(DIM, 0.3)
    best, best_s = None, -np.inf
    viol = steps = 0
    for g in range(gens):
        X = np.clip(mu + sd * rng.standard_normal((cand, DIM)), 0, 1)
        if g == 0:                                   # seed the population with the hand-designed members
            H = np.array(list(hand_policies().values()))
            X[:len(H)] = H[:cand]
        s, v, n = evaluate(pool, list(X), goal, level, b, m, seeds)
        viol += v; steps += n
        o = np.argsort(-s)
        E = X[o[:elite]]
        mu = E.mean(0); sd = np.maximum(0.7 * E.std(0) + 0.3 * sd * 0.5, 0.02)
        if s[o[0]] > best_s:
            best_s, best = float(s[o[0]]), X[o[0]].copy()
        if trace is not None:
            trace.append(dict(opt="cem", gen=g, evals=(g + 1) * cand * len(seeds), best_so_far=best_s,
                              gen_best=float(s[o[0]])))
    return best, best_s, viol, steps


def cmaes(pool, goal, level, b, m, seeds, rng, popsize=16, gens=25, trace=None, x0=None):
    import cma
    es = cma.CMAEvolutionStrategy(list(np.full(DIM, 0.5) if x0 is None else x0), 0.3,
                                  {"popsize": popsize, "bounds": [0, 1], "seed": int(rng.integers(1, 2**31 - 1)),
                                   "verbose": -9})
    best, best_s = None, -np.inf
    viol = steps = 0
    for g in range(gens):
        X = np.clip(np.array(es.ask()), 0, 1)
        s, v, n = evaluate(pool, list(X), goal, level, b, m, seeds)
        viol += v; steps += n
        es.tell(list(X), list(-s))
        o = int(np.argmax(s))
        if s[o] > best_s:
            best_s, best = float(s[o]), X[o].copy()
        if trace is not None:
            trace.append(dict(opt="cma", gen=g, evals=(g + 1) * popsize * len(seeds), best_so_far=best_s,
                              gen_best=float(s[o])))
    return best, best_s, viol, steps


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--attacker", default="A6")
    ap.add_argument("--goals", default="G1,G2,G3,G4")
    ap.add_argument("--btot", default="b0,b1")
    ap.add_argument("--margins", default="20")
    ap.add_argument("--opt", default="cem")
    ap.add_argument("--seed-block", type=int, default=12000)
    ap.add_argument("--par", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--cand", type=int, default=12)
    ap.add_argument("--elite", type=int, default=4)
    ap.add_argument("--gens", type=int, default=25)
    ap.add_argument("--missions", type=int, default=16)
    ap.add_argument("--out", default=str(C.RESULTS / "a6_search.csv"))
    a = ap.parse_args(argv)
    if a.attacker != "A6":
        raise SystemExit("only A6 is searched here (A1-A5 need the language harness, P4)")
    if a.seed_block not in (12000, 13000):
        raise SystemExit("search seed blocks are 12xxx (primary) and 13xxx (held-out re-search)")
    from run_campaign import dispatchable
    lv = level_values()
    seeds = [a.seed_block + j for j in range(a.missions)]
    rows, trace_rows = [], []
    out = C.RESULTS / os.path.basename(a.out) if not os.path.isabs(a.out) else a.out
    done = set()
    if os.path.exists(out):
        for r in csv.DictReader(open(out)):
            done.add((r["goal"], r["b_tot_level"], float(r["m"]), r["opt"]))
            rows.append(r)
    with Pool(a.par, initializer=quiet) as pool:
        for m in (float(x) for x in a.margins.split(",")):
            for level in a.btot.split(","):
                if not dispatchable(level, m):
                    print(f"skip {level} m={m:g}: not dispatchable", flush=True)
                    continue
                for goal in a.goals.split(","):
                    for opt in a.opt.split(","):
                        if (goal, level, m, opt) in done:
                            continue
                        rng = np.random.default_rng(a.seed_block + 100 * ("G1", "G2", "G3", "G4").index(goal)
                                                    + 10 * ("b0", "b1", "b2", "b3").index(level) + int(m)
                                                    + (500 if opt == "cma" else 0))
                        t0 = time.perf_counter(); tr = []
                        f = cem if opt == "cem" else cmaes
                        kw = dict(cand=a.cand, elite=a.elite, gens=a.gens) if opt == "cem" else dict(gens=a.gens)
                        best, s, viol, steps = f(pool, goal, level, lv[level], m, seeds, rng, trace=tr, **kw)
                        row = dict(attacker="A6", goal=goal, b_tot_level=level, b_tot_m=lv[level], m=m, opt=opt,
                                   seed_block=a.seed_block, missions=a.missions, best_score=s,
                                   evaluations=tr[-1]["evals"], search_aircraft_steps=steps, search_violations=viol,
                                   wall_s=round(time.perf_counter() - t0, 1),
                                   theta=";".join(f"{x:.5f}" for x in best), b_att=B_ATT_SEARCH,
                                   nature=json.dumps(NATURE), provenance="sim")
                        rows.append(row)
                        for t in tr:
                            trace_rows.append(dict(goal=goal, b_tot_level=level, m=m, seed_block=a.seed_block, **t))
                        print(f"{goal} {level} m={m:g} {opt}: best {s:.4f}, {viol} violations in {steps} "
                              f"search aircraft-steps, {row['wall_s']} s", flush=True)
                        with open(out, "w", newline="") as fh:
                            w = csv.DictWriter(fh, fieldnames=list(row)); w.writeheader(); w.writerows(rows)
                        tp = str(out).replace(".csv", "_trace.csv")
                        new = not os.path.exists(tp)
                        with open(tp, "a", newline="") as fh:
                            w = csv.DictWriter(fh, fieldnames=list(trace_rows[0]))
                            if new:
                                w.writeheader()
                            w.writerows(trace_rows)
                        trace_rows = []


if __name__ == "__main__":
    main()
