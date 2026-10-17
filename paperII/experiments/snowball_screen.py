#!/usr/bin/env python3
"""Amendment 5: screening batches for a snowballing iteration, and the merge of both screeners.

An iteration with at most 3,000 new candidates is screened in full by L1 and L2 exactly as in
amendment 2 (same rule, same prompt, same 125-record batches); a record is excluded only when
both screeners exclude it. Batches list the candidates in a random order (seed 20261022 + k),
since every record is screened.

Above 3,000 the candidates are ranked by the frozen ranker: the rank_v1 model of screen_rank.py
(word TF-IDF, PU bagging on the development half of the pilot set, no screening labels, exactly
as held fixed by amendment 2), fitted on corpus/candidates.csv and applied to the new records
in its own vocabulary; it is not retrained on anything new. Core = ranks 1-1,500, screened in
full; remainder = the rest, of which a simple random sample of 500 (seed 20261022 + k, drawn
from the sorted cids, as in screen_sample.py) is screened. Core and sample are batched together
in one random order from the same generator, so screeners see neither stratum nor rank.
Includes are estimated as core includes + N_rem x p_hat (95 % Clopper-Pearson), as amendment 3.

  python3 snowball_screen.py batches --iter 1     -> screening/llm/batch_N<k><nnn>.txt / .cids
                                                    (above 3,000 also snowball/iter<k>_rank.csv,
                                                    iter<k>_strata.csv)
  python3 snowball_screen.py merge   --iter 1     -> snowball/iter<k>_decisions.csv, iter<k>_screening_status.csv
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import beta

HERE = Path(__file__).resolve().parent
C = HERE.parent / "corpus"
L = C / "screening" / "llm"
B = 125
LARGE, CORE, SRS = 3000, 1500, 500


def cl(s):
    return (s or "").replace("�", "?").replace("\n", " ").strip()


def cp(x, n, a=0.05):
    lo = beta.ppf(a / 2, x, n - x + 1) if x > 0 else 0.0
    hi = beta.ppf(1 - a / 2, x + 1, n - x) if x < n else 1.0
    return lo, hi


def frozen_ranker(new_texts: list[str]):
    """Scores of new records under the rank_v1 model; also the rank_v1 scores of corpus/candidates.csv."""
    sys.path.insert(0, str(HERE))
    import screen_rank as SR
    import search_sensitivity as SS
    cand = list(csv.DictReader((C / "candidates.csv").open()))
    texts = [(r["title"] or "") + ". " + (r["abstract"] or "") for r in cand]
    gold = list(csv.DictReader((C / "corpus_index.csv").open()))
    gnum = lambda g: int(re.sub(r"\D", "", g) or 0)  # noqa: E731
    key = {SS.strip_note(g["title"])[:SS.PREFIX]: g["gid"] for g in gold}
    gid = [key.get(SS.strip_note(r["title"])[:SS.PREFIX]) for r in cand]
    y_pos = np.array([g is not None and gnum(g) % 2 == 1 for g in gid])
    X = SR.features(texts, "word")
    # the same vocabulary and idf as SR.features, to project the new records
    docs = []
    for t in texts:
        w = SR.TOKEN.findall(t.lower()); docs.append(Counter(w + [a + " " + b for a, b in zip(w, w[1:])]))
    df = Counter(term for d in docs for term in d)
    terms = sorted(t for t, c in df.items() if c >= 2)
    vocab = {t: j for j, t in enumerate(terms)}
    idf = np.array([math.log((1 + len(docs)) / (1 + df[t])) + 1 for t in terms])
    assert X.shape[1] == len(vocab)
    rows, cols, vals = [], [], []
    for i, t in enumerate(new_texts):
        w = SR.TOKEN.findall(t.lower())
        for term, tf in Counter(w + [a + " " + b for a, b in zip(w, w[1:])]).items():
            j = vocab.get(term)
            if j is not None:
                rows.append(i); cols.append(j); vals.append((1 + math.log(tf)) * idf[j])
    from scipy import sparse
    Xn = sparse.csr_matrix((vals, (rows, cols)), shape=(len(new_texts), len(vocab)))
    nrm = np.sqrt(np.asarray(Xn.multiply(Xn).sum(axis=1)).ravel()); nrm[nrm == 0] = 1
    Xn = sparse.diags(1 / nrm) @ Xn
    pool = np.flatnonzero(~y_pos)
    known = np.flatnonzero(y_pos)
    old, new = np.zeros(len(cand)), np.zeros(len(new_texts))
    for i in range(SR.N_BAGS):
        negs = np.random.default_rng(SR.SEED + i).choice(pool, size=min(SR.N_PU, len(pool)), replace=False)
        idx = np.concatenate([known, negs])
        w, b = SR.fit_lr(X[idx], np.concatenate([np.ones(len(known)), np.zeros(len(negs))]))
        old += 1 / (1 + np.exp(-(X @ w + b))) / SR.N_BAGS
        new += 1 / (1 + np.exp(-(Xn @ w + b))) / SR.N_BAGS
    return new, {r["cid"]: s for r, s in zip(cand, old)}


def rank_and_sample(k: int, rows: list[dict]) -> list[dict]:
    S = C / "snowball"
    score, old = frozen_ranker([(r["title"] or "") + ". " + (r["abstract"] or "") for r in rows])
    # the ranker must be the one that produced rank_v1.csv: compare its scores there
    v1 = {r["cid"]: float(r["score"]) for r in csv.DictReader((C / "screening" / "rank_v1.csv").open())}
    dev = max(abs(old[c] - v1[c]) for c in v1)
    if dev > 1e-6:
        raise SystemExit(f"frozen ranker does not reproduce rank_v1.csv (max score difference {dev:.2e})")
    order = np.argsort(-score, kind="stable")
    with (S / f"iter{k}_rank.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["rank", "cid", "score"])
        w.writerows([(j, rows[i]["cid"], f"{score[i]:.6f}") for j, i in enumerate(order, 1)])
    core = [rows[i] for i in order[:CORE]]
    rem = sorted(rows[i]["cid"] for i in order[CORE:])
    rng = np.random.default_rng(20261022 + k)
    pick = set(rem[i] for i in rng.choice(len(rem), size=SRS, replace=False))
    rank = {rows[i]["cid"]: j for j, i in enumerate(order, 1)}
    with (S / f"iter{k}_strata.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["cid", "rank", "stratum"])
        for r in sorted(rows, key=lambda r: rank[r["cid"]]):
            st = "core" if rank[r["cid"]] <= CORE else ("sample" if r["cid"] in pick else "remainder_unscreened")
            w.writerow([r["cid"], rank[r["cid"]], st])
    print(f"frozen ranker reproduces rank_v1.csv (max |diff| {dev:.1e}); core {len(core)}, "
          f"remainder {len(rem)}, sample {len(pick)}")
    scr = core + [r for r in rows if r["cid"] in pick]
    return [scr[i] for i in rng.permutation(len(scr))]


def batches(k: int) -> None:
    csv.field_size_limit(10 ** 9)
    rows = list(csv.DictReader((C / "snowball" / f"iter{k}_candidates.csv").open()))
    if len(rows) > LARGE:
        order = rank_and_sample(k, rows)
    else:
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
    print(f"{n} new batches for iteration {k} ({len(order)} of {len(rows)} records)")


def merge(k: int) -> None:
    sp = C / "snowball" / f"iter{k}_strata.csv"
    stratum = {r["cid"]: r["stratum"] for r in csv.DictReader(sp.open())} if sp.exists() else {}
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
                dec.append({"cid": c, "include": int(a == "1" or b2 == "1"), "L1": a, "L2": b2, "batch": b,
                            **({"stratum": stratum[c]} if stratum else {})})
    with (C / "snowball" / f"iter{k}_decisions.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["cid", "include", "L1", "L2", "batch"] + (["stratum"] if stratum else []), lineterminator="\n")
        w.writeheader(); w.writerows(dec)
    n = len(dec); inc = sum(d["include"] for d in dec)
    agree = sum(d["L1"] == d["L2"] for d in dec)
    p1 = sum(d["L1"] == "1" for d in dec) / n if n else 0; p2 = sum(d["L2"] == "1" for d in dec) / n if n else 0
    pe = p1 * p2 + (1 - p1) * (1 - p2)
    kappa = (agree / n - pe) / (1 - pe) if n and pe < 1 else float("nan")
    rows = [("screened", n), ("included", inc), ("excluded_both", n - inc), ("L1_includes", sum(d["L1"] == "1" for d in dec)),
            ("L2_includes", sum(d["L2"] == "1" for d in dec)), ("kappa_L1_L2", round(kappa, 3)),
            ("batches_pending", len(pending)), ("batches_invalid", len(bad))]
    if stratum:
        n_rem = sum(v != "core" for v in stratum.values())
        cs = [d for d in dec if d["stratum"] == "core"]; ss = [d for d in dec if d["stratum"] == "sample"]
        ci, si = sum(d["include"] for d in cs), sum(d["include"] for d in ss)
        lo, hi = cp(si, len(ss)) if ss else (float("nan"),) * 2
        p = si / len(ss) if ss else float("nan")
        rows += [("core_screened", len(cs)), ("core_included", ci), ("sample_screened", len(ss)),
                 ("sample_included", si), ("remainder_size", n_rem),
                 ("remainder_included_est", round(n_rem * p, 1)),
                 ("included_est", round(ci + n_rem * p, 1)), ("included_lo", round(ci + n_rem * lo, 1)),
                 ("included_hi", round(ci + n_rem * hi, 1))]
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
