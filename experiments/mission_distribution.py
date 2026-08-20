#!/usr/bin/env python3
"""
Campaign arm B: how much does MCR depend on the mission distribution?

A co-author observed that MCR = P(mission completes) is a probability over a
distribution of missions, so a bound on it is a statement about a population and
not about an arbitrary flight, and asked us to discuss the point explicitly.
paperD_v6 discusses it. This measures it.

UAV-EW-Bench-2026 flies 93,600 simulated missions over a full factorial of
  defense  x  J/S (dB)  x  seed  x  mission profile  x  receiver model
with a binary completion outcome per flight. The mission profile and the
receiver model are exactly the two axes along which "the mission distribution"
can be changed while everything else is held fixed. So we can ask, directly:

    holding the attack and the defence fixed, how far apart are the MCRs of
    two different mission distributions?

If the answer is "not far", the benchmark number transfers and the caveat is
theoretical. If the answer is "far", then quoting a single MCR without naming
its distribution is misleading, and the paper must say so with a number.

PROVENANCE: simulation (physics-informed). This arm is NOT real-flight data,
and its role is to size a sensitivity, not to certify anything.

Writes:
  results/mission_distribution.csv
  results/paper_figures/block_paperD_tab_missiondist.tex
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
SRC = (REPO / "data" / "raw" / "uav_ew_bench_2026" / "UAV-EW-Bench-2026"
       / "data" / "per_flight.csv")
OUT = REPO / "results" / "mission_distribution.csv"
BLOCK = REPO / "results" / "paper_figures" / "block_paperD_tab_missiondist.tex"

# The defence whose numbers the paper quotes.
FOCUS_DEFENSE = "ours_m1m4m6m7"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval: correct for proportions near 0 and 1, where the
    normal approximation gives bounds outside [0,1]."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - h) / d, (c + h) / d)


def main() -> int:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC.relative_to(REPO)}; stage the corpus first")

    rows = list(csv.DictReader(SRC.open()))
    print(f"loaded {len(rows)} simulated flights")

    # completion counts keyed by (defense, js_db, mission, receiver)
    agg: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])   # [completed, n]
    for r in rows:
        try:
            js = float(r["js_db"])
            done = int(r["completed"])
        except (ValueError, KeyError):
            continue
        k = (r["defense"], js, r["mission"], r["receiver"])
        agg[k][0] += done
        agg[k][1] += 1

    missions = sorted({k[2] for k in agg})
    receivers = sorted({k[3] for k in agg})
    js_levels = sorted({k[1] for k in agg})
    print(f"  {len(missions)} mission profiles, {len(receivers)} receiver models, "
          f"{len(js_levels)} J/S levels")

    out: list[dict] = []
    # ---- spread across mission profile, at fixed J/S and receiver ----------
    spreads_mission, spreads_receiver = [], []
    for js in js_levels:
        for rx in receivers:
            vals = []
            for ms in missions:
                k = (FOCUS_DEFENSE, js, ms, rx)
                if k in agg and agg[k][1] > 0:
                    vals.append((ms, agg[k][0] / agg[k][1], agg[k][1]))
            if len(vals) > 1:
                lo = min(v[1] for v in vals)
                hi = max(v[1] for v in vals)
                spreads_mission.append((js, rx, hi - lo, lo, hi))
    for js in js_levels:
        for ms in missions:
            vals = []
            for rx in receivers:
                k = (FOCUS_DEFENSE, js, ms, rx)
                if k in agg and agg[k][1] > 0:
                    vals.append((rx, agg[k][0] / agg[k][1], agg[k][1]))
            if len(vals) > 1:
                lo = min(v[1] for v in vals)
                hi = max(v[1] for v in vals)
                spreads_receiver.append((js, ms, hi - lo, lo, hi))

    # ---- per-distribution MCR, marginalised over J/S -----------------------
    for ms in missions:
        for rx in receivers:
            k_tot = [0, 0]
            for js in js_levels:
                k = (FOCUS_DEFENSE, js, ms, rx)
                if k in agg:
                    k_tot[0] += agg[k][0]
                    k_tot[1] += agg[k][1]
            if k_tot[1] == 0:
                continue
            p = k_tot[0] / k_tot[1]
            lo, hi = wilson(k_tot[0], k_tot[1])
            out.append({"scope": "per_distribution", "mission": ms,
                        "receiver": rx, "js_db": "all", "n": k_tot[1],
                        "mcr": round(p, 4), "ci_low": round(lo, 4),
                        "ci_high": round(hi, 4)})

    mcrs = [r["mcr"] for r in out if r["scope"] == "per_distribution"]
    worst, best = min(mcrs), max(mcrs)
    out.append({"scope": "summary", "mission": "spread_over_distributions",
                "receiver": "", "js_db": "all", "n": len(mcrs),
                "mcr": round(best - worst, 4),
                "ci_low": round(worst, 4), "ci_high": round(best, 4)})

    if spreads_mission:
        mx = max(spreads_mission, key=lambda x: x[2])
        out.append({"scope": "summary", "mission": "max_spread_across_mission",
                    "receiver": mx[1], "js_db": mx[0], "n": len(spreads_mission),
                    "mcr": round(mx[2], 4), "ci_low": round(mx[3], 4),
                    "ci_high": round(mx[4], 4)})
    if spreads_receiver:
        rx = max(spreads_receiver, key=lambda x: x[2])
        out.append({"scope": "summary", "mission": "max_spread_across_receiver",
                    "receiver": rx[1], "js_db": rx[0], "n": len(spreads_receiver),
                    "mcr": round(rx[2], 4), "ci_low": round(rx[3], 4),
                    "ci_high": round(rx[4], 4)})

    # ---- the J/S at which each distribution first drops below 0.90 --------
    for ms in missions:
        for rx in receivers:
            cross = None
            for js in js_levels:
                k = (FOCUS_DEFENSE, js, ms, rx)
                if k in agg and agg[k][1] and agg[k][0] / agg[k][1] < 0.90:
                    cross = js
                    break
            out.append({"scope": "js_at_mcr_0.90", "mission": ms,
                        "receiver": rx, "js_db": cross if cross is not None else "none",
                        "n": "", "mcr": "", "ci_low": "", "ci_high": ""})

    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["scope", "mission", "receiver",
                                           "js_db", "n", "mcr",
                                           "ci_low", "ci_high"])
        w.writeheader()
        w.writerows(out)
    print(f"-> {OUT.relative_to(REPO)}")

    # ---- LaTeX ------------------------------------------------------------
    pm = {"cargo_mixed_terrain": "cargo, mixed terrain",
          "perimeter_patrol": "perimeter patrol",
          "search_and_rescue": "search and rescue"}
    pr = {"gp_software_receiver": "GP software", "novatel_oem7_sim": "NovAtel OEM7",
          "ublox_f9p_sim": "u-blox F9P"}
    lines = ["% AUTO-GENERATED by experiments/mission_distribution.py. Do not hand-edit.\n",
             "% PROVENANCE: simulation (physics-informed), UAV-EW-Bench-2026.\n",
             "\\begin{tabular}{@{}llrr@{}}\n\\toprule\n",
             "Mission profile & Receiver & MCR & 95\\% CI\\\\\n\\midrule\n"]
    last = None
    for r in sorted([o for o in out if o["scope"] == "per_distribution"],
                    key=lambda x: (x["mission"], x["receiver"])):
        ms = pm.get(r["mission"], r["mission"])
        lines.append(f"{ms if ms != last else ''} & {pr.get(r['receiver'], r['receiver'])} "
                     f"& {r['mcr']:.3f} & [{r['ci_low']:.3f}, {r['ci_high']:.3f}]\\\\\n")
        last = ms
    lines += ["\\midrule\n",
              f"\\multicolumn{{2}}{{@{{}}l}}{{Spread across mission distributions}} & "
              f"\\multicolumn{{2}}{{r}}{{{best - worst:.3f} "
              f"({worst:.3f}--{best:.3f})}}\\\\\n",
              "\\bottomrule\n\\end{tabular}\n"]
    BLOCK.write_text("".join(lines))
    print(f"-> {BLOCK.relative_to(REPO)}")

    print(f"\nMCR across the {len(mcrs)} mission distributions "
          f"(same defence, same attack sweep):")
    print(f"  worst {worst:.3f}   best {best:.3f}   SPREAD {best - worst:.3f}")
    if spreads_mission:
        mx = max(spreads_mission, key=lambda x: x[2])
        print(f"  max spread from mission profile alone: {mx[2]:.3f} "
              f"(at J/S={mx[0]:g} dB, receiver {mx[1]})")
    if spreads_receiver:
        rx = max(spreads_receiver, key=lambda x: x[2])
        print(f"  max spread from receiver model alone : {rx[2]:.3f} "
              f"(at J/S={rx[0]:g} dB, mission {rx[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
