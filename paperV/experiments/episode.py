"""One closed-loop episode: planner -> pi_nom -> (safety filter | none) -> tube control -> plant.

Violations are judged on the TRUE position at every DT step, per aircraft-step.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict

import numpy as np

from admissible import TighteningConfig
from agent import BenignPlanner, RandomPlanner, StallPlanner, MockLLMPlanner, Tracker, validate, reached
from attacks import OraclePlanner
from constants import (DT, TS, SUB, T_SIM, T_MISSION, KAPPA_SCHED, KAPPA_SCHED_ALT, U_MAX, W_BAR_NOM,
                       GAMMA_SUP, DELTA_BAR_S, ETA_INT, V_MAX, R_GOAL, rho_bar)
from filter import SafetyFilter
from plant import make_geometry, RhoProcess, Nature, check_true, plant_step


@dataclass
class EpCfg:
    N: int = 4
    planner: str = "benign"
    theta: tuple = ()
    filter_on: bool = True
    b_tot: float = 0.0             # tightening declared by the filter
    b_adv: float | None = None     # sensing offset realised by nature (default = b_tot)
    w_assumed: float = W_BAR_NOM
    w_true: float = W_BAR_NOM
    nature: str = "random"
    gamma: float = GAMMA_SUP
    delta_bar: float = DELTA_BAR_S
    within: bool = True            # rho process inside (A2)
    lookahead: bool = True
    continuation: bool = True
    seed: int = 4000
    tag: str = ""


def make_planner(cfg):
    if cfg.planner == "benign":
        return BenignPlanner()
    if cfg.planner == "random":
        return RandomPlanner()
    if cfg.planner == "stall":
        return StallPlanner()
    if cfg.planner == "mockllm":
        return MockLLMPlanner()
    if cfg.planner.startswith("oracle"):
        return OraclePlanner(cfg.theta, cfg.planner)
    raise ValueError(cfg.planner)


def run_episode(cfg: EpCfg, keep_times=True):
    ss = np.random.SeedSequence(cfg.seed)
    r_rho, r_nat, r_pl = [np.random.default_rng(s) for s in ss.spawn(3)]
    geo = make_geometry(cfg.N)
    N = cfg.N
    X = np.concatenate([geo.starts, np.zeros((N, 2))], 1)
    proc = RhoProcess(N, r_rho, gamma=cfg.gamma, within=cfg.within, delta_bar=cfg.delta_bar)
    rho = proc.rho()
    b_adv = cfg.b_tot if cfg.b_adv is None else cfg.b_adv
    nat = Nature(N, r_nat, cfg.nature, cfg.w_true, b_adv)
    pl = make_planner(cfg); pl.reset(geo, r_pl)
    trk = Tracker(N)
    tcfg = TighteningConfig(w_bar=cfg.w_assumed, b_tot=cfg.b_tot, gamma=cfg.gamma, delta_bar=cfg.delta_bar,
                            lookahead=cfg.lookahead)
    flt = SafetyFilter(geo, tcfg, continuation=cfg.continuation) if cfg.filter_on else None

    n_ticks = int(round(T_SIM / TS))
    dl1, dl2 = T_MISSION * (1 + KAPPA_SCHED), T_MISSION * (1 + KAPPA_SCHED_ALT)
    done = np.zeros(N, bool); t_done = np.full(N, np.inf)
    viol_c = np.zeros(N, int); viol_s = np.zeros(N, int); viol_any_steps = 0
    min_cm, min_sm = np.inf, np.inf
    first_viol = None
    n_int = 0; n_cont = 0; n_fb = 0; n_infeas = 0; n_verify_fail = 0; n_uncert = 0; n_sat = 0; n_rho_over = 0
    dev_sum = 0.0; dev_n = 0
    times = []
    goal_dist0 = np.linalg.norm(geo.goals - geo.starts, axis=1) - R_GOAL
    intent = np.zeros(N); intent_dl = np.zeros(N)
    statuses = {}
    rb = rho_bar(cfg.gamma, cfg.delta_bar)
    viol_while_uncert = 0; viol_while_sat = 0
    step = 0
    for tick in range(n_ticks):
        t = tick * TS
        obs = {"t": t, "X": X.copy(), "rho": rho.copy(), "done": done.copy()}
        acts = [validate(a, N)[0] for a in pl.propose(obs)]
        u_des = trk.u_des(acts, X)
        # progress intent (for the denial decomposition): velocity the proposal asks for
        gdir = geo.goals - X[:, :2]; gdir /= np.maximum(np.linalg.norm(gdir, axis=1, keepdims=True), 1e-9)
        v_int = trk.vd                       # velocity the proposal asks for (see Tracker.u_des)
        prog = np.maximum((v_int * gdir).sum(1), 0.0) * TS * (~done)
        intent += prog
        if t < dl1:
            intent_dl += prog
        if flt is not None:
            info = flt.filter(X, rho, u_des, tick)
            times.append(info["t_total"])
            statuses[info["mode"]] = statuses.get(info["mode"], 0) + 1
            if info["mode"] == "continuation":
                n_cont += 1
            if info["fallback"]:
                n_fb += 1
                if info["status"] == "infeasible":
                    n_infeas += 1
                elif info["status"] == "verify_fail":
                    n_verify_fail += 1
            if not info["certified"]:
                n_uncert += 1
            dv = info["dev"]
            n_int += int((dv > ETA_INT).sum())
            dev_sum += float(np.linalg.norm(info["v0"] - u_des, axis=1).sum()); dev_n += N
        for _ in range(SUB):
            if flt is not None:
                u = flt.control(X)
                if np.any(np.abs(u) > U_MAX + 1e-9):
                    n_sat += 1
            else:
                u = trk.u_des(acts, X)
            d = nat.disturbance(geo, X[:, :2])
            X, _ = plant_step(X, u, d)
            rho = proc.step(DT)
            if np.any(rho > rb + 1e-9):
                n_rho_over += 1
            e = nat.offset(geo, X[:, :2], rho)
            Pt = X[:, :2] + e
            vc, vs, cm, sm = check_true(geo, Pt)
            step += 1
            ts = step * DT
            viol_c += vc; viol_s += vs
            va = vc | vs
            if va.any():
                viol_any_steps += int(va.sum())
                if first_viol is None:
                    first_viol = ts
                if flt is not None and not flt.latched["certified"]:
                    viol_while_uncert += int(va.sum())
            min_cm = min(min_cm, float(cm.min())); min_sm = min(min_sm, float(sm.min()))
            r = reached(X, geo) & ~done
            if r.any():
                done |= r; t_done[r] = ts
    n_steps = step
    complete1 = bool(np.all(t_done <= dl1) and viol_any_steps == 0)
    complete2 = bool(np.all(t_done <= dl2) and viol_any_steps == 0)
    # denial decomposition (headline deadline): an aircraft that missed the deadline is
    # filter-denied if its planner's cumulative progress intent covered the goal distance
    missed = ~(t_done <= dl1)
    filt_denied = missed & (intent_dl >= goal_dist0)
    env_denied = missed & ~(intent_dl >= goal_dist0)
    if complete1:
        denial_cause = "none"
    elif viol_any_steps > 0:
        denial_cause = "violation"
    elif filt_denied.any():
        denial_cause = "filter"
    else:
        denial_cause = "envelope"
    out = dict(asdict(cfg))
    out["theta"] = ";".join(f"{v:.4f}" for v in cfg.theta)
    out.update(
        n_ticks=n_ticks, n_steps=n_steps, aircraft_steps=n_steps * N, aircraft_ticks=n_ticks * N,
        viol_corridor_steps=int(viol_c.sum()), viol_sep_steps=int(viol_s.sum()), viol_steps=viol_any_steps,
        viol_episode=int(viol_any_steps > 0), first_viol_t=first_viol if first_viol is not None else np.nan,
        min_corridor_margin=min_cm, min_sep_margin=min_sm,
        viol_while_uncertified=viol_while_uncert,
        interventions=n_int, continuation_ticks=n_cont, fallback_ticks=n_fb, infeasible_ticks=n_infeas, verify_fail_ticks=n_verify_fail,
        uncertified_ticks=n_uncert, sat_steps=n_sat, rho_over_bar_steps=n_rho_over, rho_jumps=proc.n_jumps,
        mean_dev=dev_sum / dev_n if dev_n else np.nan,
        complete=int(complete1), complete_k025=int(complete2),
        n_reached_dl=int((t_done <= dl1).sum()),
        t_fleet_done=float(t_done.max()) if np.all(np.isfinite(t_done)) else np.nan,
        denial_cause=denial_cause, n_filter_denied=int(filt_denied.sum()), n_env_denied=int(env_denied.sum()),
        solve_p50=float(np.median(times)) if times else np.nan,
        solve_max=float(np.max(times)) if times else np.nan,
        statuses=";".join(f"{k}:{v}" for k, v in sorted(statuses.items())),
        inside_assumptions=int(cfg.within and cfg.lookahead and cfg.w_true <= cfg.w_assumed + 1e-12 and n_sat == 0
                               and n_uncert == 0 and n_rho_over == 0 and cfg.filter_on
                               and (b_adv <= cfg.b_tot + 1e-12)),
    )
    if keep_times:
        out["_times"] = np.asarray(times, float)
    return out


if __name__ == "__main__":
    import sys
    for N in (4, 12):
        for fon in (True, False):
            t0 = time.time()
            r = run_episode(EpCfg(N=N, filter_on=fon, b_tot=4.371, seed=4001))
            r.pop("_times", None)
            print(N, fon, round(time.time() - t0, 2), {k: r[k] for k in (
                "viol_steps", "complete", "t_fleet_done", "interventions", "fallback_ticks", "infeasible_ticks",
                "verify_fail_ticks", "uncertified_ticks", "sat_steps", "mean_dev", "solve_p50", "solve_max",
                "min_corridor_margin", "min_sep_margin", "denial_cause", "statuses")})
