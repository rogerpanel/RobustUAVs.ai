"""P2 campaigns (runbook P2.2): the stealth monitor on A0, the held-out evaluation, the budget curve.

  --phase p2-budget --stage monitor   A0 scripted fleets on block 11xxx: per aircraft-episode
                                      interventions and fallbacks; thresholds at the 99th percentile
                                      (1% FPR) -> results/stealth_monitor.csv
  --phase p2                          scripted, random, A6 best (12xxx search) and A6 held-out
                                      (13xxx re-search) on held-out missions (14xxx), full fleets,
                                      every filter; non-dispatchable cells logged once as infeasible_t0
  --phase p2-budget --stage curve     A6 best (G2, G3) vs b_att in {0,1,2,4,8,14} x hijacked {1,4,12}
"""
from __future__ import annotations

import csv
import itertools

import numpy as np

try:
    from . import constants as C
    from .attacks import OracleAdversarialPlanner, N_EPOCH
    from .budget import level_values
    from .episode import EpisodeCfg
    from .run_campaign import execute, dispatchable, meta_update, env_meta, Store
    from .stats import read_campaign
except ImportError:
    import constants as C
    from attacks import OracleAdversarialPlanner, N_EPOCH
    from budget import level_values
    from episode import EpisodeCfg
    from run_campaign import execute, dispatchable, meta_update, env_meta, Store
    from stats import read_campaign

NATURE = dict(w_mode="dryden", e_mode="vertex")
B_ATT = (0, 1, 2, 4, 8, 14)
N_HIJACK = (1, 4, 12)


def best_theta(path, goal, level, m):
    """Best policy of a search file for one cell (best of CEM and CMA-ES)."""
    best = None
    if not path.exists():
        return None
    for r in csv.DictReader(open(path)):
        if r["goal"] == goal and r["b_tot_level"] == level and float(r["m"]) == float(m):
            if best is None or float(r["best_score"]) > float(best["best_score"]):
                best = r
    return None if best is None else np.array([float(x) for x in best["theta"].split(";")])


def _cells(a):
    lv = level_values()
    for m in (float(x) for x in a.margins.split(",")):
        for level in a.btot.split(","):
            for gamma in (float(x) for x in a.gamma.split(",")):
                yield m, level, lv[level], gamma


def run(a):
    stage = getattr(a, "stage", None)
    if a.phase == "p2-budget" and a.campaign_id in ("p2_budget",) and stage is None:
        stage = "curve"
    if a.phase == "p2-budget" and (stage == "monitor" or a.campaign_id.endswith("monitor")):
        return monitor(a)
    if a.phase == "p2-budget":
        return curve(a)
    return evaluate(a)


def monitor(a):
    cid = a.campaign_id if a.campaign_id.endswith("monitor") else "p2_monitor"
    cfgs = []
    for m, level, b, gamma in _cells(a):
        if gamma != C.GAMMA_SUP or not dispatchable(level, m):
            continue
        for j in range(a.missions):
            cfgs.append(EpisodeCfg(m=m, b_tot_level=level, b_tot_m=b, planner="scripted", attacker="A0",
                                   mission_seed=11000 + j, campaign_id=cid, **NATURE))
    execute(cfgs, cid, a.par, a.resume, a.shard)
    recs = [r for r in read_campaign(cid) if r["status"] == "ok"]
    rows = []
    for (level, m), g in itertools.groupby(sorted(recs, key=lambda r: (r["b_tot_level"], r["m"])),
                                           key=lambda r: (r["b_tot_level"], r["m"])):
        g = list(g)
        I = np.concatenate([r["interventions_i"] for r in g]); F = np.concatenate([r["fallback_i"] for r in g])
        rows.append(dict(b_tot_level=level, m=m, aircraft_episodes=len(I),
                         thr_interventions=float(np.quantile(I, 0.99)), thr_fallback=float(np.quantile(F, 0.99)),
                         a0_interventions_mean=float(I.mean()), a0_fallback_mean=float(F.mean()),
                         a0_completed=float(np.mean([r["completed"] for r in g])),
                         seed_block="11000-%d" % (11000 + a.missions - 1), fpr_target=0.01, provenance="sim"))
    p = C.RESULTS / "stealth_monitor.csv"
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    meta_update("p2_monitor", dict(missions=a.missions, env=env_meta()))
    print("wrote", p)


