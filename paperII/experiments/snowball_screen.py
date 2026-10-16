#!/usr/bin/env python3
"""Amendment 5: screening batches for a snowballing iteration, and the merge of both screeners.

An iteration with at most 3,000 new candidates is screened in full by L1 and L2 exactly as in
amendment 2 (same rule, same prompt, same 125-record batches); a record is excluded only when
both screeners exclude it. Batches list the candidates in a random order (seed 20261022 + k),
since every record is screened.

  python3 snowball_screen.py batches --iter 1     -> screening/llm/batch_N<k><nnn>.txt / .cids
  python3 snowball_screen.py merge   --iter 1     -> snowball/iter<k>_decisions.csv, iter<k>_screening_status.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

C = Path(__file__).resolve().parent.parent / "corpus"
L = C / "screening" / "llm"
B = 125


def cl(s):
    return (s or "").replace("�", "?").replace("\n", " ").strip()


def batches(k: int) -> None:
    csv.field_size_limit(10 ** 9)
    rows = list(csv.DictReader((C / "snowball" / f"iter{k}_candidates.csv").open()))
    if len(rows) > 3000:
        raise SystemExit(f"{len(rows)} candidates: amendment 5 asks for ranking and sampling above 3,000")
    order = [rows[i] for i in np.random.default_rng(20261022 + k).permutation(len(rows))]
    L.mkdir(parents=True, exist_ok=True)
    n = 0
    for b in range(0, len(order), B):
        name = f"N{k}{b // B + 1:02d}"
        p = L / f"batch_{name}.txt"
        if p.exists():
            continue
        chunk = order[b:b + B]
        lines = [f"# Batch {name}: {len(chunk)} records. One block per record.\n"]
        for j, r in enumerate(chunk, 1):
            lines.append(f"\n[{j}] cid: {r['cid']}\nTitle: {cl(r['title'])}\nYear: {r['year']} | Venue: {cl(r['venue'])} "
                         f"| Type: {r['type']}\nAbstract: {cl(r['abstract']) or '(none)'}\n")
        p.write_text("".join(lines))
        (L / f"batch_{name}.cids").write_text("\n".join(r["cid"] for r in chunk) + "\n")
        n += 1
    print(f"{n} new batches for iteration {k} ({len(rows)} records)")


def merge(k: int) -> None:
    dec, pending, bad = [], [], []
    for cf in sorted(L.glob(f"batch_N{k}*.cids")):
        b = cf.stem.replace("batch_", "")
        cids = cf.read_text().split()
        got = {}
        for who in ("L1", "L2"):
            p = L / f"{who}_{b}.csv"
            if not p.exists():
                pending.append(f"{who}_{b}"); continue
            r = {x["cid"].strip(): x["include"].strip() for x in csv.DictReader(p.open())}
            if sorted(r) != sorted(cids) or set(r.values()) - {"0", "1"}:
                bad.append(f"{who}_{b}"); continue
            got[who] = r
        if len(got) == 2:
            for c in cids:
                a, b2 = got["L1"][c], got["L2"][c]
                dec.append({"cid": c, "include": int(a == "1" or b2 == "1"), "L1": a, "L2": b2, "batch": b})
    with (C / "snowball" / f"iter{k}_decisions.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["cid", "include", "L1", "L2", "batch"], lineterminator="\n")
        w.writeheader(); w.writerows(dec)
    n = len(dec); inc = sum(d["include"] for d in dec)
    agree = sum(d["L1"] == d["L2"] for d in dec)
    p1 = sum(d["L1"] == "1" for d in dec) / n if n else 0; p2 = sum(d["L2"] == "1" for d in dec) / n if n else 0
    pe = p1 * p2 + (1 - p1) * (1 - p2)
    kappa = (agree / n - pe) / (1 - pe) if n and pe < 1 else float("nan")
    rows = [("screened", n), ("included", inc), ("excluded_both", n - inc), ("L1_includes", sum(d["L1"] == "1" for d in dec)),
            ("L2_includes", sum(d["L2"] == "1" for d in dec)), ("kappa_L1_L2", round(kappa, 3)),
            ("batches_pending", len(pending)), ("batches_invalid", len(bad))]
    with (C / "snowball" / f"iter{k}_screening_status.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["metric", "value"]); w.writerows(rows)
    for r in rows:
        print(f"{r[0]:<18} {r[1]}")
    for x in bad:
        print("INVALID", x)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("batches", "merge")); ap.add_argument("--iter", type=int, default=1)
    a = ap.parse_args()
    {"batches": batches, "merge": merge}[a.cmd](a.iter)
