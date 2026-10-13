"""Nested-eligibility combinatorics and the projection layer.

Eligibility: agent i may hold task j iff rho_i <= alpha_j. Because the
condition is a single scalar threshold on each side, neighbourhoods are nested
(a *difference* / chain bipartite graph): an agent eligible for a demanding task
is eligible for every easier one. All closed forms below rest on that.

Conventions. Tasks are sorted by alert limit ascending (most demanding first),
a_(1) <= ... <= a_(M), and n_k = |{i : rho_i <= a_(k)}| is the count profile.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

IDLE = -1


# ------------------------------------------------------------ closed forms
def count_profile(rho, alpha):
    """n_k for tasks sorted ascending by alpha. O(N log N + M log M)."""
    r = np.sort(np.asarray(rho, float))
    a = np.sort(np.asarray(alpha, float))
    return np.searchsorted(r, a, side="right")


def deficiency(rho, alpha):
    """Ore deficiency of the nested graph: d = max_k (k - n_k)^+ (Lemma 1)."""
    n = count_profile(rho, alpha)
    k = np.arange(1, len(n) + 1)
    return int(max(0, (k - n).max(initial=0)))


def max_coverage(rho, alpha):
    return len(alpha) - deficiency(rho, alpha)


def coverage_margin(rho, alpha):
    """Largest k such that full coverage survives ANY k certificate collapses
    (Lemma 2): min_j (n_j - j); returns -1 when full coverage already fails."""
    n = count_profile(rho, alpha)
    j = np.arange(1, len(n) + 1)
    m = int((n - j).min(initial=len(rho)))
    return m if m >= 0 else -1


def worst_case_deficiency(rho, alpha, b):
    """Deficiency after an adversary collapses the b agents of its choice
    (Proposition 3). Optimal attack: collapse the b smallest-rho agents."""
    n = count_profile(rho, alpha)
    k = np.arange(1, len(n) + 1)
    return int(max(0, (k - np.maximum(n - b, 0)).max(initial=0)))


def batch_deficiency(rho, alpha):
    """Vectorised over a leading batch axis. rho (B,N), alpha (B,M) or (M,)."""
    rho = np.sort(np.asarray(rho, float), axis=-1)
    alpha = np.asarray(alpha, float)
    if alpha.ndim == 1:
        alpha = np.broadcast_to(alpha, (rho.shape[0], alpha.size))
    a = np.sort(alpha, axis=-1)
    n = np.stack([np.searchsorted(rho[b], a[b], side="right") for b in range(rho.shape[0])])
    k = np.arange(1, a.shape[1] + 1)
    return np.maximum(0, (k - n).max(axis=1))


# ------------------------------------------------------- projection layers
def nested_greedy(rho, alpha, score=None, value=None):
    """Policy-guided greedy nested projection (GNP).

    1. Task set: matroid greedy over the transversal matroid, tasks in order of
       decreasing value (ties: most demanding first). A task is added iff the
       set stays matchable, tested in O(|S| log |S|) by the deficiency formula.
       Without values every basis has size M - d, so this is max-cardinality.
    2. Agents: tasks of the chosen set in increasing alpha; each takes the
       still-free eligible agent with the highest policy score (any free
       eligible agent keeps the rest matchable, by nestedness).
    Returns assign[i] in {IDLE, 0..M-1}.
    """
    rho = np.asarray(rho, float)
    alpha = np.asarray(alpha, float)
    N, M = rho.size, alpha.size
    rs = np.sort(rho)
    if value is None:
        order = np.argsort(alpha, kind="stable")
    else:
        order = np.lexsort((alpha, -np.asarray(value, float)))
    chosen = []
    chosen_alpha = []
    for j in order:
        trial = np.sort(np.append(chosen_alpha, alpha[j]))
        n = np.searchsorted(rs, trial, side="right")
        if np.all(n >= np.arange(1, trial.size + 1)):
            chosen.append(j)
            chosen_alpha = list(trial)
        if len(chosen) == N:
            break
    assign = np.full(N, IDLE, dtype=int)
    free = np.ones(N, bool)
    for j in sorted(chosen, key=lambda t: alpha[t]):
        elig = np.flatnonzero(free & (rho <= alpha[j]))
        if score is None:
            i = elig[np.argmax(rho[elig])]   # tightest fit: keep strong agents free
        else:
            i = elig[np.argmax(score[elig, j])]
        assign[i] = j
        free[i] = False
    return assign


BIG = 1.0e4


def lexicographic_projection(elig, proposal, value=None, prev=None, eps_prev=0.0):
    """Exact projection by max-weight bipartite matching (Hungarian).

    Lexicographic objective, enforced by weight scaling:
      (1) maximise the number of covered tasks;
      (2) maximise covered value (if given);
      (3) maximise agreement with the policy's proposal (+ eps_prev * keep prev).
    elig: (N,M) bool eligibility (may encode hysteresis, so need not be nested).
    proposal: (N,) int in {IDLE,0..M-1}. Returns assign (N,).
    """
    N, M = elig.shape
    if value is None:
        value = np.ones(M)
    value = np.asarray(value, float)
    # Scale so that each level strictly dominates the total of the next:
    # agreement total <= N*(1+eps_prev) < c_v * (smallest value gap) and
    # value total <= M*c_v*max(value) < big.
    uv = np.unique(value)
    # Lexicographic scaling (Thm 1(ii)). Agreement contributes at most
    # min(N,M)*(1+eps_prev) < c_v*gap, so any single value-improving basis
    # exchange (worth >= gap) beats any agreement change; the value plus
    # agreement total of a whole matching is below `big`, so cardinality first.
    gap = float(np.min(np.diff(uv))) if uv.size > 1 else 1.0
    c_v = (N + 1) * (1.0 + eps_prev) / gap if uv.size > 1 else 0.0
    vmax = float(uv.max()) if uv.size else 0.0
    big = M * (c_v * vmax + 1.0 + eps_prev) + 1.0
    W = np.full((N, M), big) + c_v * value[None, :]
    agree = np.zeros((N, M))
    ok = proposal >= 0
    agree[np.flatnonzero(ok), proposal[ok]] = 1.0
    W += agree
    if prev is not None and eps_prev > 0:
        okp = prev >= 0
        keep = np.zeros((N, M))
        keep[np.flatnonzero(okp), prev[okp]] = 1.0
        W += eps_prev * keep
    # Ineligible pairs get weight 0 and are discarded after solving; since
    # every eligible weight exceeds the whole value+agreement budget, the
    # solver never trades an eligible pair for an ineligible one.
    Wf = np.where(elig, W, 0.0)
    ri, ci = linear_sum_assignment(Wf, maximize=True)
    assign = np.full(N, IDLE, dtype=int)
    for i, j in zip(ri, ci):
        if elig[i, j]:
            assign[i] = j
    return assign


def eligibility(rho, alpha, holder_of=None, h=0.0, lookahead=0.0, eta=0.0,
                keep_lookahead=0.0):
    """(N,M) eligibility used by the projection.

    Acquire task j:  rho + lookahead      <= (1 - eta) * alpha_j - h
    Keep    task j:  rho + keep_lookahead <= alpha_j      (current holder only)
    h / eta give absolute / relative hysteresis (Thm 2); lookahead gives
    predictive acquisition and keep_lookahead = L_rho * dt gives predictive
    release (Thm 3). With all four zero this is the plain constraint."""
    rho = np.asarray(rho, float)[:, None]
    a = np.asarray(alpha, float)[None, :]
    acquire = rho + lookahead <= (1.0 - eta) * a - h
    if holder_of is None:
        return acquire
    # the holder's own edge is governed by the keep rule alone
    el = acquire.copy()
    ok = holder_of >= 0
    idx = np.flatnonzero(ok)
    el[idx, holder_of[ok]] = (rho[idx, 0] + keep_lookahead <= a[0, holder_of[ok]])
    return el


def resolve_conflicts(proposal, M):
    """Non-projected baselines: first claimant (lowest index) wins a task."""
    taken = np.zeros(M, bool)
    out = np.full(proposal.size, IDLE, dtype=int)
    for i, j in enumerate(proposal):
        if j >= 0 and not taken[j]:
            out[i] = j
            taken[j] = True
    return out


# ---------------------------------------------------------- brute force
def brute_max_matching(elig):
    """Reference oracle: Hopcroft-Karp via scipy on the eligibility graph."""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import maximum_bipartite_matching
    if elig.size == 0:
        return 0
    m = maximum_bipartite_matching(csr_matrix(elig.astype(np.int8)), perm_type="column")
    return int((m >= 0).sum())


def nested_greedy_fast(rho, alpha):
    """Unweighted GNP in O(N log N + M log M): two pointers over sorted lists.
    Task j (ascending alpha) takes the next unused agent in ascending-rho order
    if that agent is eligible; by nestedness this is a maximum matching."""
    rho = np.asarray(rho, float)
    alpha = np.asarray(alpha, float)
    ai = np.argsort(rho, kind="stable")
    tj = np.argsort(alpha, kind="stable")
    rs = rho[ai]
    assign = np.full(rho.size, IDLE, dtype=int)
    used = 0
    for j in tj:
        if used < rs.size and rs[used] <= alpha[j]:
            assign[ai[used]] = j
            used += 1
    return assign
