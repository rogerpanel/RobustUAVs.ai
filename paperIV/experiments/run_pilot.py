#!/usr/bin/env python3
"""Paper IV pilot (v2).

  E1   threshold calibration, FPR by wind / benign source, ROC vs naive offsets
  E2   cross-entropy-method (CEM) attacker per (stack x family x operating point)
  E2x  cross-evaluation of EVERY optimised attacker against EVERY stack (RQ1);
       removes the dependence of the disguise matrix on optimiser failures
  E2b  anchor-interval sweep, pooled over attackers (every interval closed)
  E2c  same sweep with the final interval left unchecked (terminal window)
  E3   benign marginals, envelope-matched marginal, dependence + temporal gap,
       per-mission sub-additivity across sources (RQ3, Lemma 2)
  E4   pooled stealth budget; held-out attackers; soundness of Theorem 1 tested
       on its own event {fail and undetected} (RQ2, RQ4); saturation control
  E5   negative controls: C2' broken (no anchor), C4 broken (severe wind)

Seed blocks (no reuse across roles; wind draws use an offset of 10^6):
  1xxx calibration (thresholds, marginals, pooled stealth budget)
  2xxx attacker optimisation (CEM; inner simulation seeds = seed*100 + gen)
  3xxx held-out attacker optimisation (independent CEM seeds)
  4xxx held-out evaluation missions
Usage:  python3 run_pilot.py [--quick]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy.stats import binom, beta

from constants import *  # noqa
import sim as SIM
from sim import simulate, alarms, decode, ATTACK_BOX, DETECTORS
import depbounds as db

RES = Path(os.environ.get("P4_RESULTS") or Path(__file__).resolve().parents[1] / "results")
RES.mkdir(exist_ok=True)
W_LO, W_HI = W20_KT["light"], W20_KT["moderate"]
W_SEV = (W20_KT["severe"], W20_KT["severe"] + 15.0)
STACKS = {"D1": ("D1",), "D2": ("D2",), "D3": ("D3",), "D4": ("D4",),
          "ALL": ("D1", "D2", "D3", "D4")}
FAMILIES = ("step", "ramp", "fault_mimic", "gnss_mimic", "weather_mimic")
FPR_GRID = (0.01, 0.02, 0.05, 0.10, 0.20)
OPS = (0.01, 0.05, 0.10)
CEM_GENS, CEM_K = 25, 48


def wind(N, seed, lo=W_LO, hi=W_HI):
    return np.random.default_rng(seed + 1_000_000).uniform(lo, hi, N)


def write(name, rows):
    if not rows:
        return
    with open(RES / name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def cp_interval(k, n, a=0.05):
    if n == 0:
        return float("nan"), float("nan")
    lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
    return lo, hi


def holm(ps):
    ps = np.asarray(ps, float); order = np.argsort(ps); M = len(ps)
    adj = np.empty(M); run = 0.0
    for rank, idx in enumerate(order):
        run = max(run, min(1.0, (M - rank) * ps[idx])); adj[idx] = run
    return adj


# ------------------------------------------------------------------ E1
def e1_calibrate(N):
    out = simulate(N, 1001, w20=wind(N, 1001))
    stats = {d: out["S" + d[1]] for d in DETECTORS}
    th = {f: {d: float(np.quantile(stats[d], 1 - f)) for d in DETECTORS} for f in FPR_GRID}
    stack_th = {f: {d: float(np.quantile(stats[d], 1 - f / 4)) for d in DETECTORS} for f in FPR_GRID}
    anchor_th = float(np.quantile(out["SA"], 0.99))
    write("e1_thresholds.csv", [{"fpr_target": f, "detector": d, "theta": round(th[f][d], 5),
                                 "theta_stack": round(stack_th[f][d], 5)} for f in FPR_GRID for d in DETECTORS])
    rows = []
    for k, wname in enumerate(("light", "moderate", "severe")):
        o = simulate(N // 2, 1101 + k, w20=W20_KT[wname])
        for d in DETECTORS:
            rows.append({"wind": wname, "detector": d, "fpr": round(float(np.mean(o["S" + d[1]] > th[0.05][d])), 4)})
        full = alarms(o, stack_th[0.05], STACKS["ALL"]) | (o["SA"] > anchor_th)
        rows.append({"wind": wname, "detector": "ALL", "fpr": round(float(full.mean()), 4)})
        rows.append({"wind": wname, "detector": "anchor", "fpr": round(float(np.mean(o["SA"] > anchor_th)), 4)})
    write("e1_fpr_by_wind.csv", rows)
    rows = []
    for k, (src, kw) in enumerate((("wind_only", dict(gnss=False, fault=False)),
                                   ("gnss_only", dict(env_on=False, fault=False)),
                                   ("fault_only", dict(env_on=False, gnss=False)))):
        o = simulate(N // 2, 1201 + k, w20=wind(N // 2, 1201 + k), **kw)
        for d in DETECTORS:
            rows.append({"source": src, "detector": d, "fpr": round(float(np.mean(o["S" + d[1]] > th[0.05][d])), 4)})
    write("e1_fpr_by_source.csv", rows)
    rows = []
    for k, (fam, par) in enumerate((("step", {"amp": 5.0, "t0": 25.0}),
                                    ("ramp", {"rate": 0.5, "t0": 25.0, "cap": 40.0}))):
        o = simulate(N // 2, 1301 + k, w20=wind(N // 2, 1301 + k), attack=fam, aparams=par)
        for d in DETECTORS:
            for q in np.linspace(0.0, 1.0, 41):
                thq = float(np.quantile(stats[d], q))
                rows.append({"attack": fam, "detector": d, "fpr": round(1 - q, 4),
                             "tpr": round(float(np.mean(o["S" + d[1]] > thq)), 4)})
    write("e1_roc.csv", rows)
    (RES / "e1_calibration.json").write_text(json.dumps(
        {"single": {str(k): v for k, v in th.items()}, "stack": {str(k): v for k, v in stack_th.items()},
         "anchor": anchor_th}, indent=1))
    return {"single": th, "stack": stack_th, "anchor": anchor_th}


def stealth_mask(o, cal, stack_name, fpr):
    thd = cal["stack"][fpr] if stack_name == "ALL" else cal["single"][fpr]
    return ~(alarms(o, thd, STACKS[stack_name]) | (o["SA"] > cal["anchor"]))


# ------------------------------------------------------------------ attacker
def cem(family, stack_name, fpr, cal, seed, gens=None, lam=12, K=None, elite=4,
        anchor=T_ANCHOR, terminal=True, wl=W_LO, wh=W_HI):
    gens = gens or CEM_GENS; K = K or CEM_K
    k = len(ATTACK_BOX[family])
    rng = np.random.default_rng(seed)
    mu, sd = np.full(k, 0.5), np.full(k, 0.3)
    best = (-1.0, mu.copy())
    for g in range(gens):
        U = np.clip(mu + sd * rng.normal(size=(lam, k)), 0, 1)
        P = decode(family, np.repeat(U, K, axis=0))
        N = lam * K; s = seed * 100 + g
        o = simulate(N, s, w20=wind(N, s, wl, wh), attack=family, aparams=P, anchor=anchor, terminal=terminal)
        st = stealth_mask(o, cal, stack_name, fpr)
        J = (o["maxdev_after"] * st).reshape(lam, K).mean(1)
        order = np.argsort(J)[::-1]
        if J[order[0]] > best[0]:
            best = (float(J[order[0]]), U[order[0]].copy())
        E = U[order[:elite]]
        mu = E.mean(0); sd = np.maximum(E.std(0), 0.02)
    return best


def _cem_job(args):
    family, stack_name, fpr, cal, seed, kw = args
    J, u = cem(family, stack_name, fpr, cal, seed, **kw)
    return family, stack_name, fpr, seed, J, u.tolist()


def run_attack(family, u, N, seed, wl=W_LO, wh=W_HI, anchor=T_ANCHOR, terminal=True, benign=True):
    """Full mission, attack-only counterfactual (same time-varying system), benign-only."""
    P = decode(family, np.asarray(u)); w = wind(N, seed, wl, wh)
    o = simulate(N, seed, w20=w, attack=family, aparams=P, anchor=anchor, terminal=terminal)
    oa = simulate(N, seed, w20=w, attack=family, aparams=P, anchor=anchor, terminal=terminal, noise=False)
    ob = simulate(N, seed, w20=w, anchor=anchor, terminal=terminal) if benign else None
    return o, oa, ob


# ------------------------------------------------------------------ E2 / E2x
def e2_optimise(cal, pool):
    jobs = []
    for sname in STACKS:
        for fam in FAMILIES:
            jobs.append((fam, sname, 0.05, cal, 2000 + len(jobs), {}))
    for fpr in (0.01, 0.10):
        for fam in FAMILIES:
            jobs.append((fam, "ALL", fpr, cal, 2000 + len(jobs), {}))
    res = pool.map(_cem_job, jobs)
    rows = [{"attacker_id": i, "family": f, "origin_stack": s, "origin_fpr": p, "cem_seed": sd,
             "J_train": round(J, 4), "params": json.dumps([round(x, 4) for x in u])}
            for i, (f, s, p, sd, J, u) in enumerate(res)]
    write("e2_attackers.csv", rows)
    return rows


def e2x_cross(cal, attackers, N_eval):
    """Every attacker x every stack at 5% FPR, one simulation per attacker."""
    rows = []
    benign = simulate(N_eval, 4999, w20=wind(N_eval, 4999))
    for a in attackers:
        u = json.loads(a["params"]); i = int(a["attacker_id"])
        o, oa, _ = run_attack(a["family"], u, N_eval, 4100 + i, benign=False)
        for sname in STACKS:
            st = stealth_mask(o, cal, sname, 0.05)
            ks = max(_ks(o["S" + d[1]], benign["S" + d[1]]) for d in STACKS[sname])
            rows.append({"attacker_id": i, "family": a["family"], "origin_stack": a["origin_stack"],
                         "origin_fpr": a["origin_fpr"], "stack": sname,
                         "evasion_rate": round(float(st.mean()), 4), "n_stealthy": int(st.sum()),
                         "attack_only_dev_max": round(float(oa["maxdev"][st].max()) if st.any() else 0.0, 3),
                         "stealthy_dev_max": round(float(o["maxdev_after"][st].max()) if st.any() else 0.0, 3),
                         "ks_to_benign": round(ks, 4)})
    write("e2x_cross.csv", rows)
    return rows


def _ks(a, b):
    xs = np.sort(np.concatenate([a, b]))
    Fa = np.searchsorted(np.sort(a), xs, side="right") / len(a)
    Fb = np.searchsorted(np.sort(b), xs, side="right") / len(b)
    return float(np.max(np.abs(Fa - Fb)))


# ------------------------------------------------------------------ E2b / E2c
def e2_anchor(cal, attackers, N_eval, pool, terminal, tag, seed0, eval0):
    jobs = []
    for Ta in (5.0, 10.0, 20.0):
        for fam in FAMILIES:
            jobs.append((fam, "ALL", 0.05, cal, seed0 + len(jobs), {"anchor": Ta, "terminal": terminal}))
    res = pool.map(_cem_job, jobs)
    own = [(f, u, jobs[i][5]["anchor"]) for i, (f, s, p, sd, J, u) in enumerate(res)]
    pool_att = own + [(a["family"], json.loads(a["params"]), None) for a in attackers if a["origin_stack"] == "ALL"]
    rows = []
    for j, (fam, u, Ta_opt) in enumerate(pool_att):
        for Ta in (5.0, 10.0, 20.0):           # same seed across Ta: anchor times are nested
            o, oa, _ = run_attack(fam, u, N_eval // 2, eval0 + j, anchor=Ta, terminal=terminal, benign=False)
            st = stealth_mask(o, cal, "ALL", 0.05)
            rows.append({"attacker": j, "family": fam, "optimised_for_Ta": Ta_opt if Ta_opt else "E2",
                         "T_anchor_s": Ta, "evasion_rate": round(float(st.mean()), 4),
                         "attack_only_dev_max": round(float(oa["maxdev"][st].max()) if st.any() else 0.0, 3)})
    write(f"{tag}.csv", rows)
    return rows


# ------------------------------------------------------------------ E3
def e3_budget(N):
    env = simulate(N, 1501, w20=W_HI, gnss=False, fault=False)["maxdev"]          # stochastically largest
    env_lo = simulate(N, 1502, w20=W_LO, gnss=False, fault=False)["maxdev"]
    gn = simulate(N, 1503, env_on=False, fault=False)["maxdev"]
    fa = simulate(N, 1504, env_on=False, gnss=False)["maxdev"]
    # joint and its per-source decomposition on the SAME realisation (larger sample)
    NJ = 5 * N; wj = wind(NJ, 1505)
    joint = simulate(NJ, 1505, w20=wj)["maxdev"]
    xe = simulate(NJ, 1505, w20=wj, gnss=False, fault=False)["maxdev"]
    xg = simulate(NJ, 1505, w20=wj, env_on=False, fault=False)["maxdev"]
    xf = simulate(NJ, 1505, w20=wj, env_on=False, gnss=False)["maxdev"]
    subadd = float(np.mean(joint <= xe + xg + xf + 1e-9))
    env_mix = xe                                                                  # envelope-matched marginal
    np.savez(RES / "e3_marginals.npz", env=env, env_lo=env_lo, gnss=gn, fault=fa, joint=joint,
             env_mix=env_mix, sum_same=xe + xg + xf)
    rows = [{"marginal": nm, "n": len(x), "median": round(float(np.median(x)), 3),
             "p95": round(float(np.quantile(x, .95)), 3), "p99": round(float(np.quantile(x, .99)), 3),
             "max": round(float(x.max()), 3)}
            for nm, x in (("env_upper", env), ("env_lower", env_lo), ("env_mix", env_mix), ("gnss", gn),
                          ("fault", fa), ("joint", joint))]
    rows.append({"marginal": "subadditivity_frac", "n": NJ, "median": round(subadd, 5), "p95": "", "p99": "", "max": ""})
    write("e3_marginal_summary.csv", rows)
    gap = []
    for s in np.round(np.arange(1.0, 10.01, 0.5), 2):
        X = [gn, fa, env]
        gap.append({"s_m": s, "union": round(db.union_bound(X, s), 6), "ra": round(db.ra_bound(X, s, N=1000), 6),
                    "indep": round(db.indep_tail(X, s), 6), "indep_mix": round(db.indep_tail([gn, fa, env_mix], s), 6),
                    "comon": round(db.comon_tail(X, s), 6), "sum_same": round(float(np.mean(xe + xg + xf > s)), 6),
                    "joint_sim": round(float(np.mean(joint > s)), 6), "joint_k": int(np.sum(joint > s)),
                    "union_d2": round(db.union_bound([gn, env], s), 6),
                    "ra_d2": round(db.ra_bound([gn, env], s, N=1000), 6),
                    "ra_d2_raw": round(db._ra_bound([gn, env], s, N=1000), 6)})
    write("e3_gap.csv", gap)
    return (env, env_lo, gn, fa)


# ------------------------------------------------------------------ E4
def net_tube(theta_net):
    return AMP * GAMMA_SUP * H_HOPS * min(theta_net, SLACK_S)


def pbar(marg, s, method="ra"):
    env, env_lo, gn, fa = marg
    X = [gn, fa, env]
    if s <= 0:
        return 1.0
    return {"ra": lambda: db.ra_bound(X, s, N=1000), "union": lambda: db.union_bound(X, s),
            "indep": lambda: db.indep_tail(X, s)}[method]()


def e4(cal, marg, attackers, N_eval, pool):
    dadv, rows = {}, []
    for fpr in OPS:                       # same calibration seed per attacker across FPRs -> monotone
        sup, arg = 0.0, None
        for a in attackers:
            i = int(a["attacker_id"])
            o, oa, _ = run_attack(a["family"], json.loads(a["params"]), N_eval // 2, 1700 + i, benign=False)
            st = stealth_mask(o, cal, "ALL", fpr)
            if st.any() and float(oa["maxdev"][st].max()) > sup:
                sup, arg = float(oa["maxdev"][st].max()), a["family"]
        dadv[fpr] = sup
        rows.append({"fpr": fpr, "delta_adv_cal_m": round(sup, 3), "argmax_family": arg,
                     "n_attackers_pooled": len(attackers)})
    write("e4_delta_adv.csv", rows)

    jobs = [(fam, "ALL", fpr, cal, 3000 + i, {}) for i, (fpr, fam) in
            enumerate([(f, a) for f in OPS for a in FAMILIES])]
    held = pool.map(_cem_job, jobs)
    rows, sat = [], []
    pb = {}
    for i, (fam, sname, fpr, seed, J, u) in enumerate(held):
        for wi, (wname, (wl, wh)) in enumerate((("light", (W_LO, W_LO)), ("moderate", (W_HI, W_HI)),
                                                ("envelope", (W_LO, W_HI)))):
            o, oa, ob = run_attack(fam, u, N_eval, 4400 + 10 * i + wi, wl=wl, wh=wh)
            st = stealth_mask(o, cal, "ALL", fpr)
            n_u = int(st.sum())
            adv_max = float(oa["maxdev"][st].max()) if n_u else 0.0
            sp = float(np.mean(o["maxdev"] <= oa["maxdev"] + ob["maxdev"] + 1e-9))
            spx = float(np.max(o["maxdev"] - oa["maxdev"] - ob["maxdev"]))
            puL, _ = cp_interval(n_u, N_eval)
            for m in (5.0, 10.0, 20.0):
                for tn in (0.0, 0.25):
                    s_av = m - dadv[fpr] - net_tube(tn)
                    key = (round(s_av, 6),)
                    if key not in pb:
                        pb[key] = (pbar(marg, s_av, "ra"), pbar(marg, s_av, "union"), pbar(marg, s_av, "indep"))
                    p_ra, p_un, p_in = pb[key]
                    fail_u = (o["maxdev"] + net_tube(tn) > m) & st     # the event Theorem 1 bounds
                    k = int(fail_u.sum())
                    mcr_u = 1 - k / n_u if n_u else float("nan")
                    lo_u, hi_u = cp_interval(n_u - k, n_u) if n_u else (float("nan"),) * 2
                    rows.append({
                        "family": fam, "fpr": fpr, "wind": wname, "m": m, "theta_net": tn,
                        "delta_adv": round(dadv[fpr], 3), "net_tube": round(net_tube(tn), 3),
                        "n": N_eval, "n_undetected": n_u, "k_fail_undetected": k,
                        "rate_fail_undetected": round(k / N_eval, 5),
                        "pbar_ra": round(p_ra, 5), "pbar_union": round(p_un, 5), "p_indep": round(p_in, 5),
                        "f_cert_ra": round(1 - p_ra, 5), "f_cert_union": round(1 - p_un, 5),
                        "f_indep": round(1 - p_in, 5),
                        "mcr_undetected": round(mcr_u, 5), "mcr_u_cp_lo": round(lo_u, 5),
                        "f_cond_ra": round(max(0.0, 1 - p_ra / puL), 5) if puL > 0 else 0.0,
                        "p_violation": float(binom.sf(k - 1, N_eval, p_ra)) if k > 0 else 1.0,
                        "p_violation_indep": float(binom.sf(k - 1, N_eval, p_in)) if k > 0 else 1.0,
                        "heldout_params": json.dumps([round(x, 4) for x in u]),
                        "heldout_adv_max": round(adv_max, 3), "adv_sup_holds": int(adv_max <= dadv[fpr] + 1e-9),
                        "superposition_frac": round(sp, 4), "superposition_max_excess_m": round(spx, 3)})
            if fpr == 0.05 and wname == "envelope":                 # saturation control
                old = SIM.U_MAX; SIM.U_MAX = 1e9
                try:
                    o2, oa2, ob2 = run_attack(fam, u, N_eval, 4400 + 10 * i + wi, wl=wl, wh=wh)
                finally:
                    SIM.U_MAX = old
                sat.append({"family": fam, "superposition_frac_saturated": round(sp, 4),
                            "superposition_frac_unsaturated": round(float(np.mean(o2["maxdev"] <= oa2["maxdev"] + ob2["maxdev"] + 1e-9)), 6),
                            "max_excess_unsaturated_m": float(np.max(o2["maxdev"] - oa2["maxdev"] - ob2["maxdev"]))})
    for key, col in (("p_violation", "p_holm"), ("p_violation_indep", "p_holm_indep")):
        adj = holm([r[key] for r in rows])
        for r, a in zip(rows, adj):
            r[col] = round(float(a), 6); r[key] = round(r[key], 6)
    for r in rows:
        r["violation"] = int(r["p_holm"] < 0.05); r["violation_indep"] = int(r["p_holm_indep"] < 0.05)
    write("e4_soundness.csv", rows)
    write("e4_saturation_control.csv", sat)
    return dadv


# ------------------------------------------------------------------ E5
def e5(cal, marg, dadv, N_eval):
    rows, fpr = [], 0.05
    specs = [("no_anchor_C2_violated", fam, dict(anchor=None), (W_LO, W_HI)) for fam in ("ramp", "fault_mimic")] + \
            [("env_outside_pbox_severe", fam, {}, W_SEV) for fam in ("fault_mimic", "weather_mimic")]
    for j, (ctl, fam, kw, (wl, wh)) in enumerate(specs):
        J, u = cem(fam, "ALL", fpr, cal, 2300 + j, wl=wl, wh=wh, **kw)
        o, oa, _ = run_attack(fam, u, N_eval, 4900 + j, wl=wl, wh=wh, benign=False, **kw)
        st = stealth_mask(o, cal, "ALL", fpr)
        for m in (5.0, 10.0, 20.0):
            p_ra = pbar(marg, m - dadv[fpr], "ra")
            k = int(((o["maxdev"] > m) & st).sum())
            rows.append({"control": ctl, "family": fam, "m": m, "n": N_eval, "n_undetected": int(st.sum()),
                         "k_fail_undetected": k, "pbar_ra": round(p_ra, 5),
                         "mcr_undetected": round(1 - k / max(int(st.sum()), 1), 4),
                         "f_cert_ra": round(1 - p_ra, 4),
                         "p_violation": float(binom.sf(k - 1, N_eval, p_ra)) if k > 0 else 1.0,
                         "max_stealthy_dev": round(float(o["maxdev"][st].max()) if st.any() else 0, 2)})
    adj = holm([r["p_violation"] for r in rows])
    for r, a in zip(rows, adj):
        r["p_holm"] = round(float(a), 6); r["violation"] = int(a < 0.05); r["p_violation"] = round(r["p_violation"], 6)
    write("e5_negative_controls.csv", rows)


def main():
    global CEM_GENS, CEM_K
    ap = argparse.ArgumentParser(); ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    if a.quick:
        CEM_GENS, CEM_K = 10, 16
    N = 1000 if a.quick else 4000
    N_eval = 300 if a.quick else 1000
    cf = RES / "mission_count.txt"; cf.write_text(""); os.environ["P4_COUNT_FILE"] = str(cf)
    t0 = time.time()
    log = lambda s: print(s, round(time.time() - t0, 1), flush=True)
    with Pool(2) as pool:
        cal = e1_calibrate(N); log("E1")
        att = e2_optimise(cal, pool); log("E2")
        e2x_cross(cal, att, N_eval); log("E2x")
        e2_anchor(cal, att, N_eval, pool, True, "e2b_anchor_sweep", 2100, 4200); log("E2b")
        e2_anchor(cal, att, N_eval, pool, False, "e2c_terminal_window", 2200, 4300); log("E2c")
        marg = e3_budget(N); log("E3")
        dadv = e4(cal, marg, att, N_eval, pool); log("E4")
        e5(cal, marg, dadv, N_eval); log("E5")
    n_missions = sum(int(x) for x in cf.read_text().split())
    (RES / "run_meta.json").write_text(json.dumps({"N_cal": N, "N_eval": N_eval, "cem_gens": CEM_GENS,
                                                   "cem_K": CEM_K, "cem_lambda": 12, "n_missions": n_missions,
                                                   "wall_s": round(time.time() - t0, 1)}))


if __name__ == "__main__":
    main()
