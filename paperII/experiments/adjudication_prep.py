#!/usr/bin/env python3
"""Amendment 4: prepare LLM adjudication (ADJ) batches.

For every paper where C1 and C2 disagree, ADJ sees the full text and a table
of both codings. Rules given to ADJ (see the batch header):
  - eligibility disagreement: ADJ decides `eligible`; if it decides 1, the
    eligible coder's coding is the starting point and ADJ may revise any field
    (only one coder coded it), with a rationale for each change;
  - otherwise ADJ resolves exactly the disagreeing fields and may not touch a
    field on which C1 and C2 agree.

Usage:  python3 adjudication_prep.py --fulltext DIR --out DIR [--per 5]
Writes  <out>/batch_ADJ<nnn>.txt and .cids  (full texts stay outside the repository)
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

C = Path(__file__).resolve().parent.parent / "corpus"
FIELDS = ["class", "tier", "component", "scope", "modality", "perturbation", "lifts", "assumption", "evidence"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fulltext", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--per", type=int, default=5)
    a = ap.parse_args()
    csv.field_size_limit(10 ** 9)
    c1 = {r["cid"]: r for r in csv.DictReader((C / "codes_full_C1.csv").open())}
    c2 = {r["cid"]: r for r in csv.DictReader((C / "codes_full_C2.csv").open())}
    cand = {r["cid"]: r for r in csv.DictReader((C / "candidates.csv").open())}
    todo = []
    for cid in sorted(c1):
        x, y = c1[cid], c2[cid]
        if x["eligible"] != y["eligible"]:
            todo.append((cid, "eligibility"))
        elif x["eligible"] == "1" and any(x[f] != y[f] for f in FIELDS):
            todo.append((cid, "fields"))
    a.out.mkdir(parents=True, exist_ok=True)
    for b in range(0, len(todo), a.per):
        chunk = todo[b:b + a.per]; k = b // a.per + 1
        parts = [f"# Adjudication batch ADJ{k:03d}: {len(chunk)} papers\n"]
        for j, (cid, kind) in enumerate(chunk, 1):
            x, y = c1[cid], c2[cid]
            t = (a.fulltext / f"{cid}.txt").read_text(errors="replace")
            rows = ["| field | C1 | C2 | status |", "|---|---|---|---|",
                    f"| eligible | {x['eligible']} ({x['elig_reason']}) | {y['eligible']} ({y['elig_reason']}) | "
                    f"{'DISAGREE' if x['eligible'] != y['eligible'] else 'agreed'} |"]
            for f in FIELDS:
                st = "DISAGREE" if x[f] != y[f] else "agreed"
                rows.append(f"| {f} | {x[f]} | {y[f]} | {st} |")
            parts.append(f"\n\n========== PAPER [{j}] cid: {cid} ({kind} disagreement) ==========\n"
                         f"Title: {cand[cid]['title']}\n\nCodings:\n" + "\n".join(rows) +
                         f"\nC1 note: {x['note']}\nC2 note: {y['note']}\n\n"
                         f"Full text (first 80,000 characters):\n\n{t[:80000]}\n")
        (a.out / f"batch_ADJ{k:03d}.txt").write_text("".join(parts))
        (a.out / f"batch_ADJ{k:03d}.cids").write_text("\n".join(c for c, _ in chunk) + "\n")
    n_e = sum(1 for _, k in todo if k == "eligibility")
    print(f"{len(todo)} papers to adjudicate ({n_e} eligibility, {len(todo) - n_e} fields) "
          f"-> {(len(todo) + a.per - 1) // a.per} batches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
