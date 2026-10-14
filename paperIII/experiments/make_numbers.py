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
    extended(m)
    with (MS / "numbers.tex").open("w") as fh:
        fh.write("% generated by paperIII/experiments/make_numbers.py -- do not edit\n")
        for k, v in sorted(m.items()):
            fh.write(f"\\newcommand{{\\n{k}}}{{{v}}}\n")
    print(f"{len(m)} macros written")


# ---------------------------------------------------------------------------
# R-experiments (runbook R1, R2, R5, R6, R9): macros, tables and figure data
# ---------------------------------------------------------------------------
def tex_int(x):
    return f"{int(x):,}".replace(",", "{,}")


def cell(r):
    return (f"${float(r['r_cert_iqm']):.3f}$ {{\\scriptsize[{float(r['r_cert_lo']):.3f}, "
            f"{float(r['r_cert_hi']):.3f}]}}")


def viol_cell(r, key="eval"):
    k, n = r.get(f"{key}_violations", ""), r.get(f"{key}_agent_steps", "")
    if k in ("", None):
        return "--"
    if int(k) == 0:
        return rf"$0$ ($\le{sci(r[f'{key}_viol_cp95'])}$)"
    if key == "eval":
        return f"${100 * int(k) / int(n):.3f}$"
    return rf"${tex_int(k)}$"


R2_NAMES = {
    "mappo_lag": r"MAPPO-Lagrangian, cost critic, limit $0.005$",
    "mappo_lag0": r"MAPPO-Lagrangian, cost critic, limit $0$",
    "pid_lag": r"PID-Lagrangian PPO",
    "qmix": r"QMIX (certificate observed)",
    "qmix_mask": r"QMIX with eligibility masks",
    "cbba": r"CBBA, feasibility in the bundle",
}


