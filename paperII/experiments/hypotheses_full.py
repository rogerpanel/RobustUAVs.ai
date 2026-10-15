#!/usr/bin/env python3
"""H1-H3 quantities of the pilot (results/hypotheses.csv) re-estimated on the
full-study coded sample, weighted by stratum (see corpus_estimates.py).

Every quantity is a weighted ratio sum(w * num) / sum(w * den) over eligible
coded papers, with a 95% stratified percentile bootstrap interval (B = 4000,
seed 20261021; the remainder include count is redrawn as in corpus_estimates).
The unweighted pilot value is listed beside it for comparison.

Output   results/hypotheses_full.csv  key, description, n_den (coded), estimate, lo, hi, pilot
Usage    python3 hypotheses_full.py [codes_full_C1.csv]   (default codes_full_final.csv;
         another codes file is a sensitivity run, output hypotheses_full_<C>.csv)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

C = Path(__file__).resolve().parent.parent / "corpus"
R = C.parent / "results"
B, SEED = 4000, 20261021


def main() -> int:
    csv.field_size_limit(10 ** 9)
    codes = sys.argv[1] if len(sys.argv) > 1 else "codes_full_final.csv"
    tag = "" if codes == "codes_full_final.csv" else "_" + codes.replace("codes_full_", "").replace(".csv", "")
    st = {r["metric"]: r["value"] for r in csv.DictReader((R / "screening_status.csv").open())}
    n_core, n_samp = int(st["core_included"]), int(st["sample_included"])
    m_samp, pool = int(st["sample_screened"]), int(st["remainder_size"])
    stratum = {r["cid"]: r["stratum"] for r in csv.DictReader((C / "coding_sample.csv").open())}
    year = {r["cid"]: r["year"] for r in csv.DictReader((C / "candidates.csv").open())}
    pilot = {r["key"]: r["value"] for r in csv.DictReader((R / "hypotheses.csv").open())}
    rows = [r for r in csv.DictReader((C / codes).open()) if r["eligible"] == "1"]
    S = np.array([stratum[r["cid"]] == "core" for r in rows])
    n_c, n_r = S.sum(), (~S).sum()
    # the weights use papers coded per stratum (eligible or not), as in corpus_estimates
    k_c = sum(stratum[r["cid"]] == "core" for r in csv.DictReader((C / codes).open()))
    k_r = sum(1 for _ in csv.DictReader((C / codes).open())) - k_c
    lifts = [set(r["lifts"].split(";")) - {"none"} for r in rows]
    a = lambda f, v: np.array([r[f] == v for r in rows])  # noqa: E731
    lifted = np.array([bool(x) for x in lifts])
    acc = lifted & (a("assumption", "SE") | a("assumption", "SEC"))
    yr = np.array([int(year[r["cid"]] or 0) for r in rows])
    Q = [  # key, description, numerator, denominator, pilot key
        ("h1_AB_perc_in", "perception guarantees that are per input", a("component", "perception") & a("scope", "in"),
         a("component", "perception"), "h1_AB_perc_in"),
        ("h1_AB_ctrl_in", "control guarantees that are per input", a("component", "control") & a("scope", "in"),
         a("component", "control"), "h1_AB_ctrl_in"),
        ("h1_AB_ctrl_tr", "control guarantees that are per trajectory", a("component", "control") & a("scope", "tr"),
         a("component", "control"), "h1_AB_ctrl_tr"),
        ("h1_AB_all_in", "all guarantees that are per input", a("scope", "in"), np.ones(len(rows), bool),
         "h1_AB_all_in"),
        ("h1_A_perc_in", "tier-A perception guarantees that are per input",
         a("tier", "A") & a("component", "perception") & a("scope", "in"), a("tier", "A") & a("component", "perception"),
         "h1_A_perc_in"),
        ("h1_A_ctrl_tr", "tier-A control guarantees that are per trajectory",
         a("tier", "A") & a("component", "control") & a("scope", "tr"), a("tier", "A") & a("component", "control"),
         "h1_A_ctrl_tr"),
        ("h2_share_lifted", "guarantees that use at least one lift", lifted, np.ones(len(rows), bool), ""),
        ("h2_share_U", "lifted: assumption unstated", lifted & a("assumption", "U"), lifted, "h2_share_U"),
        ("h2_share_S", "lifted: stated, not evidenced", lifted & a("assumption", "S"), lifted, "h2_share_S"),
        ("h2_share_SE", "lifted: evidenced", lifted & a("assumption", "SE"), lifted, "h2_share_SE"),
        ("h2_share_SEC", "lifted: evidenced with confidence carried", lifted & a("assumption", "SEC"), lifted,
         "h2_share_SEC"),
        ("h2_share_accounted", "lifted: accounted (SE or SEC)", acc, lifted, "h2_share_accounted"),
        ("h2_accounted_2017", "lifted 2017-2021: accounted", acc & (yr <= 2021), lifted & (yr <= 2021),
         "h2_accounted_2017"),
        ("h2_accounted_2022", "lifted 2022-2026: accounted", acc & (yr >= 2022), lifted & (yr >= 2022),
         "h2_accounted_2022"),
    ]
    for L in ("L_dyn", "L_hor", "L_gen", "L_op", "L_rate", "L_conc", "L_sup", "L_mon"):
        use = np.array([L in x for x in lifts])
        Q.append((f"h2_{L}_use", f"guarantees using {L}", use, np.ones(len(rows), bool), ""))
        Q.append((f"h2_{L}_acc", f"{L} users: accounted", use & acc, use, f"h2_{L}_acc"))
    for comp in ("perception", "control", "estimation", "end2end", "planning"):
        Q.append((f"h3_{comp}_share_P", f"{comp} guarantees with modality P", a("component", comp) & a("modality", "P"),
                  a("component", comp), f"h3_{comp}_share_P"))
    Q += [("h3_P_perception", "modality-P guarantees that concern perception",
           a("modality", "P") & a("component", "perception"), a("modality", "P"), ""),
          ("h3_rate_use", "guarantees performing the rate lift", np.array(["L_rate" in x for x in lifts]),
           np.ones(len(rows), bool), ""),
          ("h4_share_RTA", "guarantees of class RTA", a("class", "RTA"), np.ones(len(rows), bool), ""),
          ("h4_RTA_accounted", "RTA guarantees: accounted (SE or SEC)", a("class", "RTA") & acc
           | (a("class", "RTA") & ~lifted & (a("assumption", "SE") | a("assumption", "SEC"))), a("class", "RTA"), ""),
          ("h4_RTA_L_mon", "RTA guarantees using L_mon", a("class", "RTA") & np.array(["L_mon" in x for x in lifts]),
           a("class", "RTA"), "")]

    def ratio(num, den, w):
        d = (w * den).sum()
        return (w * num).sum() / d if d > 0 else float("nan")

    def weights(Nr, idx=None):
        return np.where(S, n_core / k_c, Nr / k_r)

    Nr0 = pool * n_samp / m_samp
    w0 = weights(Nr0)
    rng = np.random.default_rng(SEED)
    ic, ir = np.flatnonzero(S), np.flatnonzero(~S)
    boot = np.empty((B, len(Q)))
    for b in range(B):
        # resample coded papers within strata (eligible and not, so the eligible count varies)
        sc = rng.integers(0, k_c, k_c); sr = rng.integers(0, k_r, k_r)
        # an eligible paper's multiplicity = how often its slot among all coded papers is drawn
        mult = np.zeros(len(rows))
        cnt_c = np.bincount(sc, minlength=k_c)[:n_c]; cnt_r = np.bincount(sr, minlength=k_r)[:n_r]
        mult[ic], mult[ir] = cnt_c, cnt_r
        wb = weights(pool * rng.binomial(m_samp, n_samp / m_samp) / m_samp) * mult
        boot[b] = [ratio(num, den, wb) for _, _, num, den, _ in Q]
    out = []
    for j, (k, desc, num, den, pk) in enumerate(Q):
        lo, hi = np.nanquantile(boot[:, j], [.025, .975])
        out.append({"key": k, "description": desc, "n_den": int(den.sum()), "estimate": round(ratio(num, den, w0), 4),
                    "lo": round(float(lo), 4), "hi": round(float(hi), 4), "pilot": pilot.get(pk, "")})
    with (R / f"hypotheses_full{tag}.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n"); w.writeheader(); w.writerows(out)
    for r in out:
        print(f"{r['key']:<20} n={r['n_den']:<4} {r['estimate']:.3f} [{r['lo']:.3f},{r['hi']:.3f}]  pilot {r['pilot']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
