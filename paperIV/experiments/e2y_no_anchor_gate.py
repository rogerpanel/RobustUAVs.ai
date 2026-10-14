#!/usr/bin/env python3
"""E2y ablation: cross-evaluate every optimised attacker against every detector
stack with the anchor fix still FUSED into the filter (C2') but its alarm gate
REMOVED. Isolates what the detectors themselves discriminate.
Seeds: 4500 + attacker_id (block 4xxx, disjoint from E2x's 4100+id)."""
import json, os
from pathlib import Path
import numpy as np
from run_pilot import RES, STACKS, run_attack, write, _ks, wind
from sim import alarms, simulate

cal_j = json.loads((RES / "e1_calibration.json").read_text())
single = {float(k): v for k, v in cal_j["single"].items()}
stack = {float(k): v for k, v in cal_j["stack"].items()}
N = json.loads((RES / "run_meta.json").read_text())["N_eval"]
(RES / "mission_count_e2y.txt").write_text("")      # a re-run must not append to an earlier count
os.environ["P4_COUNT_FILE"] = str(RES / "mission_count_e2y.txt")
rows = []
for a in __import__("csv").DictReader(open(RES / "e2_attackers.csv")):
    i = int(a["attacker_id"])
    o, oa, _ = run_attack(a["family"], json.loads(a["params"]), N, 4500 + i, benign=False)
    for s in STACKS:
        th = stack[0.05] if s == "ALL" else single[0.05]
        st = ~alarms(o, th, STACKS[s])
        rows.append({"attacker_id": i, "family": a["family"], "origin_stack": a["origin_stack"],
                     "stack": s, "evasion_rate": round(float(st.mean()), 4), "n_stealthy": int(st.sum()),
                     "attack_only_dev_max": round(float(oa["maxdev"][st].max()) if st.any() else 0.0, 3)})
write("e2y_no_anchor_gate.csv", rows)
print("E2y rows", len(rows))
