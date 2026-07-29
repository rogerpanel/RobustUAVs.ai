#!/usr/bin/env python3
"""Real MCR anchor + mission-corridor margins from UAV-EW-Bench-2026.

Replaces the published-value MCR coordinates (previously copied from the
drafts) with values computed from the released per_flight.csv, and reads the
mission-corridor waypoint distances from the benchmark's own corpus generator
so the certificate's margin family is grounded in the benchmark rather than
stated.

Outputs:
  results/ewbench_mcr_anchor.csv   defense,js_db,mcr,n,ci_low,ci_high
      (Wilson 95% interval; the report points the dissertation figure uses)
  results/ewbench_margins.csv      mission corridor parameters read from the
      benchmark config/corpus (waypoint distance range; NAV acceptance radius
      if present).
Provenance: real-corpus (UAV-EW-Bench-2026 v1.0.0 release, sim-lite backend).
"""
from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "data" / "raw" / "uav_ew_bench_2026" / "UAV-EW-Bench-2026"
PER_FLIGHT = BENCH / "data" / "per_flight.csv"
REPORT_JS = [0, 5, 10, 15, 20, 25, 30, 35, 40]


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, (c - h) / d, (c + h) / d


def nearest_js_levels(all_js):
    """Map each report point to the nearest actual J/S level in the file."""
    out = {}
    for target in REPORT_JS:
        out[target] = min(all_js, key=lambda x: abs(x - target))
    return out


def main() -> int:
    if not PER_FLIGHT.exists():
        print(f"[anchor] missing {PER_FLIGHT}"); return 1
    rows = list(csv.DictReader(open(PER_FLIGHT)))
    all_js = sorted(set(float(r["js_db"]) for r in rows))
    mapping = nearest_js_levels(all_js)

    # aggregate completed / total by (defense, actual js level)
    agg = defaultdict(lambda: [0, 0])
    for r in rows:
        key = (r["defense"], float(r["js_db"]))
        agg[key][0] += int(r["completed"])
        agg[key][1] += 1

    out = []
    for defense in ("no_def", "caf_cnn", "seq2seq_tr", "ours_m1m4m6m7"):
        for target in REPORT_JS:
            js = mapping[target]
            k, n = agg[(defense, js)]
            p, lo, hi = wilson(k, n)
            out.append({"defense": defense, "js_db": target,
                        "js_actual": round(js, 2), "mcr": round(p, 4),
                        "n": n, "ci_low": round(lo, 4), "ci_high": round(hi, 4)})

    with open(REPO / "results" / "ewbench_mcr_anchor.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(f"[anchor] {len(out)} rows -> results/ewbench_mcr_anchor.csv "
          f"({len(rows)} flights, real per_flight.csv)")
    for defense in ("no_def", "ours_m1m4m6m7"):
        pts = [(r["js_db"], r["mcr"]) for r in out if r["defense"] == defense]
        print(f"  {defense:15} " + " ".join(f"{j}:{m:.3f}" for j, m in pts))

    # ---- mission-corridor margins from the corpus generator ----
    corpus_py = (BENCH / "uavbench" / "corpus.py").read_text()
    margins = []
    import re
    m = re.search(r"waypoint_km=float\(round\(rng\.uniform\(([\d.]+),\s*([\d.]+)\)", corpus_py)
    if m:
        lo_km, hi_km = float(m.group(1)), float(m.group(2))
        margins.append({"parameter": "waypoint_distance_km",
                        "min": lo_km, "max": hi_km,
                        "source": "uavbench/corpus.py rng.uniform",
                        "note": "mission length; corridor half-width is a "
                                "fraction of this - see below"})
    # DO-326A completion = 'certified course deviation within bound'; the
    # numeric bound is read from the M7 certificate at run time (backends.py
    # TODO(site)), so the corridor half-width is NOT a hard constant in the
    # release. Record the modeling margins we use and their basis.
    for m_val, basis in [(2.0, "tight geofence / urban corridor (stated)"),
                         (5.0, "standard waypoint tolerance (stated)"),
                         (10.0, "PX4 NAV_ACC_RAD default class (stated)"),
                         (20.0, "loose corridor / open-terrain (stated)")]:
        margins.append({"parameter": "corridor_margin_m", "min": m_val,
                        "max": m_val, "source": "modeling family",
                        "note": basis})
    with open(REPO / "results" / "ewbench_margins.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(margins[0].keys()))
        w.writeheader()
        w.writerows(margins)
    print(f"[anchor] margins -> results/ewbench_margins.csv "
          "(corridor half-width is NOT a release constant: the DO-326A "
          "deviation bound is read from the M7 certificate at run time; "
          "margin family stays a stated modeling choice)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
