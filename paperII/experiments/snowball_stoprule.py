#!/usr/bin/env python3
"""Amendment 5: the stop rule for a snowballing iteration, applied to estimates.

An iteration is quiet when (a) its estimated new eligible papers are below 2 % of the estimated
eligible field before it, and (b) no coded paper of the iteration occupies a scope x modality
cell not seen before (pilot and every earlier stage). Snowballing stops after two consecutive
quiet iterations, or after three iterations.

New eligible papers = iteration includes x eligible share among its coded papers (adjudicated),
with a 95 % Clopper-Pearson interval on the share. Field before = the main study's weighted
estimate (results/corpus_estimates.csv) plus the estimates of earlier iterations.

Usage   python3 snowball_stoprule.py --iter 1     -> results/snowball_iter<k>_status.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from scipy.stats import beta

C = Path(__file__).resolve().parent.parent / "corpus"
R = C.parent / "results"
THRESH = 0.02


def cp(k, n, a=0.05):
    lo = beta.ppf(a / 2, k, n - k + 1) if k > 0 else 0.0
    hi = beta.ppf(1 - a / 2, k + 1, n - k) if k < n else 1.0
    return lo, hi


def cells(rows):
    return {(r["scope"], r["modality"]) for r in rows if r.get("eligible", "1") == "1" and r.get("scope")}


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--iter", type=int, default=1)
    k = ap.parse_args().iter
    S = C / "snowball"
    est = {(r["field"], r["value"]): r for r in csv.DictReader((R / "corpus_estimates.csv").open())}
    field = float(est[("eligible", "1")]["papers"])
    seen = cells(csv.DictReader((C / "codes_ADJ.csv").open())) | cells(csv.DictReader((C / "codes_full_final.csv").open()))
    for j in range(1, k):
        p = R / f"snowball_iter{j}_status.csv"
        prev = {r["metric"]: r["value"] for r in csv.DictReader(p.open())}
        field += float(prev["new_eligible_est"])
        seen |= cells(csv.DictReader((S / f"iter{j}_codes_full_final.csv").open()))
    st = {r["metric"]: r["value"] for r in csv.DictReader((S / f"iter{k}_screening_status.csv").open())}
    inc = int(st["included"])
    final = list(csv.DictReader((S / f"iter{k}_codes_full_final.csv").open()))
    n = len(final); e = sum(r["eligible"] == "1" for r in final)
    lo, hi = cp(e, n)
    new = inc * e / n
    new_cells = sorted(cells(final) - seen)
    new_classes = sorted({r["class"] for r in final if r["eligible"] == "1" and r["class"].startswith("NEW:")})
    frac = new / field
    rows = [("iteration", k), ("candidates_screened", st["screened"]), ("includes", inc), ("coded", n),
            ("eligible_coded", e), ("eligible_share", round(e / n, 4)),
            ("eligible_share_lo", round(lo, 4)), ("eligible_share_hi", round(hi, 4)),
            ("new_eligible_est", round(new)), ("new_eligible_lo", round(inc * lo)), ("new_eligible_hi", round(inc * hi)),
            ("field_before", round(field)), ("new_fraction", round(frac, 4)),
            ("condition_a_below_2pct", int(frac < THRESH)),
            ("new_type_cells", ";".join(f"{a}/{b}" for a, b in new_cells) or "none"),
            ("condition_b_no_new_cell", int(not new_cells)),
            ("quiet", int(frac < THRESH and not new_cells)),
            ("new_class_labels", len(new_classes))]
    with (R / f"snowball_iter{k}_status.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["metric", "value"]); w.writerows(rows)
    for a, b in rows:
        print(f"{a:<26} {b}")
    for c in new_classes:
        print("  NEW class label:", c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
