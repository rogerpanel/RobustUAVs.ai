#!/usr/bin/env python3
"""Write manuscript/numbers.tex (one macro per quoted number) and
manuscript/tab_main.tex (the main results table) from the result CSVs.
Never type a number into main.tex by hand: re-run run_all.sh instead."""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from certcmdp.certificate import (OUT, KAPPA, L_LOC, GAMMA_SUP, THETA_BENIGN,  # noqa: E402
                                  ALERT_LIMITS)

MS = OUT.parent / "manuscript"


def rd(name):
    p = OUT / name
    if not p.exists():
        return []
    with p.open() as fh:
        return list(csv.DictReader(fh))


def pick(rows, **kw):
    for r in rows:
        if all(str(r[k]) == str(v) for k, v in kw.items()):
            return r
    raise KeyError(kw)


def f(x, nd=3):
    return f"{float(x):.{nd}f}"


def sci(x):
    x = float(x)
    if x == 0:
        return "0"
    e = int(math.floor(math.log10(abs(x))))
    m = x / 10 ** e
    return f"{m:.1f}\\times10^{{{e}}}"


def main():
    m = {}
    const = {r["name"]: float(r["value"]) for r in rd("constants_paperIII.csv")}
    m["Kappa"] = f(KAPPA, 2)
    m["GammaSup"] = f(GAMMA_SUP, 3)
    m["Lloc"] = f(L_LOC, 3)
    m["Expl"] = f(math.exp(L_LOC), 2)
    m["RhoFloor"] = f(KAPPA * THETA_BENIGN, 2)
    m["ThetaBen"] = f(THETA_BENIGN, 3)
    m["NBenign"] = f"{int(const['n_benign_hops']):,}".replace(",", "{,}")
    m["NHidden"] = f"{int(const['n_hidden_hops']):,}".replace(",", "{,}")
    m["NHops"] = "15{,}392"
    m["HiddenMed"] = f(const["hidden_residual_median_s"], 2)
    m["HiddenMax"] = f(const["hidden_residual_max_s"], 2)
    m["JumpMed"] = f(KAPPA * 2 * const["hidden_residual_median_s"], 1)
    m["JumpOneMed"] = f(KAPPA * const["hidden_residual_median_s"], 1)
    m["AlphaMin"] = f(min(ALERT_LIMITS), 0)
    m["AlphaMax"] = f(max(ALERT_LIMITS), 0)
    dt_max = (min(ALERT_LIMITS) - KAPPA * THETA_BENIGN) / KAPPA
    m["DtMax"] = f(dt_max, 3)
    m["RateMin"] = f(1 / dt_max, 2)
    # E1
    v = rd("e1_verify.csv")
    if v:
        m["VerInst"] = f"{int(pick(v, check='deficiency')['instances']):,}".replace(",", "{,}")
        m["VerChecks"] = str(len(v))
        m["VerTotal"] = f"{sum(int(r['instances']) for r in v):,}".replace(",", "{,}")
        m["VerDisagree"] = str(sum(int(r["disagreements"]) for r in v))
    # E2
    c = rd("e2_collapse.csv")
    if c:
        r = pick(c, phi="0.3")
        m["CollB"] = str(int(float(r["b"])))
        m["CollNom"] = f(r["cov_nominal"], 2)
        m["CollRand"] = f(r["cov_random"], 2)
        m["CollWorst"] = f(r["cov_worst"], 2)
        m["CollGeneric"] = f(r["bound_generic"], 2)
    g = rd("e2_graded.csv")
    if g:
        m["GradTight"] = f"{100 * min(float(r['bound_tight_frac']) for r in g):.0f}"
        m["GradViol"] = str(sum(int(float(r["bound_violations"])) for r in g))
        r = pick(g, tau_s="1.0", phi="0.6")
        m["GradRandSix"] = f(r["cov_random"], 2)
        m["GradWorstSix"] = f(r["cov_worst"], 2)
    lift = rd("e2_lift.csv")
    if lift:
        for dep, nm in (("independent", "Ind"), ("spatial_jammers", "Sp")):
            r0 = pick(lift, dependence=dep, event="d=0")
            m[f"Lift{nm}FullPred"] = f(r0["p_iid_pred"], 3)
            m[f"Lift{nm}FullSim"] = f(r0["p_sim"], 3)
            r4 = pick(lift, dependence=dep, event="d>=4")
            m[f"Lift{nm}FourPred"] = f(100 * float(r4["p_iid_pred"]), 1)
            m[f"Lift{nm}FourSim"] = f(100 * float(r4["p_sim"]), 1)
            m[f"Lift{nm}FourLo"] = f(100 * float(r4["p_sim_lo"]), 1)
            m[f"Lift{nm}FourHi"] = f(100 * float(r4["p_sim_hi"]), 1)
            r3 = pick(lift, dependence=dep, event="d>=3")
            m[f"Lift{nm}ThreePred"] = f(100 * float(r3["p_iid_pred"]), 1)
            m[f"Lift{nm}ThreeSim"] = f(100 * float(r3["p_sim"]), 1)
        r6 = pick(lift, dependence="spatial_jammers", event="d>=6")
        m["LiftSpSixPred"] = f(100 * float(r6["p_iid_pred"]), 1)
        m["LiftSpSixSim"] = f(100 * float(r6["p_sim"]), 1)
        m["LiftSpSixLo"] = f(100 * float(r6["p_sim_lo"]), 1)
        m["LiftSpSixHi"] = f(100 * float(r6["p_sim_hi"]), 1)
        m["LiftUnder"] = f(float(r6["p_sim"]) / float(r6["p_iid_pred"]), 1)
        r0 = pick(lift, dependence="spatial_jammers", event="d=0")
        m["LiftSpFullLo"] = f(r0["p_sim_lo"], 3)
        m["LiftSpFullHi"] = f(r0["p_sim_hi"], 3)
        m["LiftOver"] = f(float(r0["p_sim"]) / float(r0["p_iid_pred"]), 1)
        m["LiftSpQnone"] = f(100 * (1 - float(r0["q_le20"])), 0)
        m["LiftIndQnone"] = f(100 * (1 - float(pick(lift, dependence="independent", event="d=0")["q_le20"])), 0)
        m["LiftFleets"] = str(int(float(r6["n_fleets"])))
    fs = rd("e2_fleet_sizing.csv")
    if fs:
        for dep, nm in (("independent", "Ind"), ("spatial_jammers", "Sp")):
            ok = [int(r["N"]) for r in fs if r["dependence"] == dep
                  and float(r["p_full_pred_iid"]) >= 0.99]
            m[f"Size{nm}"] = str(min(ok)) if ok else ">30"
    # E3
    lat = rd("e3_latency.csv")
    if lat:
        def L(N, a, q="p50_ms"):
            return float(pick(lat, N=N, algorithm=a)[q])
        m["LatCFHundredK"] = f(L(100000, "closed_form_check"), 1)
        m["LatGNPHundredK"] = f(L(100000, "gnp_fast"), 0)
        m["LatGNPTenK"] = f(L(10000, "gnp_fast"), 1)
        m["LatGNPThousand"] = f(L(1000, "gnp_fast"), 2)
        m["LatCFThousand"] = f(L(1000, "closed_form_check"), 3)
        m["LatHunThousand"] = f(L(1000, "lexicographic_hungarian"), 1)
        m["LatHunTwoK"] = f(L(2000, "lexicographic_hungarian"), 0)
        m["LatHunTwelve"] = f(L(12, "lexicographic_hungarian"), 3)
        m["LatHKTenK"] = f(L(10000, "hopcroft_karp"), 0)
        m["LatCPU"] = pick(lat, N=12, algorithm="gnp_fast")["cpu"].replace("_", "-")
    # E4
    la = rd("e4_lookahead.csv")
    if la:
        for cfg, nm in (("standard", "Std"), ("predictive_dt", "Pdt"), ("predictive_1s", "Pone"),
                        ("predictive_2s", "Ptwo"), ("standard_5Hz", "StdFive"),
                        ("predictive_dt_5Hz", "PdtFive"), ("release_only", "Rel")):
            r = pick(la, config=cfg)
            m[f"Exp{nm}"] = f(100 * float(r["exposure_per_agent_step"]), 2)
            m[f"Cov{nm}"] = f(r["r_cert"], 3)
            m[f"ExpNoJ{nm}"] = str(int(r["exposure_without_jump"]))
            m[f"Sw{nm}"] = f(100 * float(r["switches_per_agent_step"]), 2)
            m[f"Ratio{nm}"] = f(r["assigned_over_bound"], 3)
        m["ExpCut"] = f(float(pick(la, config="standard")["exposure_per_agent_step"])
                        / float(pick(la, config="predictive_dt")["exposure_per_agent_step"]), 1)
        m["ExpCutFive"] = f(float(pick(la, config="standard_5Hz")["exposure_per_agent_step"])
                            / float(pick(la, config="predictive_dt_5Hz")["exposure_per_agent_step"]), 1)
    hy = rd("e4_hysteresis.csv")
    if hy:
        m["HystHolds"] = f"{100 * min(float(r['thm2_bound_holds_frac']) for r in hy if r['thm2_bound_holds_frac']):.0f}"
        r0, r5 = pick(hy, eta="0.0"), pick(hy, eta="0.5")
        m["HystSwZero"] = f(100 * float(r0["switches_per_agent_step"]), 2)
        m["HystSwHalf"] = f(100 * float(r5["switches_per_agent_step"]), 2)
        m["HystCovZero"] = f(r0["r_cert"], 3)
        m["HystCovHalf"] = f(r5["r_cert"], 3)
    li = rd("e4_liars.csv")
    if li:
        m["LiarMaxDev"] = str(max(int(r["max_abs_dev_d"]) - int(r["liars_f"]) for r in li))
        m["LiarHonest"] = str(sum(int(r["violations_by_honest"]) for r in li))
        m["LiarInst"] = f"{int(li[0]['instances']):,}".replace(",", "{,}")
    # E5/E6
    mn = rd("e6_main.csv")
    names = {
        "ours": r"\textbf{Projection (SE) + PPO (ours)}",
        "ours_nodev": r"\quad ablation: no deviation penalty",
        "mask": r"Per-agent action masking + PPO",
        "mask+proj": r"\quad + projection at deployment",
        "lagrangian": r"PPO-Lagrangian (certificate observed)",
        "lagrangian+proj": r"\quad + projection at deployment",
        "blind": r"Jamming-blind PPO",
        "blind+proj": r"\quad + projection at deployment",
        "heuristic+proj": r"Keep-or-nearest + projection",
        "gnp": r"Tightest-fit greedy, re-solved each epoch",
        "fixed_margin": r"Fixed design margin (1\,s dead reckoning)",
        "heuristic_none": r"Keep-or-nearest, no certificate",
    }
    order = ["ours", "ours_nodev", "mask", "mask+proj", "lagrangian", "lagrangian+proj",
             "blind", "blind+proj", "heuristic+proj", "gnp", "fixed_margin", "heuristic_none"]
    if mn:
        byname = {r["method"]: r for r in mn}
        lines = []
        for k in order:
            if k not in byname:
                continue
            r = byname[k]
            if k == "heuristic+proj":
                lines.append(r"\midrule")
            tv = r["train_violations"]
            if tv == "":
                tvs = "--"
            elif int(tv) == 0:
                tvs = rf"$0$ ($\le{sci(r['train_viol_cp95'])}$)"
            else:
                tvs = rf"${int(tv):,}$".replace(",", "{,}")
            ev = float(r["viol_iqm"])
            evs = (rf"$0$ ($\le{sci(r['eval_viol_cp95'])}$)" if int(r["eval_violations"]) == 0
                   else f"${100 * ev:.2f}$")
            lines.append(
                f"{names[k]} & ${float(r['r_cert_iqm']):.3f}$ {{\\scriptsize[{float(r['r_cert_lo']):.3f}, {float(r['r_cert_hi']):.3f}]}}"
                f" & ${float(r['cov_ratio_iqm']):.2f}$ & {evs} & {tvs}"
                f" & ${100 * float(r['exposure_iqm']):.2f}$ & ${100 * float(r['switches_iqm']):.1f}$ \\\\")
        head = ("\\resizebox{\\linewidth}{!}{%\n\\begin{tabular}{@{}lcccccc@{}}\n\\toprule\n"
                "Method & $r_{\\mathrm{cert}}$ & cov.\\ ratio & eval viol. [\\%] & train viol."
                " & exposure [\\%] & reassign. [\\%]\\\\\n\\midrule\n")
        tail = "\\bottomrule\n\\end{tabular}}\n"
        (MS / "tab_main.tex").write_text(head + "\n".join(lines) + "\n" + tail)
        o = byname.get("ours")
        if o:
            m["OursCov"] = f(o["r_cert_iqm"], 3)
            m["OursCovLo"] = f(o["r_cert_lo"], 3)
            m["OursCovHi"] = f(o["r_cert_hi"], 3)
            m["OursRatio"] = f(o["cov_ratio_iqm"], 2)
            m["OursTrainSteps"] = sci(o["train_agent_steps"])
            m["OursTrainCP"] = sci(o["train_viol_cp95"])
            m["NSeeds"] = o["n_train_seeds"]
        for k, nm in (("lagrangian", "Lag"), ("blind", "Blind"), ("mask", "Mask"),
                      ("heuristic+proj", "Heur"), ("lagrangian+proj", "LagProj"),
                      ("blind+proj", "BlindProj"), ("fixed_margin", "Fixed"),
                      ("heuristic_none", "HeurNone"), ("gnp", "Gnp"), ("ours_nodev", "NoDev"),
                      ("mask+proj", "MaskProj")):
            if k in byname:
                r = byname[k]
                m[f"{nm}Cov"] = f(r["r_cert_iqm"], 3)
                m[f"{nm}Viol"] = f(100 * float(r["viol_iqm"]), 2)
                m[f"{nm}Ratio"] = f(r["cov_ratio_iqm"], 2)
                m[f"{nm}ViolMean"] = f(100 * int(r["eval_violations"]) / int(r["eval_agent_steps"]), 2)
                m[f"{nm}Switch"] = f(100 * float(r["switches_iqm"]), 1)
                if r["train_violations"] not in ("", None):
                    m[f"{nm}TrainViol"] = f"{int(r['train_violations']):,}".replace(",", "{,}")
                    m[f"{nm}TrainRate"] = f(100 * int(r["train_violations"]) / int(r["train_agent_steps"]), 2)
    with (MS / "numbers.tex").open("w") as fh:
        fh.write("% generated by paperIII/experiments/make_numbers.py -- do not edit\n")
        for k, v in sorted(m.items()):
            fh.write(f"\\newcommand{{\\n{k}}}{{{v}}}\n")
    print(f"{len(m)} macros written")


if __name__ == "__main__":
    main()
