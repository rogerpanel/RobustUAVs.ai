#!/usr/bin/env python3
"""Turn paperIV/results/*.csv into manuscript/numbers.tex (one macro per quoted
number), manuscript/tab_*_body.tex and manuscript/figdata/*.dat.
Never type a number into the manuscript; re-run this script instead."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

import depbounds as db
from constants import AMP, GAMMA_SUP, H_HOPS, SLACK_S, L_LOC

ROOT = Path(__file__).resolve().parents[1]
RES, MS = ROOT / "results", ROOT / "manuscript"
FIG = MS / "figdata"; FIG.mkdir(parents=True, exist_ok=True)
rd = lambda n: list(csv.DictReader(open(RES / n)))
M = {}
_W = {"0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five",
      "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine"}


def mac(name, val):
    """LaTeX macro names cannot contain digits: spell them out."""
    for k, v in (("20", "Twenty"), ("10", "Ten")):
        name = name.replace(k, v)
    M["".join(_W.get(c, c) for c in name)] = val


fmt = lambda x, d=2: f"{x:.{d}f}"
pct = lambda x, d=0: f"{100 * x:.{d}f}\\%"
th_ = lambda n: f"{int(n):,}".replace(",", "{,}")
FAM = ["step", "ramp", "fault_mimic", "gnss_mimic", "weather_mimic"]
FN = {"step": "Step", "ramp": "Ramp", "fault_mimic": "FaultMimic", "gnss_mimic": "GnssMimic",
      "weather_mimic": "WeatherMimic"}
STK = ["D1", "D2", "D3", "D4", "ALL"]
DET = ["D1", "D2", "D3", "D4"]
hum = lambda f: f.replace("_", " ")

# ------------------------------------------------------------- parent + run
mac("nParentSlack", fmt(SLACK_S, 2)); mac("nParentHops", th_(15392))
mac("nParentGamma", fmt(GAMMA_SUP, 3)); mac("nParentL", fmt(L_LOC, 3))
net_tube = lambda t: AMP * GAMMA_SUP * H_HOPS * min(t, SLACK_S)
mac("nNetTubeQuarter", fmt(net_tube(0.25), 2)); mac("nAmp", fmt(AMP, 2))
# benchmark totals come from the parent's provenance ledger (repository results/)
mac("nEventsTotal", th_(431773)); mac("nEventsReal", th_(200610))
meta = json.loads((RES / "run_meta.json").read_text())
mac("nCalMissions", th_(meta["N_cal"])); mac("nEvalMissions", th_(meta["N_eval"]))
mac("nJointMissions", th_(5 * meta["N_cal"]))
mac("nWallMin", str(int(round(meta["wall_s"] / 60)) + 2))   # + E2y ablation (~1-2 min)
mac("nCemGens", str(meta["cem_gens"])); mac("nCemK", str(meta["cem_K"]))
_e2y = RES / "mission_count_e2y.txt"
n_e2y = sum(int(x) for x in _e2y.read_text().split()) if _e2y.exists() else 0
mac("nMissionsTotal", th_(meta["n_missions"] + n_e2y))

# ------------------------------------------------------------- E1
g = {(r["wind"], r["detector"]): float(r["fpr"]) for r in rd("e1_fpr_by_wind.csv")}
mac("nFprModMin", pct(min(g[("moderate", d)] for d in DET), 1))
mac("nFprModMax", pct(max(g[("moderate", d)] for d in DET), 1))
mac("nFprSevereDThree", pct(g[("severe", "D3")], 1))
mac("nFprSevereOtherMax", pct(max(g[("severe", d)] for d in ("D1", "D2", "D4")), 1))
mac("nFprAnchor", pct(g[("moderate", "anchor")], 2))
mac("nBenignNoAlarm", pct(1 - g[("moderate", "ALL")]))
src = {(r["source"], r["detector"]): float(r["fpr"]) for r in rd("e1_fpr_by_source.csv")}
mac("nFprGnssOnlyMax", pct(max(src[("gnss_only", d)] for d in DET), 1))
mac("nFprWindFaultMax", pct(max(src[(s, d)] for s in ("wind_only", "fault_only") for d in DET), 1))
roc = rd("e1_roc.csv")
for att in ("step", "ramp"):
    for d in DET:
        rows = sorted([(float(r["fpr"]), float(r["tpr"])) for r in roc if r["attack"] == att and r["detector"] == d])
        with open(FIG / f"roc_{att}_{d}.dat", "w") as fh:
            fh.write("fpr tpr\n" + "".join(f"{a} {b}\n" for a, b in rows))
        mac(f"nTpr{att.capitalize()}{d}", pct(min(rows, key=lambda x: abs(x[0] - 0.05))[1]))

# ------------------------------------------------------------- E2 / E2x
att = rd("e2_attackers.csv"); X = rd("e2x_cross.csv")
mac("nPooledAttackers", str(len(att)))
cell = {}
own_fail = 0
for s in STK:
    for f in FAM:
        rs = [r for r in X if r["stack"] == s and r["family"] == f]
        ev = max(float(r["evasion_rate"]) for r in rs)
        ok = [r for r in rs if float(r["evasion_rate"]) >= 0.05 and int(r["n_stealthy"]) >= 10]
        dv = max((float(r["attack_only_dev_max"]) for r in ok), default=0.0)
        own = [r for r in rs if r["origin_stack"] == s and float(r["origin_fpr"]) == 0.05]
        own_ev = max((float(r["evasion_rate"]) for r in own), default=0.0)
        if own_ev < 0.05 <= ev:
            own_fail += 1
        cell[(s, f)] = (ev, dv, own_ev)
        mac(f"nEv{s}{FN[f]}", pct(ev)); mac(f"nDev{s}{FN[f]}", fmt(dv, 1))
mac("nOwnOptFail", str(own_fail)); mac("nCells", str(len(STK) * len(FAM)))
evmin = min(cell[(s, f)][0] for s in DET for f in FAM)
mac("nCrossEvMin", pct(evmin))
mac("nCrossEvMinAll", pct(min(cell[("ALL", f)][0] for f in FAM)))
for s in STK:
    best = max(FAM, key=lambda f: cell[(s, f)][1])
    mac(f"nBest{s}Fam", hum(best)); mac(f"nBest{s}Dev", fmt(cell[(s, best)][1], 1))
devs_single = [cell[(s, f)][1] for s in DET for f in FAM]
mac("nDevSingleMin", fmt(min(devs_single), 1)); mac("nDevSingleMax", fmt(max(devs_single), 1))
devs_all = [cell[("ALL", f)][1] for f in FAM]
mac("nDevAllMin", fmt(min(devs_all), 1)); mac("nDevAllMax", fmt(max(devs_all), 1))
ks_e = [float(r["ks_to_benign"]) for r in X if float(r["evasion_rate"]) >= 0.5]
ks_c = [float(r["ks_to_benign"]) for r in X if float(r["evasion_rate"]) < 0.05]
mac("nKsStealthyMed", fmt(float(np.median(ks_e)), 2) if ks_e else "--")
mac("nKsCaughtMed", fmt(float(np.median(ks_c)), 2) if ks_c else "--")
shade = lambda ev: f"\\cellcolor{{cRed!{int(round(70 * ev))}}}"
NAME = {"D1": "D1 signature", "D2": "D2 $\\chi^2$ gate", "D3": "D3 SAVIOR-style", "D4": "D4 IMU--GNSS inv.",
        "ALL": "\\textsc{All} (stack)"}
(MS / "tab_disguise_body.tex").write_text("\n".join(
    NAME[s] + " & " + " & ".join(f"{shade(cell[(s, f)][0])}{100 * cell[(s, f)][0]:.0f} / {cell[(s, f)][1]:.1f}"
                                 for f in FAM) + " \\\\" for s in STK) + "\n")

# ------------------------------------------------------------- E2y (anchor gate removed)
Y = rd("e2y_no_anchor_gate.csv")
ycell = {}
for s_ in STK:
    for f in FAM:
        rs = [r for r in Y if r["stack"] == s_ and r["family"] == f]
        ev = max(float(r["evasion_rate"]) for r in rs)
        ok = [float(r["attack_only_dev_max"]) for r in rs if float(r["evasion_rate"]) >= 0.05 and int(r["n_stealthy"]) >= 10]
        ycell[(s_, f)] = (ev, max(ok, default=0.0))
        mac(f"nNg{s_}{FN[f]}", fmt(ycell[(s_, f)][1], 1))
mac("nNgEvMin", pct(min(v[0] for v in ycell.values())))
for s_ in STK:
    mac(f"nNgCap{s_}", fmt(max(ycell[(s_, f)][1] for f in FAM), 1))
    mac(f"nNgArg{s_}", hum(max(FAM, key=lambda f: ycell[(s_, f)][1])))
mac("nNgMax", fmt(max(v[1] for v in ycell.values()), 1))
mac("nGatedCap", fmt(max(cell[(s_, f)][1] for s_ in STK for f in FAM), 1))
# unfiltered maxima (any evading mission, however rare) -- disclosed next to the filtered table
def unf(rows, s_, f):
    return max((float(r["attack_only_dev_max"]) for r in rows if r["stack"] == s_ and r["family"] == f
                and int(r["n_stealthy"]) > 0), default=0.0)
gu = max(((unf(X, s_, f), s_, f) for s_ in STK for f in FAM))
mac("nGatedUnfMax", fmt(gu[0], 1)); mac("nGatedUnfFam", hum(gu[2]))
mac("nGatedUnfStacks", ", ".join(sorted({s_ for s_ in STK for f in FAM if abs(unf(X, s_, f) - gu[0]) < 0.05})))
mac("nNgStepUnfMax", fmt(max(unf(Y, s_, "step") for s_ in STK), 1))
mac("nNgDFourGnssUnf", fmt(unf(Y, "D4", "gnss_mimic"), 1))
mac("nNgDTwoUnfMax", fmt(max(unf(Y, "D2", f) for f in FAM), 1))
(MS / "tab_disguise_nogate_body.tex").write_text("\n".join(
    NAME[s_] + " & " + " & ".join(f"{shade(min(ycell[(s_, f)][1] / 75.0, 1.0))}{ycell[(s_, f)][1]:.1f}" for f in FAM)
    + " \\\\" for s_ in STK) + "\n")

# ------------------------------------------------------------- E2b / E2c (pooled)
def sweep(name, out):
    rs = rd(name); by = defaultdict(dict)
    for r in rs:
        ta, f = float(r["T_anchor_s"]), r["family"]
        if float(r["evasion_rate"]) > 0:
            by[ta][f] = max(by[ta].get(f, 0.0), float(r["attack_only_dev_max"]))
    with open(FIG / out, "w") as fh:
        fh.write("Ta " + " ".join(FAM) + " maxall\n")
        for ta in sorted(by):
            v = [by[ta].get(f, 0.0) for f in FAM]
            fh.write(f"{ta} " + " ".join(f"{x:.3f}" for x in v) + f" {max(v):.3f}\n")
    return {ta: (max(by[ta].values()), max(by[ta], key=by[ta].get)) for ta in by}


cl = sweep("e2b_anchor_sweep.csv", "anchor_sweep.dat")
op = sweep("e2c_terminal_window.csv", "anchor_sweep_open.dat")
for ta in (5.0, 10.0, 20.0):
    mac(f"nAnchorMax{int(ta)}", fmt(cl[ta][0], 1)); mac(f"nAnchorArg{int(ta)}", hum(cl[ta][1]))
    mac(f"nOpenMax{int(ta)}", fmt(op[ta][0], 1)); mac(f"nOpenArg{int(ta)}", hum(op[ta][1]))
mac("nAnchorMultTwenty", fmt(cl[20.0][0] / cl[5.0][0], 1))
mac("nOpenMultTwenty", fmt(op[20.0][0] / op[5.0][0], 0))
mac("nOpenRatioTwenty", fmt(op[20.0][0] / cl[20.0][0], 0))

# ------------------------------------------------------------- E3
ms = {r["marginal"]: r for r in rd("e3_marginal_summary.csv")}
mac("nSubaddSources", pct(float(ms["subadditivity_frac"]["median"]), 2))
for k, nm in (("env_upper", "EnvUp"), ("env_lower", "EnvLo"), ("env_mix", "EnvMix"), ("gnss", "Gnss"),
              ("fault", "Fault"), ("joint", "Joint")):
    mac(f"nMarg{nm}Pnf", fmt(float(ms[k]["p95"]), 2)); mac(f"nMarg{nm}Max", fmt(float(ms[k]["max"]), 2))
gap = rd("e3_gap.csv")
with open(FIG / "gap.dat", "w") as fh:
    fh.write("s union ra indep indepmix comon sumsame joint\n")
    for r in gap:
        v = [max(float(r[k]), 1e-5) for k in ("union", "ra", "indep", "indep_mix", "comon", "sum_same", "joint_sim")]
        fh.write(r["s_m"] + " " + " ".join(f"{x:.6g}" for x in v) + "\n")
sel = {float(r["s_m"]): r for r in gap}
mac("nUnionRaDtwoMaxErr", f"{max(abs(float(r['union_d2']) - float(r['ra_d2_raw'])) for r in gap if float(r['union_d2']) > 0.002):.3f}")
S0 = 4.0
r = sel[S0]
F = lambda k: float(r[k])
mac("nGapS", fmt(S0, 0))
for k, nm in (("union", "Union"), ("ra", "Ra"), ("indep", "Indep"), ("indep_mix", "IndepMix"),
              ("sum_same", "SumSame"), ("joint_sim", "Joint")):
    mac(f"nGap{nm}", f"{F(k):.4f}")
mac("nGapJointK", str(int(r["joint_k"])))
mac("nRaGain", pct(1 - F("ra") / F("union")))
mac("nDepRatio", fmt(F("ra") / max(F("indep"), 1e-9), 0))
mac("nEnvRatio", fmt(F("indep") / max(F("indep_mix"), 1e-9), 1))
mac("nTimeRatio", fmt(F("sum_same") / max(F("joint_sim"), 1e-9), 1))
mac("nNatRatio", fmt(F("indep_mix") / max(F("sum_same"), 1e-9), 2))

# ------------------------------------------------------------- E4
da = rd("e4_delta_adv.csv")
dadv = {float(r["fpr"]): float(r["delta_adv_cal_m"]) for r in da}
for r in da:
    tag = {0.01: "One", 0.05: "Five", 0.1: "Ten"}[float(r["fpr"])]
    mac(f"nDadv{tag}", fmt(float(r["delta_adv_cal_m"]), 2)); mac(f"nDadvArg{tag}", hum(r["argmax_family"]))
snd = rd("e4_soundness.csv")
mac("nSoundPoints", str(len(snd)))
mac("nSoundViol", str(sum(int(r["violation"]) for r in snd)))
mac("nSoundViolIndep", str(sum(int(r["violation_indep"]) for r in snd)))
mac("nSoundNontrivial", str(sum(float(r["pbar_ra"]) < 1 for r in snd)))
mac("nSoundWithFail", str(sum(int(r["k_fail_undetected"]) > 0 and float(r["pbar_ra"]) < 1 for r in snd)))
cells = {(r["family"], r["fpr"], r["wind"]): r for r in snd}
mac("nSupChecks", str(len(cells)))
mac("nSupExceed", str(sum(1 - int(r["adv_sup_holds"]) for r in cells.values())))
mac("nZeroUndet", str(sum(int(r["n_undetected"]) == 0 for r in cells.values())))
hmax = max(cells.values(), key=lambda r: float(r["heldout_adv_max"]))
mac("nHeldoutAdvMax", fmt(float(hmax["heldout_adv_max"]), 2)); mac("nHeldoutAdvFam", hum(hmax["family"]))
mac("nHeldoutAdvFpr", pct(float(hmax["fpr"])))
mac("nHeldoutAdvRatio", fmt(float(hmax["heldout_adv_max"]) / dadv[float(hmax["fpr"])], 2))
mac("nUndetectedTotal", th_(sum(int(r["n_undetected"]) for r in cells.values())))
mac("nSuperposMin", pct(min(float(r["superposition_frac"]) for r in snd), 1))
mac("nSuperposExcessMax", fmt(max(float(r["superposition_max_excess_m"]) for r in snd), 2))
sat = rd("e4_saturation_control.csv")
mac("nSatUnsatMin", pct(min(float(r["superposition_frac_unsaturated"]) for r in sat), 2))
mac("nSatUnsatExcess", f"{max(float(r['max_excess_unsaturated_m']) for r in sat):.1e}")
nt = [r for r in snd if float(r["pbar_ra"]) < 1]
ratio = max((float(r["rate_fail_undetected"]) / float(r["pbar_ra"]) for r in nt if float(r["pbar_ra"]) > 0), default=0)
mac("nMaxRateRatio", fmt(ratio, 2))
lines = []
for fpr in ("0.01", "0.05", "0.1"):
    for tn in ("0.0", "0.25"):
        for m in ("5.0", "10.0", "20.0"):
            rs = [r for r in snd if r["fpr"] == fpr and r["theta_net"] == tn and r["m"] == m]
            p = float(rs[0]["pbar_ra"]); pu = float(rs[0]["pbar_union"]); pi = float(rs[0]["p_indep"])
            rate = max(float(r["rate_fail_undetected"]) for r in rs)
            mcr = [float(r["mcr_undetected"]) for r in rs if r["mcr_undetected"] not in ("nan", "")]
            lines.append(f"{100 * float(fpr):.0f}\\% & {float(tn):.2f} & {float(m):.0f} & {pu:.3f} & {p:.3f} & {pi:.4f} & "
                         f"{rate:.4f} & {min(mcr):.3f} & {sum(int(r['violation']) for r in rs)} & "
                         f"{sum(int(r['violation_indep']) for r in rs)} \\\\")
(MS / "tab_soundness_body.tex").write_text("\n".join(lines) + "\n")

Z = np.load(RES / "e3_marginals.npz"); Xs = [Z["gnss"], Z["fault"], Z["env"]]
with open(FIG / "floor_curve.dat", "w") as fh:
    fh.write("m ra union indep ranet\n")
    for m in np.arange(4.0, 25.01, 0.5):
        s0, s1 = m - dadv[0.05], m - dadv[0.05] - net_tube(0.25)
        f = lambda s, meth: (0.0 if s <= 0 else 1 - {"ra": lambda: db.ra_bound(Xs, s, N=1000),
                                                    "union": lambda: db.union_bound(Xs, s),
                                                    "indep": lambda: db.indep_tail(Xs, s, n=100_000)}[meth]())
        fh.write(f"{m:.1f} {f(s0, 'ra'):.5f} {f(s0, 'union'):.5f} {f(s0, 'indep'):.5f} {f(s1, 'ra'):.5f}\n")
with open(FIG / "floor_points.dat", "w") as fh:
    fh.write("m obs\n")
    for m in ("5.0", "10.0", "20.0"):
        rs = [r for r in snd if r["fpr"] == "0.05" and r["m"] == m and r["theta_net"] == "0.0"]
        fh.write(f"{float(m)} {1 - max(float(r['rate_fail_undetected']) for r in rs):.4f}\n")
cur = [list(map(float, l.split())) for l in open(FIG / "floor_curve.dat").read().splitlines()[1:]]
first = lambda c, lv: next((row[0] for row in cur if row[c] >= lv), float("nan"))
mac("nMNinety", fmt(first(1, 0.9), 1)); mac("nMNinetyNine", fmt(first(1, 0.99), 1))
mac("nMNinetyNet", fmt(first(4, 0.9), 1)); mac("nMNinetyIndep", fmt(first(3, 0.9), 1))

# ------------------------------------------------------------- E5
neg = rd("e5_negative_controls.csv")
YES = {True: "\\textbf{yes}", False: "no"}
CT = {"no_anchor_C2_violated": "C2$'$: no anchor", "env_outside_pbox_severe": "C4: severe wind"}
FS = {"ramp": "ramp", "fault_mimic": "fault", "weather_mimic": "weather"}
(MS / "tab_negative_body.tex").write_text("\n".join(
    f"{CT[r['control']]} & {FS[r['family']]} & {float(r['m']):.0f} & {th_(int(r['n_undetected']))} & "
    f"{int(r['k_fail_undetected'])} & {float(r['pbar_ra']):.3f} & " + YES[int(r["violation"]) == 1] +
    f" & {float(r['max_stealthy_dev']):.1f} \\\\" for r in neg) + "\n")
for ctl, tag in (("no_anchor", "Ctwo"), ("env_outside", "Cfour")):
    rs = [r for r in neg if r["control"].startswith(ctl)]
    mac(f"nNeg{tag}Viol", str(sum(int(r["violation"]) for r in rs)))
    mac(f"nNeg{tag}Rows", str(len(rs)))
    mac(f"nNeg{tag}MaxDev", fmt(max(float(r["max_stealthy_dev"]) for r in rs), 1))
    vf = sorted({FS[r["family"]] for r in rs if int(r["violation"])})
    mac(f"nNeg{tag}ViolFam", " and ".join(vf) if vf else "none")

# ------------------------------------------------------------- R1 (stronger attackers, scaled E4)
if (RES / "r1_e4_soundness.csv").exists():
    r1a = rd("r1_attackers.csv") + rd("r1_attackers_tail.csv")
    mac("nROneAttackers", str(len(r1a)))
    mac("nROnePerOpt", str(sum(r["optimiser"] == "cma" for r in r1a)))
    b1 = meta["r1"]["budget"]
    mac("nROneCmaGens", str(b1["gens"])); mac("nROneCmaPop", str(b1["pop"]))
    mac("nROneK", str(b1["k"])); mac("nROneTrials", str(b1["trials"]))
    mac("nROneEvalN", th_(meta["r1"]["n_eval"])); mac("nROneHeldSeeds", str(meta["r1"]["held_seeds"]))
    rda = {float(r["fpr"]): r for r in rd("r1_delta_adv.csv")}
    for f_, tag in ((0.01, "One"), (0.05, "Five"), (0.1, "Ten")):
        mac(f"nROneDadv{tag}", fmt(float(rda[f_]["delta_pooled_m"]), 2))
        mac(f"nROneDadvRatio{tag}", fmt(float(rda[f_]["ratio"]), 2))
    r5_ = rda[0.05]
    mac("nROneDadvArg", f"{hum(r5_['argmax_family'])} (tail-objective TPE)")
    for k_, nm in (("sup_cem", "Cem"), ("sup_cma", "Cma"), ("sup_tpe", "Tpe"), ("sup_tpe_tail", "TpeTail")):
        mac(f"nROneSup{nm}", fmt(float(r5_[k_]), 2))
    s1 = rd("r1_e4_soundness.csv")
    mac("nROneTests", th_(len(s1))); mac("nROneViol", str(sum(int(r["violation"]) for r in s1)))
    c1 = {(r["family"], r["fpr"], r["heldout_seed"], r["wind"]): r for r in s1}
    mac("nROneCells", str(len(c1))); mac("nROneUndet", th_(sum(int(r["n_undetected"]) for r in c1.values())))
    mac("nROneSupExceed", str(sum(1 - int(r["adv_sup_holds"]) for r in c1.values())))
    hm = max(c1.values(), key=lambda r: float(r["heldout_adv_max"]))
    mac("nROneAdvMax", fmt(float(hm["heldout_adv_max"]), 2)); mac("nROneAdvMaxFam", hum(hm["family"]))
    mac("nROneSuperposMin", pct(min(float(r["superposition_frac"]) for r in s1), 1))
    vv = [r for r in s1 if r["violation"] == "1"]
    mac("nROneViolM", fmt(min(float(r["m"]) for r in vv), 0) if vv else "--")
    mac("nROneViolPbarMax", fmt(max(float(r["pbar_ra"]) for r in vv), 3) if vv else "--")
    dg = rd("r1_violation_diagnosis.csv") if (RES / "r1_violation_diagnosis.csv").exists() else []
    if dg:
        mac("nDiagMissions", str(len(dg)))
        mac("nDiagBenignMin", fmt(min(float(r["maxdev_benign_only_m"]) for r in dg), 1))
        mac("nDiagBenignMax", fmt(max(float(r["maxdev_benign_only_m"]) for r in dg), 1))
        mac("nDiagAttackMax", fmt(max(float(r["maxdev_attack_only_m"]) for r in dg), 1))
        mac("nDiagAllSat", "all" if all(r["saturated_benign_only"] == "1" for r in dg) else "not all")

# ------------------------------------------------------------- R5 (measured GNSS envelope)
if (RES / "r5_floor_sensitivity.csv").exists():
    ev = rd("r5_gnss_envelope.csv")
    mac("nRFiveSamples", ev[0]["n_samples"]); mac("nRFiveEnvMax", fmt(max(float(r["err_envelope_m"]) for r in ev), 1))
    mac("nRFiveEnvTen", fmt(next(float(r["err_envelope_m"]) for r in ev if float(r["staleness_s"]) == 10.0), 1))
    fs = {(r["fpr"], r["m"], r["theta_net"]): r for r in rd("r5_floor_sensitivity.csv")}
    r_ = fs[("0.05", "10.0", "0.0")]
    for k_, nm in (("floor_sim", "Sim"), ("floor_measured_env", "Meas"), ("floor_measured_45s", "Long"),
                   ("floor_cp_sim", "CpSim"), ("floor_cp_measured_env", "CpMeas"), ("floor_cp_measured_45s", "CpLong")):
        mac(f"nRFiveFloor{nm}", fmt(float(r_[k_]), 2))
    mac("nRFivePnnSim", fmt(float(r_["gnss_p99_sim"]), 1)); mac("nRFivePnnMeas", fmt(float(r_["gnss_p99_measured_env"]), 1))
    mac("nRFiveFloorCpTwenty", fmt(float(fs[("0.05", "20.0", "0.0")]["floor_cp_sim"]), 3))

# ------------------------------------------------------------- R8 (analytic stealth budget)
if (RES / "r8_analytic_bound.csv").exists():
    r8 = rd("r8_analytic_bound.csv")
    pick = lambda ta, pre, f_="0.05": next(r for r in r8 if r["T_anchor_s"] in (ta, ta + ".0") and r["fpr"] == f_
                                          and r["constraints"].startswith(pre))
    mac("nREightDOneFive", fmt(float(pick("5", "anchor gate + D1 (")["delta_lp_m"]), 0))
    sat5 = [float(r["delta_lp_m"]) for r in r8 if r["T_anchor_s"] in ("5", "5.0")
            and r["constraints"].startswith("anchor gate + D1 + D_sat")]
    mac("nREightSatFive", fmt(max(sat5), 1))
    mac("nREightSatRatio", fmt(max(sat5) / float(rda[0.05]["delta_pooled_m"]), 1))
    mac("nREightSatRatioAdv", fmt(max(sat5) / max(float(r["heldout_adv_max"]) for r in s1), 1))
    gate5 = pick("5", "anchor gate only")["delta_lp_m"]
    mac("nREightGateOnly", "unbounded" if gate5 == "inf" else fmt(float(gate5), 1))
    for ta in ("10", "20"):
        try:
            v = pick(ta, "anchor gate + D1 + D_sat")["delta_lp_m"]
            mac(f"nREightSat{ta}", v if v in ("inf", "unsolved") else fmt(float(v), 1))
        except StopIteration:
            pass

# ------------------------------------------------------------- E4 revised (fresh seeds)
if (RES / "e4r_fpr.csv").exists():
    fr = {r["fpr_target"]: r for r in rd("e4r_fpr.csv")}
    f5 = fr["0.05"]
    mac("nRevSatAlone", pct(float(f5["sat_alarm_alone"]), 1))
    mac("nRevFprStack", pct(float(f5["fpr_stack_anchor"]), 1)); mac("nRevFprSat", pct(float(f5["fpr_with_sat_alarm"]), 1))
    from depbounds import G_GRID
    mac("nRevGrid", str(G_GRID))
if (RES / "e4r_soundness.csv").exists():
    er = rd("e4r_soundness.csv")
    mac("nRevAttackers", str(len(rd("e4r_heldout.csv"))))
    for var, tag in (("r1_pooled", "Emp"), ("lp_revised", "Lp")):
        rv = [r for r in er if r["delta_variant"] == var]
        cl = {(r["optimiser"], r["family"], r["fpr"], r["heldout_seed"], r["wind"]): r for r in rv}
        mac(f"nRev{tag}Tests", th_(len(rv))); mac(f"nRev{tag}Viol", str(sum(int(r["violation"]) for r in rv)))
        mac(f"nRev{tag}Within", str(sum(int(r["adv_within_delta"]) for r in cl.values())))
        mac(f"nRev{tag}Cells", str(len(cl)))
        mac(f"nRev{tag}Exceed", str(sum(1 - int(r["adv_within_delta"]) for r in cl.values())))
        inf_ = [r for r in rv if float(r["bound"]) < 1]
        mac(f"nRev{tag}Informative", str(len(inf_)))
        mac(f"nRev{tag}FailInf", str(sum(int(r["k_fail_undetected"]) > 0 for r in inf_)))
        mx = max(rv, key=lambda r: float(r["rate_fail_undetected"]) / max(float(r["bound"]), 1e-12)
                 if float(r["bound"]) < 1 else -1)
        mac(f"nRev{tag}MaxRatio", fmt(float(mx["rate_fail_undetected"]) / max(float(mx["bound"]), 1e-12), 2)
            if float(mx["bound"]) < 1 else "--")
        for m_ in ("10.0", "20.0"):
            b_ = [float(r["f_cert"]) for r in rv if r["m"] == m_ and r["theta_net"] == "0.0" and r["fpr"] == "0.05"]
            mac(f"nRev{tag}Floor{m_[:2].rstrip('.')}", fmt(min(b_), 3))
    cl = {(r["optimiser"], r["family"], r["fpr"], r["heldout_seed"], r["wind"]): r
          for r in er if r["delta_variant"] == "r1_pooled"}
    mac("nRevUndet", th_(sum(int(r["n_undetected"]) for r in cl.values())))
    hm = max(cl.values(), key=lambda r: float(r["heldout_adv_max"]))
    mac("nRevAdvMax", fmt(float(hm["heldout_adv_max"]), 2)); mac("nRevAdvMaxFam", hum(hm["family"]))
    mac("nRevAdvMaxOpt", {"cem": "CEM", "tpe_tail": "tail-objective TPE"}[hm["optimiser"]])
    mac("nRevSupUnsat", f"{max(float(r['superposition_max_excess_unsat_m']) for r in cl.values()):.1e}")
    mac("nRevSatAlarmMax", pct(max(float(r["frac_sat_alarm"]) for r in cl.values()), 1))
    mac("nRevZeroUndet", str(sum(int(r["n_undetected"]) == 0 for r in cl.values())))

with open(MS / "numbers.tex", "w") as fh:
    fh.write("% Generated by experiments/make_numbers.py -- do not edit by hand.\n")
    for k in sorted(M):
        fh.write(f"\\newcommand{{\\{k}}}{{{M[k]}}}\n")
print(f"{len(M)} macros; missions={meta['n_missions']}")
