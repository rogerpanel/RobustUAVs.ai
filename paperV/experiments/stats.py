"""Statistics (runbook §1.5, §8), re-implemented after Paper III e6_aggregate.py and Paper IV
run_pilot.py: Clopper-Pearson, Wilson, Holm-Bonferroni, IQM with stratified bootstrap,
Cochran-Armitage and Page's L trend tests, and the campaign readers.

    python3 stats.py --campaign p2_main,p2_budget --rq rq1,denial_envelope
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
from scipy import stats as ss

try:
    from . import constants as C
except ImportError:
    import constants as C


# ------------------------------------------------------------------ intervals
def cp_interval(k, n, a=0.05):
    if n == 0:
        return (np.nan, np.nan)
    lo = 0.0 if k == 0 else float(ss.beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(ss.beta.ppf(1 - a / 2, k + 1, n - k))
    return (lo, hi)


def cp_upper(k, n, a=0.05):
    """One-sided (1 - a) Clopper-Pearson upper bound; k = 0 gives 1 - a^(1/n) ~ 3/n."""
    if n == 0:
        return np.nan
    return 1.0 if k >= n else float(ss.beta.ppf(1 - a, k + 1, n - k))


def wilson(k, n, a=0.05):
    if n == 0:
        return (np.nan, np.nan)
    z = ss.norm.ppf(1 - a / 2); p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def holm(ps):
    """Holm-Bonferroni adjusted p-values (same order as the input)."""
    ps = np.asarray(ps, float)
    m = len(ps)
    order = np.argsort(ps)
    adj = np.empty(m)
    run = 0.0
    for r, i in enumerate(order):
        run = max(run, (m - r) * ps[i])
        adj[i] = min(1.0, run)
    return adj


def iqm(x):
    x = np.sort(np.asarray(x, float)[np.isfinite(x)])
    if len(x) == 0:
        return np.nan
    n = len(x); lo, hi = int(np.floor(0.25 * n)), int(np.ceil(0.75 * n))
    return float(x[lo:hi].mean()) if hi > lo else float(x.mean())


def strat_boot(groups, stat=iqm, B=2000, a=0.05, seed=10900):
    """Stratified bootstrap: resample within each group (e.g. per seed block), statistic on the pool."""
    rng = np.random.default_rng(seed)
    groups = [np.asarray(g, float) for g in groups if len(g)]
    point = stat(np.concatenate(groups))
    draws = np.empty(B)
    for b in range(B):
        draws[b] = stat(np.concatenate([g[rng.integers(0, len(g), len(g))] for g in groups]))
    return point, float(np.quantile(draws, a / 2)), float(np.quantile(draws, 1 - a / 2))


def boot_mean(x, B=2000, a=0.05, seed=10901):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) == 0:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), (B, len(x)))].mean(1)
    return (float(x.mean()), float(np.quantile(m, a / 2)), float(np.quantile(m, 1 - a / 2)))


# ------------------------------------------------------------------ trend tests
def cochran_armitage(counts, n, scores=None, alternative="increasing"):
    """Cochran-Armitage test for a trend in proportions counts/n over ordered levels.
    Returns (z, one-sided p for the stated alternative)."""
    counts = np.asarray(counts, float); n = np.asarray(n, float)
    s = np.arange(len(counts), dtype=float) if scores is None else np.asarray(scores, float)
    N = n.sum(); p = counts.sum() / N
    if p in (0.0, 1.0):
        return 0.0, 1.0
    T = np.sum(s * (counts - n * p))
    var = p * (1 - p) * (np.sum(n * s * s) - np.sum(n * s) ** 2 / N)
    if var <= 0:
        return 0.0, 1.0
    z = T / np.sqrt(var)
    pval = ss.norm.sf(z) if alternative == "increasing" else ss.norm.cdf(z)
    return float(z), float(pval)


def page_l(data):
    """Page's L for an increasing trend; data shape (n_blocks, k_levels)."""
    r = ss.page_trend_test(np.asarray(data, float))
    return float(r.statistic), float(r.pvalue)


# ------------------------------------------------------------------ campaign records
def campaign_dir(cid):
    return C.RESULTS / "campaign" / cid


def read_campaign(cid):
    rows = []
    for f in sorted(campaign_dir(cid).glob("shard_*.jsonl.gz")):
        with gzip.open(f, "rt") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass                     # a torn last line from an interrupted writer
    return rows


def rq1_rows(records):
    """Per cell: aircraft-steps, violations, CP upper bound (provenance sim)."""
    import pandas as pd
    d = pd.DataFrame([r for r in records if r["status"] == "ok"])
    if d.empty:
        return []
    keys = ["planner", "filter", "b_tot_level", "m", "gamma", "attacker", "goal"]
    out = []
    for k, g in d.groupby(keys, dropna=False):
        ast = int(g.aircraft_steps.sum()); v = int(g.violations_corridor.sum())
        inside = g[~g.assumption_violated.astype(bool)]
        ai = int(inside.aircraft_steps.sum()); vi = int(inside.violations_corridor.sum())
        out.append(dict(zip(keys, k), episodes=len(g), aircraft_steps=ast, violations=v,
                        cp_upper=cp_upper(v, ast), episodes_inside=len(inside), aircraft_steps_inside=ai,
                        violations_inside=vi, cp_upper_inside=cp_upper(vi, ai),
                        min_true_margin=float(g.min_true_margin.min()), provenance="sim"))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", default="")
    ap.add_argument("--rq", default="rq1")
    a = ap.parse_args()
    import csv
    recs = [r for c in a.campaign.split(",") if c for r in read_campaign(c)]
    print(f"{len(recs)} episode records")
    if "rq1" in a.rq:
        rows = rq1_rows(recs)
        if rows:
            p = C.RESULTS / "rq1_violations.csv"
            with p.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
            print("wrote", p)
