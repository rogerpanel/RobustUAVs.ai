#!/usr/bin/env python3
"""P2: full clean DATAMUt campaign — per-seed operating curve + hop ledger.

Runs the patched demo across all three topologies (1 grid, 2 ring,
3 double-ring), both delay modes (low U[1,7], medium U[1,10]), an epsilon
grid, and 8 seeds; each operating point runs in a FRESH working directory
(the demo appends to its summary CSV, so a shared directory contaminates
every point after the first — the bug behind the pre-2026-07-28 curve).

Outputs (tidy, per-seed, host-agnostic):
  results/theta_operating_curve_perseed.csv
      scenario,mode,epsilon,seed,policy,tp,fp,fn,tn,precision,recall,f1,fpr
  results/theta_operating_curve.csv           (regenerated clean aggregate,
      same schema as before: scenario,mode,epsilon,recall,fpr,precision,n_runs)
  results/hop_ledger.csv
      per observed hop: residual delay, path-match, suspicious verdict,
      whether the SENDER is ground-truth malicious - the raw material for
      the trigger decomposition and the measured undetected-delay budget.
  results/missed_windows.csv
      per missed forwarding opportunity (the TWiG knee, measured).

Provenance: local runs of the patched third-party DATAMUt replay
(deterministic per seed); simulation-derived.

Usage: python3 experiments/sweep_full.py [--eps ...] [--seeds 8] [--quick]
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BINARY = REPO / "build" / "datamut_demo"
RESULTS = REPO / "results"

MODES = {"low": (1.0, 7.0), "medium": (1.0, 10.0)}
EPS_DEFAULT = "0.25,0.5,1,1.5,2,3,4,5,6,6.5,7,8,10"

RE_SEED = re.compile(r"^--- running seed (\d+) ---")
RE_PACKET = re.compile(r"^\[(\w+)\] packet (\d+)")
RE_HOP = re.compile(
    r"^\s+hop (\d+): (\S+) -> (\S+) \| intended_send=([\d.\-]+) "
    r"local_next=(\S+) observed=([\d.\-]+) residual=([\d.\-]+) "
    r"epsilon=([\d.\-]+) pathMatch=(yes|no) suspicious=(yes|no)")
RE_MISSED = re.compile(
    r"packet (\d+) missed opportunity: (\S+) -> (\S+) window=(\S+) "
    r"expected=([\d.\-]+) send=([\d.\-]+)")

MALICIOUS = {"1": {"n6", "n10"}, "2": {"n4", "n3"}, "3": {"n5", "n3"}}


def run_point(scenario, mode, eps, dmin, dmax, seeds):
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ,
                   DATAMUT_SCENARIO=scenario, DATAMUT_NUM_SEEDS=str(seeds),
                   DATAMUT_EPSILON=str(eps),
                   DATAMUT_DELAY_MIN=str(dmin), DATAMUT_DELAY_MAX=str(dmax))
        proc = subprocess.run([str(BINARY)], env=env, cwd=tmp,
                              capture_output=True, text=True, check=True)
        summary = list(csv.DictReader(
            open(Path(tmp) / "datamut-paper-metrics-summary.csv")))

    tag = dict(scenario=scenario, mode=mode, epsilon=eps)
    perseed = [{**tag, "seed": r["seed"], "policy": r["policy"],
                "tp": r["tp"], "fp": r["fp"], "fn": r["fn"], "tn": r["tn"],
                "precision": r["precision"], "recall": r["recall"],
                "f1": r["f1"], "fpr": r["fpr"]} for r in summary]

    hops, missed = [], []
    seed = policy = packet = None
    mal = MALICIOUS[scenario]
    for line in proc.stdout.splitlines():
        m = RE_SEED.match(line)
        if m:
            seed = m.group(1)
            continue
        m = RE_PACKET.match(line)
        if m:
            policy, packet = m.group(1), m.group(2)
            continue
        m = RE_HOP.match(line)
        if m:
            (hop, frm, to, intended, local_next, observed, residual,
             _eps, pmatch, susp) = m.groups()
            hops.append({**tag, "seed": seed, "policy": policy,
                         "packet": packet, "hop": hop, "from": frm, "to": to,
                         "residual_s": residual,
                         "path_match": int(pmatch == "yes"),
                         "suspicious": int(susp == "yes"),
                         "malicious_sender": int(frm in mal)})
            continue
        m = RE_MISSED.search(line)
        if m:
            pkt, frm, to, window, expected, send = m.groups()
            missed.append({**tag, "seed": seed, "policy": policy or "sim",
                           "packet": pkt, "from": frm, "to": to,
                           "window": window, "expected_s": expected,
                           "send_s": send,
                           "overshoot_s": f"{float(send) - float(expected):.3f}",
                           "malicious_sender": int(frm in mal)})
    return perseed, hops, missed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eps", default=EPS_DEFAULT)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--scenarios", default="1,2,3")
    a = ap.parse_args()
    if not BINARY.exists():
        print("build the demo first (see CLAUDE.md Build & run)"); return 1

    all_seed, all_hops, all_missed, agg = [], [], [], []
    for scen in a.scenarios.split(","):
        for mode, (dmin, dmax) in MODES.items():
            for eps in (float(x) for x in a.eps.split(",")):
                ps, hp, ms = run_point(scen, mode, eps, dmin, dmax, a.seeds)
                all_seed += ps
                all_hops += hp
                all_missed += ms
                n = len(ps)
                rec = sum(float(r["recall"]) for r in ps) / n
                fpr = sum(float(r["fpr"]) for r in ps) / n
                pre = sum(float(r["precision"]) for r in ps) / n
                agg.append({"scenario": scen, "mode": mode, "epsilon": eps,
                            "recall": rec, "fpr": fpr, "precision": pre,
                            "n_runs": n})
                print(f"scen={scen} mode={mode:>6} eps={eps:>5}: "
                      f"recall={rec:.3f} fpr={fpr:.3f} "
                      f"({len(hp)} hops, {len(ms)} missed-windows)")

    RESULTS.mkdir(exist_ok=True)
    for name, rows in [("theta_operating_curve_perseed.csv", all_seed),
                       ("hop_ledger.csv", all_hops),
                       ("missed_windows.csv", all_missed),
                       ("theta_operating_curve.csv", agg)]:
        if not rows:
            continue
        with open(RESULTS / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"[sweep-full] {len(rows):>6} rows -> results/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