def evaluate(a):
    cid = a.campaign_id
    lv = level_values()
    cfgs = []
    infeasible = []
    for m, level, b, gamma in _cells(a):
        if not dispatchable(level, m, gamma=gamma):
            infeasible.append(dict(m=m, level=level, gamma=gamma))
            continue
        for planner in a.planners.split(","):
            for flt in a.filters.split(","):
                if planner.startswith("oracle"):
                    src = C.RESULTS / ("a6_search.csv" if planner.endswith("best") else "a6_search_heldout.csv")
                    for goal in a.goals.split(","):
                        th = best_theta(src, goal, level, m)
                        if th is None:
                            continue
                        for j in range(a.missions):
                            pl = OracleAdversarialPlanner(th, b_att=14, n_hijack=C.N_UAV, name=planner)
                            cfgs.append(EpisodeCfg(m=m, b_tot_level=level, b_tot_m=b, gamma=gamma, filter=flt,
                                                   planner=planner, planner_obj=pl, attacker="A6", goal=goal,
                                                   mission_seed=a.seed_block + j, campaign_id=cid, **NATURE))
                else:
                    for j in range(a.missions):
                        cfgs.append(EpisodeCfg(m=m, b_tot_level=level, b_tot_m=b, gamma=gamma, filter=flt,
                                               planner=planner, attacker="A0" if planner == "scripted" else "random",
                                               mission_seed=a.seed_block + j, campaign_id=cid, **NATURE))
    st = Store(cid, a.shard)
    have = st.done_keys()
    for c in infeasible:                        # logged once per cell, never run
        cfg = EpisodeCfg(m=c["m"], b_tot_level=c["level"], b_tot_m=lv[c["level"]], gamma=c["gamma"],
                         campaign_id=cid, mission_seed=-1)
        if (cfg.cell_id(), -1, 0) not in have:
            st.append(dict(schema_version=1, campaign_id=cid, cell_id=cfg.cell_id(), mission_seed=-1, repeat=0,
                           status="infeasible_t0", m=c["m"], b_tot_level=c["level"], b_tot_m=lv[c["level"]],
                           gamma=c["gamma"], note="tightened terminal half-width <= 0: dispatch refused (A5 fails)"))
    execute(cfgs, cid, a.par, a.resume, a.shard)
    meta_update(cid, dict(missions=a.missions, seed_block=a.seed_block, planners=a.planners, filters=a.filters,
                          margins=a.margins, btot=a.btot, gamma=a.gamma, infeasible_cells=infeasible,
                          nature=NATURE, env=env_meta()))


def curve(a):
    cid = a.campaign_id
    cfgs = []
    for m, level, b, gamma in _cells(a):
        if gamma != C.GAMMA_SUP or not dispatchable(level, m):
            continue
        for goal in ("G2", "G3"):
            th = best_theta(C.RESULTS / "a6_search.csv", goal, level, m)
            if th is None:
                continue
            for b_att, nh in itertools.product(B_ATT, N_HIJACK):
                for j in range(a.missions):
                    pl = OracleAdversarialPlanner(th, b_att=b_att, n_hijack=nh, name=f"oracle_batt{b_att}_h{nh}")
                    cfgs.append(EpisodeCfg(m=m, b_tot_level=level, b_tot_m=b, planner=pl.name, planner_obj=pl,
                                           attacker="A6", goal=f"{goal}|b_att={b_att}|hijack={nh}",
                                           mission_seed=a.seed_block + j, campaign_id=cid, **NATURE))
    execute(cfgs, cid, a.par, a.resume, a.shard)
    meta_update(cid, dict(missions=a.missions, seed_block=a.seed_block, b_att=B_ATT, n_hijack=N_HIJACK, env=env_meta()))
