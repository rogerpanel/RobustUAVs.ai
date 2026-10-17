#!/usr/bin/env python3
"""SORA Annex A-shaped evidence generator (Paper II, Sec. VIII).

Reads the parent artifact's committed result files and emits an evidence pack
for one certified configuration.  The pack demonstrates the *sound* transfer
path of the parent composition (Q_in -> Q_tr -> Q_op -> Q_pop) typed by the
lift calculus, and lists every lift assumption as an obligation with its
evidence status, instead of hiding it inside the result.

Inputs (parent artifact, ../../results):
  certified_floor_vs_theta.csv, certified_operating_window.csv,
  local_lipschitz.csv, gamma_campaign_bins.csv, mission_distribution.csv
Outputs (../results):
  evidence_pack.json, evidence_obligations.csv, evidence_contingency.csv,
  lift_chain.csv
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from quantifier import OBLIGATIONS, shortest_path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent.parent / "results"
R = HERE.parent / "results"
R.mkdir(exist_ok=True)

THETA = 0.25          # parent operating point (s)
H = 2                 # attacker-controlled hops (parent)
MAPPINGS = ["empirical_ekf", "empirical_campaign_sup", "kinematic_v15"]
MARGINS = [2.0, 5.0, 10.0, 20.0]


def rows(name):
    return list(csv.DictReader(open(PARENT / name)))


def main():
    floor = [r for r in rows("certified_floor_vs_theta.csv")
             if abs(float(r["theta_s"]) - THETA) < 1e-9 and r["scenario"] == "1"
             and r["amplification"].startswith("gronwall")]
    lip = {r["estimator"]: r for r in rows("local_lipschitz.csv")}
    L_loc = float(lip["L_local_max (data-driven trajectories)"]["value"])
    bins = rows("gamma_campaign_bins.csv")
    cov = {r["factor"].split(":", 1)[1]: (r["bin"], r["gamma_max"] if r["gamma_max"] else r.get("", ""))
           for r in bins if r["factor"].startswith("COVERAGE:")}
    n_samples = [r for r in bins if r["factor"] == "OVERALL"][0]["n"]
    md = [r for r in rows("mission_distribution.csv") if r["scope"] == "per_distribution"]
    mcr_lo = min(float(r["mcr"]) for r in md); mcr_hi = max(float(r["mcr"]) for r in md)

    # ---------------- contingency extent per mapping and margin ----------------
    cont = []
    for r in floor:
        if r["mapping"] not in MAPPINGS:
            continue
        tube = float(r["tube_m"])
        for m in MARGINS:
            cont.append({"mapping": r["mapping"], "gamma_m_s": float(r["gamma_m_s"]),
                         "delta_s": float(r["delta_evade_worst_s"]), "delta_pos_m": float(r["delta_pos_m"]),
                         "tube_m": tube, "margin_m": m, "fits": int(tube <= m),
                         "residual_m": round(m - tube, 3)})
    with open(R / "evidence_contingency.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cont[0].keys())); w.writeheader(); w.writerows(cont)

    # ---------------- the parent chain, typed ----------------
    chain = [
        {"step": 1, "from": "detector threshold theta", "to": "residual delay Delta(theta)",
         "type_from": "in/A", "type_to": "in/A", "lift": "Lemma 1 (budget)", "obligations": "",
         "status": "proved; cap measured 4.84 s over 15392 hops"},
        {"step": 2, "from": "Delta(theta)", "to": "input perturbation delta",
         "type_from": "in/A", "type_to": "in/A", "lift": "interface gamma (calibration)",
         "obligations": "O_cal", "status": f"measured on 3 flights of one airframe, {n_samples} samples; supremum used"},
        {"step": 3, "from": "delta", "to": "trajectory tube rho", "type_from": "in/A", "type_to": "tr/A",
         "lift": "L_dyn", "obligations": "O_lip", "status": f"local L = {L_loc:.3f} measured on the checkpoint"},
        {"step": 4, "from": "rho over Tc", "to": "corridor predicate over [0,T]", "type_from": "tr/A",
         "type_to": "op/A", "lift": "L_hor", "obligations": "O_hor", "status": "assumed (Definition 2); holds by construction for a delay adversary only"},
        {"step": 5, "from": "per-operation predicate", "to": "MCR over the mission distribution",
         "type_from": "op/A", "type_to": "popd/P", "lift": "L_sup", "obligations": "O_odd",
         "status": f"distribution named; MCR {mcr_lo:.3f}-{mcr_hi:.3f} across 9 profiles (simulation)"},
        {"step": 6, "from": "MCR per mission", "to": "per flight hour objective", "type_from": "popd/P",
         "type_to": "poph/P", "lift": "L_rate", "obligations": "O_dep", "status": "open: not claimed by the parent"},
    ]
    # check the chain against the calculus: in/A -> poph/P
    calc = shortest_path(("in", "A"), ("poph", "P"))
    via_op = shortest_path(("in", "A"), ("op", "A"))
    with open(R / "lift_chain.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(chain[0].keys())); w.writeheader(); w.writerows(chain)

    # ---------------- obligations with status ----------------
    obl = [
        {"id": "O_cal", "text": "interface rate gamma transfers to the deployment (C3)", "kind": "statistical",
         "status": "partially evidenced", "evidence": "real PX4 spoofing/jamming flights; hover only; one airframe",
         "coverage_gap": f"platform: {cov.get('platform', ('',))[0]}; flight mode: {cov.get('flight_mode', ('',))[0]}; airspeed: {cov.get('airspeed', ('',))[0]}"},
        {"id": "O_lip", "text": OBLIGATIONS["O_lip"][0], "kind": OBLIGATIONS["O_lip"][1],
         "status": "evidenced (model)", "evidence": f"local Lipschitz constant {L_loc:.4f} on operating-region trajectories",
         "coverage_gap": "outside the smooth envelope (stall, saturation, aggressive manoeuvre) no finite L"},
        {"id": "O_hor", "text": OBLIGATIONS["O_hor"][0], "kind": OBLIGATIONS["O_hor"][1],
         "status": "assumed", "evidence": "re-anchoring every Tc = 1 s; satisfied by construction for delay adversaries",
         "coverage_gap": "fails under persistent denial (Paper I, Prop. regimes)"},
        {"id": "O_odd", "text": OBLIGATIONS["O_odd"][0], "kind": OBLIGATIONS["O_odd"][1],
         "status": "stated", "evidence": "mission distribution (3 profiles x 3 receivers) named; simulated",
         "coverage_gap": "deployment distribution not sampled"},
        {"id": "O_dep", "text": OBLIGATIONS["O_dep"][0], "kind": OBLIGATIONS["O_dep"][1],
         "status": "open", "evidence": "none", "coverage_gap": "no per-hour claim is made"},
        {"id": "O_thr", "text": OBLIGATIONS["O_thr"][0], "kind": OBLIGATIONS["O_thr"][1],
         "status": "stated", "evidence": "time-delay adversary below detector threshold; GNSS RF manipulation via unit bridge",
         "coverage_gap": "denial, insider key compromise, monitor-input attacks not covered"},
    ]
    with open(R / "evidence_obligations.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(obl[0].keys())); w.writeheader(); w.writerows(obl)

    ekf = [c for c in cont if c["mapping"] == "empirical_ekf"]
    pack = {
        "schema": "paperII.evidence_pack.v1",
        "configuration": {"theta_s": THETA, "H": H, "Tc_s": 1.0, "L_local": L_loc, "mapping": "empirical_ekf"},
        "operational_design_domain": {
            "source": "parent measured operating region",
            "attitude": "away from gimbal singularity", "airspeed": "below stall; hover/loiter measured",
            "actuators": "unsaturated", "coverage": {k: v[0] for k, v in cov.items()}},
        "sora_annex_a": {
            "operational_volume": "flight geography + contingency volume",
            "contingency_volume_terms": {
                "gnss_accuracy_m": "OPERATOR (open)",
                "position_holding_error_under_attack_m": ekf[0]["tube_m"],
                "map_error_m": "OPERATOR (open)",
                "reaction_distance_m": "OPERATOR (open)",
                "contingency_manoeuvre_m": "OPERATOR (open)"},
            "certified_margins_m": [c["margin_m"] for c in ekf if c["fits"]],
            "not_certified_margins_m": [c["margin_m"] for c in ekf if not c["fits"]]},
        "typed_chain": chain,
        "calculus_check": {"in/A->poph/P": calc, "in/A->op/A": via_op},
        "obligations": obl,
        "provenance": "generated by paperII/experiments/evidence_pack.py from parent results/*.csv",
        "disclaimer": "maps a mathematical guarantee onto an evidence framework; certifies nothing",
    }
    json.dump(pack, open(R / "evidence_pack.json", "w"), indent=2)
    return pack


if __name__ == "__main__":
    p = main()
    print(json.dumps(p["sora_annex_a"], indent=1))
    print(p["calculus_check"])
