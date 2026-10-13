#!/usr/bin/env python3
"""Write manuscript/figdata/*.dat (whitespace tables read by pgfplots)."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from certcmdp.certificate import OUT  # noqa: E402

FIG = OUT.parent / "manuscript" / "figdata"
FIG.mkdir(parents=True, exist_ok=True)


def rd(name):
    p = OUT / name
    if not p.exists():
        return []
    with p.open() as fh:
        return list(csv.DictReader(fh))


def dat(name, header, rows):
    with (FIG / name).open("w") as fh:
        fh.write(" ".join(header) + "\n")
        for r in rows:
            fh.write(" ".join(str(x) for x in r) + "\n")


def main():
    c = rd("e2_collapse.csv")
    dat("collapse.dat", ["phi", "nominal", "random", "p05", "worst", "generic"],
        [(r["phi"], r["cov_nominal"], r["cov_random"], r["cov_random_p05"], r["cov_worst"],
          r["bound_generic"]) for r in c])
    g = rd("e2_graded.csv")
    for tau in ("0.5", "1.0", "2.0"):
        dat(f"graded_tau{tau.replace('.', 'p')}.dat", ["phi", "random", "worst", "bound"],
            [(r["phi"], r["cov_random"], r["cov_worst"], r["cov_bound"]) for r in g
             if r["tau_s"] == tau])
    lift = rd("e2_lift.csv")
    for dep in ("independent", "spatial_jammers"):
        rows = [r for r in lift if r["dependence"] == dep and r["event"] != "d=0"]
        dat(f"lift_{dep}.dat", ["k", "iid", "sim", "lo", "hi"],
            [(r["event"].replace("d>=", ""), r["p_iid_pred"], r["p_sim"], r["p_sim_lo"],
              r["p_sim_hi"]) for r in rows])
    lat = rd("e3_latency.csv")
    for alg in ("closed_form_check", "gnp_fast", "lexicographic_hungarian", "hopcroft_karp"):
        dat(f"lat_{alg}.dat", ["N", "p50", "p99"],
            [(r["N"], r["p50_ms"], r["p99_ms"]) for r in lat if r["algorithm"] == alg])
    cur = rd("e6_curves.csv")

    def smooth(x, w=10):        # trailing moving average over updates (display only)
        out = []
        for i in range(len(x)):
            seg = x[max(0, i - w + 1):i + 1]
            out.append(sum(seg) / len(seg))
        return out
    for m in sorted({r["method"] for r in cur}):
        rows = [r for r in cur if r["method"] == m]
        rc = smooth([float(r["r_cert_mean"]) for r in rows])
        lo = smooth([float(r["r_cert_lo"]) for r in rows])
        hi = smooth([float(r["r_cert_hi"]) for r in rows])
        dat(f"curve_{m}.dat", ["steps", "rcert", "lo", "hi", "viol", "cumviol"],
            [(int(r["env_steps"]) / 1e3, a, b, c, r["viol_mean"],
              max(float(r["cum_viol_mean"]), 1.0)) for r, a, b, c in zip(rows, rc, lo, hi)])
    fs = rd("e2_fleet_sizing.csv")
    for dep in ("independent", "spatial_jammers"):
        dat(f"sizing_{dep}.dat", ["N", "p"],
            [(r["N"], r["p_full_pred_iid"]) for r in fs if r["dependence"] == dep])
    print("figdata written to", FIG)


if __name__ == "__main__":
    main()
