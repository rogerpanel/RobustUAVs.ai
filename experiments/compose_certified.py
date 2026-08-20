#!/usr/bin/env python3
"""P2: the theta -> delta -> MCR composition on the time-delay class,
with the corrected (state-space) interface, plus baselines and statistics.

Corrected model (docs/certified_regime_analysis.md):
  * The time-delay attack never touches the RF front-end; its perturbation is
    STALENESS of the network-delivered correction. delta enters in vehicle
    state space (metres), NOT through the CAF feature bridge.
  * Residual budget (tightened Lemma 1, measured): an attacker that evades
    the detector at theta keeps every per-hop residual <= theta, and the
    contact-window slack s caps invisible delay at s regardless of theta
    (measured: max undetected malicious residual 4.84 s over 15,392 hops;
    a delay > s forces a missed window whose >=55 s residual is flagged at
    any epsilon). Hence per hop: r <= min(theta, s), and over H malicious
    hops:      Delta(theta) <= H * min(theta, s).
  * Kinematic mapping (staleness_v0, sound worst case): delta_pos =
    v_max * Delta(theta). The Whelan-grounded empirical tightening is
    real-corpus work (Kaggle unreachable this session).
  * State-space Gronwall tube: rho(theta) = delta_pos(theta) * exp(L*T).
    L defaults to the MEASURED LOCAL constant 1.181 (experiments/
    local_lipschitz.py), not the global power-iteration estimate 1.01. The
    local value is the defensible one because it is LARGER: it is measured
    along the hidden-state trajectories the integrator actually visits on
    operating-region inputs, so it does not flatter the bound. Using the
    global estimate here while the paper's headline figure quotes the local
    one produced an internal inconsistency (gamma_req 7.28 vs 6.14 m/s at
    m=10) -- the conclusion was unchanged but two quoted numbers came from a
    different L than the caption claimed. Override with LIPSCHITZ_L= to
    reproduce the earlier global-L numbers. We also report the un-amplified
    kinematic tube (A=1) as the lower envelope.
  * Certified floor for corridor margin m: mission certified iff
    rho(theta) <= m. Margin family M = {2, 5, 10, 20} m (stated parameters;
    10 m is the PX4-default-class acceptance radius NAV_ACC_RAD). Floor =
    fraction of M certified (uniform weight) -- a stated margin model, NOT a
    measured mission distribution.

Baselines:
  * composed        : Delta = measured undetected malicious delay at epsilon
                      (per seed), i.e. what actually slipped past.
  * composed-worst  : Delta = H * min(theta, s)  (analytic worst case).
  * autonomy-only   : no detector -> nothing is removed; Delta = the FULL
                      measured malicious delay including missed-window
                      penalties (per seed).
  * network-only    : detector but no navigation certificate -> no floor
                      exists for evading attacks by definition (floor 0).

Outputs:
  results/composition_perseed.csv   per-(scenario,mode,eps,seed,policy) budgets
  results/certified_floor_vs_theta.csv  the corrected headline curve
  results/stats_wilcoxon.csv        Wilcoxon signed-rank + Holm for the
                                    headline comparisons
Provenance: DATAMUt local simulation (deterministic per seed) + stated
model parameters; fixture/simulation-derived throughout.
"""
from __future__ import annotations

import csv
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"

SLACK_S = 5.0          # inter-UAV contact window (Keiwan R2)
V_MAX = 15.0           # m/s, stated kinematic worst-case speed
# Measured local Lipschitz constant over the operating region. Overridable so
# the earlier global-L campaign stays reproducible.
L_REF = float(os.environ.get("LIPSCHITZ_L", "1.181"))
T_REF = float(os.environ.get("HORIZON_T", "1.0"))
AMP = math.exp(L_REF * T_REF)          # tube amplification, 3.258 at L=1.181
AMP_TAG = f"gronwall_L{L_REF:g}_T{T_REF:g}"
MARGINS_M = [2.0, 5.0, 10.0, 20.0]     # stated margin family (10 = PX4-class)


