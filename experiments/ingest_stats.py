#!/usr/bin/env python3
"""Corpus-wide ingest statistics -> results/ingest_stats.csv.

Reads the staged (gitignored) adapter outputs and records, per source, the
real event/window counts and class distribution the paper tables cite. Run
after experiments/run_real_corpus.sh; sources with no staging output are
recorded as absent (never invented).

Provenance: real-corpus for whatever was staged when it ran; the CSV itself
is committed so paper tables are machine-generated from it.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STG = REPO / "data" / "staging"
OUT = REPO / "results" / "ingest_stats.csv"

SOURCES = {
    "uav_ew_bench_2026": ["ewbench"],
    "uav_attack_whelan": ["whelan_real"],
    "uavids_2025": ["uavids_0"],
    "hcrl_uavcan": [f"hcrl/type{i}" for i in range(1, 11)],
    "uav_cas": ["uavcas_stat", "uavcas_stat_cfg"],
}


def count_dir(d: Path):
    ev = d / "events.jsonl"
    wn = d / "windows.jsonl"
    n_ev = n_wn = 0
    dist = Counter()
    if ev.exists():
        for line in open(ev):
            if line.strip():
                n_ev += 1
                dist[json.loads(line)["label_class"]] += 1
    if wn.exists():
        n_wn = sum(1 for l in open(wn) if l.strip())
    return n_ev, n_wn, dist


def main() -> int:
    rows = []
    for source, dirs in SOURCES.items():
        n_ev = n_wn = 0
        dist = Counter()
        present = False
        for sub in dirs:
            d = STG / sub
            if d.exists():
                present = True
                e, w, c = count_dir(d)
                n_ev += e
                n_wn += w
                dist += c
        rows.append({
            "source": source,
            "staged": int(present),
            "events": n_ev, "windows": n_wn,
            "class_distribution": ";".join(f"{k}:{v}" for k, v in
                                           sorted(dist.items())) or "absent",
        })
        print(f"  {source:20} staged={present} events={n_ev} windows={n_wn}")
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[ingest-stats] -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
