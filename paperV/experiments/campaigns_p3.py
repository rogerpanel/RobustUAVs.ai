"""P3: benign LLM campaigns (runbook P3.3) and the cost estimate (P3.2).

  --estimate-only   projected calls, tokens and USD per role from models.lock.json; makes no call
  --cache-only      replay from the cache; a miss stops the campaign (exit gate: bit-for-bit replay)
  --planner scripted runs the same cells offline as the zero-cost reference
"""
from __future__ import annotations

import math

import numpy as np

try:
    from . import constants as C
    from .agent import LLMPlanner, render_system, render_situation, FLEET_SCHEMA
    from .budget import level_values
    from .episode import EpisodeCfg
    from .run_campaign import execute, dispatchable, meta_update, env_meta
except ImportError:
    import constants as C
    from agent import LLMPlanner, render_system, render_situation, FLEET_SCHEMA
    from budget import level_values
    from episode import EpisodeCfg
    from run_campaign import execute, dispatchable, meta_update, env_meta

CALLS_PER_EPISODE = math.ceil(C.T_HORIZON_SIM / C.PLAN_PERIOD)   # 18 planner calls to 87.5 s


def cells(a):
    lv = level_values()
    for m in (float(x) for x in a.margins.split(",")):
        for level in a.btot.split(","):
            if not dispatchable(level, m):
                print(f"skip {level} m={m:g}: not dispatchable (logged in budget_levels.csv)")
                continue
            for flt in a.filters.split(","):
                yield m, level, lv[level], flt


def build(a):
    cfgs = []
    roles = a.roles.split(",") if a.planner == "api" else ["scripted"]
    for m, level, b, flt in cells(a):
        for role in roles:
            for j in range(a.missions):
                for rep in range(a.repeats):
                    seed = a.seed_block + j
                    if a.planner == "api":
                        pl = LLMPlanner(role, repeat_idx=rep, mission_seed=seed, cache_only=a.cache_only,
                                        context=dict(campaign_id=a.campaign_id, mission_seed=seed))
                        name = f"llm:{role}"
                    else:
                        pl, name = None, "scripted"
                    cfgs.append(EpisodeCfg(m=m, b_tot_level=level, b_tot_m=b, filter=flt, planner=name,
                                           planner_obj=pl, attacker=a.attacker, mission_seed=seed, repeat=rep,
                                           campaign_id=a.campaign_id, log_steps=a.log_steps,
                                           w_mode="dryden", e_mode="random"))
    return cfgs


def estimate(a, cfgs):
    """Projected cost from a rendered prompt; prices from models.lock.json."""
    try:
        from . import llm_harness as H
    except ImportError:
        import llm_harness as H
    from plant import make_layout
    lay = make_layout(C.N_UAV, 20.0)
    obs = {"t": 0.0, "X": np.zeros((C.N_UAV, 4)), "next_wp": np.zeros(C.N_UAV, int)}
    sys_tok = len(render_system(20.0)) / 3.5
    sit_tok = len(render_situation(obs, lay)) / 3.5
    lock = H.load_lock()
    print(f"prompt ~ {sys_tok:.0f} system (cacheable) + {sit_tok:.0f} situation tokens per call; "
          f"{CALLS_PER_EPISODE} calls per episode")
    tot = 0.0
    for role in a.roles.split(","):
        e = H.role_entry(role, lock)
        n = sum(1 for c in cfgs if c.planner == f"llm:{role}") * CALLS_PER_EPISODE
        out = float(e.get("expected_output_tokens", 2000))
        usd_nocache = H.call_cost(e, int(sys_tok + sit_tok), 0, 0, int(out)) * n
        usd_cache = H.call_cost(e, int(sys_tok + sit_tok), int(sys_tok), 0, int(out)) * n
        tot += usd_nocache
        print(f"{role}: {e['provider']}/{e['model_id']}: {n} calls, {n * (sys_tok + sit_tok) / 1e6:.2f} Mtok in, "
              f"{n * out / 1e6:.2f} Mtok out (expected_output_tokens={out:g}, thinking included); "
              f"${usd_cache:,.2f} with system-prompt caching, ${usd_nocache:,.2f} without")
    print(f"TOTAL (no caching, worst case): ${tot:,.2f}; set PAPERV_MAX_USD to 1.5x the P3-P5 total")


def run(a):
    cfgs = build(a)
    if a.estimate_only:
        return estimate(a, cfgs)
    par = a.concurrency or a.par
    execute(cfgs, a.campaign_id, par, a.resume, a.shard)
    meta_update(a.campaign_id, dict(phase="p3", planner=a.planner, roles=a.roles, attacker=a.attacker,
                                    missions=a.missions, repeats=a.repeats, seed_block=a.seed_block,
                                    margins=a.margins, btot=a.btot, filters=a.filters, cache_only=a.cache_only,
                                    env=env_meta()))
