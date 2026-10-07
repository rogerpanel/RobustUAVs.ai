#!/usr/bin/env python3
"""Apply the logged adjudication to coder C1 and write codes_ADJ.csv.
Every change is a row in corpus/adjudication.csv with its rationale; the
adjudicated file is what all downstream analysis consumes."""
import csv
from pathlib import Path
C = Path(__file__).resolve().parent.parent / "corpus"
rows = list(csv.DictReader(open(C / "codes_C1.csv")))
by = {r["gid"]: r for r in rows}
n = 0
for a in csv.DictReader(open(C / "adjudication.csv")):
    by[a["gid"]][a["field"]] = a["value"]; n += 1
with open(C / "codes_ADJ.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
print(f"adjudicated: {n} field changes over {len({a['gid'] for a in csv.DictReader(open(C/'adjudication.csv'))})} papers")
