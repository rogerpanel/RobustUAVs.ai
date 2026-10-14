#!/usr/bin/env python3
"""R1 -- stronger attackers and a re-pooled stealth budget (runbook R1, load-bearing).

1. Optimisers, per (stack x family x operating point), on the same objective as
   the pilot's CEM (mean over K missions of the post-onset deviation of stealthy
   missions):
     cma   CMA-ES (popsize 16, 200 generations, bounds [0,1], one IPOP restart),
           K = 128 rollouts per candidate with COMMON RANDOM NUMBERS: every
           candidate of a generation flies the same 128 missions;
     tpe   Bayesian optimisation (optuna TPE, 400 trials, K = 128, CRN blocks of
           16 trials).
   Families: the five pilot families plus `mixed` (begins as one family and
   hands over to another at an optimised switch time).
2. delta_adv is recomputed by pooling the pilot's 35 attackers with every R1
   attacker, on the pilot's calibration missions (seed 1700 + attacker id).
   Acceptance: pooled <= 1.25 x pilot, else the floors are regenerated.
3. E4 scaled: 5 held-out CEM attackers per (FPR x family, incl. mixed) and
   n = 5,000 held-out missions per (attacker x wind); Theorem 1 is tested on
   {fail and undetected} with Holm across every test.

Seed blocks (R1 takes 6xxx-8xxx; see results/run_meta.json):
  6000 + j       optimiser job j; inner simulation seeds (6000 + j) * 1000 + g
  1700 + id      pooled-delta calibration missions (pilot convention, ids >= 35)
  7000 + h       held-out CEM attacker h (inner seeds (7000 + h) * 100 + g)
  8000 + 10h + w held-out evaluation missions
Outputs: results/r1_attackers.csv, r1_delta_adv.csv, r1_heldout.csv,
         r1_e4_soundness.csv (provenance = sim)
Usage:   python3 r1_attackers.py [--quick] [--par 4]
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy.stats import binom

import run_pilot as RP
from run_pilot import (stealth_mask, run_attack, wind, cp_interval, holm, net_tube, pbar,
                       W_LO, W_HI, STACKS, OPS)
from sim import simulate, decode, ATTACK_BOX

RES = RP.RES
FAMS = ("step", "ramp", "fault_mimic", "gnss_mimic", "weather_mimic", "mixed")
POP, GENS, K, TRIALS = 16, 200, 128, 400


def load_cal():
    js = json.loads((RES / "e1_calibration.json").read_text())
    return {"single": {float(k): v for k, v in js["single"].items()},
            "stack": {float(k): v for k, v in js["stack"].items()}, "anchor": js["anchor"]}


OBJECTIVE = "mean"


def objective(U, family, stack, fpr, cal, seed, k=K):
    """J for each row of U, all rows on the same k missions (CRN). 'mean' is the
    pilot's objective (mean stealthy post-onset deviation); 'tail' targets the
    supremum that defines delta_adv (90th percentile over the k missions)."""
    U = np.atleast_2d(U)
    pop = len(U)
    P = decode(family, np.repeat(U, k, axis=0))
    w = np.tile(wind(k, seed), pop)
    o = simulate(pop * k, seed, w20=w, attack=family, aparams=P, crn=k)
    st = stealth_mask(o, cal, stack, fpr)
    x = (o["maxdev_after"] * st).reshape(pop, k)
    return np.quantile(x, 0.9, axis=1) if OBJECTIVE == "tail" else x.mean(1)


def run_cma(family, stack, fpr, cal, job, gens, pop, k):
    import cma
    dim = len(ATTACK_BOX[family])
    best = (-1.0, None)
    g = 0
    for restart, popsize in enumerate((pop, 2 * pop)):          # one IPOP restart
        es = cma.CMAEvolutionStrategy(np.full(dim, 0.5), 0.3,
                                      {"bounds": [0, 1], "popsize": popsize, "seed": 6000 + job + 7 * restart,
                                       "verbose": -9, "maxiter": gens // 2})
        while not es.stop():
            X = np.clip(np.asarray(es.ask()), 0, 1)
            J = objective(X, family, stack, fpr, cal, (6000 + job) * 1000 + g, k)
            g += 1
            es.tell(list(X), list(-J))
            i = int(np.argmax(J))
            if J[i] > best[0]:
                best = (float(J[i]), X[i].copy())
    return best, g


def run_tpe(family, stack, fpr, cal, job, trials, k):
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    dim = len(ATTACK_BOX[family])
    best = [-1.0, None]

    def f(trial):
        u = np.array([trial.suggest_float(f"u{i}", 0.0, 1.0) for i in range(dim)])
        J = float(objective(u, family, stack, fpr, cal, (6000 + job) * 1000 + trial.number // 16, k)[0])
        if J > best[0]:
            best[0], best[1] = J, u
        return J
    study = optuna.create_study(direction="maximize",
                                sampler=optuna.samplers.TPESampler(seed=6000 + job))
    study.optimize(f, n_trials=trials)
    return (best[0], best[1]), trials


def _job(args):
    global OBJECTIVE
    opt, family, stack, fpr, job, budget, objective_name = args
    OBJECTIVE = objective_name
    cal = load_cal()
    t0 = time.time()
    if opt == "cma":
        (J, u), n = run_cma(family, stack, fpr, cal, job, budget["gens"], budget["pop"], budget["k"])
    else:
        (J, u), n = run_tpe(family, stack, fpr, cal, job, budget["trials"], budget["k"])
    return {"optimiser": opt + ("_tail" if objective_name == "tail" else ""), "family": family,
            "origin_stack": stack, "origin_fpr": fpr,
            "job_seed": 6000 + job, "evaluations": n, "J_train": round(J, 4),
            "params": json.dumps([round(float(x), 5) for x in u]), "wall_s": round(time.time() - t0, 1)}


def _delta_job(args):
    a, fprs = args
    cal = load_cal()
    o, oa, _ = run_attack(a["family"], json.loads(a["params"]), 500, 1700 + int(a["attacker_id"]), benign=False)
    out = {}
    for fpr in fprs:
        st = stealth_mask(o, cal, "ALL", fpr)
        out[fpr] = (float(oa["maxdev"][st].max()) if st.any() else 0.0, float(st.mean()))
    return a["attacker_id"], out


def _held_job(args):
    fam, fpr, h, gens, k = args
    cal = load_cal()
    J, u = RP.cem(fam, "ALL", fpr, cal, 7000 + h, gens=gens, K=k)
    return fam, fpr, h, J, u.tolist()


def _eval_job(args):
    fam, fpr, h, u, n, dadv, marg_path = args
    cal = load_cal()
    z = np.load(marg_path)
    marg = (z["env"], z["env_lo"], z["gnss"], z["fault"])
    rows = []
    for wi, (wname, (wl, wh)) in enumerate((("light", (W_LO, W_LO)), ("moderate", (W_HI, W_HI)),
                                            ("envelope", (W_LO, W_HI)))):
        o, oa, ob = run_attack(fam, u, n, 8000 + 10 * h + wi, wl=wl, wh=wh)
        st = stealth_mask(o, cal, "ALL", fpr)
        n_u = int(st.sum())
        adv_max = float(oa["maxdev"][st].max()) if n_u else 0.0
        sp = float(np.mean(o["maxdev"] <= oa["maxdev"] + ob["maxdev"] + 1e-9))
        puL, _ = cp_interval(n_u, n)
        for m in (5.0, 10.0, 20.0):
            for tn in (0.0, 0.25):
                s_av = m - dadv[fpr] - net_tube(tn)
                p_ra, p_in = pbar(marg, s_av, "ra"), pbar(marg, s_av, "indep")
                fail_u = (o["maxdev"] + net_tube(tn) > m) & st
                kk = int(fail_u.sum())
                rows.append({"family": fam, "fpr": fpr, "heldout_seed": 7000 + h, "wind": wname, "m": m,
                             "theta_net": tn, "delta_adv": round(dadv[fpr], 3), "n": n, "n_undetected": n_u,
                             "k_fail_undetected": kk, "pbar_ra": round(p_ra, 5), "f_cert_ra": round(1 - p_ra, 5),
                             "p_indep": round(p_in, 5),
                             "mcr_undetected": round(1 - kk / n_u, 5) if n_u else "",
                             "f_cond_ra": round(max(0.0, 1 - p_ra / puL), 5) if puL > 0 else 0.0,
                             "p_violation": float(binom.sf(kk - 1, n, p_ra)) if kk > 0 else 1.0,
                             "p_violation_indep": float(binom.sf(kk - 1, n, p_in)) if kk > 0 else 1.0,
                             "heldout_adv_max": round(adv_max, 3), "adv_sup_holds": int(adv_max <= dadv[fpr] + 1e-9),
                             "superposition_frac": round(sp, 4), "provenance": "sim"})
    return rows


def write(name, rows):
    if rows:
        with open(RES / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--par", type=int, default=4)
    ap.add_argument("--stage", default="all", choices=("all", "optimise", "optimise_tail", "delta", "e4"))
    a = ap.parse_args()
    budget = dict(gens=GENS, pop=POP, k=K, trials=TRIALS)
    n_eval, held_seeds, held_gens, held_k = 5000, 5, RP.CEM_GENS, RP.CEM_K
    if a.quick:
        budget = dict(gens=6, pop=8, k=16, trials=12)
        n_eval, held_seeds, held_gens, held_k = 300, 1, 4, 8
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:7.0f}s] {s}", flush=True)
    with Pool(a.par) as pool:
        combos = [(f, s, 0.05) for s in STACKS for f in FAMS] + [(f, "ALL", p) for p in (0.01, 0.10) for f in FAMS]
        if a.stage == "optimise_tail":
            # tail objective, TPE only: seeds 6500 + j, ids after the mean-objective attackers
            jobs = [("tpe", f, s, p, 500 + j, budget, "tail") for j, (f, s, p) in enumerate(combos)]
            rows = []
            for r in pool.imap_unordered(_job, jobs):
                rows.append(r); log(f"{r['optimiser']} {r['family']} {r['origin_stack']} {r['origin_fpr']} J={r['J_train']}")
            rows.sort(key=lambda r: (r["origin_stack"], r["origin_fpr"], r["family"]))
            base = 35 + sum(1 for _ in csv.DictReader((RES / "r1_attackers.csv").open()))
            write("r1_attackers_tail.csv", [{"attacker_id": base + i, **r} for i, r in enumerate(rows)])
        if a.stage in ("all", "optimise"):
            jobs = [(opt, f, s, p, j, budget, "mean") for j, (opt, (f, s, p)) in
                    enumerate([(o, c) for o in ("tpe", "cma") for c in combos])]
            rows = []
            for r in pool.imap_unordered(_job, jobs):
                rows.append(r); log(f"{r['optimiser']} {r['family']} {r['origin_stack']} {r['origin_fpr']} J={r['J_train']}")
            rows.sort(key=lambda r: (r["optimiser"], r["origin_stack"], r["origin_fpr"], r["family"]))
            for i, r in enumerate(rows):
                r["attacker_id"] = 35 + i
            write("r1_attackers.csv", [{"attacker_id": r.pop("attacker_id"), **r} for r in rows])
        if a.stage in ("all", "delta"):
            pilot = list(csv.DictReader((RES / "e2_attackers.csv").open()))
            r1 = list(csv.DictReader((RES / "r1_attackers.csv").open()))
            if (RES / "r1_attackers_tail.csv").exists():
                r1 += list(csv.DictReader((RES / "r1_attackers_tail.csv").open()))
            allatt = [dict(p, optimiser="cem") for p in pilot] + r1
            res = dict(pool.map(_delta_job, [(x, OPS) for x in allatt]))
            pilot_d = {float(r["fpr"]): float(r["delta_adv_cal_m"]) for r in csv.DictReader((RES / "e4_delta_adv.csv").open())}
            rows = []
            for fpr in OPS:
                best = max(allatt, key=lambda x: res[x["attacker_id"]][fpr][0])
                by_opt = {}
                for x in allatt:
                    by_opt[x["optimiser"]] = max(by_opt.get(x["optimiser"], 0.0), res[x["attacker_id"]][fpr][0])
                pooled = res[best["attacker_id"]][fpr][0]
                rows.append({"fpr": fpr, "delta_pilot_m": pilot_d[fpr], "delta_pooled_m": round(pooled, 3),
                             "ratio": round(pooled / pilot_d[fpr], 3) if pilot_d[fpr] else "",
                             "accept_1p25": int(pooled <= 1.25 * pilot_d[fpr] + 1e-9),
                             "argmax_optimiser": best["optimiser"], "argmax_family": best["family"],
                             "argmax_attacker_id": best["attacker_id"],
                             **{f"sup_{k}": round(v, 3) for k, v in sorted(by_opt.items())},
                             "n_attackers": len(allatt), "provenance": "sim"})
                log(f"delta_adv fpr={fpr}: pilot {pilot_d[fpr]} -> pooled {pooled:.3f} ({best['optimiser']}/{best['family']})")
            write("r1_delta_adv.csv", rows)
        if a.stage in ("all", "e4"):
            dr = {float(r["fpr"]): r for r in csv.DictReader((RES / "r1_delta_adv.csv").open())}
            # the certificate uses the pooled value whether or not it passes the 1.25x acceptance
            dadv = {f: max(float(dr[f]["delta_pooled_m"]), float(dr[f]["delta_pilot_m"])) for f in OPS}
            hjobs = [(fam, fpr, h, held_gens, held_k) for h, (fam, fpr) in
                     enumerate([(f, p) for p in OPS for f in FAMS for _ in range(held_seeds)])]
            held = pool.map(_held_job, hjobs)
            write("r1_heldout.csv", [{"family": f, "fpr": p, "heldout_seed": 7000 + h, "J_train": round(J, 4),
                                      "params": json.dumps([round(x, 5) for x in u])} for f, p, h, J, u in held])
            log("held-out attackers optimised")
            ejobs = [(f, p, h, u, n_eval, dadv, str(RES / "e3_marginals.npz")) for f, p, h, J, u in held]
            rows = []
            for rr in pool.imap_unordered(_eval_job, ejobs):
                rows += rr
            rows.sort(key=lambda r: (r["fpr"], r["family"], r["heldout_seed"], r["wind"], r["m"], r["theta_net"]))
            for key, col in (("p_violation", "p_holm"), ("p_violation_indep", "p_holm_indep")):
                adj = holm([r[key] for r in rows])
                for r, x in zip(rows, adj):
                    r[col] = round(float(x), 6); r[key] = round(r[key], 6)
            for r in rows:
                r["violation"] = int(r["p_holm"] < 0.05); r["violation_indep"] = int(r["p_holm_indep"] < 0.05)
            write("r1_e4_soundness.csv", rows)
            log(f"E4 scaled: {len(rows)} tests, {sum(r['violation'] for r in rows)} Holm-significant violations")
    meta = RES / "run_meta.json"
    m = json.loads(meta.read_text()) if meta.exists() else {}
    m["r1"] = {"budget": budget, "n_eval": n_eval, "held_seeds": held_seeds, "seed_blocks":
               {"optimise": "6000+j (inner (6000+j)*1000+g)", "pooled_delta": "1700+id",
                "heldout_cem": "7000+h", "heldout_eval": "8000+10h+w"}, "quick": a.quick}
    meta.write_text(json.dumps(m))


if __name__ == "__main__":
    main()
