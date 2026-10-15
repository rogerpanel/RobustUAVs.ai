#!/usr/bin/env python3
"""Amendments 3-4: weighted corpus-level estimates from the coded sample.

Strata   core       N = included records of ranks 1-2,750 (screened in full)
         remainder  N = 22,623 x p_hat (simple random sample of 1,250, L1/L2)
Each coded paper of stratum s stands for N_s / n_s included records (n_s =
papers coded in s). For every field value the estimate is the weighted share
among full-text-eligible papers, and the weighted number of papers.

Intervals: 95% percentile bootstrap (B = 4000, seed 20261020). Each replicate
resamples the coded papers within each stratum and redraws the remainder
include count as 22,623 x Binomial(1,250, p_hat) / 1,250, so the interval
carries both the coding-sample and the screening-sample uncertainty.

Inputs   corpus/codes_full_final.csv, corpus/coding_sample.csv,
         results/screening_status.csv
Outputs  results/corpus_estimates.csv     field, value, coded counts, share and papers with intervals
         results/type_plane_full.csv      scope x modality cells (the type plane)
Usage    python3 corpus_estimates.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

C = Path(__file__).resolve().parent.parent / "corpus"
R = C.parent / "results"
FIELDS = ["class", "tier", "component", "scope", "modality", "perturbation", "assumption", "evidence"]
LIFTS = ["L_dyn", "L_hor", "L_gen", "L_op", "L_rate", "L_conc", "L_sup", "L_mon", "none"]
B, SEED = 4000, 20261020


def indicators(rows):
    """(field, value) -> 0/1 vector over the coded papers (eligible only)."""
    out = {("eligible", "1"): np.array([r["eligible"] == "1" for r in rows], float)}
    el = [r["eligible"] == "1" for r in rows]
    vals = lambda f: sorted({r[f] for r, e in zip(rows, el) if e})  # noqa: E731
    for f in FIELDS:
        for v in vals(f):
            out[(f, v)] = np.array([e and r[f] == v for r, e in zip(rows, el)], float)
    out[("class", "NEW:* (all new classes)")] = np.array(
        [e and r["class"].startswith("NEW:") for r, e in zip(rows, el)], float)
    for L in LIFTS:
        out[("lifts", L)] = np.array([e and L in r["lifts"].split(";") for r, e in zip(rows, el)], float)
    for v in sorted({r["scope"] + "/" + r["modality"] for r, e in zip(rows, el) if e}):
        out[("scope_x_modality", v)] = np.array(
            [e and r["scope"] + "/" + r["modality"] == v for r, e in zip(rows, el)], float)
    return out


def main() -> int:
    st = {r["metric"]: r["value"] for r in csv.DictReader((R / "screening_status.csv").open())}
    n_core, n_samp = int(st["core_included"]), int(st["sample_included"])
    m_samp, n_rem_pool = int(st["sample_screened"]), int(st["remainder_size"])
    stratum = {r["cid"]: r["stratum"] for r in csv.DictReader((C / "coding_sample.csv").open())}
    rows = list(csv.DictReader((C / "codes_full_final.csv").open()))
    strata = {s: [r for r in rows if stratum[r["cid"]] == s] for s in ("core", "remainder")}
    ind = {s: indicators(strata[s]) for s in strata}
    keys = sorted(set(ind["core"]) | set(ind["remainder"]), key=lambda k: (k[0], k[1]))
    for s in strata:
        n = len(strata[s])
        for k in keys:
            ind[s].setdefault(k, np.zeros(n))
    N = {"core": float(n_core), "remainder": n_rem_pool * n_samp / m_samp}

    def est(sel, Ns):
        """papers[k], share[k] for index selections sel[s] and stratum sizes Ns."""
        pap = {k: sum(Ns[s] * ind[s][k][sel[s]].mean() for s in strata) for k in keys}
        el = pap[("eligible", "1")]
        return pap, {k: (pap[k] / el if k[0] != "eligible" else pap[k] / sum(Ns.values())) for k in keys}

    full = {s: np.arange(len(strata[s])) for s in strata}
    pap0, sh0 = est(full, N)
    rng = np.random.default_rng(SEED)
    bp = {k: np.empty(B) for k in keys}; bs = {k: np.empty(B) for k in keys}
    for b in range(B):
        sel = {s: rng.integers(0, len(strata[s]), len(strata[s])) for s in strata}
        Nb = {"core": N["core"], "remainder": n_rem_pool * rng.binomial(m_samp, n_samp / m_samp) / m_samp}
        p, sh = est(sel, Nb)
        for k in keys:
            bp[k][b], bs[k][b] = p[k], sh[k]
    q = lambda x: (float(np.quantile(x, .025)), float(np.quantile(x, .975)))  # noqa: E731
    out = []
    for k in keys:
        (sl, sh_), (pl, ph) = q(bs[k]), q(bp[k])
        nc, nr = int(ind["core"][k].sum()), int(ind["remainder"][k].sum())
        elc = ind["core"][("eligible", "1")].sum(); elr = ind["remainder"][("eligible", "1")].sum()
        den_c, den_r = (len(strata["core"]), len(strata["remainder"])) if k[0] == "eligible" else (elc, elr)
        out.append({"field": k[0], "value": k[1], "coded_core": nc, "coded_remainder": nr,
                    "share_core": round(nc / den_c, 4), "share_remainder": round(nr / den_r, 4),
                    "share": round(sh0[k], 4), "share_lo": round(sl, 4), "share_hi": round(sh_, 4),
                    "papers": round(pap0[k]), "papers_lo": round(pl), "papers_hi": round(ph)})
    R.mkdir(exist_ok=True)
    with (R / "corpus_estimates.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n"); w.writeheader(); w.writerows(out)
    tp = [{"scope": r["value"].split("/")[0], "modality": r["value"].split("/")[1],
           **{x: r[x] for x in ("coded_core", "coded_remainder", "share", "share_lo", "share_hi", "papers")}}
          for r in out if r["field"] == "scope_x_modality"]
    with (R / "type_plane_full.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(tp[0]), lineterminator="\n"); w.writeheader(); w.writerows(tp)
    print(f"strata: core N={N['core']:.0f} coded {len(strata['core'])}; remainder N={N['remainder']:.0f} "
          f"coded {len(strata['remainder'])}")
    for r in out:
        if r["field"] in ("eligible", "scope", "modality", "tier", "component", "assumption", "evidence") or \
                r["value"].startswith("NEW:*") or (r["field"] == "class" and r["share"] >= 0.03):
            print(f"{r['field']:<13} {r['value']:<26} {r['share']:.3f} [{r['share_lo']:.3f},{r['share_hi']:.3f}]"
                  f"  ~{r['papers']} [{r['papers_lo']},{r['papers_hi']}]  core {r['share_core']:.2f} rem {r['share_remainder']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
