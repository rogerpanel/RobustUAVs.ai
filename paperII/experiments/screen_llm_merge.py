#!/usr/bin/env python3
"""S2 amendment 2: merge the LLM screeners' batch outputs and evaluate the
stopping rule.

Inputs   corpus/screening/llm/batch_<P><nnn>.cids   the records of each batch
         corpus/screening/llm/L1_<P><nnn>.csv, L2_...  cid,include,reason
Checks   every output covers exactly its batch's cids, include in {0,1};
         a batch failing the check is reported and left out (re-run it).
Outputs  corpus/screening/screen_L1.csv, screen_L2.csv  (cid,include,reason,batch)
         corpus/screening/decisions.csv  consensus in screening order, with the
             stratum (core = batches A, ranks 1-2,750; sample = batches S, the
             simple random sample of the remainder, amendment 3):
             include = 1 unless BOTH screeners exclude (amendment 2)
         results/screening_status.csv   counts, kappa, the core's run state, the
             remainder estimate with a 95% Clopper-Pearson interval, and where
             the held-out pilot papers fell (a check only)

Usage:  python3 screen_llm_merge.py
"""
from __future__ import annotations

import csv
import re
import sys

from scipy.stats import beta
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parent / "corpus"
L = C / "screening" / "llm"
R = HERE.parent / "results"
sys.path.insert(0, str(HERE))
import search_sensitivity as SS  # noqa: E402

PHASE_A_MIN, RUN_A, RUN_B = 2538, 250, 100
N_REMAINDER = 22623


def cp(k, n, a=0.05):
    lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
    return lo, hi


def kappa(pairs):
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(a == b for a, b in pairs) / n
    p1 = sum(a for a, _ in pairs) / n; p2 = sum(b for _, b in pairs) / n
    pe = p1 * p2 + (1 - p1) * (1 - p2)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def main() -> int:
    csv.field_size_limit(10 ** 9)
    batches = sorted(p.stem.replace("batch_", "") for p in L.glob("batch_*.cids"))
    out = {"L1": [], "L2": []}
    order, bad, pending = [], [], []
    for b in batches:
        cids = (L / f"batch_{b}.cids").read_text().split()
        got = {}
        for who in ("L1", "L2"):
            p = L / f"{who}_{b}.csv"
            if not p.exists():
                pending.append(f"{who}_{b}"); continue
            rows = list(csv.DictReader(p.open()))
            ids = [r["cid"].strip() for r in rows]
            ok = (sorted(ids) == sorted(cids) and all(r["include"].strip() in ("0", "1") for r in rows))
            if not ok:
                bad.append(f"{who}_{b}: {len(rows)} rows, {len(set(ids) & set(cids))}/{len(cids)} cids match")
                continue
            got[who] = {r["cid"].strip(): (int(r["include"]), r["reason"].strip()) for r in rows}
        if len(got) == 2:
            order += [(c, b) for c in cids]
            for who in ("L1", "L2"):
                out[who] += [(c, *got[who][c], b) for c in cids]
    for who in ("L1", "L2"):
        with (C / "screening" / f"screen_{who}.csv").open("w", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n"); w.writerow(["cid", "include", "reason", "batch"])
            w.writerows(out[who])
    d1 = {c: i for c, i, _, _ in out["L1"]}; d2 = {c: i for c, i, _, _ in out["L2"]}
    run = 0; inc = 0
    with (C / "screening" / "decisions.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["cid", "include", "L1", "L2", "batch", "stratum"])
        for c, b in order:
            i = int(d1[c] or d2[c]); inc += i
            if b.startswith("A"):
                run = 0 if i else run + 1
            w.writerow([c, i, d1[c], d2[c], b, "core" if b.startswith("A") else "sample"])
    pairs = [(d1[c], d2[c]) for c, _ in order]
    # held-out pilot papers (even gid): screened? included? -- a check, never an input
    cand = {r["cid"]: r["title"] for r in csv.DictReader((C / "candidates.csv").open())}
    gold = list(csv.DictReader((C / "corpus_index.csv").open()))
    key = {SS.strip_note(g["title"])[:SS.PREFIX]: g["gid"] for g in gold}
    gnum = lambda g: int(re.sub(r"\D", "", g) or 0)
    held = {c: key[SS.strip_note(t)[:SS.PREFIX]] for c, t in cand.items()
            if SS.strip_note(t)[:SS.PREFIX] in key and gnum(key[SS.strip_note(t)[:SS.PREFIX]]) % 2 == 0}
    dec = {c: int(d1[c] or d2[c]) for c, _ in order}
    h_scr = [c for c in held if c in dec]; h_inc = [c for c in h_scr if dec[c]]
    n = len(order)
    core = [c for c, b in order if b.startswith("A")]; samp = [c for c, b in order if b.startswith("S")]
    k_s = sum(dec[c] for c in samp); lo, hi = cp(k_s, len(samp)) if samp else (float("nan"),) * 2
    p_s = k_s / len(samp) if samp else float("nan")
    rows_s = [("core_screened", len(core)), ("core_included", sum(dec[c] for c in core)),
              ("sample_screened", len(samp)), ("sample_included", k_s),
              ("sample_include_rate", f"{p_s:.4f}"), ("sample_rate_ci95", f"{lo:.4f}-{hi:.4f}"),
              ("remainder_size", N_REMAINDER),
              ("remainder_includes_est", round(N_REMAINDER * p_s) if samp else ""),
              ("remainder_includes_ci95", f"{round(N_REMAINDER * lo)}-{round(N_REMAINDER * hi)}" if samp else "")]
    rows = [("batches_merged", sum(1 for b in batches if not any(x.endswith(b) for x in pending + bad))),
            ("batches_pending", len(pending)), ("batches_invalid", len(bad)),
            ("screened", n), ("included_consensus", inc), ("excluded_both", n - inc),
            ("L1_includes", sum(d1[c] for c, _ in order)), ("L2_includes", sum(d2[c] for c, _ in order)),
            ("disagreements", sum(a != b for a, b in pairs)), ("kappa_L1_L2", f"{kappa(pairs):.3f}"),
            ("current_run_double_exclude", run),
            ("phaseA_min_met", int(n >= PHASE_A_MIN)), ("phaseA_run_met", int(run >= RUN_A)),
            ("heldout_pilot_in_candidates", len(held)), ("heldout_pilot_screened", len(h_scr)),
            ("heldout_pilot_included", len(h_inc))] + rows_s
    R.mkdir(exist_ok=True)
    with (R / "screening_status.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["metric", "value"]); w.writerows(rows)
    for k, v in rows:
        print(f"{k:<30} {v}")
    for x in bad:
        print("INVALID", x)
    missed = [held[c] for c in h_scr if not dec[c]]
    if missed:
        print("held-out pilot papers excluded by both:", ", ".join(sorted(missed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
