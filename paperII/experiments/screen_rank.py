#!/usr/bin/env python3
"""S2, amendment 1: rank the candidates for prioritised title/abstract screening.

Implements corpus/SCREENING_PROCEDURE.md exactly (fixed 2026-10-15, before any
ranking existed):

  representation  --repr word: TF-IDF over lower-cased words and word bigrams
                  (Phase A); --repr char: character 3-5-grams (Phase B, model
                  switch). Sublinear tf, smooth idf, terms in >= 2 records,
                  rows L2-normalised.
  classifier      L2-regularised logistic regression, C = 1, balanced class
                  weights, fitted with L-BFGS (numpy/scipy only).
  labels          positives: the development half (odd gid) of the pilot set
                  that the search retrieved, plus every human include in
                  corpus/screening/decisions.csv; negatives: every human
                  exclude. While fewer than 50 human excludes exist, a fixed
                  random sample of 2,000 unlabelled records (seed 20261015 + i)
                  stands in as provisional negatives, averaged over 5 samples
                  (PU bagging).
  output          corpus/screening/rank_v<N>.csv  -- rank, cid, score, title,
                  year, venue of every UNSCREENED candidate, best first. It
                  carries no pilot-set marks, so screeners see only the order.
                  results/screen_rank_check.csv   -- where each held-out (even
                  gid) pilot paper landed; a check of the ranker, never an
                  input to the stopping rule.

The LLM never ranks and its output is never a label.

Usage:  python3 screen_rank.py --version 1 [--repr word|char]
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
from scipy import sparse
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
C = HERE.parent / "corpus"
R = HERE.parent / "results"
sys.path.insert(0, str(HERE))
import search_sensitivity as SS  # noqa: E402  (the same title matching as the recall check)

SEED = 20261015
N_PU, N_BAGS, MIN_HUMAN_NEG = 2000, 5, 50
TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def features(texts: list[str], how: str):
    docs = []
    for t in texts:
        t = t.lower()
        if how == "word":
            w = TOKEN.findall(t)
            docs.append(Counter(w + [a + " " + b for a, b in zip(w, w[1:])]))
        else:
            t = " " + re.sub(r"\s+", " ", t) + " "
            docs.append(Counter(t[i:i + n] for n in (3, 4, 5) for i in range(len(t) - n + 1)))
    df = Counter(term for d in docs for term in d)
    vocab = {term: j for j, term in enumerate(sorted(t for t, c in df.items() if c >= 2))}
    n = len(docs)
    idf = np.array([math.log((1 + n) / (1 + df[t])) + 1 for t in sorted(vocab, key=vocab.get)])
    rows, cols, vals = [], [], []
    for i, d in enumerate(docs):
        for term, tf in d.items():
            j = vocab.get(term)
            if j is not None:
                rows.append(i); cols.append(j); vals.append((1 + math.log(tf)) * idf[j])
    X = sparse.csr_matrix((vals, (rows, cols)), shape=(n, len(vocab)))
    norm = np.sqrt(np.asarray(X.multiply(X).sum(axis=1)).ravel()); norm[norm == 0] = 1
    return sparse.diags(1 / norm) @ X


def fit_lr(X, y, c=1.0):
    """Balanced-weight L2 logistic regression; returns (w, b)."""
    n, d = X.shape
    pos = y.sum(); neg = n - pos
    sw = np.where(y == 1, n / (2 * pos), n / (2 * neg))

    def f(theta):
        w, b = theta[:d], theta[d]
        z = X @ w + b
        p = 1 / (1 + np.exp(-np.clip(z, -35, 35)))
        loss = np.sum(sw * (np.logaddexp(0, z) - y * z)) + 0.5 / c * w @ w
        g = sw * (p - y)
        return loss, np.concatenate([X.T @ g + w / c, [g.sum()]])
    r = minimize(f, np.zeros(d + 1), jac=True, method="L-BFGS-B", options={"maxiter": 500})
    return r.x[:d], r.x[d]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--repr", choices=("word", "char"), default="word")
    a = ap.parse_args()
    csv.field_size_limit(10 ** 9)
    cand = list(csv.DictReader((C / "candidates.csv").open()))
    texts = [(r["title"] or "") + ". " + (r["abstract"] or "") for r in cand]
    gold = list(csv.DictReader((C / "corpus_index.csv").open()))
    gnum = lambda g: int(re.sub(r"\D", "", g) or 0)
    key = {SS.strip_note(g["title"])[:SS.PREFIX]: g["gid"] for g in gold}
    gid = [key.get(SS.strip_note(r["title"])[:SS.PREFIX]) for r in cand]
    dev = np.array([g is not None and gnum(g) % 2 == 1 for g in gid])
    held = [i for i, g in enumerate(gid) if g is not None and gnum(g) % 2 == 0]

    dec_path = C / "screening" / "decisions.csv"
    human = {}
    if dec_path.exists():
        human = {r["cid"]: int(r["include"]) for r in csv.DictReader(dec_path.open())}
    lab = np.array([human.get(r["cid"], -1) for r in cand])
    y_pos = dev | (lab == 1)
    y_neg = lab == 0
    screened = lab >= 0

    X = features(texts, a.repr)
    score = np.zeros(len(cand))
    if y_neg.sum() >= MIN_HUMAN_NEG:
        idx = np.flatnonzero(y_pos | y_neg)
        w, b = fit_lr(X[idx], y_pos[idx].astype(float))
        score = 1 / (1 + np.exp(-(X @ w + b)))
        how = f"human labels ({int(y_pos.sum())} positive, {int(y_neg.sum())} negative)"
    else:
        pool = np.flatnonzero(~y_pos & ~y_neg)
        for i in range(N_BAGS):
            rng = np.random.default_rng(SEED + i)
            negs = rng.choice(pool, size=min(N_PU, len(pool)), replace=False)
            known = np.flatnonzero(y_pos | y_neg)
            idx = np.concatenate([known, negs])
            yy = np.concatenate([y_pos[known].astype(float), np.zeros(len(negs))])
            w, b = fit_lr(X[idx], yy)
            score += 1 / (1 + np.exp(-(X @ w + b))) / N_BAGS
        how = f"PU bagging: {int(y_pos.sum())} positives, {N_BAGS} x {N_PU} provisional negatives"

    order = [i for i in np.argsort(-score, kind="stable") if not screened[i]]
    out = C / "screening" / f"rank_v{a.version}.csv"
    with out.open("w", newline="") as fh:
        wr = csv.writer(fh, lineterminator="\n")
        wr.writerow(["rank", "cid", "score", "title", "year", "venue"])
        for k, i in enumerate(order, 1):
            r = cand[i]
            wr.writerow([k, r["cid"], f"{score[i]:.6f}", r["title"], r["year"], r["venue"]])
    pos_of = {i: k for k, i in enumerate(order, 1)}
    n_un = len(order)
    R.mkdir(exist_ok=True)
    chk = R / "screen_rank_check.csv"
    rows = [{"version": a.version, "repr": a.repr, "gid": gid[i], "rank": pos_of.get(i, "screened"),
             "of_unscreened": n_un, "pct": f"{100 * pos_of[i] / n_un:.2f}" if i in pos_of else ""}
            for i in held]
    old = [r for r in csv.DictReader(chk.open())] if chk.exists() else []
    old = [r for r in old if not (r["version"] == str(a.version) and r["repr"] == a.repr)]
    with chk.open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=["version", "repr", "gid", "rank", "of_unscreened", "pct"],
                            lineterminator="\n")
        wr.writeheader(); wr.writerows(old + rows)
    ranks = sorted(pos_of[i] for i in held if i in pos_of)
    at = lambda f: sum(r <= f * n_un for r in ranks)
    print(f"[rank v{a.version}/{a.repr}] {how}; {n_un} unscreened ranked -> {out}")
    print(f"[rank v{a.version}/{a.repr}] held-out pilot papers in candidates: {len(held)}; "
          f"within top 10%: {at(0.10)}, top 20%: {at(0.20)}, top 50%: {at(0.50)} (check only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
