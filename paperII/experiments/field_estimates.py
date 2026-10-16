#!/usr/bin/env python3
"""Amendment 6: corpus-level estimates and hypothesis quantities over the expanded field.

The expanded field is the searched corpus (strata core and remainder, amendments 3-4) plus the
snowballing strata of amendment 5 (snowball1; snowball2_core and snowball2_remainder; snowball3).
Each coded paper of stratum s stands for N_s / k_s records: N_s the stratum's estimated includes
(the screened count where the stratum was screened in full, N_rem x p_hat where it was sampled),
k_s its papers coded, eligible or not. Intervals: stratified percentile bootstrap (B = 4000;
seed 20261020 for the field estimates, 20261021 for the hypothesis quantities, as in
corpus_estimates.py and hypotheses_full.py): coded papers resampled within each stratum, and the
include count of every sampled stratum redrawn as N_rem x Binomial(m, p_hat) / m.

Outputs  results/field_strata.csv                 stratum, N, coded, eligible_coded, sampled
         results/field_estimates.csv              field, value, coded, share [lo, hi], papers [lo, hi],
                                                  share_searched (amendment 4, for comparison)
         results/type_plane_field.csv             scope x modality cells on the expanded field
         results/field_hypotheses{_C1,_C2}.csv    key, description, n_den, estimate [lo, hi], searched
Usage    python3 field_estimates.py [final|C1|C2]   (C1/C2: each coder's codes alone, all strata)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from corpus_estimates import indicators  # noqa: E402
from hypotheses_full import quantities  # noqa: E402

C = HERE.parent / "corpus"
S = C / "snowball"
R = C.parent / "results"
B = 4000


def rd(p):
    return list(csv.DictReader(p.open()))


def strata(tag: str):
    """[(name, rows, N, redraw)], redraw = (pool, m, x) for a sampled stratum, else None; and years."""
    csv.field_size_limit(10 ** 9)
    out, year = [], {}
    st = {r["metric"]: r["value"] for r in rd(R / "screening_status.csv")}
    smp = {r["cid"]: r["stratum"] for r in rd(C / "coding_sample.csv")}
    main = rd(C / f"codes_full_{tag}.csv")
    year.update({r["cid"]: r["year"] for r in rd(C / "candidates.csv")})
    pool, m, x = int(st["remainder_size"]), int(st["sample_screened"]), int(st["sample_included"])
    out.append(("core", [r for r in main if smp[r["cid"]] == "core"], float(st["core_included"]), None))
    out.append(("remainder", [r for r in main if smp[r["cid"]] == "remainder"], pool * x / m, (pool, m, x)))
    k = 1
    while (S / f"iter{k}_codes_full_{tag}.csv").exists():
        codes = rd(S / f"iter{k}_codes_full_{tag}.csv")
        ss = {r["metric"]: r["value"] for r in rd(S / f"iter{k}_screening_status.csv")}
        smp = {r["cid"]: r["stratum"] for r in rd(S / f"iter{k}_coding_sample.csv")}
        year.update({r["cid"]: r["year"] for r in rd(S / f"iter{k}_candidates.csv")})
        if "included_est" not in ss:
            out.append((f"snowball{k}", codes, float(ss["included"]), None))
        else:
            p, mm, xx = int(ss["remainder_size"]), int(ss["sample_screened"]), int(ss["sample_included"])
            out.append((f"snowball{k}_core", [r for r in codes if smp[r["cid"]].endswith("_core")],
                        float(ss["core_included"]), None))
            out.append((f"snowball{k}_remainder", [r for r in codes if smp[r["cid"]].endswith("_remainder")],
                        p * xx / mm, (p, mm, xx)))
        k += 1
    return out, year


class Boot:
    """Row weights for the point estimate and for each bootstrap replicate."""

    def __init__(self, st, seed):
        self.st = st
        self.sizes = [len(r) for _, r, _, _ in st]
        self.off = np.cumsum([0] + self.sizes)
        self.rng = np.random.default_rng(seed)

    def point(self):
        return np.concatenate([np.full(k, N / k) for (_, _, N, _), k in zip(self.st, self.sizes)])

    def draw(self):
        w = np.empty(self.off[-1])
        for j, ((_, _, N, rd_), k) in enumerate(zip(self.st, self.sizes)):
            if rd_:
                pool, m, x = rd_
                N = pool * self.rng.binomial(m, x / m) / m
            mult = np.bincount(self.rng.integers(0, k, k), minlength=k)
            w[self.off[j]:self.off[j + 1]] = mult * N / k
        return w


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "final"
    st, year = strata(tag)
    rows = [r for _, rr, _, _ in st for r in rr]
    sfx = "" if tag == "final" else f"_{tag}"
    q = lambda x: (float(np.nanquantile(x, .025)), float(np.nanquantile(x, .975)))  # noqa: E731
    if tag == "final":
        R.mkdir(exist_ok=True)
        with (R / "field_strata.csv").open("w", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n"); w.writerow(["stratum", "N", "coded", "eligible_coded", "sampled"])
            for name, rr, N, rdw in st:
                w.writerow([name, round(N, 1), len(rr), sum(r["eligible"] == "1" for r in rr), int(bool(rdw))])
        # corpus-level estimates
        ind = indicators(rows)
        keys = sorted(ind, key=lambda k: (k[0], k[1]))
        el = ind[("eligible", "1")]
        bt = Boot(st, 20261020)

        def est(w):
            tot, elw = w.sum(), (w * el).sum()
            return {k: ((w * ind[k]).sum(), (w * ind[k]).sum() / (tot if k[0] == "eligible" else elw)) for k in keys}
        e0 = est(bt.point())
        bp = {k: np.empty(B) for k in keys}; bs = {k: np.empty(B) for k in keys}
        for b in range(B):
            e = est(bt.draw())
            for k in keys:
                bp[k][b], bs[k][b] = e[k]
        searched = {(r["field"], r["value"]): r["share"] for r in rd(R / "corpus_estimates.csv")}
        out = []
        for k in keys:
            (sl, sh), (pl, ph) = q(bs[k]), q(bp[k])
            out.append({"field": k[0], "value": k[1], "coded": int(ind[k].sum()),
                        "share": round(e0[k][1], 4), "share_lo": round(sl, 4), "share_hi": round(sh, 4),
                        "papers": round(e0[k][0]), "papers_lo": round(pl), "papers_hi": round(ph),
                        "share_searched": searched.get(k, "")})
        with (R / "field_estimates.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n"); w.writeheader(); w.writerows(out)
        tp = [{"scope": r["value"].split("/")[0], "modality": r["value"].split("/")[1], "coded": r["coded"],
               "share": r["share"], "share_lo": r["share_lo"], "share_hi": r["share_hi"], "papers": r["papers"],
               "share_searched": r["share_searched"]} for r in out if r["field"] == "scope_x_modality"]
        with (R / "type_plane_field.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(tp[0]), lineterminator="\n"); w.writeheader(); w.writerows(tp)
        for name, rr, N, rdw in st:
            print(f"stratum {name:<20} N={N:8.1f} coded {len(rr):3d}{' (sampled)' if rdw else ''}")
        for r in out:
            if r["field"] in ("eligible", "tier", "scope", "modality", "component", "assumption") or \
                    (r["field"] == "class" and r["share"] >= 0.04):
                print(f"{r['field']:<11} {r['value']:<28} {r['share']:.3f} [{r['share_lo']:.3f},{r['share_hi']:.3f}]"
                      f" ~{r['papers']}  searched {r['share_searched']}")
    # hypothesis quantities on the eligible coded papers of all strata
    elig = [r["eligible"] == "1" for r in rows]
    erows = [r for r, e in zip(rows, elig) if e]
    Q = quantities(erows, year)
    E = np.array(elig)
    bt = Boot(st, 20261021)

    def ratio(num, den, w):
        d = (w * den).sum()
        return (w * num).sum() / d if d > 0 else float("nan")
    w0 = bt.point()[E]
    boot = np.empty((B, len(Q)))
    for b in range(B):
        wb = bt.draw()[E]
        boot[b] = [ratio(num, den, wb) for _, _, num, den, _ in Q]
    searched = {r["key"]: r["estimate"] for r in rd(R / f"hypotheses_full{sfx}.csv")}
    out = []
    for j, (k, desc, num, den, _) in enumerate(Q):
        lo, hi = q(boot[:, j])
        out.append({"key": k, "description": desc, "n_den": int(den.sum()), "estimate": round(ratio(num, den, w0), 4),
                    "lo": round(lo, 4), "hi": round(hi, 4), "searched": searched.get(k, "")})
    with (R / f"field_hypotheses{sfx}.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n"); w.writeheader(); w.writerows(out)
    for r in out:
        print(f"{r['key']:<20} n={r['n_den']:<4} {r['estimate']:.3f} [{r['lo']:.3f},{r['hi']:.3f}]  searched {r['searched']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
