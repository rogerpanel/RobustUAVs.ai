#!/usr/bin/env python3
"""Amendment 4: apply the adjudicator's (ADJ) decisions and write the final codes.

Inputs   corpus/codes_full_C1.csv, codes_full_C2.csv      (coding_merge.py)
         corpus/coding/batch_ADJ<nnn>.cids                (adjudication_prep.py)
         corpus/coding/ADJ_ADJ<nnn>.csv                   cid, field, value, rationale

Rules (as given to ADJ, see adjudication_prep.py):
  - C1 and C2 agree on eligible = 0: excluded, no adjudication;
  - eligibility disagreement: ADJ's `eligible` row decides; if 1, the eligible
    coder's coding is the start and ADJ's field rows replace its values;
  - both eligible: agreed fields are kept, each disagreeing field takes ADJ's
    value. An ADJ row for an agreed field breaks the rule: it is logged and
    ignored. A disagreeing field without an ADJ row is left unresolved.
Every final row is checked against the codebook vocabulary (coding_merge.check).

Outputs  corpus/codes_full_final.csv              one row per coded paper
         corpus/coding/adjudication_log.csv    every ADJ decision with C1, C2 and its rationale
         results/adjudication_status.csv       counts
Usage:   python3 adjudication_merge.py
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

from coding_merge import FIELDS, check, norm_lifts

C = Path(__file__).resolve().parent.parent / "corpus"
D = C / "coding"
R = C.parent / "results"
COLS = ["cid", "eligible", "elig_reason"] + FIELDS + ["resolved_by"]


def clean(field: str, v: str) -> str:
    v = v.strip().strip('"').strip()
    if field == "lifts":
        return norm_lifts(v)
    if field == "class" and v.upper().startswith("NEW:"):
        return "NEW:" + v[4:].strip()
    return v


def main() -> int:
    csv.field_size_limit(10 ** 9)
    classes = {r["class"] for r in csv.DictReader((C / "classes.csv").open())}
    c1 = {r["cid"]: r for r in csv.DictReader((C / "codes_full_C1.csv").open())}
    c2 = {r["cid"]: r for r in csv.DictReader((C / "codes_full_C2.csv").open())}
    adj, pending, expected = {}, [], set()
    for cf in sorted(D.glob("batch_ADJ*.cids")):
        b = cf.stem.replace("batch_", "")
        cids = set(cf.read_text().split()); expected |= cids
        p = D / f"ADJ_{b}.csv"
        if not p.exists():
            pending.append(b); continue
        for r in csv.DictReader(p.open()):
            cid, f = r["cid"].strip(), r["field"].strip()
            if cid not in cids:
                print(f"WARNING {b}: cid {cid} not in batch, ignored"); continue
            adj.setdefault(cid, {})[f] = (clean(f, r["value"]), r["rationale"].strip(), b)
    final, log, stat = [], [], Counter()
    for cid in sorted(c1):
        x, y = c1[cid], c2[cid]
        a = adj.get(cid, {})
        if x["eligible"] == y["eligible"] == "0":
            final.append({**{k: x[k] for k in ("cid", "eligible", "elig_reason")}, **{f: "" for f in FIELDS},
                          "resolved_by": "C1=C2"}); stat["excluded_agreed"] += 1; continue
        if x["eligible"] != y["eligible"]:
            stat["elig_disagree"] += 1
            if "eligible" not in a:
                stat["unresolved_eligibility"] += 1; continue
            e, why, b = a["eligible"]
            log.append({"cid": cid, "field": "eligible", "C1": x["eligible"], "C2": y["eligible"], "ADJ": e,
                        "choice": "C1" if e == x["eligible"] else "C2", "rationale": why, "batch": b})
            stat[f"elig_adj_{e}"] += 1
            if e != "1":
                final.append({"cid": cid, "eligible": "0", "elig_reason": why, **{f: "" for f in FIELDS},
                              "resolved_by": "ADJ"}); continue
            base = x if x["eligible"] == "1" else y
            row = {"cid": cid, "eligible": "1", "elig_reason": "", **{f: base[f] for f in FIELDS}, "resolved_by": "ADJ"}
            for f in FIELDS:
                if f in a:
                    v, why, b = a[f]
                    stat["elig_field_revised"] += v != base[f]
                    row[f] = v
        else:
            row = {"cid": cid, "eligible": "1", "elig_reason": "", **{f: x[f] for f in FIELDS},
                   "resolved_by": "C1=C2"}
            for f in FIELDS:
                if x[f] == y[f]:
                    if f in a:
                        stat["rule_violation_agreed_field"] += 1
                        print(f"RULE {cid} {f}: ADJ changed an agreed field, ignored")
                    continue
                stat["field_disagree"] += 1
                if f not in a:
                    stat["unresolved_field"] += 1; row[f] = ""; continue
                v, why, b = a[f]
                ch = "C1" if v == x[f] else "C2" if v == y[f] else "third"
                stat[f"field_choice_{ch}"] += 1
                log.append({"cid": cid, "field": f, "C1": x[f], "C2": y[f], "ADJ": v, "choice": ch,
                            "rationale": why, "batch": b})
                row[f] = v; row["resolved_by"] = "ADJ"
        err = check({**row, "note": ""}, classes)
        if err:
            stat["invalid_final"] += 1; print(f"INVALID {cid}: {err} = {row.get(err)!r}")
        final.append(row)
    with (C / "codes_full_final.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, lineterminator="\n"); w.writeheader(); w.writerows(final)
    with (D / "adjudication_log.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["cid", "field", "C1", "C2", "ADJ", "choice", "rationale", "batch"],
                           lineterminator="\n"); w.writeheader(); w.writerows(log)
    rows = [("papers_coded", len(c1)), ("papers_to_adjudicate", len(expected)), ("adj_batches_pending", len(pending)),
            ("papers_final", len(final)), ("eligible_final", sum(r["eligible"] == "1" for r in final))]
    rows += sorted(stat.items())
    R.mkdir(exist_ok=True)
    with (R / "adjudication_status.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["metric", "value"]); w.writerows(rows)
    for k, v in rows:
        print(f"{k:<30} {v}")
    if pending:
        print("pending:", " ".join(pending))
    return 0


if __name__ == "__main__":
    sys.exit(main())
