#!/usr/bin/env python3
"""Search sensitivity: how much of the purposive pilot set the S1 search finds.

A systematic search is validated against a set of papers known to belong in
the review. Here that set is the pilot's 86 guarantees (corpus/corpus_index.csv),
split by the adjudicated tier (corpus/codes_ADJ.csv). A pilot paper counts as
found when a retrieved record (search_raw and venue_raw, before dedup) matches
its title: normalised, with a trailing parenthetical annotation such as
"(DeepPoly)" removed, compared on the first 45 characters.

Writes results/search_sensitivity.csv (scope,found,n,recall) and lists every
missed paper in corpus/search_misses.csv, so a low recall can be traced to the
query strings rather than guessed at. Stdlib only.

    python3 search_sensitivity.py
"""
from __future__ import annotations

import csv
import gzip
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
C, R = HERE.parent / "corpus", HERE.parent / "results"
PREFIX = 45


def norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def strip_note(t: str) -> str:
    return norm(re.sub(r"\s*\([^)]*\)\s*$", "", t or ""))


def raw_titles() -> list[str]:
    out = []
    for name in ("search_raw.jsonl", "venue_raw.jsonl"):
        p = C / name
        if not p.exists() and p.with_suffix(".jsonl.gz").exists():
            p = p.with_suffix(".jsonl.gz")
        if not p.exists():
            continue
        opener = gzip.open if p.suffix == ".gz" else open
        out += [norm(json.loads(line).get("title")) for line in opener(p, "rt") if line.strip()]
    return out


def main() -> int:
    titles = raw_titles()
    if not titles:
        print("[sensitivity] no search output in corpus/. Nothing written.")
        return 1
    by_head = {}
    for t in titles:
        by_head.setdefault(t[:10], []).append(t)

    def found(title: str) -> bool:
        k = strip_note(title)[:PREFIX]
        return any(x.startswith(k) or k.startswith(x[:PREFIX]) for x in by_head.get(k[:10], []))

    tier = {r["gid"]: r["tier"] for r in csv.DictReader((C / "codes_ADJ.csv").open())}
    pilot = list(csv.DictReader((C / "corpus_index.csv").open()))
    rows, misses = [], []
    for scope, keep in (("tier A", "A"), ("tier B", "B"), ("all", None)):
        sel = [p for p in pilot if keep is None or tier.get(p["gid"]) == keep]
        hit = [p for p in sel if found(p["title"])]
        rows.append(dict(scope=scope, found=len(hit), n=len(sel),
                         recall=round(len(hit) / len(sel), 4) if sel else ""))
        print(f"[sensitivity] {scope:<6} {len(hit):>3}/{len(sel):<3} = {len(hit) / max(1, len(sel)):.0%}")
    misses = [dict(gid=p["gid"], tier=tier.get(p["gid"], ""), year=p["year"], venue=p["venue"],
                   title=p["title"]) for p in pilot if not found(p["title"])]

    R.mkdir(parents=True, exist_ok=True)
    with (R / "search_sensitivity.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["scope", "found", "n", "recall"], lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    with (C / "search_misses.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["gid", "tier", "year", "venue", "title"], lineterminator="\n")
        w.writeheader(); w.writerows(misses)
    print(f"[sensitivity] {len(misses)} misses -> {C / 'search_misses.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
