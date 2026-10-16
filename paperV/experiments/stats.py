"""Statistics helpers (Paper III/IV conventions): Wilson and Clopper-Pearson intervals,
stratified bootstrap over episodes, ordered-trend test."""
from __future__ import annotations

import numpy as np
from scipy.stats import beta, norm, spearmanr


def wilson(k, n, a=0.05):
    if n == 0:
        return (np.nan, np.nan)
    z = norm.ppf(1 - a / 2); p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def cp_interval(k, n, a=0.05):
    lo = 0.0 if k == 0 else beta.ppf(a / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - a / 2, k + 1, n - k)
    return (lo, hi)


def cp_upper(k, n, a=0.05):
    """One-sided (1-a) Clopper-Pearson upper bound (k=0 -> 1-(a)^(1/n) ~ 3/n)."""
    if n == 0:
        return np.nan
    return 1.0 if k >= n else float(beta.ppf(1 - a, k + 1, n - k))


def boot_mean(x, B=2000, a=0.05, seed=0):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) == 0:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    m = rng.choice(x, size=(B, len(x))).mean(1)
    return (float(x.mean()), float(np.quantile(m, a / 2)), float(np.quantile(m, 1 - a / 2)))


def trend(levels, values):
    """Spearman rank correlation between ordered level and per-episode value, with p."""
    r, p = spearmanr(levels, values)
    return float(r), float(p)
