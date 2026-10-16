#!/usr/bin/env python3
"""Amendment 5: the coding sample of a snowballing iteration.

All included records of the iteration (iter<k>_decisions.csv) are listed in a random order
(seed 20261023 + k). The first N_CODE (at most 100) form the sample; a record whose open-access
full text cannot be retrieved is replaced by the next in that order (as in amendment 3).
Each coded paper stands for (iteration includes) / (papers coded) records.

Output  corpus/snowball/iter<k>_coding_sample.csv: stratum, order, cid, doi, title, year,
        venue, in_first_300 (here: in the first N_CODE), weight
Usage   python3 snowball_sample.py --iter 1
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

C = Path(__file__).resolve().parent.parent / "corpus"
N_CODE = 100


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--iter", type=int, default=1)
    k = ap.parse_args().iter
    csv.field_size_limit(10 ** 9)
    S = C / "snowball"
    cand = {r["cid"]: r for r in csv.DictReader((S / f"iter{k}_candidates.csv").open())}
    inc = sorted(r["cid"] for r in csv.DictReader((S / f"iter{k}_decisions.csv").open()) if r["include"] == "1")
    order = [inc[i] for i in np.random.default_rng(20261023 + k).permutation(len(inc))]
    n = min(N_CODE, len(order))
    rows = [{"stratum": f"snowball{k}", "order": j, "cid": c, "doi": cand[c]["doi"], "title": cand[c]["title"],
             "year": cand[c]["year"], "venue": cand[c]["venue"], "in_first_300": int(j <= n),
             "weight": round(len(inc) / n, 4)} for j, c in enumerate(order, 1)]
    with (S / f"iter{k}_coding_sample.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n"); w.writeheader(); w.writerows(rows)
    print(f"iteration {k}: {len(inc)} includes; coding sample {n} (+ replacements in order)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
