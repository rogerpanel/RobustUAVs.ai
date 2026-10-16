#!/usr/bin/env python3
"""Amendment 5: the coding sample of a snowballing iteration.

All included records of the iteration (iter<k>_decisions.csv) are listed in a random order
(seed 20261023 + k). The first N_CODE (at most 100) form the sample; a record whose open-access
full text cannot be retrieved is replaced by the next in that order (as in amendment 3).
Each coded paper stands for (iteration includes) / (papers coded) records.

A ranked iteration (above 3,000 candidates, iter<k>_strata.csv) is sampled per stratum as in
amendment 3: the N_CODE papers are allocated in proportion to the estimated includes of the core
(screened in full) and of the remainder (N_rem x p_hat from its random sample), with at least
N_CODE / 4 per stratum (amendment 3's 75 of 300, scaled); each stratum is ordered at random with
the same generator (core first), and a coded paper of stratum s stands for
(estimated includes of s) / (papers coded in s).

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
    st0 = {r["metric"]: r["value"] for r in csv.DictReader((S / f"iter{k}_screening_status.csv").open())}
    if int(st0["batches_pending"]) or int(st0["batches_invalid"]):
        raise SystemExit(f"iteration {k}: screening incomplete ({st0['batches_pending']} pending, "
                         f"{st0['batches_invalid']} invalid batches); not sampling")
    dec = list(csv.DictReader((S / f"iter{k}_decisions.csv").open()))
    rng = np.random.default_rng(20261023 + k)
    if "stratum" not in dec[0]:
        inc = sorted(r["cid"] for r in dec if r["include"] == "1")
        order = [inc[i] for i in rng.permutation(len(inc))]
        n = min(N_CODE, len(order))
        rows = [{"stratum": f"snowball{k}", "order": j, "cid": c, "doi": cand[c]["doi"], "title": cand[c]["title"],
                 "year": cand[c]["year"], "venue": cand[c]["venue"], "in_first_300": int(j <= n),
                 "weight": round(len(inc) / n, 4)} for j, c in enumerate(order, 1)]
        print(f"iteration {k}: {len(inc)} includes; coding sample {n} (+ replacements in order)")
    else:
        st = {r["metric"]: float(r["value"]) for r in csv.DictReader((S / f"iter{k}_screening_status.csv").open())}
        est = {"core": st["core_included"], "remainder": st["remainder_included_est"]}
        src = {"core": "core", "remainder": "sample"}
        inc = {s: sorted(r["cid"] for r in dec if r["include"] == "1" and r["stratum"] == src[s]) for s in est}
        tot = sum(est.values())
        n_rem = min(len(inc["remainder"]), max(N_CODE // 4, round(N_CODE * est["remainder"] / tot)))
        n_core = min(len(inc["core"]), max(N_CODE // 4, N_CODE - n_rem))
        quota = {"core": n_core, "remainder": n_rem}
        rows = []
        for s in ("core", "remainder"):
            order = [inc[s][i] for i in rng.permutation(len(inc[s]))]
            rows += [{"stratum": f"snowball{k}_{s}", "order": j, "cid": c, "doi": cand[c]["doi"],
                      "title": cand[c]["title"], "year": cand[c]["year"], "venue": cand[c]["venue"],
                      "in_first_300": int(j <= quota[s]), "weight": round(est[s] / quota[s], 4)}
                     for j, c in enumerate(order, 1)]
            print(f"iteration {k} {s}: {len(inc[s])} includes screened, {est[s]:.1f} estimated; "
                  f"coding sample {quota[s]} (+ replacements in order)")
    with (S / f"iter{k}_coding_sample.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n"); w.writeheader(); w.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
