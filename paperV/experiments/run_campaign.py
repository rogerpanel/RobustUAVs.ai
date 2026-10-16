"""Paper V NON-LLM pilot campaign.

Stages (all seeds fixed; evaluation seeds 4xxx shared across stages = common random numbers):
  cem       CEM tuning of the oracle (violation / denial objectives) on 2xxx seeds, N=4;
            the N=4 optimum is transferred unchanged to N=12 (stated, not re-tuned)
  main      N in {4,12} x {benign, random, stall, oracle_violation, oracle_denial} x filter {ON, OFF}
  hand      hand-designed oracle family members (press_wall, press_neighbour, overspeed,
            goal_plus_neighbour, goal_plus_wall), ON and OFF
  budget    b_tot sweep (and gamma / staleness-envelope levels) with the covert sensing offset
            realised at the budget (A7-style composition)
  mismatch  w_true in {0, 1x, 2x, 4x} of the assumed w_bar (negative control beyond 1x)
  negative  outside (A2): uncapped staleness + relay jumps (5xxx seeds); ablations
            (no look-ahead, no continuation)
  nested    one-step nestedness / transparency study (budget.py)

Usage: python run_campaign.py [stage ...]   (default: all). Counts via env SCALE (float).
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

from adaptive import cem
from attacks import HAND_VIOLATION, HAND_DENIAL
from budget import budget_levels, nestedness_study
from constants import RESULTS, DELTA_ADV, W_BAR_NOM, GAMMA_LEVELS, provenance_rows
from episode import EpCfg, run_episode

SCALE = float(os.environ.get("SCALE", "1.0"))
WORKERS = int(os.environ.get("WORKERS", "2"))


def n(k):
    return max(2, int(round(k * SCALE)))


def _job(cfg):
    t0 = time.time()
    r = run_episode(cfg)
    r["wall_s"] = time.time() - t0
    return r


def run_jobs(jobs, stage, pool):
    jobs = sorted(jobs, key=lambda c: -(c.N * (3 if c.filter_on else 0.1)))
    rows, times = [], {}
    t0 = time.time()
    for i, r in enumerate(pool.imap_unordered(_job, jobs, chunksize=1)):
        tm = r.pop("_times", None)
        key = f"{r['tag']}|N{r['N']}|{r['planner']}|{'on' if r['filter_on'] else 'off'}|b{r['b_tot']:.3f}|w{r['w_true']:.2f}"
        if tm is not None and len(tm):
            times.setdefault(key, []).append(tm)
        rows.append(r)
        if (i + 1) % 25 == 0 or i + 1 == len(jobs):
            print(f"  [{stage}] {i+1}/{len(jobs)} episodes, {time.time()-t0:.0f}s", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / f"episodes_{stage}.csv", index=False)
    np.savez_compressed(RESULTS / f"solve_times_{stage}.npz",
                        **{k.replace("|", "__"): np.concatenate(v) for k, v in times.items()})
    return df


def load_theta():
    p = RESULTS / "oracle_theta.json"
    return json.loads(p.read_text()) if p.exists() else None


def stage_cem(pool):
    log = []
    base = dict(filter_on=True, b_tot=DELTA_ADV, nature="adversarial")
    tv, sv = cem(4, "violation", base, pool=pool, n_cand=n(8), n_elite=3, n_gen=4, n_train=2, seed=2000, log=log)
    td, sd = cem(4, "denial", base, pool=pool, n_cand=n(8), n_elite=3, n_gen=4, n_train=2, seed=2100, log=log)
    out = {"violation": tv.tolist(), "violation_score": sv, "denial": td.tolist(), "denial_score": sd,
           "note": "CEM on seeds 2000-2001 (violation) / 2100-2101 (denial), N=4, filter ON, b_tot=delta_adv, "
                   "adversarial nature; transferred unchanged to N=12."}
    (RESULTS / "oracle_theta.json").write_text(json.dumps(out, indent=1))
    pd.DataFrame(log).to_csv(RESULTS / "cem_log.csv", index=False)
    return out


def planners(theta):
    return [("benign", (), "random"), ("random", (), "random"), ("stall", (), "random"),
            ("oracle_violation", tuple(theta["violation"]), "adversarial"),
            ("oracle_denial", tuple(theta["denial"]), "adversarial")]


def stage_main(pool, theta):
    jobs = []
    for N, ne in ((4, n(40)), (12, n(14))):
        for name, th, nat in planners(theta):
            for fon in (True, False):
                for e in range(ne):
                    jobs.append(EpCfg(N=N, planner=name, theta=th, filter_on=fon, b_tot=DELTA_ADV, nature=nat,
                                      seed=4000 + e, tag="main"))
    return run_jobs(jobs, "main", pool)


def stage_hand(pool):
    jobs = []
    for N, ne in ((4, n(16)), (12, n(5))):
        for name, th in list(HAND_VIOLATION.items()) + list(HAND_DENIAL.items()):
            for fon in (True, False):
                for e in range(ne):
                    jobs.append(EpCfg(N=N, planner="oracle_" + name, theta=th, filter_on=fon, b_tot=DELTA_ADV,
                                      nature="adversarial", seed=4000 + e, tag="hand"))
    return run_jobs(jobs, "hand", pool)


def stage_budget(pool, theta):
    levels, ss = budget_levels()
    jobs = []
    for b, lab in levels:
        for e in range(n(16)):
            jobs.append(EpCfg(N=4, planner="benign", filter_on=True, b_tot=b, nature="adversarial",
                              seed=4000 + e, tag="budget"))
            jobs.append(EpCfg(N=4, planner="oracle_denial", theta=tuple(theta["denial"]), filter_on=True,
                              b_tot=b, nature="adversarial", seed=4000 + e, tag="budget"))
        for e in range(n(5)):
            jobs.append(EpCfg(N=12, planner="benign", filter_on=True, b_tot=b, nature="adversarial",
                              seed=4000 + e, tag="budget"))
    # gamma levels and staleness-envelope levels at b = delta_adv (benign, N=4)
    for g in GAMMA_LEVELS:
        for e in range(n(12)):
            jobs.append(EpCfg(N=4, planner="benign", filter_on=True, b_tot=DELTA_ADV, gamma=g, nature="adversarial",
                              seed=4000 + e, tag=f"gamma{g}"))
    for dbar in (0.5, 2.0):
        for e in range(n(12)):
            jobs.append(EpCfg(N=4, planner="benign", filter_on=True, b_tot=DELTA_ADV, delta_bar=dbar,
                              nature="adversarial", seed=4000 + e, tag=f"dbar{dbar}"))
    df = run_jobs(jobs, "budget", pool)
    (RESULTS / "budget_levels.json").write_text(json.dumps({"levels": levels, "s_star": ss}, indent=1))
    return df


def stage_mismatch(pool, theta):
    jobs = []
    for mult in (0.0, 1.0, 2.0, 4.0):
        w = mult * W_BAR_NOM
        for e in range(n(16)):
            jobs.append(EpCfg(N=4, planner="benign", filter_on=True, b_tot=DELTA_ADV, w_true=w, nature="random",
                              seed=4000 + e, tag="mismatch"))
            jobs.append(EpCfg(N=4, planner="oracle_violation", theta=tuple(theta["violation"]), filter_on=True,
                              b_tot=DELTA_ADV, w_true=w, nature="adversarial", seed=4000 + e, tag="mismatch"))
            jobs.append(EpCfg(N=4, planner="oracle_press_wall", theta=HAND_VIOLATION["press_wall"], filter_on=True,
                              b_tot=DELTA_ADV, w_true=w, nature="adversarial", seed=4000 + e, tag="mismatch"))
        for e in range(n(4)):
            jobs.append(EpCfg(N=12, planner="oracle_violation", theta=tuple(theta["violation"]), filter_on=True,
                              b_tot=DELTA_ADV, w_true=w, nature="adversarial", seed=4000 + e, tag="mismatch"))
    return run_jobs(jobs, "mismatch", pool)


def stage_negative(pool, theta):
    jobs = []
    for e in range(n(16)):
        for name, th in (("benign", ()), ("oracle_violation", tuple(theta["violation"])),
                         ("oracle_press_wall", HAND_VIOLATION["press_wall"])):
            jobs.append(EpCfg(N=4, planner=name, theta=th, filter_on=True, b_tot=DELTA_ADV, within=False,
                              nature="adversarial", seed=5000 + e, tag="outsideA2"))
        jobs.append(EpCfg(N=4, planner="oracle_press_wall", theta=HAND_VIOLATION["press_wall"], filter_on=True,
                          b_tot=DELTA_ADV, lookahead=False, nature="adversarial", seed=4000 + e, tag="no_lookahead"))
        jobs.append(EpCfg(N=4, planner="oracle_denial", theta=tuple(theta["denial"]), filter_on=True,
                          b_tot=DELTA_ADV, continuation=False, nature="adversarial", seed=4000 + e,
                          tag="no_continuation"))
    for e in range(n(4)):
        jobs.append(EpCfg(N=12, planner="benign", filter_on=True, b_tot=DELTA_ADV, within=False,
                          nature="adversarial", seed=5000 + e, tag="outsideA2"))
    return run_jobs(jobs, "negative", pool)


def stage_nested():
    levels, _ = budget_levels()
    rows = nestedness_study([b for b, _ in levels], M=n(300))
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "nestedness.csv", index=False)
    return df


def main(stages):
    t_all = time.time()
    meta_p = RESULTS / "run_meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    pd.DataFrame(provenance_rows(), columns=["name", "value", "provenance"]).to_csv(RESULTS / "constants_paperV.csv",
                                                                                    index=False)
    with Pool(WORKERS) as pool:
        theta = load_theta()
        for st in stages:
            t0 = time.time()
            print(f"== stage {st}", flush=True)
            if st == "cem":
                theta = stage_cem(pool)
                n_ep = len(pd.read_csv(RESULTS / "cem_log.csv")) * 2
            elif st == "nested":
                df = stage_nested(); n_ep = 0
            else:
                fn = {"main": stage_main, "budget": stage_budget, "mismatch": stage_mismatch,
                      "negative": stage_negative}.get(st)
                df = stage_hand(pool) if st == "hand" else fn(pool, theta)
                n_ep = len(df)
            meta[st] = {"wall_s": round(time.time() - t0, 1), "episodes": int(n_ep)}
            print(f"== stage {st} done in {time.time()-t0:.0f}s ({n_ep} episodes)", flush=True)
            meta_p.write_text(json.dumps(meta, indent=1))
    meta["_env"] = {"python": sys.version.split()[0], "platform": platform.platform(), "numpy": np.__version__,
                    "scale": SCALE, "workers": WORKERS}
    import osqp, clarabel, scipy
    meta["_env"].update(osqp=osqp.__version__, clarabel=clarabel.__version__, scipy=scipy.__version__)
    meta["_last_invocation_wall_s"] = round(time.time() - t_all, 1)
    meta_p.write_text(json.dumps(meta, indent=1))


if __name__ == "__main__":
    st = sys.argv[1:] or ["cem", "main", "hand", "budget", "mismatch", "negative", "nested"]
    main(st)
