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


def full_study(N):
    """Macros for the full study (amendments 1-5). Prefix fs. Shares are weighted
    estimates with 95 % intervals; see corpus_estimates.py and hypotheses_full.py."""
    import re
    C = HERE.parent / "corpus"
    st = {r["metric"]: r["value"] for r in rd("screening_status.csv")}
    pr = {r["stage"]: r["n"] for r in csv.DictReader(open(C / "prisma_counts.csv"))}
    big = lambda x: f"{int(round(float(x))):,}".replace(",", "{,}")  # noqa: E731
    N["fsIdentified"] = big(pr["identified"]); N["fsDuplicates"] = big(pr["duplicates"])
    N["fsCandidates"] = big(int(pr["identified"]) - int(pr["duplicates"]))
    N["fsVenueRecords"] = big(pr["identified_venues"])
    log = (C / "logs" / "s1_rev1_2026-10-15.txt").read_text()
    for lab, key in (("tier A", "TierA"), ("all", "All"), ("held-out \\(even gid\\)", "Held")):
        m = re.search(r"\[sensitivity\] rev1 " + lab + r"\s+(\d+)/(\d+)", log)
        N["fsRecall" + key] = pct(int(m.group(1)) / int(m.group(2)))
        N["fsRecall" + key + "N"] = f"{m.group(1)}/{m.group(2)}"
    ss = {(r["search"], r["scope"]): r for r in rd("search_sensitivity.csv")}
    N["fsRecallRevZero"] = pct(ss[("rev0", "all")]["recall"])
    N["fsScreened"] = big(st["screened"]); N["fsCoreN"] = big(st["core_screened"])
    N["fsCoreInc"] = big(st["core_included"]); N["fsSampleN"] = big(st["sample_screened"])
    N["fsSampleInc"] = st["sample_included"]; N["fsRemSize"] = big(st["remainder_size"])
    lo, hi = st["sample_rate_ci95"].split("-")
    N["fsSampleRate"] = pct(st["sample_include_rate"]); N["fsSampleRateLo"] = pct(lo); N["fsSampleRateHi"] = pct(hi)
    lo, hi = st["remainder_includes_ci95"].split("-")
    N["fsRemInc"] = big(st["remainder_includes_est"]); N["fsRemIncLo"] = big(lo); N["fsRemIncHi"] = big(hi)
    N["fsKappaScreen"] = f2(st["kappa_L1_L2"])
    N["fsHeldScreened"] = st["heldout_pilot_screened"]; N["fsHeldIncluded"] = st["heldout_pilot_included"]
    N["fsHeldLost"] = int(st["heldout_pilot_screened"]) - int(st["heldout_pilot_included"])
    samp = list(csv.DictReader(open(C / "coding_sample.csv")))
    ft = {r["cid"]: r for r in csv.DictReader(open(C / "fulltext_status.csv"))} if (C / "fulltext_status.csv").exists() else {}
    codes = list(csv.DictReader(open(C / "codes_full_final.csv")))
    stratum = {r["cid"]: r["stratum"] for r in samp}
    N["fsCoded"] = len(codes)
    N["fsCodedCore"] = sum(stratum[r["cid"]] == "core" for r in codes)
    N["fsCodedRem"] = N["fsCoded"] - N["fsCodedCore"]
    for sname, key in (("core", "Core"), ("remainder", "Rem")):
        N[f"fs{key}Tried"] = sum(1 for r in ft.values() if r["stratum"] == sname)
        N[f"fs{key}NotRetrieved"] = sum(1 for r in ft.values() if r["stratum"] == sname and r["status"] != "retrieved")
    N["fsEligible"] = sum(r["eligible"] == "1" for r in codes)
    cs = {r["metric"]: r["value"] for r in rd("coding_status.csv")}
    N["fsAgreeElig"] = cs["agree_eligible"].replace("/", "/")
    ad = {r["metric"]: r["value"] for r in rd("adjudication_status.csv")}
    N["fsAdjPapers"] = ad["papers_to_adjudicate"]; N["fsAdjElig"] = ad["elig_disagree"]
    N["fsAdjEligToZero"] = ad.get("elig_adj_0", "0"); N["fsAdjEligToOne"] = ad.get("elig_adj_1", "0")
    N["fsAdjFields"] = ad["field_disagree"]; N["fsAdjChoseCOne"] = ad.get("field_choice_C1", "0")
    N["fsAdjChoseCTwo"] = ad.get("field_choice_C2", "0"); N["fsAdjChoseThird"] = ad.get("field_choice_third", "0")
    rel = {r["field"]: r for r in rd("reliability_full_C1_full_C2.csv")}
    for key, nm in (("eligible", "Elig"), ("class", "Class"), ("tier", "Tier"), ("scope_x_modality", "Type"),
                    ("assumption", "Assm"), ("evidence", "Evid"), ("perturbation", "Pert")):
        N["fsRel" + nm + "Kappa"] = f2(rel[key]["kappa"]); N["fsRel" + nm + "Alpha"] = f2(rel[key]["alpha"])
        N["fsRel" + nm + "AcOne"] = f2(rel[key]["ac1"]); N["fsRel" + nm + "Agree"] = pct(rel[key]["agree"])
        N["fsRel" + nm + "AlphaLo"] = f2(rel[key]["alpha_lo"]); N["fsRel" + nm + "AlphaHi"] = f2(rel[key]["alpha_hi"])
    N["fsRelJaccard"] = f2(rel["lifts:jaccard_mean"]["agree"])
    N["fsRelN"] = rel["class"]["n"]
    est = {(r["field"], r["value"]): r for r in rd("corpus_estimates.csv")}
    def E(field, value, key):
        r = est[(field, value)]
        N[key] = pct(r["share"]); N[key + "Lo"] = pct(r["share_lo"]); N[key + "Hi"] = pct(r["share_hi"])
        N[key + "Papers"] = big(r["papers"]); N[key + "Core"] = pct(r["share_core"]); N[key + "Rem"] = pct(r["share_remainder"])
    e = est[("eligible", "1")]
    N["fsField"] = big(e["papers"]); N["fsFieldLo"] = big(e["papers_lo"]); N["fsFieldHi"] = big(e["papers_hi"])
    N["fsEligShare"] = pct(e["share"]); N["fsEligCore"] = pct(e["share_core"]); N["fsEligRem"] = pct(e["share_remainder"])
    for (f, v), k in {("class", "CP"): "fsCP", ("class", "RTA"): "fsRTA", ("class", "BP"): "fsBP",
                      ("class", "SMT"): "fsSMT", ("class", "PIL"): "fsPIL", ("class", "PACB"): "fsPACB", ("class", "NEW:* (all new classes)"): "fsNew",
                      ("evidence", "proof"): "fsProof", ("evidence", "simulated"): "fsSim",
                      ("evidence", "measured"): "fsMeas", ("scope", "in"): "fsScIn", ("scope", "tr"): "fsScTr",
                      ("scope", "op"): "fsScOp", ("scope", "pop"): "fsScPop", ("modality", "A"): "fsModA",
                      ("modality", "P"): "fsModP", ("modality", "E"): "fsModE", ("tier", "A"): "fsTierA",
                      ("component", "perception"): "fsPerc", ("component", "control"): "fsCtrl",
                      ("component", "estimation"): "fsEst"}.items():
        E(f, v, k)
    tp = rd("type_plane_full.csv")
    N["fsTypeCells"] = len(tp)
    pilot_cells = {(r["scope"] if r["scope"] != "pop" else "pop", r["modality"])
                   for r in csv.DictReader(open(C / "codes_ADJ.csv"))}
    N["fsTypeNewCells"] = sum((r["scope"], r["modality"]) not in pilot_cells for r in tp)
    hyp = {}
    for tag in ("", "_C1", "_C2"):
        for r in rd(f"hypotheses_full{tag}.csv"):
            hyp[(tag, r["key"])] = r
    def Hm(key, mac, both=False):
        r = hyp[("", key)]
        N[mac] = pct(r["estimate"]); N[mac + "Lo"] = pct(r["lo"]); N[mac + "Hi"] = pct(r["hi"]); N[mac + "N"] = r["n_den"]
        N[mac + "CA"] = pct(hyp[("_C1", key)]["estimate"]); N[mac + "CB"] = pct(hyp[("_C2", key)]["estimate"])
    for key, mac in (("h1_AB_perc_in", "fsHOnePercIn"), ("h1_AB_ctrl_in", "fsHOneCtrlIn"),
                     ("h1_AB_ctrl_tr", "fsHOneCtrlTr"), ("h1_AB_all_in", "fsHOneAllIn"),
                     ("h1_A_perc_in", "fsHOnePercInA"), ("h1_A_ctrl_tr", "fsHOneCtrlTrA"),
                     ("h2_share_lifted", "fsHTwoLifted"), ("h2_share_U", "fsHTwoU"), ("h2_share_S", "fsHTwoS"),
                     ("h2_share_SE", "fsHTwoSE"), ("h2_share_SEC", "fsHTwoSEC"), ("h2_share_accounted", "fsHTwoAcc"),
                     ("h2_accounted_2017", "fsHTwoAccEarly"), ("h2_accounted_2022", "fsHTwoAccLate"),
                     ("h2_L_dyn_use", "fsHTwoDynUse"), ("h2_L_dyn_acc", "fsHTwoDynAcc"),
                     ("h2_L_conc_use", "fsHTwoConcUse"), ("h2_L_conc_acc", "fsHTwoConcAcc"),
                     ("h2_L_mon_use", "fsHTwoMonUse"), ("h2_L_mon_acc", "fsHTwoMonAcc"),
                     ("h2_L_sup_use", "fsHTwoSupUse"), ("h2_L_gen_use", "fsHTwoGenUse"),
                     ("h3_perception_share_P", "fsHThreePercP"), ("h3_control_share_P", "fsHThreeCtrlP"),
                     ("h3_estimation_share_P", "fsHThreeEstP"), ("h3_planning_share_P", "fsHThreePlanP"),
                     ("h3_rate_use", "fsHThreeRate"), ("h4_share_RTA", "fsHFourRta"),
                     ("h4_RTA_accounted", "fsHFourRtaAcc"), ("h4_RTA_L_mon", "fsHFourRtaMon")):
        Hm(key, mac)
    N["fsHTwoStated"] = pct(1 - float(hyp[("", "h2_share_U")]["estimate"]))
    ttf = rd("transfer_table_full.csv")
    from collections import Counter
    V = Counter(r["verdict"] for r in ttf)
    N["fsTtRows"] = len({r["class"] for r in ttf}); N["fsTtCells"] = len(ttf)
    N["fsTtD"], N["fsTtL"], N["fsTtX"] = V["D"], V["L"], V["X"]
    N["fsTtTOneReach"] = len({r["class"] for r in ttf if r["type"] == "T1" and r["verdict"] != "X"})
    N["fsTtTOneD"] = sum(r["type"] == "T1" and r["verdict"] == "D" for r in ttf)
    N["fsTtTFourReach"] = len({r["class"] for r in ttf if r["type"] == "T4" and r["verdict"] != "X"})
    N["fsTtTFourD"] = sum(r["type"] == "T4" and r["verdict"] == "D" for r in ttf)
    N["fsTtTSixD"] = sum(r["type"] == "T6" and r["verdict"] == "D" for r in ttf)
    N["fsTtAllX"] = sum(all(r["verdict"] == "X" for r in ttf if r["class"] == c) for c in {r["class"] for r in ttf})
    N["fsClassesAdded"] = sum(r["source"] == "full study (added)" for r in rd("class_states_full.csv"))
    nm = list(csv.DictReader(open(C / "new_class_map.csv")))
    N["fsNewCoded"] = len(nm)
    for k in ("GEN", "LUC", "ALG", "GLOB", "IMPL"):
        N["fsNewN" + k.capitalize()] = sum(r["class"] == k for r in nm)
    chk = rd("class_state_check.csv")
    have = [r for r in chk if r["full_state"]]
    N["fsStateSame"] = sum(r["same"] == "1" for r in have); N["fsStateChecked"] = len(have)
    cp = next(r for r in chk if r["class"] == "CP")
    N["fsCpPopd"] = big(cp["full_state_weights"].split(";")[0].split()[-1])


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

    full_study(N)
    with open(M / "numbers.tex", "w") as fh:
        fh.write("% Generated by paperII/experiments/make_numbers.py -- do not edit by hand.\n")
        for k, v in N.items():
            fh.write(f"\\newcommand{{\\{k}}}{{{v}}}\n")

    # ---------------- figure data ----------------
    dist = rd("distribution_full.csv")
    for tier in ("A", "AB"):
        with open(FD / f"dist_{tier}.dat", "w") as fh:
            fh.write("component in tr op popd\n")
            for comp in ("perception", "estimation", "control", "planning", "end2end"):
                v = {d["scope"]: d["papers"] for d in dist if d["tier"] == tier and d["component"] == comp}
                fh.write(f"{comp} {v['in']} {v['tr']} {v['op']} {v['pop']}\n")
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
    # full study (amendment 5): pilot classes with pilot states, added classes, field variants
    tt = rd("transfer_table_full.csv")
    cs = {r["class"]: r for r in rd("class_states_full.csv")}
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
        ev = c["evidenced_share_full"]
        ev = f"{100*float(ev):.0f}" if ev != "" else "--"
        name = cls.replace(" (field)", "$^{\\mathrm{f}}$")
        if c["source"] == "full study (added)":
            name += "$^{+}$"
        n = c["est_papers_full"] if int(c["n_coded_full"]) else "0"
        if c["source"] == "full study (added)" and cls == next(k for k, v in cs.items() if v["source"] == "full study (added)"):
            lines.append("\\midrule")
        lines.append(f"{name} & {n} & {typ} & " + " & ".join(cells) + f" & {ev} \\\\")
    (M / "tab_transfer_body.tex").write_text("% generated by make_numbers.py\n" + "\n".join(lines) + "\n")
    objs = list(csv.DictReader(open(HERE.parent / "corpus" / "objectives.csv")))
    ol = []
    for o in objs:
        tgt = sci(o["target_per_h"], 0) if o["target_per_h"] else "--"
        tgt = f"${tgt}$" if o["target_per_h"] else tgt
        chk = "" if o["source_check"] == "primary" else "$^\\dagger$"
        ol.append(f"{o['oid']} & {o['doc'].replace('&', 'and')}{chk} & {o['statement']} & \\Q{{{o['scope']}}}{{{o['modality']}}} & {o['hazard']} & {tgt} \\\\")
    (M / "tab_objectives_body.tex").write_text("% generated by make_numbers.py\n" + "\n".join(ol) + "\n")
    relf = {r["field"]: r for r in rd("reliability_full_C1_full_C2.csv")}
    rl = []
    for key, lab in (("eligible", "full-text eligibility"), ("class", "class"), ("tier", "tier"),
                     ("component", "component"), ("scope", "scope"), ("modality", "modality"),
                     ("scope_x_modality", "type (scope$\\times$modality)"), ("perturbation", "perturbation"),
                     ("assumption", "assumption status"), ("evidence", "evidence class")):
        r = relf[key]
        rl.append(f"{lab} & {r['n']} & {100*float(r['agree']):.0f} & {float(r['kappa']):.2f} & {float(r['alpha']):.2f} [{float(r['alpha_lo']):.2f}, {float(r['alpha_hi']):.2f}] & {float(r['ac1']):.2f} & {float(r['pabak']):.2f} \\\\")
    (M / "tab_reliability_body.tex").write_text("% generated by make_numbers.py\n" + "\n".join(rl) + "\n")
    print(f"numbers.tex: {len(N)} macros; figdata and tab_transfer_body.tex written")


if __name__ == "__main__":
    main()
