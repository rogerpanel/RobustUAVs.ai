#!/usr/bin/env python3
"""S2 amendment 3: draw the stratified full-text/coding sample.

Strata   core     = included records of ranks 1-2,750 (screened in full);
         remainder = included records of the simple random sample of the other
                     22,623 candidates.
Size     300, allocated in proportion to the estimated number of includes per
         stratum (core: its count; remainder: 22,623 x sample include rate),
         at least 75 per stratum. Seed 20261019. Each stratum is listed in a
         random order: records whose full text cannot be retrieved are replaced
         by the next record of the same stratum in that order.
Weights  w = (estimated includes in stratum) / (coded records in stratum), so
         corpus-level shares are weighted estimates.

Output   corpus/coding_sample.csv: stratum, order, cid, doi, title, year, venue,
         in_first_300, weight

Usage:   python3 coding_sample.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

C = Path(__file__).resolve().parent.parent / "corpus"
N_CODE, MIN_STRATUM, SEED, N_REM = 300, 75, 20261019, 22623


def main() -> int:
    csv.field_size_limit(10 ** 9)
    cand = {r["cid"]: r for r in csv.DictReader((C / "candidates.csv").open())}
    dec = list(csv.DictReader((C / "screening" / "decisions.csv").open()))
    core = sorted(r["cid"] for r in dec if r["stratum"] == "core" and r["include"] == "1")
    samp = [r for r in dec if r["stratum"] == "sample"]
    rem = sorted(r["cid"] for r in samp if r["include"] == "1")
    est = {"core": len(core), "remainder": N_REM * len(rem) / len(samp)}
    tot = sum(est.values())
    n_core = max(MIN_STRATUM, round(N_CODE * est["core"] / tot)); n_rem = N_CODE - n_core
    if n_rem < MIN_STRATUM:
        n_rem, n_core = MIN_STRATUM, N_CODE - MIN_STRATUM
    if n_rem > len(rem):
        raise SystemExit(f"remainder stratum needs {n_rem} but only {len(rem)} includes are available")
    rng = np.random.default_rng(SEED)
    rows = []
    for name, pool, n in (("core", core, n_core), ("remainder", rem, n_rem)):
        order = [pool[i] for i in rng.permutation(len(pool))]
        for k, c in enumerate(order, 1):
            r = cand[c]
            rows.append({"stratum": name, "order": k, "cid": c, "doi": r["doi"], "title": r["title"],
                         "year": r["year"], "venue": r["venue"], "in_first_300": int(k <= n),
                         "weight": round(est[name] / n, 4)})
    with (C / "coding_sample.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n"); w.writeheader(); w.writerows(rows)
    print(f"estimated includes: core {est['core']}, remainder {est['remainder']:.0f}; "
          f"coding sample: core {n_core}, remainder {n_rem} (+ replacements in order)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
