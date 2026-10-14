#!/usr/bin/env python3
"""E4-revised -- the source-agnostic floor after the scaled test exposed three
failed conditions (results/r1_e4_soundness.csv):

  C1  superposition failed under actuator saturation (up to 14.6 m excess);
  C3  the benign p-box carried no sampling uncertainty (pbar = 0 beyond the
      largest of 4,000 samples, while 1-in-5,000 benign missions failed);
  dadv  an empirical supremum over 500 calibration missions was exceeded by
      held-out attackers on 5,000 missions (36 of 270 cells, up to 1.61x).

Revisions, fixed BEFORE this evaluation and judged on fresh seeds:
  (i)   saturation alarm D_sat: the autopilot flags any epoch at which the
        commanded acceleration reaches U_MAX. Stealth now also requires no
        saturation; on unsaturated missions superposition is exact (checked).
  (ii)  two stealth budgets, each tested as its own Holm family:
        "r1_pooled" -- the R1 calibration supremum (results/r1_delta_adv.csv),
                       fixed before this run and NOT widened with the R1
                       held-out maxima (runbook ground rule);
        "lp_revised" -- the R8 linear-programming bound for the revised stack
                       (anchor gate + D1 + D_sat, T_a = 5 s), which holds for
                       EVERY stealthy attack with probability >= 1 - eps over
                       the benign noise; eps is added to the bound.
  (iii) per-source Clopper-Pearson upper tails aggregated by the union
        (Makarov) bound over all splits of the available budget. The splits are
        chosen after seeing the data, so the tails must hold SIMULTANEOUSLY on
        the whole split grid: each of the 3 x G_GRID tail bounds is taken at
        level alpha / (3 G_GRID) (Bonferroni), and with probability >= 1 - alpha
        every pbar_U below is a valid upper bound on the true union bound.
Bound tested:  Pr[fail and undetected] <= pbar_U(m - delta - net) + eps (eps = 0 for r1_pooled).

Seed blocks (fresh; the --quick smoke test used 9000/9500/90000 and is NOT
reused): 9201 benign FPR check; 9200 + h held-out CEM attackers, 9700 + h
held-out tail-TPE attackers (both optimised AGAINST the revised stack);
92000 + 10 h + w (+5000 for TPE) held-out evaluation missions.
Outputs: results/e4r_fpr.csv, e4r_heldout.csv, e4r_soundness.csv
Usage:   python3 e4_revised.py [--quick] [--par 4]
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from multiprocessing import Pool

import numpy as np
from scipy.stats import binom

import run_pilot as RP
import r1_attackers as R1
from sim import simulate
from depbounds import cp_tails, pbar_union_cp, G_GRID

RES = RP.RES
FAMS = R1.FAMS
_orig_mask = RP.stealth_mask


def stealth_rev(o, cal, stack, fpr):
    """Detector stack + anchor gate + saturation alarm."""
    return _orig_mask(o, cal, stack, fpr) & ~o["sat"]


# every optimiser and evaluation below sees the revised stack
RP.stealth_mask = stealth_rev
R1.stealth_mask = stealth_rev


def _held_cem(args):
    fam, fpr, h, gens, k = args
    cal = R1.load_cal()
    J, u = RP.cem(fam, "ALL", fpr, cal, 9200 + h, gens=gens, K=k)
    return "cem", fam, fpr, 9200 + h, J, u.tolist()


def _held_tail(args):
    fam, fpr, h, budget = args
    R1.OBJECTIVE = "tail"
    cal = R1.load_cal()
    (J, u), _ = R1.run_tpe(fam, "ALL", fpr, cal, 3700 + h, budget["trials"], budget["k"])
    return "tpe_tail", fam, fpr, 9700 + h, J, [float(x) for x in u]


def _eval(args):
    opt, fam, fpr, hseed, u, n, budgets, pb = args
    cal = R1.load_cal()
    rows = []
    for wi, (wname, (wl, wh)) in enumerate((("light", (RP.W_LO, RP.W_LO)), ("moderate", (RP.W_HI, RP.W_HI)),
                                            ("envelope", (RP.W_LO, RP.W_HI)))):
        o, oa, ob = RP.run_attack(fam, u, n, 92000 + 10 * (hseed % 1000) + wi + (5000 if opt != "cem" else 0),
                                  wl=wl, wh=wh)
        st = stealth_rev(o, cal, "ALL", fpr)
        n_u = int(st.sum())
        adv = float(oa["maxdev"][st].max()) if n_u else 0.0
        ex = (o["maxdev"] - oa["maxdev"] - ob["maxdev"])[st]
        unsat = st & ~o["sat"]
        ex_u = (o["maxdev"] - oa["maxdev"] - ob["maxdev"])[unsat]
        for var, (dadv, eps) in budgets.items():
            for m in (5.0, 10.0, 20.0):
                for tn in (0.0, 0.25):
                    s_av = m - dadv[fpr] - RP.net_tube(tn)
                    p_b = pb[(var, fpr, m, tn)]
                    bound = min(1.0, p_b + eps)
                    k = int(((o["maxdev"] + RP.net_tube(tn) > m) & st).sum())
                    rows.append({"delta_variant": var, "optimiser": opt, "family": fam, "fpr": fpr,
                                 "heldout_seed": hseed, "wind": wname,
                                 "m": m, "theta_net": tn, "delta_adv": round(dadv[fpr], 3), "eps": eps,
                                 "s_available_m": round(s_av, 3), "pbar_union_cp": round(p_b, 6),
                                 "bound": round(bound, 6), "f_cert": round(1 - bound, 6), "n": n,
                                 "n_undetected": n_u, "frac_sat_alarm": round(float(o["sat"].mean()), 4),
                                 "k_fail_undetected": k, "rate_fail_undetected": round(k / n, 6),
                                 "p_violation": float(binom.sf(k - 1, n, bound)) if k > 0 else 1.0,
                                 "heldout_adv_max": round(adv, 3), "adv_within_delta": int(adv <= dadv[fpr] + 1e-9),
                                 "superposition_max_excess_m": round(float(ex.max()) if ex.size else 0.0, 4),
                                 "superposition_max_excess_unsat_m": round(float(ex_u.max()) if ex_u.size else 0.0, 6),
                                 "provenance": "sim"})
    return rows


def write(name, rows):
    if rows:
        with open(RES / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--quick", action="store_true")
    ap.add_argument("--par", type=int, default=4)
    a = ap.parse_args()
    n, n_fpr, seeds_cem, gens, k = 5000, 8000, 3, RP.CEM_GENS, RP.CEM_K
    budget = dict(trials=R1.TRIALS, k=R1.K)
    if a.quick:
        n, n_fpr, seeds_cem, gens, k = 300, 1000, 1, 4, 8
        budget = dict(trials=12, k=16)
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:7.0f}s] {s}", flush=True)
    cal = R1.load_cal()
    # benign false-alarm rate of the revised stack (envelope wind, fresh seed)
    b = simulate(n_fpr, 9201, w20=RP.wind(n_fpr, 9201))
    rows = []
    for fpr in RP.OPS:
        quiet = _orig_mask(b, cal, "ALL", fpr)               # no alarm from the stack + anchor gate
        rev = stealth_rev(b, cal, "ALL", fpr)
        rows.append({"fpr_target": fpr, "fpr_stack_anchor": round(1 - float(quiet.mean()), 4),
                     "fpr_with_sat_alarm": round(1 - float(rev.mean()), 4),
                     "sat_alarm_alone": round(float(b["sat"].mean()), 4), "n": n_fpr, "provenance": "sim"})
    write("e4r_fpr.csv", rows); log(f"FPR: {rows}")
    # delta from R8
    r8 = [r for r in csv.DictReader((RES / "r8_analytic_bound.csv").open())
          if r["T_anchor_s"] in ("5.0", "5") and r["constraints"].startswith("anchor gate + D1 + D_sat")]
    budgets = {"r1_pooled": ({float(r["fpr"]): float(r["delta_pooled_m"])
                              for r in csv.DictReader((RES / "r1_delta_adv.csv").open())}, 0.0),
               "lp_revised": ({float(r["fpr"]): float(r["delta_lp_m"]) for r in r8}, float(r8[0]["eps"]))}
    z = np.load(RES / "e3_marginals.npz")
    margs = [z["gnss"], z["fault"], z["env"]]
    U = cp_tails(margs)
    pb = {}
    for var, (dadv, _) in budgets.items():
        for fpr in RP.OPS:
            for m in (5.0, 10.0, 20.0):
                for tn in (0.0, 0.25):
                    pb[(var, fpr, m, tn)] = pbar_union_cp(U, m - dadv[fpr] - RP.net_tube(tn))
    log(f"budgets {budgets}; pbar computed")
    with Pool(a.par) as pool:
        jobs_c = [(f, p, h, gens, k) for h, (f, p) in
                  enumerate([(f, p) for p in RP.OPS for f in FAMS for _ in range(seeds_cem)])]
        jobs_t = [(f, p, h, budget) for h, (f, p) in enumerate([(f, p) for p in RP.OPS for f in FAMS])]
        held = pool.map(_held_cem, jobs_c) + pool.map(_held_tail, jobs_t)
        write("e4r_heldout.csv", [{"optimiser": o, "family": f, "fpr": p, "heldout_seed": s, "J_train": round(J, 4),
                                   "params": json.dumps([round(x, 5) for x in u])} for o, f, p, s, J, u in held])
        log(f"{len(held)} held-out attackers optimised against the revised stack")
        rows = []
        for rr in pool.imap_unordered(_eval, [(o, f, p, s, u, n, budgets, pb) for o, f, p, s, J, u in held]):
            rows += rr
    rows.sort(key=lambda r: (r["delta_variant"], r["fpr"], r["family"], r["optimiser"], r["heldout_seed"],
                             r["wind"], r["m"], r["theta_net"]))
    for var in budgets:                           # one Holm family per stealth budget
        rv = [r for r in rows if r["delta_variant"] == var]
        adj = RP.holm([r["p_violation"] for r in rv])
        for r, x in zip(rv, adj):
            r["p_holm"] = round(float(x), 6); r["p_violation"] = round(r["p_violation"], 6)
            r["violation"] = int(x < 0.05)
        cells = {(r["optimiser"], r["family"], r["fpr"], r["heldout_seed"], r["wind"]): r for r in rv}
        log(f"[{var}] {len(rv)} tests, {sum(r['violation'] for r in rv)} Holm-significant violations; "
            f"held-out attack-only deviation within delta in {sum(c['adv_within_delta'] for c in cells.values())}"
            f"/{len(cells)} cells; max superposition excess {max(c['superposition_max_excess_m'] for c in cells.values())} m "
            f"(unsaturated stealthy missions: {max(c['superposition_max_excess_unsat_m'] for c in cells.values())} m)")
    write("e4r_soundness.csv", rows)
    meta = RES / "run_meta.json"
    mm = json.loads(meta.read_text()) if meta.exists() else {}
    mm["e4_revised"] = {"n": n, "held_cem_seeds": seeds_cem, "tail_tpe": budget, "quick": a.quick,
                        "seed_blocks": {"fpr": 9201, "held_cem": "9200+h", "held_tail": "9700+h (TPE seed 3700+h)",
                                        "eval": "92000+10h+w (+5000 for tail)"},
                        "cp_band": f"simultaneous Bonferroni over 3 x {G_GRID} grid points, alpha 0.05"}
    meta.write_text(json.dumps(mm))


if __name__ == "__main__":
    main()