def r2_table(m, byname):
    lines = []
    for k in ("mappo_lag", "mappo_lag0", "pid_lag", "qmix", "qmix_mask", "cbba"):
        for name, label in ((k, R2_NAMES[k]), (k + "+proj", r"\quad + projection at deployment")):
            r = byname.get(name)
            if r is None:
                continue
            lines.append(f"{label} & {cell(r)} & ${float(r['cov_ratio_iqm']):.2f}$ & "
                         f"{viol_cell(r)} & {viol_cell(r, 'train') if '+proj' not in name else '--'} \\\\")
    for name, label in (("ours", r"\textbf{Projection (SE) + PPO (ours)}"),
                        ("heuristic+proj", r"Keep-or-nearest + projection")):
        r = byname.get(name)
        if r is not None:
            lines.insert(0 if name == "ours" else 1,
                         f"{label} & {cell(r)} & ${float(r['cov_ratio_iqm']):.2f}$ & {viol_cell(r)} & "
                         f"{viol_cell(r, 'train') if name == 'ours' else '--'} \\\\")
    if len(lines) <= 2:
        return
    lines.insert(2, r"\midrule")
    head = ("\\begin{tabular}{@{}lcccc@{}}\n\\toprule\nMethod & $r_{\\mathrm{cert}}$ & cov.\\ ratio & "
            "eval viol. [\\%] & train viol.\\\\\n\\midrule\n")
    (MS / "tab_r2.tex").write_text(head + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")
    for k, nm in (("mappo_lag", "MLag"), ("mappo_lag0", "MLagZero"), ("pid_lag", "PidLag"),
                  ("qmix", "Qmix"), ("qmix_mask", "QmixMask"), ("cbba", "Cbba")):
        r = byname.get(k)
        if r is None:
            continue
        m[f"{nm}Cov"] = f(r["r_cert_iqm"], 3)
        m[f"{nm}CovLo"] = f(r["r_cert_lo"], 3)
        m[f"{nm}CovHi"] = f(r["r_cert_hi"], 3)
        m[f"{nm}Ratio"] = f(r["cov_ratio_iqm"], 2)
        m[f"{nm}EvalViolPct"] = f(100 * int(r["eval_violations"]) / int(r["eval_agent_steps"]), 3)
        m[f"{nm}EvalViol"] = tex_int(r["eval_violations"])
        if r["train_violations"] not in ("", None):
            m[f"{nm}TrainViol"] = tex_int(r["train_violations"])
            m[f"{nm}TrainRate"] = f(100 * int(r["train_violations"]) / int(r["train_agent_steps"]), 2)
        rp = byname.get(k + "+proj")
        if rp is not None:
            m[f"{nm}ProjCov"] = f(rp["r_cert_iqm"], 3)
            m[f"{nm}ProjRatio"] = f(rp["cov_ratio_iqm"], 2)
        m[f"{nm}Seeds"] = r["n_train_seeds"]


def r1_scale(m):
    """R1: certified coverage and coverage ratio against fleet size."""
    sizes = [(12, rd("e6_main.csv"))] + [(n, rd(f"e6_main_e5_marl_N{n}.csv")) for n in (24, 48, 96)]
    sizes = [(n, rows) for n, rows in sizes if rows]
    if len(sizes) < 2:
        return
    fig = MS / "figdata"
    fig.mkdir(exist_ok=True)
    meths = ("ours", "mask", "mask+proj", "lagrangian", "lagrangian+proj", "blind", "blind+proj",
             "heuristic+proj", "cbba")
    for meth in meths:
        pts = []
        for n, rows in sizes:
            r = {x["method"]: x for x in rows}.get(meth)
            if r:
                pts.append((n, r["r_cert_iqm"], r["r_cert_lo"], r["r_cert_hi"], r["cov_ratio_iqm"]))
        with (fig / f"scale_{meth.replace('+', '_')}.dat").open("w") as fh:
            fh.write("N rcert lo hi ratio\n")
            for p in pts:
                fh.write(" ".join(str(x) for x in p) + "\n")
    lines, ratios, zero_ok, beats = [], [], True, []
    names = {12: "Twelve", 24: "TwentyFour", 48: "FortyEight", 96: "NinetySix"}
    for n, rows in sizes:
        b = {x["method"]: x for x in rows}
        o, h = b.get("ours"), b.get("heuristic+proj")
        if o is None:
            continue
        ratios.append(float(o["cov_ratio_iqm"]))
        for k in ("ours", "ours_nodev", "mask"):
            if k in b and b[k]["train_violations"] not in ("", None) and int(b[k]["train_violations"]) > 0:
                zero_ok = False
        lag = b.get("lagrangian")
        seeds = o["n_train_seeds"]
        cb = b.get("cbba")
        cells = [str(n), seeds, cell(o), f"${float(o['cov_ratio_iqm']):.2f}$",
                 cell(b["mask+proj"]) if "mask+proj" in b else "--",
                 cell(h) if h else "--", cell(cb) if cb else "--",
                 viol_cell(lag, "train") if lag else "--"]
        lines.append(" & ".join(cells) + r" \\")
        nm = names[n]
        m[f"Scale{nm}Ours"] = f(o["r_cert_iqm"], 3)
        m[f"Scale{nm}Ratio"] = f(o["cov_ratio_iqm"], 2)
        if cb:
            m[f"Scale{nm}Cbba"] = f(cb["r_cert_iqm"], 3)
            m[f"Scale{nm}CbbaLo"] = f(cb["r_cert_lo"], 3)
        m[f"Scale{nm}OursHi"] = f(o["r_cert_hi"], 3)
        m[f"Scale{nm}OursLo"] = f(o["r_cert_lo"], 3)
        if "mask+proj" in b:
            m[f"Scale{nm}MaskProj"] = f(b["mask+proj"]["r_cert_iqm"], 3)
        if lag:
            m[f"Scale{nm}Lag"] = f(lag["r_cert_iqm"], 3)
        if h:
            m[f"Scale{nm}Heur"] = f(h["r_cert_iqm"], 3)
            sep = float(o["r_cert_lo"]) > float(h["r_cert_hi"])
            beats.append((n, sep))
        if lag and lag["train_violations"] not in ("", None):
            m[f"Scale{nm}LagTrain"] = tex_int(lag["train_violations"])
    head = ("\\begin{tabular}{@{}rrcccccc@{}}\n\\toprule\n$N$ & seeds & ours $r_{\\mathrm{cert}}$ & "
            "cov.\\ ratio & masking + proj. & keep-or-nearest + proj. & CBBA & Lagrangian train viol.\\\\\n"
            "\\midrule\n")
    (MS / "tab_scale.tex").write_text(head + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")
    m["ScaleMinRatio"] = f(min(ratios), 2)
    m["ScaleZeroTrain"] = "yes" if zero_ok else "no"
    m["ScaleSizes"] = ", ".join(str(n) for n, _ in sizes)
    m["ScaleBeatsHeur"] = (", ".join(str(n) for n, s in beats if s) or "none")
    m["ScaleTiesHeur"] = (", ".join(str(n) for n, s in beats if not s) or "none")


def r5_consensus(m):
    rows = rd("r5_consensus.csv")
    if not rows:
        return
    m["CnsInst"] = rows[0]["instances"]
    m["CnsHonestViol"] = str(sum(int(r["violations_by_honest"]) for r in rows))
    m["CnsLiarViol"] = tex_int(sum(int(r["violations_by_liars"]) for r in rows))
    fwd = [r for r in rows if r["relay"] == "forward"]
    m["CnsFwdMaxExcess"] = str(max(int(r["max_abs_dev_d"]) - int(r["f"]) for r in fwd))
    robust = [r for r in rows if float(r["frac_2f1_robust"]) == 1.0 and r["f"] != "0"]
    m["CnsRobustAgree"] = f(min(float(r["frac_agreed"]) for r in robust), 2) if robust else "--"
    eq = {(r["mesh"], r["f"], r["relay"]): r for r in rows if r["strategy"] == "equivocate"}
    for mesh, nm in (("2", "Ring"), ("4", "Four"), ("6", "Six"), ("complete", "Full")):
        for fv in ("1", "2"):
            r = eq.get((mesh, fv, "forward"))
            if r:
                m[f"CnsEq{nm}F{'One' if fv == '1' else 'Two'}"] = f(100 * float(r["frac_agreed"]), 0)
        rr = [r for r in rows if r["mesh"] == mesh]
        m[f"CnsRob{nm}"] = f(float(rr[0]["robustness_median"]), 0)
    drop = [r for r in rows if r["relay"] == "drop"]
    worst = max(drop, key=lambda r: int(r["max_abs_dev_d"]) - int(r["f"]))
    m["CnsDropExcess"] = str(int(worst["max_abs_dev_d"]) - int(worst["f"]))
    m["CnsDropDev"] = worst["max_abs_dev_d"]
    m["CnsDropF"] = worst["f"]
    m["CnsDropMesh"] = worst["mesh"]
    m["CnsDropLost"] = f(100 * float(worst["frac_reports_lost"]), 0)
    ag = [r for r in rows if r.get("max_abs_dev_d_agreed") not in ("", None)]
    if ag:
        m["CnsAgreedMaxExcess"] = str(max(int(r["max_abs_dev_d_agreed"]) - int(r["f"]) for r in ag))
    full = [r for r in rows if r["mesh"] == "complete" and r["rounds_max"] not in ("", None)]
    m["CnsFullRoundsMax"] = str(max(int(r["rounds_max"]) for r in full)) if full else "--"
    # table
    lines = []
    for r in rows:
        if r["f"] == "0" or r["relay"] != "forward" and r["strategy"] != "deflate":
            continue
        lines.append(" & ".join([r["mesh"].replace("complete", "full"), r["f"], r["strategy"], r["relay"],
                                 f"{float(r['frac_2f1_robust']):.2f}", f"{100 * float(r['frac_agreed']):.0f}",
                                 str(r["rounds_median"]).replace(".0", ""), r["max_abs_dev_d"],
                                 r["violations_by_honest"]]) + r" \\")
    head = ("\\begin{tabular}{@{}lrllrrrrr@{}}\n\\toprule\nmesh & $f$ & liar & relay & $(2f{+}1)$-rob. & "
            "agreed [\\%] & rounds & $\\max|\\Delta d|$ & honest viol.\\\\\n\\midrule\n")
    (MS / "tab_r5.tex").write_text(head + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")


def r6_vector(m):
    rows = rd("r6_vector.csv")
    if not rows:
        return
    r = pick(rows, N="12", sigma="0.5")
    m["VecLostTwelve"] = f(r["coverage_lost_mean"], 2)
    m["VecLossFracTwelve"] = f(100 * float(r["frac_instances_with_loss"]), 0)
    m["VecNestedTwelve"] = f(100 * float(r["frac_exact_graph_nested"]), 0)
    m["VecGapTwelve"] = f(r["worst_gap_b2_mean"], 2)
    r1 = pick(rows, N="20", sigma="1.0")
    m["VecLostTwenty"] = f(r1["coverage_lost_mean"], 2)
    m["VecLostTwentyMax"] = r1["coverage_lost_max"]
    m["VecNestedTwenty"] = f(100 * float(r1["frac_exact_graph_nested"]), 0)
    m["VecGapTwenty"] = f(r1["worst_gap_b2_mean"], 2)
    m["VecInst"] = rows[0]["instances"]
    b8, b20 = pick(rows, N="8", sigma="0.5"), pick(rows, N="20", sigma="0.5")
    m["VecBruteEight"] = f(b8["brute_ms_b3_median"], 1)
    m["VecBruteTwenty"] = f(b20["brute_ms_b3_median"], 0)
    m["VecClosed"] = f(max(float(x["closed_form_ms_median"]) for x in rows), 2)
    m["VecSigZeroLost"] = f(max(float(x["coverage_lost_mean"]) for x in rows if float(x["sigma"]) == 0), 1)


def r9_sensitivity(m):
    """R9 table: each knob value on 3 seeds; the default comes from the E5 runs on seeds 0-2."""
    import glob as _g
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from e6_aggregate import iqm, strat_boot
    rows = []

    def agg(paths, method_name, base_dir):
        rs, tv, ts = [], 0, 0
        for p in paths:
            with open(p) as fh:
                rs += [r for r in csv.DictReader(fh) if r["method"] == method_name]
            tp = p.replace("_eval.csv", "_train.csv")
            with open(tp) as fh:
                last = list(csv.DictReader(fh))[-1]
            tv += int(last["cum_violations"])
            ts += int(last["env_steps"]) * int(last.get("N") or 12)
        if not rs:
            return None
        g = {}
        for r in rs:
            g.setdefault(r["train_seed"], []).append(float(r["r_cert"]))
        import numpy as _np
        g = {k: _np.asarray(v) for k, v in g.items()}
        lo, hi = strat_boot(g)
        return {"rcert": iqm([float(r["r_cert"]) for r in rs]), "lo": lo, "hi": hi,
                "ratio": iqm([float(r["cov_ratio"]) for r in rs]), "train_viol": tv, "train_steps": ts,
                "seeds": len(g)}
    E5 = OUT / "e5_marl"
    R9 = OUT / "r9"
    if not R9.exists():
        return
    spec = [
        ("$\\lambda_{\\mathrm{dev}}$", "ours", [("0", E5, "ours_nodev"), ("0.02", R9, "ours-ldev0.02"),
                                                ("0.05", E5, "ours"), ("0.1", R9, "ours-ldev0.1"),
                                                ("0.2", R9, "ours-ldev0.2")]),
        ("keep-logit prior", "ours", [("0", R9, "ours-kb0"), ("1", R9, "ours-kb1"), ("3", E5, "ours")]),
        ("cost limit", "lagrangian", [("0", R9, "lagrangian-cl0"), ("0.001", R9, "lagrangian-cl0.001"),
                                      ("0.005", E5, "lagrangian"), ("0.02", R9, "lagrangian-cl0.02")]),
        ("dual step", "lagrangian", [("0.1", R9, "lagrangian-ds0.1"), ("1", E5, "lagrangian"),
                                     ("5", R9, "lagrangian-ds5")]),
        ("threat rates (ours)", "ours", [("$\\times0.5$", R9, "ours-thr0.5"), ("$\\times1$", E5, "ours"),
                                         ("$\\times2$", R9, "ours-thr2")]),
        ("threat rates (Lagrangian)", "lagrangian", [("$\\times0.5$", R9, "lagrangian-thr0.5"),
                                                     ("$\\times1$", E5, "lagrangian"),
                                                     ("$\\times2$", R9, "lagrangian-thr2")]),
    ]
    lines = []
    for knob, base, vals in spec:
        first = True
        for v, d, name in vals:
            paths = sorted(p for s in (0, 1, 2) for p in _g.glob(str(d / f"{name}_s{s}_eval.csv")))
            a = agg(paths, name, d) if paths else None
            if a is None:
                cells = ["not run"] * 3
            else:
                cells = [f"${a['rcert']:.3f}$ {{\\scriptsize[{a['lo']:.3f}, {a['hi']:.3f}]}}",
                         f"${a['ratio']:.2f}$", rf"${tex_int(a['train_viol'])}$"]
                rows.append((knob, v, a))
            lines.append(" & ".join([knob if first else "", v] + cells) + r" \\")
            first = False
        lines.append(r"\midrule")
    if lines and lines[-1] == r"\midrule":
        lines.pop()
    head = ("\\begin{tabular}{@{}llccr@{}}\n\\toprule\nknob & value & $r_{\\mathrm{cert}}$ (IQM, 95\\% CI) & "
            "cov.\\ ratio & train viol.\\\\\n\\midrule\n")
    (MS / "tab_r9.tex").write_text(head + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")
    ours = [a for k, v, a in rows if k.startswith("$\\lambda") or k.startswith("keep") or k == "threat rates (ours)"]
    if ours:
        m["SensOursMaxTrainViol"] = tex_int(max(a["train_viol"] for a in ours))
        m["SensOursMinRatio"] = f(min(a["ratio"] for a in ours), 2)
    lag = [a for k, v, a in rows if "Lagrangian" in k or k in ("cost limit", "dual step")]
    if lag:
        m["SensLagMinTrainViol"] = tex_int(min(a["train_viol"] for a in lag))


def extended(m):
    mn = rd("e6_main.csv")
    if mn:
        r2_table(m, {r["method"]: r for r in mn})
        pr = [float(r["cov_ratio_iqm"]) for r in mn if r["method"].endswith("+proj")]
        m["ProjMinRatio"] = f(min(pr), 2)
    r1_scale(m)
    r5_consensus(m)
    r6_vector(m)
    try:
        r9_sensitivity(m)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    main()
