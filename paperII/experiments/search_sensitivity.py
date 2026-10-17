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


def raw_titles(names=("search_raw.jsonl", "venue_raw.jsonl")) -> list[str]:
    out = []
    for name in names:
        p = C / name
        if not p.exists() and p.with_suffix(".jsonl.gz").exists():
            p = p.with_suffix(".jsonl.gz")
        if not p.exists():
            continue
        opener = gzip.open if p.suffix == ".gz" else open
        out += [norm(json.loads(line).get("title")) for line in opener(p, "rt") if line.strip()]
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", nargs="+", default=["search_raw.jsonl", "venue_raw.jsonl"],
                    help="raw files in corpus/ that make up the search being evaluated")
    ap.add_argument("--label", default="rev0", help="name of the search revision, e.g. rev0, rev1")
    a = ap.parse_args()
    titles = raw_titles(a.raw)
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
    def gnum(p):
        return int(re.sub(r"\D", "", p["gid"]) or 0)
    # F2 split, fixed before the revision: odd gid = development half (terms chosen
    # from its misses), even gid = held-out half (recall reported, never inspected).
    scopes = (("tier A", lambda p: tier.get(p["gid"]) == "A"), ("tier B", lambda p: tier.get(p["gid"]) == "B"),
              ("all", lambda p: True), ("dev (odd gid)", lambda p: gnum(p) % 2 == 1),
              ("held-out (even gid)", lambda p: gnum(p) % 2 == 0),
              ("held-out tier A", lambda p: gnum(p) % 2 == 0 and tier.get(p["gid"]) == "A"))
    for scope, keep in scopes:
        sel = [p for p in pilot if keep(p)]
        hit = [p for p in sel if found(p["title"])]
        rows.append(dict(search=a.label, scope=scope, found=len(hit), n=len(sel),
                         recall=round(len(hit) / len(sel), 4) if sel else ""))
        print(f"[sensitivity] {a.label} {scope:<20} {len(hit):>3}/{len(sel):<3} = {len(hit) / max(1, len(sel)):.0%}")
    misses = [dict(search=a.label, gid=p["gid"], tier=tier.get(p["gid"], ""), year=p["year"], venue=p["venue"],
                   title=p["title"]) for p in pilot if not found(p["title"])]

    R.mkdir(parents=True, exist_ok=True)
    def merge(path, new, fields):            # keep other revisions' rows, replace this one's
        old = [r for r in csv.DictReader(path.open())] if path.exists() else []
        old = [dict(r, search=r.get("search") or "rev0") for r in old if (r.get("search") or "rev0") != a.label]
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
            w.writeheader(); w.writerows(old + new)
    merge(R / "search_sensitivity.csv", rows, ["search", "scope", "found", "n", "recall"])
    merge(C / "search_misses.csv", misses, ["search", "gid", "tier", "year", "venue", "title"])
    print(f"[sensitivity] {len(misses)} misses -> {C / 'search_misses.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
