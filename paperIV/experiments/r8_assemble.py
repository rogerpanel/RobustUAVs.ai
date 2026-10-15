#!/usr/bin/env python3
"""Assemble results/r8_analytic_bound.csv for the full T_a sweep from a run log.

The full sweep (r8_analytic_bound.py, 144 jobs) takes about 14 h on 4 cores,
and its rows are written only at the end. A sandbox restart stopped one run
after 140 jobs; this script rebuilds the table from that run's log
(results/logs/r8_interrupted.txt), recomputes any missing job with the same
code (bound() in r8_analytic_bound.py), and keeps the T_a = 5 s rows -- the
only ones the manuscript uses -- exactly as r8_analytic_bound.py wrote them
(results/logs/r8_ta5_only.csv). For log-derived rows the time of the maximum
was not logged, so argmax_t_s is left empty.

Usage:  python3 r8_assemble.py [--par 4]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from multiprocessing import Pool

import numpy as np

import run_pilot as RP
import r8_analytic_bound as R8
from constants import U_MAX
from sim import simulate

RES = RP.RES
LAB = {0: "anchor gate only (every stack)", 1: "anchor gate + D1 (stacks D1, ALL)",
       2: "anchor gate + D1 + D_sat (revised stack)"}
LOES = (1.0, 0.9, 0.8, 0.7)
EPS, STRIDE = 0.01, 10


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--par", type=int, default=4)
    a = ap.parse_args()
    js = json.loads((RES / "e1_calibration.json").read_text())
    stack = {float(k): v for k, v in js["stack"].items()}
    thA = js["anchor"]
    ben = simulate(4000, 1001, w20=RP.wind(4000, 1001))
    q1 = float(np.quantile(ben["S1"], 1 - EPS / 3)); qA = float(np.quantile(ben["SA"], 1 - EPS / 3))
    qu = float(np.quantile(ben["umax"], 1 - EPS / 3)); cu = U_MAX + qu
    ca = np.sqrt(thA) + np.sqrt(qA)
    got = {}
    for line in (RES / "logs" / "r8_interrupted.txt").open():
        m = re.match(r"\[\d+/\d+\] fpr=(\S+) Ta=(\S+) set=(\d) loe=(\S+) -> (\S+)", line)
        if m:
            f, ta, s, loe, v = m.groups()
            got[(float(f), None if ta == "None" else float(ta), int(s), float(loe))] = float(v)
    todo = [(f, ta, s, loe) for f in RP.OPS for ta in (5.0, 10.0, 20.0, None) for s in (0, 1, 2) for loe in LOES
            if (f, ta, s, loe) not in got]
    jobs = [(f, ta, s, loe, (stack[f]["D1"] + q1) if s >= 1 else None, ca, STRIDE, cu) for f, ta, s, loe in todo]
    with Pool(a.par) as pool:
        for f, ta, s, loe, b, kb in pool.imap_unordered(R8._job, jobs):
            got[(f, ta, s, loe)] = b
            print(f"computed fpr={f} Ta={ta} set={s} loe={loe} -> {b:.3f}", flush=True)
    ta5 = [r for r in csv.DictReader((RES / "logs" / "r8_ta5_only.csv").open())]
    emp = {float(r["fpr"]): float(r["delta_adv_cal_m"]) for r in csv.DictReader((RES / "e4_delta_adv.csv").open())}
    emp_r1 = {float(r["fpr"]): float(r["delta_pooled_m"]) for r in csv.DictReader((RES / "r1_delta_adv.csv").open())}
    rows = []
    for f in RP.OPS:
        for ta in (5.0, 10.0, 20.0, None):
            for s in (0, 1, 2):
                if ta == 5.0:
                    r = next(x for x in ta5 if float(x["fpr"]) == f and x["constraints"] == LAB[s])
                    rows.append({**r, "source": "r8_analytic_bound.py (T_a = 5 s run)"}); continue
                vals = [(got[(f, ta, s, l)], l) for l in LOES]
                b, loe = max(vals)
                fin = np.isfinite(b)
                rows.append({"fpr": f, "T_anchor_s": ta if ta else "none (C2' violated)", "constraints": LAB[s],
                             "theta_D1": round(stack[f]["D1"], 4) if s >= 1 else "", "S1_benign_q": round(q1, 4),
                             "theta_anchor": round(thA, 4), "SA_benign_q": round(qA, 4),
                             "umax_benign_q": round(qu, 4) if s == 2 else "", "eps": EPS,
                             "delta_lp_m": round(b, 3) if fin else "inf", "worst_loe": loe, "argmax_t_s": "",
                             "stride_steps": STRIDE, "delta_emp_pilot_m": emp[f], "delta_emp_r1_m": emp_r1[f],
                             "ratio_lp_to_emp": round(b / max(emp[f], emp_r1[f]), 3) if fin else "",
                             "provenance": "physics_model", "source": "run log (time of maximum not logged)"})
    with (RES / "r8_analytic_bound.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[-1]), lineterminator="\n"); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} rows -> results/r8_analytic_bound.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
