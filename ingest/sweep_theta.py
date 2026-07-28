#!/usr/bin/env python3
"""Detector operating curve for DATAMUt: recall/FPR vs epsilon (theta).

Runs the patched demo (DATAMUT_EPSILON / DATAMUT_DELAY_MIN / DATAMUT_DELAY_MAX
env vars) across scenarios, seeds, epsilon grid, and both attack modes
(low: U[1,7] s, medium: U[1,10] s per Keiwan Soltani's R2), and writes a tidy
CSV: scenario, mode, epsilon, recall, fpr, precision, n_runs. This curve is the
network-side input to the composition theorem (theta -> detection tradeoff).

Usage:
  python3 sweep_theta.py <demo_binary> <out_csv> \
      [--scenarios 1,2,3] [--seeds 8] [--eps 0.25,0.5,1,2,3,4,5,6,7,8,10]
"""
import argparse, csv, os, subprocess, sys, tempfile
from pathlib import Path

MODES = {"low": (1.0, 7.0), "medium": (1.0, 10.0)}


def run_once(binary, scenario, n_seeds, eps, dmin, dmax, workdir):
    env = dict(os.environ,
               DATAMUT_SCENARIO=str(scenario), DATAMUT_NUM_SEEDS=str(n_seeds),
               DATAMUT_EPSILON=str(eps),
               DATAMUT_DELAY_MIN=str(dmin), DATAMUT_DELAY_MAX=str(dmax))
    # The demo APPENDS to its summary CSV; a stale file from a previous
    # operating point would contaminate this point's average (this exact bug
    # produced the pre-2026-07-28 committed operating curve - see
    # docs/certified_regime_analysis.md). Start every point clean.
    summary = Path(workdir) / "datamut-paper-metrics-summary.csv"
    summary.unlink(missing_ok=True)
    subprocess.run([binary], env=env, cwd=workdir,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    rows = list(csv.DictReader(open(summary)))
    n = len(rows)
    return {
        "recall": sum(float(r["recall"]) for r in rows) / n,
        "fpr": sum(float(r["fpr"]) for r in rows) / n,
        "precision": sum(float(r["precision"]) for r in rows) / n,
        "n_runs": n,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("binary"); ap.add_argument("out_csv")
    ap.add_argument("--scenarios", default="1,2,3")
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--eps", default="0.25,0.5,1,1.5,2,3,4,5,6,7,8,10")
    a = ap.parse_args()
    binary = str(Path(a.binary).resolve())

    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for scen in a.scenarios.split(","):
            for mode, (dmin, dmax) in MODES.items():
                for eps in (float(x) for x in a.eps.split(",")):
                    r = run_once(binary, scen, a.seeds, eps, dmin, dmax, tmp)
                    out.append({"scenario": scen, "mode": mode, "epsilon": eps, **r})
                    print(f"scen={scen} mode={mode} eps={eps:>5}: "
                          f"recall={r['recall']:.3f} fpr={r['fpr']:.3f}")

    with open(a.out_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    print(f"[sweep] {len(out)} operating points -> {a.out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
