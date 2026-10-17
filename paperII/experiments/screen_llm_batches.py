#!/usr/bin/env python3
"""S2 amendment 2: write the LLM screeners' batch files from the fixed ranking.

batch_<P><nnn>.txt holds 125 records (cid, title, year, venue, type, abstract)
in rank order, with no rank, score or pilot-set mark; batch_<P><nnn>.cids lists
its cids. Existing batches are never rewritten.

Usage:  python3 screen_llm_batches.py --version 1 --phase A --upto 6000
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

C = Path(__file__).resolve().parent.parent / "corpus"
B = 125


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, default=1)
    ap.add_argument("--phase", default="A")
    ap.add_argument("--upto", type=int, required=True)
    a = ap.parse_args()
    csv.field_size_limit(10 ** 9)
    cand = {r["cid"]: r for r in csv.DictReader((C / "candidates.csv").open())}
    rank = [r["cid"] for r in csv.DictReader((C / "screening" / f"rank_v{a.version}.csv").open())]
    out = C / "screening" / "llm"; out.mkdir(parents=True, exist_ok=True)
    cl = lambda s: (s or "").replace("�", "?").replace("\n", " ").strip()
    n = 0
    for b in range(a.upto // B):
        p = out / f"batch_{a.phase}{b + 1:03d}.txt"
        if p.exists():
            continue
        ids = rank[b * B:(b + 1) * B]
        lines = [f"# Batch {a.phase}{b + 1:03d}: {len(ids)} records. One block per record.\n"]
        for j, c in enumerate(ids, 1):
            r = cand[c]
            lines.append(f"\n[{j}] cid: {c}\nTitle: {cl(r['title'])}\nYear: {r['year']} | Venue: {cl(r['venue'])} "
                         f"| Type: {r['type']}\nAbstract: {cl(r['abstract']) or '(none)'}\n")
        p.write_text("".join(lines)); (out / f"batch_{a.phase}{b + 1:03d}.cids").write_text("\n".join(ids) + "\n")
        n += 1
    print(f"{n} new batches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
