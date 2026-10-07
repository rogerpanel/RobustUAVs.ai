#!/usr/bin/env python3
"""S1 of the Paper II runbook: PRISMA 2020 identification counts.

Writes corpus/prisma_counts.csv with columns stage,n, for the stages the
runbook names: identified, duplicates, screened, full-text, included.

  identified  OpenAlex records retrieved (lines of search_raw.jsonl) plus rows
              appended to candidates.csv from other databases (IEEE Xplore,
              ACM DL, Scopus, Web of Science), recognised by an empty openalex
              column.
  duplicates  identified minus the number of distinct records, keyed exactly as
              search_corpus.py dedup keys them (DOI if present, else the
              normalised title), so the count matches the candidates file.
  screened, full-text, included
              left empty until S2-S4 have produced decisions. They are filled
              from the screening and inclusion files when those exist; this
              script never infers them.

Breakdown rows (identified_openalex, identified_external, truncated_queries)
follow the five stages so the flow diagram can show where records came from
and whether any query hit its page cap.

Stdlib only. Usage:  python3 prisma_counts.py [--corpus DIR]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from search_corpus import norm_title  # noqa: E402  (same key as dedup)


def key(doi: str, title: str) -> str:
    return (doi or "").lower() or norm_title(title)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=HERE.parent / "corpus")
    a = ap.parse_args()
    raw, cand = a.corpus / "search_raw.jsonl", a.corpus / "candidates.csv"
    if not raw.exists() or not cand.exists():
        print(f"[S1] not run yet: need {raw.name} and {cand.name} in {a.corpus}. "
              "Run search_corpus.py search and dedup first. Nothing written.")
        return 1

    n_oa = sum(1 for line in raw.open() if line.strip())
    rows = list(csv.DictReader(cand.open()))
    external = [r for r in rows if not (r.get("openalex") or "").strip()]
    oa_keys = set()
    for line in raw.open():
        if line.strip():
            r = json.loads(line)
            oa_keys.add(key(r.get("doi", ""), r.get("title", "")))
    all_keys = oa_keys | {key(r.get("doi", ""), r.get("title", "")) for r in external}
    identified = n_oa + len(external)

    truncated = 0
    log = a.corpus / "search_log.jsonl"
    if log.exists():
        for line in log.open():
            e = json.loads(line)
            if e.get("total_hits") is not None and e.get("cap") and e["total_hits"] > e["cap"]:
                truncated += 1

    out = a.corpus / "prisma_counts.csv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["stage", "n"])
        w.writerow(["identified", identified])
        w.writerow(["duplicates", identified - len(all_keys)])
        w.writerow(["screened", ""])
        w.writerow(["full-text", ""])
        w.writerow(["included", ""])
        w.writerow(["identified_openalex", n_oa])
        w.writerow(["identified_external", len(external)])
        w.writerow(["truncated_queries", truncated])
    print(f"[S1] identified {identified} (OpenAlex {n_oa}, other databases {len(external)}); "
          f"duplicates {identified - len(all_keys)}; {len(all_keys)} records to screen; "
          f"{truncated} queries hit the page cap")
    print(f"[S1] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
