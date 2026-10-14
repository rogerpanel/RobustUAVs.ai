"""Dependence-uncertainty bounds for the unified budget.

For non-negative random variables X_1..X_d with known marginals and unknown
coupling, bound   p(s) = Pr[X_1 + ... + X_d > s].

  union_bound    inf over splits sum s_i = s of min(1, sum_i Pr[X_i > s_i])
                 (the "standard bound"; sharp for d = 2, Makarov / Rueschendorf)
  ra_bound       worst case over all copulas, computed with the Rearrangement
                 Algorithm (Puccetti & Rueschendorf 2012; Embrechts et al. 2013)
  indep_tail     Pr[S > s] under independence (Monte Carlo)
  comon_tail     Pr[S > s] under comonotonicity (quantile sum)

Deterministic (Dirac) terms enter only as a shift of s: a point mass has a
single coupling with any other variable, so it contributes no dependence gap.
"""
from __future__ import annotations

import numpy as np


def _q(sample, u):
    return np.quantile(sample, np.clip(u, 0.0, 1.0), method="linear")


def tail(sample, s):
    return float(np.mean(np.asarray(sample) > s))


def union_bound(samples, s, grid=200):
    d = len(samples)
    if s <= 0:
        return 1.0
    if d == 1:
        return tail(samples[0], s)
    srt = [np.sort(x) for x in samples]
    surv = lambda i, t: 1.0 - np.searchsorted(srt[i], t, side="right") / len(srt[i])
    ts = np.linspace(0, s, grid + 1)
    if d == 2:
        return float(min(1.0, np.min(surv(0, ts) + surv(1, s - ts))))
    if d == 3:
        best = 1.0
        for t1 in ts:
            t2 = ts[ts <= s - t1]
            val = surv(0, t1) + surv(1, t2) + surv(2, s - t1 - t2)
            best = min(best, float(val.min()))
        return min(1.0, best)
    raise ValueError("d <= 3 supported")


def _ra_matrix(samples, alpha, N, upper):
    j = np.arange(N)
    u = alpha + (1 - alpha) * ((j + 1) / N if upper else j / N)
    u = np.minimum(u, 1.0)
    return np.stack([_q(x, u) for x in samples], 1)


def ra_worst_var(samples, alpha, N=2000, tol=1e-9, max_iter=200, seed=0):
    """Sharp upper bound on VaR_alpha(sum) over all copulas (RA, upper+lower
    discretisation; returns the conservative upper value)."""
    rng = np.random.default_rng(seed)
    vals = []
    for upper in (True, False):
        M = _ra_matrix(samples, alpha, N, upper)
        for c in range(M.shape[1]):
            M[:, c] = rng.permutation(M[:, c])
        prev = -np.inf
        for _ in range(max_iter):
            for c in range(M.shape[1]):
                rest = M.sum(1) - M[:, c]
                order = np.argsort(rest)               # ascending rest
                col = np.sort(M[:, c])[::-1]           # descending column
                M[order, c] = col                      # oppositely ordered
            cur = M.sum(1).min()
            if abs(cur - prev) <= tol:
                break
            prev = cur
        vals.append(cur)
    return max(vals)


def ra_bound(samples, s, N=2000, iters=30):
    """Worst-case Pr[S > s] over copulas, via the RA, intersected with the union
    bound (both are valid upper bounds on the worst case, so their minimum is
    too; this removes the 1/N resolution floor of the discretisation)."""
    return min(_ra_bound(samples, s, N, iters), union_bound(samples, s))


def _ra_bound(samples, s, N=2000, iters=30):
    """RA estimate of the worst-case tail: 1 - sup{alpha: VaRbar_alpha <= s}."""
    if s <= 0:
        return 1.0
    lo, hi = 0.0, 1.0 - 1.0 / N
    if ra_worst_var(samples, hi, N) <= s:
        return 1.0 / N
    if ra_worst_var(samples, lo, N) > s:
        return 1.0
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if ra_worst_var(samples, mid, N) <= s:
            lo = mid
        else:
            hi = mid
    return 1.0 - lo


def indep_tail(samples, s, n=400_000, seed=1):
    rng = np.random.default_rng(seed)
    tot = sum(rng.choice(np.asarray(x), size=n, replace=True) for x in samples)
    return float(np.mean(tot > s))


def comon_tail(samples, s, n=4001):
    u = (np.arange(n) + 0.5) / n
    tot = sum(_q(x, u) for x in samples)
    return float(np.mean(tot > s))
