#!/usr/bin/env python3
"""R5 -- decentralised count consensus with misreporting aircraft (Prop. 6).

The deficiency monitor needs only the count profile (n_k). A fleet without a
ground station must agree on it over its own mesh. Protocol, per epoch:

  1. Report flooding. Every aircraft floods its certificate report over the
     mesh (`platform/backend/app/corpus.py::sample_mesh`). Reports are signed
     (their cost is budgeted in Paper I), so a relay cannot alter another
     aircraft's report; it can only drop it. We run both relay behaviours:
     Byzantine aircraft forward honestly, or drop every report they relay. A Byzantine aircraft may report
     a false certificate and may equivocate (tell different neighbours
     different values). Each honest aircraft forms a local count profile from
     the first report it receives from each origin.
  2. W-MSR (LeBlanc et al. 2013) on the local count profiles, parameter F = f:
     each honest aircraft discards the F largest values above and the F smallest
     values below its own among its neighbours, then averages the rest with its
     own. Byzantine aircraft send each neighbour an extreme value of their choice.
     The agreed count is the rounded common value once the honest spread is
     below 1e-3.

W-MSR guarantees agreement inside the hull of honest initial values when the
graph is (2F+1)-robust; we compute the robustness of every sampled graph by
brute force (N = 12) and report agreement as observed, robust or not.

Measured per (mesh density, f, liar strategy): rounds to agree, fraction of
instances that agreed, |d_agreed - d_true| (Prop. 6: <= f), and violations
under the projection fed with the reported certificates, split into those
committed by liars and by honest aircraft (Prop. 6: honest = 0).
Output: results/r5_consensus.csv
"""
from __future__ import annotations

import csv
import itertools
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "platform" / "backend"))
from certcmdp.certificate import OUT, KAPPA, ALERT_LIMITS  # noqa: E402
from certcmdp import combinatorics as C  # noqa: E402
from app.corpus import sample_mesh  # noqa: E402

N, M = 12, 8
MAX_ROUNDS = 300
TOL = 1e-3


def adjacency(seed, density):
    ids = [str(i) for i in range(N)]
    A = np.zeros((N, N), bool)
    if density == "complete":
        A[:] = True
    else:
        for lk in sample_mesh(ids, seed=seed, degree=density):
            i, j = int(lk["src"]), int(lk["dst"])
            A[i, j] = A[j, i] = True
    np.fill_diagonal(A, False)
    return A


_LAB = None


def robustness(A):
    """Largest r such that the graph is r-robust (LeBlanc et al. 2013): for every
    pair of disjoint non-empty node sets, some node of one set has at least r
    neighbours outside its own set. Brute force over all 3^N labellings."""
    global _LAB
    if _LAB is None:
        _LAB = np.array(list(itertools.product((0, 1, 2), repeat=N)), np.int8)
    lab = _LAB
    Af = A.astype(np.int32)
    deg = Af.sum(1)
    best = N
    for s in (1, 2):
        ins = (lab == s)
        ok = ins.any(1)
        out = deg[None, :] - ins.astype(np.int32) @ Af        # neighbours outside the set
        r_s = np.where(ins, out, -1).max(1)
        if s == 1:
            r1, ok1 = r_s, ok
        else:
            pair = ok1 & ok
            if pair.any():
                best = int(np.maximum(r1[pair], r_s[pair]).min())
    return best


def flood(A, honest, reports_to, drop=True):
    """First report each honest node receives from each origin.
    reports_to[o][v] = value origin o tells neighbour v (equivocation possible).
    Byzantine relays drop everything they did not originate (worst case)."""
    known = {v: {} for v in range(N)}
    frontier = []
    for o in range(N):
        known[o][o] = reports_to[o][o]
        for v in np.flatnonzero(A[o]):
            if (honest[v] or not drop) and o not in known[v]:
                known[v][o] = reports_to[o][v]
                frontier.append(v)
    while frontier:
        nxt = []
        for u in frontier:
            for v in np.flatnonzero(A[u]):
                if not honest[v] and drop:
                    continue
                for o, val in known[u].items():
                    if o not in known[v]:
                        known[v][o] = val
                        nxt.append(v)
        frontier = nxt
    return known


def wmsr(A, x0, honest, F, byz_value, rng):
    """W-MSR on a vector state; returns (final honest states, rounds, agreed)."""
    x = x0.astype(float).copy()
    K = x.shape[1]
    hon = np.flatnonzero(honest)
    for r in range(1, MAX_ROUNDS + 1):
        spread = (x[hon].max(0) - x[hon].min(0)).max()
        if spread < TOL:
            return x, r - 1, True
        new = x.copy()
        cols = np.arange(K)
        for i in hon:
            nb = np.flatnonzero(A[i])
            vals = np.array([x[j] if honest[j] else byz_value(j, i, x, rng) for j in nb])  # (deg,K)
            own = x[i]
            srt = np.sort(vals, 0)
            a = np.minimum(F, (vals < own).sum(0))
            b = len(nb) - np.minimum(F, (vals > own).sum(0))
            cs = np.vstack([np.zeros(K), np.cumsum(srt, 0)])
            new[i] = (own + cs[b, cols] - cs[a, cols]) / (1 + b - a)
        x = new
    spread = (x[hon].max(0) - x[hon].min(0)).max()
    return x, MAX_ROUNDS, bool(spread < TOL)


