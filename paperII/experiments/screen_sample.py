#!/usr/bin/env python3
"""S2 amendment 3: draw the simple random sample of the remainder stratum and
write its screening batches (batch_S<nnn>.txt / .cids), in random order.

Remainder = every candidate outside the core (ranks 1-2,750 of rank_v1.csv).
Seed 20261018, sample size 1,000, fixed in SCREENING_PROCEDURE.md before the draw.
Writes corpus/screening/sample_remainder.csv (draw order, cid).

Usage:  python3 screen_sample.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

C = Path(__file__).resolve().parent.parent / "corpus"
CORE, N, SEED, B = 2750, 1000, 20261018, 125


def main() -> int:
    csv.field_size_limit(10 ** 9)
    cand = {r["cid"]: r for r in csv.DictReader((C / "candidates.csv").open())}
    rank = [r["cid"] for r in csv.DictReader((C / "screening" / "rank_v1.csv").open())]
    rem = sorted(rank[CORE:])                      # sorted cids: the draw does not depend on rank order
    pick = np.random.default_rng(SEED).choice(len(rem), size=N, replace=False)
    sample = [rem[i] for i in pick]
    with (C / "screening" / "sample_remainder.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["draw", "cid"])
        w.writerows([(k, c) for k, c in enumerate(sample, 1)])
    out = C / "screening" / "llm"
    cl = lambda s: (s or "").replace("�", "?").replace("\n", " ").strip()
    for b in range(N // B):
        ids = sample[b * B:(b + 1) * B]
        lines = [f"# Batch S{b + 1:03d}: {len(ids)} records. One block per record.\n"]
        for j, c in enumerate(ids, 1):
            r = cand[c]
            lines.append(f"\n[{j}] cid: {c}\nTitle: {cl(r['title'])}\nYear: {r['year']} | Venue: {cl(r['venue'])} "
                         f"| Type: {r['type']}\nAbstract: {cl(r['abstract']) or '(none)'}\n")
        (out / f"batch_S{b + 1:03d}.txt").write_text("".join(lines))
        (out / f"batch_S{b + 1:03d}.cids").write_text("\n".join(ids) + "\n")
    # execution note (amendment 3): extend by 250 from the not-yet-sampled remainder, seed + 1
    rest = sorted(set(rem) - set(sample))
    ext = [rest[i] for i in np.random.default_rng(SEED + 1).choice(len(rest), size=250, replace=False)]
    with (C / "screening" / "sample_remainder.csv").open("a", newline="") as fh:
        csv.writer(fh, lineterminator="\n").writerows([(N + k, c) for k, c in enumerate(ext, 1)])
    for b in range(2):
        ids = ext[b * B:(b + 1) * B]
        lines = [f"# Batch S{9 + b:03d}: {len(ids)} records. One block per record.\n"]
        for j, c in enumerate(ids, 1):
            r = cand[c]
            lines.append(f"\n[{j}] cid: {c}\nTitle: {cl(r['title'])}\nYear: {r['year']} | Venue: {cl(r['venue'])} "
                         f"| Type: {r['type']}\nAbstract: {cl(r['abstract']) or '(none)'}\n")
        (out / f"batch_S{9 + b:03d}.txt").write_text("".join(lines))
        (out / f"batch_S{9 + b:03d}.cids").write_text("\n".join(ids) + "\n")
    print(f"remainder {len(rem)}; sample {N} + extension 250 -> {N // B + 2} batches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
