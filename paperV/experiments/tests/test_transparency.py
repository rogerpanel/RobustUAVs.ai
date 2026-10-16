"""Lemma 1 (transparency) on random states (runbook P1.3).

If pi_nom is the first input of some feasible plan, the filter returns exactly pi_nom
(||v0* - pi_nom|| <= 1e-6) with status transparent. Conversely, whenever the filter projects,
no feasible plan starts with pi_nom (checked with an independent LP via Clarabel)."""
import numpy as np
import scipy.sparse as sp

import constants as C
from admissible import Tightening, axis_bounds, check_plan
from filter import AxisQP, PredictiveSafetyFilter


def _exists_plan_starting_with(qp, z0, b, u):
    """Independent feasibility LP with v0 fixed (Clarabel, high accuracy) + exact check."""
    import clarabel
    lo, hi = qp.bounds(z0, b)
    if not (lo[0] - 1e-12 <= u <= hi[0] + 1e-12):
        return False
    lo[0] = hi[0] = u
    if np.any(lo > hi):
        return False
    A = sp.vstack([qp.A, -qp.A]).tocsc(); bb = np.concatenate([hi, -lo])
    s = clarabel.DefaultSettings(); s.verbose = False
    sol = clarabel.DefaultSolver(sp.csc_matrix((qp.n, qp.n)), np.zeros(qp.n), A, bb,
                                 [clarabel.NonnegativeConeT(len(bb))], s).solve()
    if "Solved" not in str(sol.status):
        return False
    x = np.clip(np.asarray(sol.x), -b.u_lim, b.u_lim); x[0] = u
    return check_plan(z0, x, b)[0]


def test_lemma1_random_states():
    rng = np.random.default_rng(10200)
    t = Tightening(w_bar=C.load_wbar(), b_tot=5.463, m=20.0)
    n_tr = n_pr = 0
    for k in range(600):
        f = PredictiveSafetyFilter(t, n=1)
        rho = np.array([rng.uniform(0.2, t.rho_bar)])
        hw = t.m - t.beta_inf(rho)[0]
        X = np.array([[rng.uniform(0, 700), rng.uniform(-hw, hw), rng.uniform(0, 14), rng.uniform(-3, 3)]])
        u = rng.uniform(-C.U_MAX, C.U_MAX, (1, 2))
        if k % 2:                           # near the tightened face, moving and pushing outward
            sg = rng.choice([-1.0, 1.0])
            X[0, 1] = sg * hw * rng.uniform(0.85, 1.3); X[0, 3] = sg * rng.uniform(0.5, 3.0)
            u[0, 1] = sg * rng.uniform(0.5, C.U_MAX)
        if k % 3 == 0:                      # warm the fast path with a previous plan
            f.filter(X, u * 0, rho)
            X = X.copy(); X[0, :2] += X[0, 2:] * C.DT
        out = f.filter(X, u, rho)
        for ax in (0, 1):
            b = axis_bounds(t, rho, ax)[0]
            z0 = X[0, [ax, 2 + ax]]
            exists = _exists_plan_starting_with(f.qp[0][ax], z0, b, float(u[0, ax]))
            if exists:
                assert abs(out.v0[0, ax] - u[0, ax]) <= 1e-6, (k, ax)
        if out.status[0] == "transparent":
            n_tr += 1
            assert np.abs(out.v0[0] - u[0]).max() <= 1e-6
        elif out.status[0] == "projected":
            n_pr += 1
            assert not all(_exists_plan_starting_with(f.qp[0][ax], X[0, [ax, 2 + ax]], axis_bounds(t, rho, ax)[0],
                                                      float(u[0, ax])) for ax in (0, 1))
    print('transparent', n_tr, 'projected', n_pr)
    assert n_tr > 20 and n_pr > 20, (n_tr, n_pr)
