#!/usr/bin/env python3
"""Diagnose the Holm-significant violations of the scaled E4 test
(results/r1_e4_soundness.csv): re-simulate each violating cell with its exact
seeds and report, for every undetected failing mission, the full, attack-only
and benign-only deviations, the superposition excess and whether the actuator
saturated (with and without the attack).

Output: results/r1_violation_diagnosis.csv
Usage:  python3 r1_diagnose.py
"""
from __future__ import annotations

import csv
import json

import numpy as np

import run_pilot as RP
from r1_attackers import load_cal

RES = RP.RES
WINDS = {"light": (0, (RP.W_LO, RP.W_LO)), "moderate": (1, (RP.W_HI, RP.W_HI)),
         "envelope": (2, (RP.W_LO, RP.W_HI))}


def main():
    cal = load_cal()
    snd = list(csv.DictReader((RES / "r1_e4_soundness.csv").open()))
    held = {(r["family"], r["fpr"], r["heldout_seed"]): json.loads(r["params"])
            for r in csv.DictReader((RES / "r1_heldout.csv").open())}
    cells = sorted({(r["family"], r["fpr"], r["heldout_seed"], r["wind"]) for r in snd if r["violation"] == "1"})
    rows = []
    for fam, fpr, hs, wind in cells:
        wi, (wl, wh) = WINDS[wind]
        h = int(hs) - 7000
        o, oa, ob = RP.run_attack(fam, held[(fam, fpr, hs)], 5000, 8000 + 10 * h + wi, wl=wl, wh=wh)
        st = RP.stealth_mask(o, cal, "ALL", float(fpr))
        tn = max(float(r["theta_net"]) for r in snd if r["violation"] == "1" and (r["family"], r["fpr"], r["heldout_seed"], r["wind"]) == (fam, fpr, hs, wind))
        bad = np.flatnonzero(st & (o["maxdev"] + RP.net_tube(tn) > 20.0))
        for i in bad:
            rows.append({"family": fam, "fpr": fpr, "heldout_seed": hs, "wind": wind, "mission": int(i), "theta_net_max_violated": tn,
                         "maxdev_full_m": round(float(o["maxdev"][i]), 3),
                         "maxdev_attack_only_m": round(float(oa["maxdev"][i]), 3),
                         "maxdev_benign_only_m": round(float(ob["maxdev"][i]), 3),
                         "superposition_excess_m": round(float(o["maxdev"][i] - oa["maxdev"][i] - ob["maxdev"][i]), 3),
                         "saturated_full": int(o["sat"][i]), "saturated_benign_only": int(ob["sat"][i]),
                         "benign_only_fails_m20": int(ob["maxdev"][i] > 20.0),
                         "provenance": "sim"})
            print(rows[-1], flush=True)
    with (RES / "r1_violation_diagnosis.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
