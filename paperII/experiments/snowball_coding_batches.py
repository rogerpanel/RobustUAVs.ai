#!/usr/bin/env python3
"""Amendment 5: full-text coding batches for a snowballing iteration (same format as the main
study: 5 papers per batch, the first 80,000 characters of each text, sample order).

Usage:  python3 snowball_coding_batches.py --iter 1 --fulltext DIR --out DIR
Writes  <out>/batch_S<k>C<nnn>.txt and corpus/coding/batch_S<k>C<nnn>.cids
        (full texts stay outside the repository)
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

C = Path(__file__).resolve().parent.parent / "corpus"
PER, CHARS = 5, 80000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=1)
    ap.add_argument("--fulltext", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    k = a.iter
    csv.field_size_limit(10 ** 9)
    S = C / "snowball"
    cand = {r["cid"]: r for r in csv.DictReader((S / f"iter{k}_candidates.csv").open())}
    st = {r["cid"]: r for r in csv.DictReader((S / f"iter{k}_fulltext_status.csv").open())}
    sample = list(csv.DictReader((S / f"iter{k}_coding_sample.csv").open()))
    strata = list(dict.fromkeys(r["stratum"] for r in sample))      # sample order within each stratum
    order = [r["cid"] for r in sorted(sample, key=lambda r: (strata.index(r["stratum"]), int(r["order"])))
             if st.get(r["cid"], {}).get("status") == "retrieved"]
    a.out.mkdir(parents=True, exist_ok=True)
    (C / "coding").mkdir(exist_ok=True)
    for b in range(0, len(order), PER):
        name = f"S{k}C{b // PER + 1:03d}"
        chunk = order[b:b + PER]
        parts = [f"# Coding batch {name}: {len(chunk)} papers\n"]
        for j, c in enumerate(chunk, 1):
            t = (a.fulltext / f"{c}.txt").read_text(errors="replace")
            r = cand[c]
            parts.append(f"\n\n========== PAPER [{j}] cid: {c} ==========\nTitle: {r['title']}\n"
                         f"Year: {r['year']} | Venue: {r['venue']}\n"
                         f"Full text (first {min(CHARS, len(t))} of {len(t)} characters):\n\n{t[:CHARS]}\n")
        (a.out / f"batch_{name}.txt").write_text("".join(parts))
        (C / "coding" / f"batch_{name}.cids").write_text("\n".join(chunk) + "\n")
    print(f"iteration {k}: {len(order)} papers -> {(len(order) + PER - 1) // PER} batches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