def load_mappings():
    """delta mappings: staleness seconds -> position-error metres/second.

    Parametric by design (P2 of the certified-regime follow-up): the
    kinematic worst case is always available; the empirical rates are read
    from results/whelan_delta_calibration.csv when the real-corpus
    calibration has run (receiver = attack-injected error at the estimator
    input; ekf = filtered error the controller acts on — an EXPLICIT
    choice, see docs/certified_regime_analysis.md). Conservative pick per
    source: max over attack flights of the available gamma rates.
    """
    mappings = {"kinematic_v15": {
        "gamma_m_s": V_MAX,
        "provenance": "stated worst case (v_max=15 m/s)"}}
    cal = RESULTS / "whelan_delta_calibration.csv"
    if cal.exists():
        rows = [r for r in csv.DictReader(open(cal)) if r["flight"] != "benign"]
        for src in ("receiver", "ekf"):
            rates = [float(r[k]) for r in rows if r["source"] == src
                     for k in ("gamma_lsq_m_s", "gamma_peak_m_s")
                     if r.get(k) not in (None, "", "None")]
            rates = [x for x in rates if x > 0]
            if rates:
                mappings[f"empirical_{src}"] = {
                    "gamma_m_s": max(rates),
                    "provenance": ("real-corpus 3-flight Whelan live sample, "
                                   "hover regime, self-referenced pre-attack "
                                   "median; conservative max rate")}
    # The per-sample campaign supersedes the per-flight secant where it is
    # available. gamma_stability/gamma_campaign showed the per-flight rate is a
    # long-horizon average: measured at every post-onset sample, the
    # baseline-corrected rate reaches 1.625 m/s, ~1.19x the 1.365 the per-flight
    # secant reports. The certificate is entitled to the supremum over the
    # conditions it claims to cover, so this is the mapping the paper quotes.
    camp = RESULTS / "gamma_campaign_samples.csv"
    if camp.exists():
        vals = [float(r["gamma_delta_m_s"]) for r in csv.DictReader(open(camp))
                if r.get("gamma_delta_m_s") not in (None, "", "None")]
        if vals:
            mappings["empirical_campaign_sup"] = {
                "gamma_m_s": max(vals),
                "provenance": ("real-corpus, supremum of the baseline-corrected "
                               "per-sample rate over 674 post-onset samples from "
                               "2 attack flights; hover regime, one airframe")}
    return mappings


MAPPINGS = load_mappings()
THETA_GRID = [0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 6.5, 7.0, 8.0, 10.0]
# finer grid for the certified curve itself (sub-0.25 matters: that is where
# the worst-case kinematic tube fits real corridor margins). 0.178 s is the
# measured benign residual ceiling -> FPR=0 feasibility floor.
BENIGN_CEIL_S = 0.178
THETA_CURVE = [0.05, 0.1, 0.121, 0.15, BENIGN_CEIL_S, 0.2, 0.243, 0.25, 0.3,
               0.4, 0.5, 0.67, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 6.5, 7.0,
               8.0, 10.0]


def floor_for(delta_pos_m: float, amp: float) -> float:
    rho = delta_pos_m * amp
    return sum(1.0 for m in MARGINS_M if rho <= m) / len(MARGINS_M)


def floors_all_mappings(delta_stale_s: float, amp: float = AMP) -> dict:
    """Certified floor per delta mapping for a staleness budget (seconds)."""
    return {name: floor_for(m["gamma_m_s"] * delta_stale_s, amp)
            for name, m in MAPPINGS.items()}


def holm(pvals):
    """Holm step-down correction; returns adjusted p-values in input order."""
    order = np.argsort(pvals)
    m = len(pvals)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * pvals[idx])
        adj[idx] = min(1.0, running)
    return adj


