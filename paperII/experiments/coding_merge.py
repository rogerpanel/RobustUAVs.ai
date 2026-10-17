#!/usr/bin/env python3
"""Amendment 4: merge the LLM coders' batch outputs (corpus/coding/C{1,2}_C<nnn>.csv).

Checks every output against its batch (corpus/coding/batch_C<nnn>.cids): one
row per cid, eligible in {0,1}, and closed-vocabulary values for every coded
field (codebook v1.1; class from classes.csv or NEW:<label>). A batch that
fails is listed and left out.

Outputs  corpus/codes_full_C1.csv, codes_full_C2.csv   one row per cid
         corpus/coding/disagreements.csv               cid, field, C1, C2 (for ADJ)
         results/coding_status.csv                     counts and per-field agreement

Usage:   python3 coding_merge.py                 (main study: batch_C<nnn>)
         python3 coding_merge.py --iter 1        (snowballing iteration 1: batch_S1C<nnn>;
                                                  outputs corpus/snowball/iter1_codes_full_C{1,2}.csv,
                                                  coding/disagreements_S1C.csv, results/coding_status_S1C.csv)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

C = Path(__file__).resolve().parent.parent / "corpus"
D = C / "coding"
R = C.parent / "results"
FIELDS = ["class", "tier", "component", "scope", "modality", "perturbation", "lifts", "assumption", "evidence"]
VOCAB = {"tier": {"A", "B"}, "component": {"perception", "estimation", "control", "planning", "end2end"},
         "scope": {"in", "tr", "op", "pop"}, "modality": {"A", "Ac", "P", "E", "X"},
         "perturbation": {"norm", "semantic", "patch", "disturbance", "distribution", "poisoning", "none"},
         "assumption": {"U", "S", "SE", "SEC"}, "evidence": {"proof", "measured", "simulated", "modelled"}}
LIFTS = {"L_dyn", "L_hor", "L_gen", "L_op", "L_rate", "L_conc", "L_sup", "L_mon", "none"}
COLS = ["cid", "eligible", "elig_reason"] + FIELDS + ["note", "batch"]


def norm_lifts(v: str) -> str:
    xs = sorted({x.strip() for x in v.replace(",", ";").split(";") if x.strip()})
    return ";".join(xs) if xs else "none"


def check(row: dict, classes: set) -> str:
    if row["eligible"] not in ("0", "1"):
        return "eligible"
    if row["eligible"] == "0":
        return ""
    for f, vs in VOCAB.items():
        if row[f] not in vs:
            return f
    if not set(row["lifts"].split(";")) <= LIFTS:
        return "lifts"
    if row["class"] not in classes and not row["class"].startswith("NEW:"):
        return "class"
    return ""


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--iter", type=int, default=0)
    it = ap.parse_args().iter
    pre = f"S{it}C" if it else "C"
    codes_out = (lambda who: C / "snowball" / f"iter{it}_codes_full_{who}.csv") if it else \
        (lambda who: C / f"codes_full_{who}.csv")
    dis_out = D / (f"disagreements_{pre}.csv" if it else "disagreements.csv")
    stat_out = R / (f"coding_status_{pre}.csv" if it else "coding_status.csv")
    csv.field_size_limit(10 ** 9)
    classes = {r["class"] for r in csv.DictReader((C / "classes.csv").open())}
    out = {"C1": {}, "C2": {}}
    bad, pending = [], []
    for cf in sorted(D.glob(f"batch_{pre}[0-9]*.cids")):
        b = cf.stem.replace("batch_", "")
        cids = cf.read_text().split()
        got = {}
        for who in ("C1", "C2"):
            p = D / f"{who}_{b}.csv"
            if not p.exists():
                pending.append(f"{who}_{b}"); continue
            rows = []
            for r in csv.DictReader(p.open()):
                r = {k: (r.get(k) or "").strip() for k in COLS[:-1]}
                if r["eligible"] == "1":
                    r["lifts"] = norm_lifts(r["lifts"])
                rows.append(r)
            errs = [(r["cid"], check(r, classes)) for r in rows if check(r, classes)]
            if sorted(r["cid"] for r in rows) != sorted(cids) or errs:
                bad.append(f"{who}_{b}: rows {len(rows)}/{len(cids)}; invalid {errs[:3]}"); continue
            got[who] = {r["cid"]: {**r, "batch": b} for r in rows}
        if len(got) == 2:
            for who in ("C1", "C2"):
                out[who].update(got[who])
    for who in ("C1", "C2"):
        with codes_out(who).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLS, lineterminator="\n"); w.writeheader()
            w.writerows(out[who][c] for c in sorted(out[who]))
    dis, agree = [], {f: [0, 0] for f in ["eligible"] + FIELDS}
    for c in sorted(out["C1"]):
        a, b = out["C1"][c], out["C2"][c]
        agree["eligible"][0] += a["eligible"] == b["eligible"]; agree["eligible"][1] += 1
        if a["eligible"] != b["eligible"]:
            dis.append((c, "eligible", a["eligible"], b["eligible"]))
        if a["eligible"] == b["eligible"] == "1":
            for f in FIELDS:
                agree[f][0] += a[f] == b[f]; agree[f][1] += 1
                if a[f] != b[f]:
                    dis.append((c, f, a[f], b[f]))
    with dis_out.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["cid", "field", "C1", "C2"]); w.writerows(dis)
    rows = [("papers_merged", len(out["C1"])), ("batches_pending", len(pending)), ("batches_invalid", len(bad)),
            ("eligible_C1", sum(r["eligible"] == "1" for r in out["C1"].values())),
            ("eligible_C2", sum(r["eligible"] == "1" for r in out["C2"].values())),
            ("disagreements", len(dis))] + [(f"agree_{f}", f"{k}/{n}") for f, (k, n) in agree.items()]
    R.mkdir(exist_ok=True)
    with stat_out.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["metric", "value"]); w.writerows(rows)
    for k, v in rows:
        print(f"{k:<22} {v}")
    for x in bad:
        print("INVALID", x)
    return 0


if __name__ == "__main__":
    sys.exit(main())
