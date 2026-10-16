"""Scalar budget tightening b_tot(eps) over Paper IV quantities, and the one-step
nestedness / transparency study (Prop. 3(a)-(b), Lemma 1).

  b_tot(eps) = e^{L T_c} delta_net(theta) + delta_adv(theta) + s*(eps),   pbar(s*) <= eps

delta_adv = 4.371 m (paperIV/results/e4_delta_adv.csv), net tube 2.65 m at theta = 0.25 s,
s*(eps) from the dependence-sharp union bound over Paper IV's committed marginals
(paperIV/results/e3_marginals.npz: gnss, fault, env), computed with Paper IV's own
depbounds.union_bound imported read-only from the clone.
"""
from __future__ import annotations

import importlib.util
import time

import numpy as np

from constants import REPO, DELTA_ADV, net_tube, EPS_RISK, NP, U_MAX, V_MAX


def _depbounds():
    spec = importlib.util.spec_from_file_location("p4_depbounds", REPO / "paperIV/experiments/depbounds.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def s_star(eps=EPS_RISK, method="union"):
    db = _depbounds()
    d = np.load(REPO / "paperIV/results/e3_marginals.npz")
    X = [d["gnss"], d["fault"], d["env"]]
    lo, hi = 0.0, 20.0
    f = (lambda s: db.union_bound(X, s)) if method == "union" else (lambda s: db.ra_bound(X, s, N=1000))
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        if f(mid) <= eps:
            hi = mid
        else:
            lo = mid
    return hi


def budget_levels():
    """Ordered sweep of the scalar tightening (m) with provenance labels."""
    ss = s_star()
    return [
        (0.0, "none"), (0.5, "sweep"), (1.0, "sweep"), (2.0, "sweep"),
        (DELTA_ADV, "delta_adv (P4)"),
        (DELTA_ADV + net_tube(), "delta_adv + e^{LT}delta_net(0.25 s)"),
        (DELTA_ADV + net_tube() + ss, f"full b_tot(eps={EPS_RISK}) with s*={ss:.2f} m"),
    ], ss


# ---------------------------------------------------------------- nestedness study
def nestedness_study(levels, M=300, N=4, seed=6100):
    """For M random (state, rho, proposal) instances evaluate, at every budget level, with the
    interior-point solver (no time limit): feasibility of the re-anchored problem,
    transparency (problem with v_0 := u_des feasible) and the filter deviation.
    Returns per-instance rows. Nestedness predicts feasible/transparent are non-increasing
    and deviation non-decreasing in b; Lemma 1 predicts transparent <=> deviation ~ 0."""
    import scipy.sparse as sp
    from admissible import TighteningConfig
    from filter import SafetyFilter, UBUF
    from plant import make_geometry

    rng = np.random.default_rng(seed)
    geo = make_geometry(N)
    filters = [SafetyFilter(geo, TighteningConfig(b_tot=b)) for b in levels]
    rows = []
    xl, xh, yh = -geo.c[1], geo.c[0], geo.c[2]
    for m in range(M):
        # positions: spread over the arena, biased toward walls and neighbours
        P = np.stack([rng.uniform(xl + 2, xh - 2, N), rng.uniform(-yh + 2, yh - 2, N)], 1)
        if rng.random() < 0.5:                     # pull one pair close together
            i, j = rng.choice(N, 2, replace=False)
            P[j] = P[i] + rng.normal(0, 30, 2)
        V = rng.uniform(-0.5 * V_MAX, 0.5 * V_MAX, (N, 2)) * rng.random()
        X = np.concatenate([P, V], 1)
        rho = rng.uniform(0.1, 5.0, N)
        u_des = rng.uniform(-U_MAX, U_MAX, (N, 2)) * rng.random()
        for li, (b, f) in enumerate(zip(levels, filters)):
            normals = f._ref_normals(X) if f.pairs else None
            l, u, vals, bnode, vl, sep = f.constraints_for(X, rho, normals, 0)
            A = sp.csc_matrix((vals[f.perm], f.A.indices, f.A.indptr), shape=f.A.shape)
            q = np.zeros(f.nvar); q[f.v0_idx[:, 0]] = -u_des[:, 0]; q[f.v0_idx[:, 1]] = -u_des[:, 1]
            st, x = f._clarabel(f.P, q, A, l, u, 30.0)
            feas = st in ("Solved", "AlmostSolved")
            dev = np.nan; verified = False
            if feas:
                ok, Vp = f._accept(x, X, bnode, vl, sep)
                verified = bool(ok)
                dev = float(np.abs(x[f.v0_idx] - u_des).max())
            # transparency: fix v_0 = u_des (input rows k=0)
            l2, u2 = l.copy(), u.copy()
            r0 = [f.r_inp + (i * NP + 0) * 2 + ax for i in range(N) for ax in range(2)]
            uu = u_des.reshape(-1)
            if np.all(np.abs(uu) <= f.t.u_nom - UBUF):
                l2[r0] = uu; u2[r0] = uu
                st2, _ = f._clarabel(f.P, q, A, l2, u2, 30.0)
                transp = st2 in ("Solved", "AlmostSolved")
            else:
                transp = False
            rows.append(dict(instance=m, level=li, b_tot=b, feasible=int(feas), verified=int(verified),
                             transparent=int(transp), dev=dev, status=st))
    return rows
