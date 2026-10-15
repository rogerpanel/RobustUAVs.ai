#!/usr/bin/env python3
"""Build the record list the screening page shows (records.json).

The page shows records in the order of the current ranking. Records already
screened stay at the top, in the order they were screened (from
corpus/screening/decisions.csv), so the stopping rule's "consecutive
excludes" are counted over a stable sequence; the unscreened remainder follows
in the order of rank_v<N>.csv. Only the first --top unscreened records are
shipped (the page is limited to 16 MB); the next build extends the list.
The file carries no pilot-set marks and no LLM output.

Usage:  python3 screen_page_data.py --version 1 --top 6000 --out records.json
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

C = Path(__file__).resolve().parent.parent / "corpus"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--top", type=int, default=6000)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    csv.field_size_limit(10 ** 9)
    cand = {r["cid"]: r for r in csv.DictReader((C / "candidates.csv").open())}
    done = []
    dp = C / "screening" / "decisions.csv"
    if dp.exists():
        done = [r["cid"] for r in csv.DictReader(dp.open())]
    rank = [r["cid"] for r in csv.DictReader((C / "screening" / f"rank_v{a.version}.csv").open())]
    order = done + [c for c in rank if c not in set(done)][: a.top]
    recs = []
    for k, cid in enumerate(order, 1):
        r = cand[cid]
        # U+FFFD marks characters already lost upstream in the API record; show them as "?"
        cl = lambda s: (s or "").replace("\ufffd", "?")
        recs.append({"k": k, "c": cid, "t": cl(r["title"]), "y": r["year"], "v": cl(r["venue"]), "ty": r["type"],
                     "a": cl(r["abstract"]), "d": r["doi"]})
    out = {"version": a.version, "made": "rank_v%d" % a.version, "n_candidates": len(cand),
           "n_screened_prefix": len(done), "records": recs}
    a.out.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"{len(recs)} records ({len(done)} already screened) -> {a.out} "
          f"({a.out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
