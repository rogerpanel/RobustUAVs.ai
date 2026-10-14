#!/usr/bin/env python3
"""S1 of the Paper II runbook: PRISMA 2020 identification counts.

Writes corpus/prisma_counts.csv with columns stage,n, for the stages the
runbook names: identified, duplicates, screened, full-text, included.

  identified  OpenAlex records retrieved (lines of search_raw.jsonl) plus rows
              appended to candidates.csv from other databases (IEEE Xplore,
              ACM DL, Scopus, Web of Science), recognised by an empty openalex
              column.
  duplicates  identified minus the unique records in candidates.csv, which
              search_corpus.py dedup produces by merging on DOI or on title
              (dedup_groups); this script does not re-derive the grouping.
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
import gzip
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _lines(path: Path) -> int:
    """Records in a raw file, read from the .gz copy when only that exists."""
    if not path.exists() and path.with_suffix(".jsonl.gz").exists():
        path = path.with_suffix(".jsonl.gz")
    if not path.exists():
        return 0
    opener = gzip.open if path.suffix == ".gz" else open
    return sum(1 for line in opener(path, "rt") if line.strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=HERE.parent / "corpus")
    ap.add_argument("--search", default="search_raw.jsonl", help="database-search raw file")
    ap.add_argument("--venues", nargs="+", default=["venue_raw.jsonl"], help="venue-sweep raw files")
    a = ap.parse_args()
    cand = a.corpus / "candidates.csv"
    n_search = _lines(a.corpus / a.search)
    if not n_search or not cand.exists():
        print(f"[S1] not run yet: need search_raw.jsonl(.gz) and candidates.csv in {a.corpus}. "
              "Run search_corpus.py search and dedup first. Nothing written.")
        return 1
    per_venue_file = {v: _lines(a.corpus / v) for v in a.venues}
    n_venue = sum(per_venue_file.values())

    csv.field_size_limit(10 ** 8)
    rows = list(csv.DictReader(cand.open()))
    external = [r for r in rows if not (r.get("openalex") or "").strip()]
    identified = n_search + n_venue + len(external)
    unique = len(rows)          # dedup_groups() in search_corpus.py is authoritative

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
        w.writerow(["duplicates", identified - unique])
        w.writerow(["screened", ""])
        w.writerow(["full-text", ""])
        w.writerow(["included", ""])
        w.writerow(["identified_openalex", n_search])
        w.writerow(["identified_venues", n_venue])
        w.writerow(["identified_external", len(external)])
        w.writerow(["truncated_queries", truncated])
        for v, n in per_venue_file.items():
            w.writerow([f"identified_{v.split('.')[0]}", n])
    print(f"[S1] identified {identified} (search {n_search}, venue sweeps {n_venue}, "
          f"other databases {len(external)}); duplicates {identified - unique}; "
          f"{unique} records to screen; {truncated} queries truncated")
    print(f"[S1] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
