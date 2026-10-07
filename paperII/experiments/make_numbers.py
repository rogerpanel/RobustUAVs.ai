#!/usr/bin/env python3
"""Write manuscript/numbers.tex (one macro per quoted number), the pgfplots
data files in manuscript/figdata/, and the generated transfer-table body
manuscript/tab_transfer_body.tex.  Never edit those files by hand."""
from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parent / "results"
M = HERE.parent / "manuscript"
FD = M / "figdata"
FD.mkdir(parents=True, exist_ok=True)


def rd(name):
    return list(csv.DictReader(open(R / name)))


def pct(x):
    return f"{100 * float(x):.0f}\\,\\%"


def f2(x):
    return f"{float(x):.2f}"


def sci(x, d=1):
    m, e = f"{float(x):.{d}e}".split("e")
    return f"{m}\\times10^{{{int(e)}}}"


def main():
    H = {r["key"]: r["value"] for r in rd("hypotheses.csv")}
    rel = {r["field"]: r for r in rd("reliability_C1_C2.csv")}
    N = {}
    # corpus sizes
    N["nCorpus"] = H["n_total"]; N["nTierA"] = H["n_tierA"]; N["nTierB"] = H["n_tierB"]
    N["nObj"] = H["n_objectives"]; N["nObjPrimary"] = H["n_obj_primary"]; N["nClasses"] = H["n_classes"]
    # H1
    N["hOnePercInAB"] = pct(H["h1_AB_perc_in"]); N["hOnePercInA"] = pct(H["h1_A_perc_in"])
    N["hOneCtrlTrAB"] = pct(H["h1_AB_ctrl_tr"]); N["hOneCtrlTrA"] = pct(H["h1_A_ctrl_tr"])
    N["hOneCtrlInAB"] = pct(H["h1_AB_ctrl_in"]); N["hOneAllInAB"] = pct(H["h1_AB_all_in"])
    N["hOneNPercAB"] = H["h1_AB_n_perc"]; N["hOneNCtrlAB"] = H["h1_AB_n_ctrl"]
    N["hOneNPercA"] = H["h1_A_n_perc"]; N["hOneNCtrlA"] = H["h1_A_n_ctrl"]
    N["hOnePercInCount"] = H["h1_AB_perc_in_count"]
    # H2
    N["hTwoNLifted"] = H["h2_n_lifted"]
    for s in ("U", "S", "SE", "SEC"):
        N["hTwoShare" + s.replace("SEC", "Sec").replace("SE", "Se")] = pct(H[f"h2_share_{s}"])
    N["hTwoAccounted"] = pct(H["h2_share_accounted"]); N["hTwoConf"] = pct(H["h2_share_confidence"])
    N["hTwoAccEarly"] = pct(H["h2_accounted_2017"]); N["hTwoAccLate"] = pct(H["h2_accounted_2022"])
    N["hTwoNEarly"] = H["h2_n_2017"]; N["hTwoNLate"] = H["h2_n_2022"]
    N["hTwoDynN"] = H["h2_L_dyn_n"]; N["hTwoDynAcc"] = pct(H["h2_L_dyn_acc"])
    N["hTwoGenN"] = H["h2_L_gen_n"]; N["hTwoGenAcc"] = pct(H["h2_L_gen_acc"])
    N["hTwoConcN"] = H["h2_L_conc_n"]; N["hTwoConcAcc"] = pct(H["h2_L_conc_acc"])
    N["hTwoMonN"] = H["h2_L_mon_n"]; N["hTwoMonAcc"] = pct(H["h2_L_mon_acc"])
    N["hTwoSupN"] = H["h2_L_sup_n"]; N["hTwoRateN"] = H["h2_L_rate_n"]
    # H3
    N["hThreeNP"] = H["h3_n_P"]; N["hThreePercP"] = H["h3_perception_n_P"]
    N["hThreePercShareP"] = pct(H["h3_perception_share_P"]); N["hThreeCtrlP"] = H["h3_control_n_P"]
    N["hThreeEstShareP"] = pct(H["h3_estimation_share_P"]); N["hThreeNRate"] = H["h3_n_rate"]
    N["hThreePercPA"] = H["h3_perc_P_tierA"]
    # transfer table
    N["ttCells"] = H["tt_cells"]; N["ttD"] = H["tt_D"]; N["ttL"] = H["tt_L"]; N["ttX"] = H["tt_X"]
    N["ttTOneReach"] = H["tt_T1_reachable"]; N["ttTOneMinK"] = H["tt_T1_min_k"]
    N["ttTFourD"] = H["tt_T4_D"]; N["ttTSixD"] = H["tt_T6_D"]
    N["hFourReach"] = H["h4_T4_reachable"]; N["hFourRtaDeficit"] = H["h4_rta_deficit"]
    # reliability
    for key, nm in (("scope", "Scope"), ("modality", "Mod"), ("scope_x_modality", "Type"),
                    ("assumption", "Assm"), ("perturbation", "Pert"), ("tier", "Tier"),
                    ("component", "Comp"), ("evidence", "Evid")):
        r = rel[key]
        N["rel" + nm + "Agree"] = pct(r["agree"])
        N["rel" + nm + "Kappa"] = f2(r["kappa"]); N["rel" + nm + "Alpha"] = f2(r["alpha"])
        N["rel" + nm + "AcOne"] = f2(r["ac1"]); N["rel" + nm + "Pabak"] = f2(r["pabak"])
        N["rel" + nm + "AlphaLo"] = f2(r["alpha_lo"]); N["rel" + nm + "AlphaHi"] = f2(r["alpha_hi"])
    N["relJaccard"] = f2(rel["lifts:jaccard_mean"]["agree"])
    dis = rd("disagreements_C1_C2.csv")
    N["relNDisagree"] = len(dis); N["relNDisPapers"] = len({d["gid"] for d in dis})
    adj = list(csv.DictReader(open(HERE.parent / "corpus" / "adjudication.csv")))
    N["adjN"] = len(adj); N["adjPapers"] = len({a["gid"] for a in adj})
    # rate arithmetic
    rr = rd("rate_requirements.csv")
    p30 = [r for r in rr if float(r["lambda_per_h"]) == 1e-4 and r["f_hz"] == "30"][0]
    N["rateDecisionsPerH"] = f"{int(float(p30['decisions_per_h'])):,}".replace(",", "{,}")
    N["ratePstarThirty"] = sci(p30["p_star_k1"]); N["ratePstarKThree"] = sci(p30["p_star_k3_indep"])
    p9 = [r for r in rr if float(r["lambda_per_h"]) == 1e-9 and r["f_hz"] == "30"][0]
    N["ratePstarNine"] = sci(p9["p_star_k1"])
    corr = {float(r["rho"]): r for r in rd("rate_correlation.csv")}
    gains = [float(r["gain_vs_k1"]) for k, r in corr.items() if 0.1 <= k <= 0.99]
    N["rateGainIndep"] = sci(corr[0.0]["gain_vs_k1"], 0)
    N["rateGainMin"] = f"{min(gains):.2f}"; N["rateGainMax"] = f"{max(gains):.0f}"
    N["rateGainBound"] = "6.75"
    eco = {(float(r["lambda_per_h"]), r["f_hz"]): r for r in rd("test_economy.csv")}
    N["ecoHoursFour"] = f"{float(eco[(1e-4, '30')]['flight_hours_direct']):,.0f}".replace(",", "{,}")
    N["ecoFramesFour"] = sci(eco[(1e-4, '30')]["frames_needed"])
    N["ecoYearsSeven"] = f"{float(eco[(1e-7, '30')]['years_at_24_7']):,.0f}".replace(",", "{,}")
    N["ecoYearsNine"] = sci(eco[(1e-9, '30')]["years_at_24_7"])
    # evidence pack
    cont = rd("evidence_contingency.csv")
    ekf = [c for c in cont if c["mapping"] == "empirical_ekf"]
    sup = [c for c in cont if c["mapping"] == "empirical_campaign_sup"]
    kin = [c for c in cont if c["mapping"] == "kinematic_v15"]
    N["epTubeEkf"] = f2(ekf[0]["tube_m"]); N["epTubeSup"] = f2(sup[0]["tube_m"]); N["epTubeKin"] = f"{float(kin[0]['tube_m']):.1f}"
    N["epDeltaPos"] = f2(ekf[0]["delta_pos_m"]); N["epGammaEkf"] = f"{float(ekf[0]['gamma_m_s']):.3f}"
    N["epGammaSup"] = f"{float(sup[0]['gamma_m_s']):.3f}"
    obl = rd("evidence_obligations.csv")
    N["epNObl"] = len(obl); N["epNOpen"] = sum(o["status"] in ("open", "assumed") for o in obl)

    with open(M / "numbers.tex", "w") as fh:
        fh.write("% Generated by paperII/experiments/make_numbers.py -- do not edit by hand.\n")
        for k, v in N.items():
            fh.write(f"\\newcommand{{\\{k}}}{{{v}}}\n")

    # ---------------- figure data ----------------
    dist = rd("distribution.csv")
    for tier in ("A", "AB"):
        with open(FD / f"dist_{tier}.dat", "w") as fh:
            fh.write("component in tr op popd\n")
            for comp in ("perception", "estimation", "control", "planning", "end2end"):
                v = {d["scope"]: d["n"] for d in dist if d["tier"] == tier and d["component"] == comp}
                fh.write(f"{comp} {v['in']} {v['tr']} {v['op']} {v['popd']}\n")
    with open(FD / "rate_req.dat", "w") as fh:
        lams = [1e-3, 1e-4, 1e-5, 1e-7, 1e-9]
        fh.write("f " + " ".join(f"l{i}" for i in range(len(lams))) + "\n")
        for f in (1, 5, 10, 30, 60, 100):
            fh.write(f"{f} " + " ".join(str(lam / (3600 * f)) for lam in lams) + "\n")
    with open(FD / "rate_corr.dat", "w") as fh:
        fh.write("rho gain\n")
        for k, r in sorted(corr.items()):
            if k > 0:
                fh.write(f"{k} {r['gain_vs_k1']}\n")
    with open(FD / "assumption_period.dat", "w") as fh:
        fh.write("period U S SE SEC\n")
        for r in rd("assumption_by_period.csv"):
            n = int(r["n"])
            fh.write(f"{r['period']} " + " ".join(f"{100*int(r[s])/n:.1f}" for s in ("U", "S", "SE", "SEC")) + "\n")
    with open(FD / "reliability.dat", "w") as fh:
        fh.write("x field kappa alpha ac1 alo ahi\n")
        for i, key in enumerate(["tier", "component", "scope", "modality", "perturbation", "assumption", "evidence"]):
            r = rel[key]
            fh.write(f"{i} {key} {r['kappa']} {r['alpha']} {r['ac1']} {r['alpha_lo']} {r['alpha_hi']}\n")

    # ---------------- transfer table body ----------------
    tt = rd("transfer_table.csv")
    cs = {r["class"]: r for r in rd("class_states.csv")}
    types = ["T1", "T2", "T3", "T4", "T5", "T6"]
    lines = []
    short = {"L_alpha": "$\\alpha$", "L_dyn": "dyn", "L_hor": "hor", "L_op": "op", "L_sup": "sup",
             "L_rate": "rate", "L_mon": "mon"}
    for cls in dict.fromkeys(r["class"] for r in tt):
        c = cs[cls]
        typ = f"\\Q{{{c['scope']}}}{{{c['modality']}}}"
        cells = []
        for t in types:
            r = [x for x in tt if x["class"] == cls and x["type"] == t][0]
            if r["verdict"] == "D":
                cells.append("\\cellD")
            elif r["verdict"] == "X":
                cells.append("\\cellX")
            else:
                lf = ",".join(short.get(l, l) for l in r["lifts"].split("+") if l) or "thr"
                cells.append(f"\\cellL{{{r['k']}}}{{{lf}}}")
        ev = f"{100*float(c['evidenced_share']):.0f}"
        lines.append(f"{cls} & {c['n']} & {typ} & " + " & ".join(cells) + f" & {ev} \\\\")
    (M / "tab_transfer_body.tex").write_text("% generated by make_numbers.py\n" + "\n".join(lines) + "\n")
    objs = list(csv.DictReader(open(HERE.parent / "corpus" / "objectives.csv")))
    ol = []
    for o in objs:
        tgt = sci(o["target_per_h"], 0) if o["target_per_h"] else "--"
        tgt = f"${tgt}$" if o["target_per_h"] else tgt
        chk = "" if o["source_check"] == "primary" else "$^\\dagger$"
        ol.append(f"{o['oid']} & {o['doc'].replace('&', 'and')}{chk} & {o['statement']} & \\Q{{{o['scope']}}}{{{o['modality']}}} & {o['hazard']} & {tgt} \\\\")
    (M / "tab_objectives_body.tex").write_text("% generated by make_numbers.py\n" + "\n".join(ol) + "\n")
    rl = []
    for key, lab in (("tier", "tier"), ("component", "component"), ("scope", "scope"), ("modality", "modality"),
                     ("scope_x_modality", "type (scope$\\times$modality)"), ("perturbation", "perturbation"),
                     ("assumption", "assumption status"), ("evidence", "evidence class")):
        r = rel[key]
        rl.append(f"{lab} & {100*float(r['agree']):.0f} & {float(r['kappa']):.2f} & {float(r['alpha']):.2f} [{float(r['alpha_lo']):.2f}, {float(r['alpha_hi']):.2f}] & {float(r['ac1']):.2f} & {float(r['pabak']):.2f} \\\\")
    (M / "tab_reliability_body.tex").write_text("% generated by make_numbers.py\n" + "\n".join(rl) + "\n")
    print(f"numbers.tex: {len(N)} macros; figdata and tab_transfer_body.tex written")


if __name__ == "__main__":
    main()