def instance(rng, density, f, strategy, gseed, relay="drop"):
    A = adjacency(gseed, density)
    rho = KAPPA * rng.exponential(1.2, N)
    alpha = rng.choice(ALERT_LIMITS, M)
    a_sorted = np.sort(alpha)
    liars = rng.choice(N, f, replace=False) if f else np.array([], int)
    honest = np.ones(N, bool); honest[liars] = False
    # reports: liars either inflate eligibility (report 0), deflate (report 1e3),
    # or equivocate (random extreme per neighbour)
    reports_to = {}
    for o in range(N):
        if honest[o]:
            reports_to[o] = {v: rho[o] for v in range(N)}
        elif strategy == "inflate":
            reports_to[o] = {v: 0.0 for v in range(N)}
        elif strategy == "deflate":
            reports_to[o] = {v: 1e3 for v in range(N)}
        else:
            reports_to[o] = {v: (0.0 if rng.random() < 0.5 else 1e3) for v in range(N)}
    known = flood(A, honest, reports_to, drop=(relay == "drop"))
    missing = int(sum(N - len(known[i]) for i in np.flatnonzero(honest)))
    # local count profiles n_k^i (missing origins count as ineligible)
    x0 = np.zeros((N, M))
    for i in range(N):
        vals = np.array(list(known[i].values()))
        x0[i] = np.searchsorted(np.sort(vals), a_sorted, side="right")

    def byz_value(j, i, x, rng):
        if strategy == "deflate":
            return np.zeros(M)
        if strategy == "inflate":
            return np.full(M, float(N))
        return np.where(rng.random(M) < 0.5, 0.0, float(N))

    xf, rounds, agreed = wmsr(A, x0, honest, f, byz_value, rng)
    hon = np.flatnonzero(honest)
    n_agreed = np.rint(xf[hon].mean(0))
    k = np.arange(1, M + 1)
    d_agreed = int(max(0, (k - n_agreed).max()))
    d_true = C.deficiency(rho, alpha)
    # allocation from the reported certificates (first report seen by a fixed honest node)
    ref = hon[0]
    rep = np.array([known[ref].get(o, 1e3) for o in range(N)])
    asg = C.nested_greedy_fast(rep, alpha)
    bad = np.array([asg[i] >= 0 and rho[i] > alpha[asg[i]] for i in range(N)])
    in_hull = bool(np.all((n_agreed >= np.floor(x0[hon].min(0) - 1e-9)) &
                          (n_agreed <= np.ceil(x0[hon].max(0) + 1e-9))))
    return {"rounds": rounds, "agreed": agreed, "dev_d": abs(d_agreed - d_true),
            "viol_liar": int((bad & ~honest).sum()), "viol_honest": int((bad & honest).sum()),
            "in_hull": in_hull, "missing": missing, "A": A}


def main(n=200, seed=5):
    rng = np.random.default_rng(seed)
    rows = []
    for density in (2, 4, 6, "complete"):
        rob_cache = {}
        for f in (0, 1, 2):
            combos = [("none", "forward")] if f == 0 else [
                (st, rl) for st in ("inflate", "deflate", "equivocate") for rl in ("forward", "drop")]
            for strategy, relay in combos:
                agg = {"rounds": [], "agreed": 0, "dev": [], "vl": 0, "vh": 0, "hull": 0, "rob": [], "miss": 0, "dev_ag": []}
                for t in range(n):
                    gseed = 10_000 + t
                    r = instance(rng, density, f, strategy, gseed, relay)
                    if gseed not in rob_cache:
                        rob_cache[gseed] = robustness(r["A"])
                    agg["rob"].append(rob_cache[gseed])
                    agg["agreed"] += r["agreed"]; agg["hull"] += r["in_hull"]; agg["miss"] += r["missing"] > 0
                    if r["agreed"]:
                        agg["rounds"].append(r["rounds"])
                        agg["dev_ag"].append(r["dev_d"])
                    agg["dev"].append(r["dev_d"]); agg["vl"] += r["viol_liar"]; agg["vh"] += r["viol_honest"]
                rob = np.array(agg["rob"])
                rows.append({
                    "mesh": density, "N": N, "M": M, "f": f, "strategy": strategy, "relay": relay,
                    "instances": n, "frac_reports_lost": agg["miss"] / n,
                    "robustness_median": float(np.median(rob)),
                    "frac_2f1_robust": float(np.mean(rob >= 2 * f + 1)),
                    "frac_agreed": agg["agreed"] / n,
                    "rounds_median": float(np.median(agg["rounds"])) if agg["rounds"] else "",
                    "rounds_max": int(max(agg["rounds"])) if agg["rounds"] else "",
                    "max_abs_dev_d": int(max(agg["dev"])),
                    "mean_abs_dev_d": float(np.mean(agg["dev"])),
                    "dev_le_f": bool(max(agg["dev"]) <= f),
                    "max_abs_dev_d_agreed": int(max(agg["dev_ag"])) if agg["dev_ag"] else "",
                    "frac_in_honest_hull": agg["hull"] / n,
                    "violations_by_liars": agg["vl"], "violations_by_honest": agg["vh"],
                    "provenance": "sim",
                })
                print({k: v for k, v in rows[-1].items() if k not in ("N", "M", "provenance")}, flush=True)
    with (OUT / "r5_consensus.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