def main() -> int:
    hops = list(csv.DictReader(open(RESULTS / "hop_ledger.csv")))

    # ---- per-(scenario,mode,eps,seed,policy) budgets from the ledger ----
    acc = defaultdict(lambda: {"und": 0.0, "tot": 0.0, "H": 0})
    for h in hops:
        if h["malicious_sender"] != "1":
            continue
        key = (h["scenario"], h["mode"], h["epsilon"], h["seed"], h["policy"])
        r = float(h["residual_s"])
        acc[key]["tot"] += r
        acc[key]["H"] += 1
        if h["suspicious"] == "0":
            acc[key]["und"] += r

    perseed = []
    for (scen, mode, eps, seed, pol), v in sorted(acc.items()):
        theta = float(eps)
        H = v["H"]
        d_evade = H * min(theta, SLACK_S)
        rows = {
            "scenario": scen, "mode": mode, "epsilon": eps, "seed": seed,
            "policy": pol, "H_malicious_hops": H,
            "delta_undetected_s": round(v["und"], 3),
            "delta_total_s": round(v["tot"], 3),
            "delta_evade_worst_s": round(d_evade, 3),
            # legacy kinematic columns (headline conservative)
            "floor_composed": floor_for(V_MAX * v["und"], AMP),
            "floor_composed_worst": floor_for(V_MAX * d_evade, AMP),
            "floor_autonomy_only": floor_for(V_MAX * v["tot"], AMP),
            "floor_network_only": 0.0,
        }
        for name in MAPPINGS:
            rows[f"floor_composed__{name}"] = \
                floors_all_mappings(v["und"])[name]
            rows[f"floor_autonomy_only__{name}"] = \
                floors_all_mappings(v["tot"])[name]
        perseed.append(rows)

    with open(RESULTS / "composition_perseed.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(perseed[0].keys()))
        w.writeheader()
        w.writerows(perseed)
    print(f"[compose] {len(perseed)} per-seed rows -> results/composition_perseed.csv")

    # ---- the corrected certified curve vs theta (analytic worst case, ----
    # ---- H from the measured per-route ledger; per scenario H = max   ----
    Hs = defaultdict(int)
    for r in perseed:
        Hs[r["scenario"]] = max(Hs[r["scenario"]], r["H_malicious_hops"])
    curve = []
    for theta in THETA_CURVE:
        for scen, H in sorted(Hs.items()):
            d = H * min(theta, SLACK_S)
            for amp, amp_tag in [(AMP, AMP_TAG), (1.0, "unamplified_A1")]:
                for mname, mp in MAPPINGS.items():
                    g = mp["gamma_m_s"]
                    curve.append({
                        "theta_s": theta, "scenario": scen,
                        "H_malicious_hops": H,
                        "mapping": mname, "gamma_m_s": g,
                        "delta_evade_worst_s": round(d, 3),
                        "delta_pos_m": round(g * d, 3),
                        "tube_m": round(g * d * amp, 3),
                        "amplification": amp_tag,
                        "certified_floor": floor_for(g * d, amp),
                    })
    with open(RESULTS / "certified_floor_vs_theta.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(curve[0].keys()))
        w.writeheader()
        w.writerows(curve)
    print(f"[compose] {len(curve)} curve rows -> results/certified_floor_vs_theta.csv")

    # ---- the certified operating window: [benign ceiling, theta*(m)] ----
    # theta*(m) = m / (v_max * A * H): loosest detector setting whose
    # worst-case evading tube still fits corridor margin m. The window is
    # nonempty iff theta* > BENIGN_CEIL_S (measured FPR=0 floor).
    window = []
    for scen, H in sorted(Hs.items()):
        for amp, amp_tag in [(AMP, AMP_TAG), (1.0, "unamplified_A1")]:
            for mname, mp in MAPPINGS.items():
                g = mp["gamma_m_s"]
                for m in MARGINS_M:
                    theta_star = m / (g * amp * H)
                    # theta* beyond the slack means the knee saturation
                    # governs: certified for ALL theta iff g*H*s*amp <= m
                    saturated_ok = g * H * SLACK_S * amp <= m
                    window.append({
                        "scenario": scen, "H_malicious_hops": H,
                        "amplification": amp_tag, "mapping": mname,
                        "gamma_m_s": g, "margin_m": m,
                        "theta_star_s": round(theta_star, 4),
                        "benign_ceiling_s": BENIGN_CEIL_S,
                        "window_nonempty": int(theta_star > BENIGN_CEIL_S),
                        "certified_at_paper_theta_0.25": int(theta_star >= 0.25),
                        "certified_for_all_theta": int(saturated_ok),
                    })
    with open(RESULTS / "certified_operating_window.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(window[0].keys()))
        w.writeheader()
        w.writerows(window)
    n_open = sum(r["window_nonempty"] for r in window)
    print(f"[compose] {len(window)} window rows ({n_open} nonempty) -> "
          "results/certified_operating_window.csv")

    # ---- sensitivity: how gentle must the mapping be for theta targets? ----
    # gamma_req(theta, m) = m / (theta * A * H): the largest error-growth
    # rate for which theta is still inside the certified window.
    sens = []
    for theta_t in (0.25, 0.5, 1.0):
        for scen, H in sorted(Hs.items()):
            for amp, amp_tag in [(AMP, AMP_TAG),
                                 (1.0, "unamplified_A1")]:
                for m in MARGINS_M:
                    g_req = m / (theta_t * amp * H)
                    row = {"theta_target_s": theta_t, "scenario": scen,
                           "H_malicious_hops": H, "amplification": amp_tag,
                           "margin_m": m, "gamma_required_m_s": round(g_req, 3)}
                    for mname, mp in MAPPINGS.items():
                        row[f"ok__{mname}"] = int(mp["gamma_m_s"] <= g_req)
                    sens.append(row)
    with open(RESULTS / "delta_mapping_sensitivity.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(sens[0].keys()))
        w.writeheader()
        w.writerows(sens)
    print(f"[compose] {len(sens)} sensitivity rows -> "
          "results/delta_mapping_sensitivity.csv")

    # ---- Wilcoxon signed-rank + Holm ----
    perseed_idx = defaultdict(dict)
    for r in perseed:
        perseed_idx[(r["scenario"], r["epsilon"], r["seed"], r["policy"])][r["mode"]] = r

    tests = []

    # H1: undetected budget, medium vs low (paired per scenario/eps/seed/policy)
    for eps in [f"{t}" for t in THETA_GRID]:
        lo, med = [], []
        for (scen, e, seed, pol), modes in perseed_idx.items():
            if e == eps and "low" in modes and "medium" in modes:
                lo.append(modes["low"]["delta_undetected_s"])
                med.append(modes["medium"]["delta_undetected_s"])
        if len(lo) >= 8 and any(a != b for a, b in zip(lo, med)):
            stat, p = wilcoxon(med, lo)
            tests.append({"comparison": "undetected_budget_medium_vs_low",
                          "epsilon": eps, "n_pairs": len(lo),
                          "median_diff": round(float(np.median(np.array(med) - np.array(lo))), 3),
                          "p_raw": p})

    # H2: composed floor vs autonomy-only floor (paired, pooled modes),
    # once per delta mapping
    for mname in MAPPINGS:
        ca, cb = f"floor_composed__{mname}", f"floor_autonomy_only__{mname}"
        for eps in [f"{t}" for t in THETA_GRID]:
            a, b = [], []
            for r in perseed:
                if r["epsilon"] == eps:
                    a.append(r[ca])
                    b.append(r[cb])
            diffs = np.array(a) - np.array(b)
            if len(a) >= 8 and np.any(diffs != 0):
                stat, p = wilcoxon(a, b)
                tests.append({"comparison":
                              f"floor_composed_vs_autonomy_only__{mname}",
                              "epsilon": eps, "n_pairs": len(a),
                              "median_diff": round(float(np.median(diffs)), 3),
                              "p_raw": p})

    # H3: recall medium vs low (paired per scenario/eps/seed/policy)
    rec = list(csv.DictReader(open(RESULTS / "theta_operating_curve_perseed.csv")))
    rec_idx = defaultdict(dict)
    for r in rec:
        rec_idx[(r["scenario"], r["epsilon"], r["seed"], r["policy"])][r["mode"]] = float(r["recall"])
    for eps in [f"{t}" for t in THETA_GRID]:
        lo, med = [], []
        for (scen, e, seed, pol), modes in rec_idx.items():
            if e == eps and "low" in modes and "medium" in modes:
                lo.append(modes["low"])
                med.append(modes["medium"])
        if len(lo) >= 8 and any(a != b for a, b in zip(lo, med)):
            stat, p = wilcoxon(med, lo)
            tests.append({"comparison": "recall_medium_vs_low",
                          "epsilon": eps, "n_pairs": len(lo),
                          "median_diff": round(float(np.median(np.array(med) - np.array(lo))), 3),
                          "p_raw": p})

    # Holm within each comparison family
    by_family = defaultdict(list)
    for i, t in enumerate(tests):
        by_family[t["comparison"]].append(i)
    for fam, idxs in by_family.items():
        adj = holm([tests[i]["p_raw"] for i in idxs])
        for i, a in zip(idxs, adj):
            tests[i]["p_holm"] = float(a)
            tests[i]["significant_0.05"] = int(a < 0.05)
    for t in tests:
        t["p_raw"] = float(t["p_raw"])

    with open(RESULTS / "stats_wilcoxon.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(tests[0].keys()))
        w.writeheader()
        w.writerows(tests)
    print(f"[compose] {len(tests)} tests -> results/stats_wilcoxon.csv")
    sig = sum(t["significant_0.05"] for t in tests)
    print(f"[compose] {sig}/{len(tests)} significant after Holm within family")

    # console headline
    for mname, mp in MAPPINGS.items():
        print(f"\ncertified floor vs theta — mapping {mname} "
              f"(gamma={mp['gamma_m_s']:.3f} m/s; Gronwall amp; "
              "margins {2,5,10,20} m; scenario 1):")
        for theta in (0.178, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0):
            row = [c for c in curve if c["theta_s"] == theta
                   and c["amplification"] == AMP_TAG
                   and c["mapping"] == mname and c["scenario"] == "1"]
            if row:
                print(f"  theta={theta:>6}: floor={row[0]['certified_floor']:.2f} "
                      f"(tube {row[0]['tube_m']:.2f} m)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
