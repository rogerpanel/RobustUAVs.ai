#!/usr/bin/env python3
"""E1 -- exhaustive check of every closed form against a brute-force oracle.

For random nested instances (N, M <= 12, including ties and degenerate
profiles) we compare:
  (a) Lemma 1  deficiency d = max_k(k-n_k)^+   vs  Hopcroft-Karp maximum matching
  (b) GNP      cardinality and value            vs  oracle (exact max-weight matching)
  (c) Lemma 2  coverage margin min_j(n_j - j)   vs  enumeration of all k-subsets
  (d) Prop. 3  worst-case b-collapse deficiency vs  enumeration of all b-subsets
  (e) Thm 2    hysteresis coverage >= M - d(rho + h)
Output: results/e1_verify.csv (one row per check, with counts of disagreements).
"""
from __future__ import annotations

import csv
import itertools
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from certcmdp.certificate import OUT, ALERT_LIMITS  # noqa: E402
from certcmdp import combinatorics as C  # noqa: E402


def draw(rng):
    N = int(rng.integers(1, 11))
    M = int(rng.integers(1, 11))
    kind = rng.integers(0, 3)
    if kind == 0:     # discrete alert-limit family, ties likely
        alpha = rng.choice(ALERT_LIMITS, size=M)
        rho = rng.choice(np.r_[ALERT_LIMITS, 1.0, 3.0, 7.5, 15.0, 30.0], size=N)
    elif kind == 1:   # continuous
        alpha = rng.uniform(1, 25, M)
        rho = rng.uniform(0, 30, N)
    else:             # heavy-tailed certificates
        alpha = rng.choice(ALERT_LIMITS, size=M)
        rho = rng.lognormal(1.5, 1.0, N)
    return rho, alpha


def oracle_value(elig, value):
    best = 0.0
    N, M = elig.shape
    # exact max-value matchable task set by enumeration over task subsets
    for r in range(M, 0, -1):
        for S in itertools.combinations(range(M), r):
            if C.brute_max_matching(elig[:, S]) == r:
                best = max(best, float(value[list(S)].sum()))
    return best


def main(n_inst=10000, seed=0):
    rng = np.random.default_rng(seed)
    stats = {k: [0, 0] for k in ("deficiency", "gnp_cardinality", "gnp_value",
                                 "lex_cardinality", "lex_value", "coverage_margin",
                                 "worst_case_collapse", "hysteresis_bound",
                                 "gnp_feasible")}
    for t in range(n_inst):
        rho, alpha = draw(rng)
        N, M = rho.size, alpha.size
        elig = rho[:, None] <= alpha[None, :]
        hk = C.brute_max_matching(elig)
        d = C.deficiency(rho, alpha)
        stats["deficiency"][0] += 1
        stats["deficiency"][1] += int(M - d != hk)

        a = C.nested_greedy(rho, alpha, score=rng.random((N, M)))
        cov = int((a >= 0).sum())
        stats["gnp_cardinality"][0] += 1
        stats["gnp_cardinality"][1] += int(cov != hk)
        feas = all(rho[i] <= alpha[a[i]] for i in range(N) if a[i] >= 0)
        uniq = len(set(a[a >= 0])) == cov
        stats["gnp_feasible"][0] += 1
        stats["gnp_feasible"][1] += int(not (feas and uniq))

        prop = rng.integers(-1, M, N)
        lx = C.lexicographic_projection(elig, prop)
        stats["lex_cardinality"][0] += 1
        stats["lex_cardinality"][1] += int((lx >= 0).sum() != hk)

        if M <= 8:
            value = rng.integers(1, 5, M).astype(float)
            av = C.nested_greedy(rho, alpha, value=value)
            got = float(value[av[av >= 0]].sum())
            stats["gnp_value"][0] += 1
            best = oracle_value(elig, value)
            stats["gnp_value"][1] += int(abs(got - best) > 1e-9)
            # exact projection with non-uniform value gaps ({1,4,6}: sums can differ by
            # less than the minimum gap) must still maximise value after cardinality
            v2 = rng.choice([1.0, 4.0, 6.0], M)
            lx2 = C.lexicographic_projection(elig, rng.integers(-1, M, N), v2)
            stats["lex_value"][0] += 1
            stats["lex_value"][1] += int(abs(float(v2[lx2[lx2 >= 0]].sum())
                                             - oracle_value(elig, v2)) > 1e-9
                                         or (lx2 >= 0).sum() != hk)

        if N <= 9:
            # coverage margin: largest k with full coverage under every k-removal
            km = -1
            if hk == M:
                km = 0
                for k in range(1, N + 1):
                    ok = all(C.brute_max_matching(np.delete(elig, list(S), 0)) == M
                             for S in itertools.combinations(range(N), k))
                    if ok:
                        km = k
                    else:
                        break
            stats["coverage_margin"][0] += 1
            stats["coverage_margin"][1] += int(km != C.coverage_margin(rho, alpha))
            b = int(rng.integers(0, N + 1))
            worst = max((M - C.brute_max_matching(np.delete(elig, list(S), 0))
                         for S in itertools.combinations(range(N), b)), default=M - hk)
            stats["worst_case_collapse"][0] += 1
            stats["worst_case_collapse"][1] += int(worst != C.worst_case_deficiency(rho, alpha, b))

        h = float(rng.uniform(0, 5))
        holder = C.nested_greedy(rho + rng.normal(0, 2, N), alpha)  # some prior holding
        holder = np.where((holder >= 0) & (rho <= np.r_[alpha, np.inf][holder]), holder, -1)
        eh = C.eligibility(rho, alpha, holder_of=holder, h=h)
        stats["hysteresis_bound"][0] += 1
        stats["hysteresis_bound"][1] += int(C.brute_max_matching(eh) < M - C.deficiency(rho + h, alpha))

    rows = [{"check": k, "instances": v[0], "disagreements": v[1]} for k, v in stats.items()]
    with (OUT / "e1_verify.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["check", "instances", "disagreements"])
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
