"""Nestedness in b_tot (runbook P1.3): for random (x_hat, a), feasible under b' => feasible under
every b <= b', and an intervention under b => an intervention under every b' >= b."""
import numpy as np

import constants as C
from admissible import Tightening, axis_bounds
from filter import AxisQP
from budget import level_values
from test_transparency import _exists_plan_starting_with

N_CASES = 10_000


def _feasible(qp, z0, b):
    lo, hi = qp.bounds(z0, b)
    if np.any(lo > hi):
        return False
    x, st = qp.clarabel(z0, b, 0.0)
    if x is None:
        return False
    from admissible import check_plan
    return check_plan(z0, np.clip(x, -b.u_lim, b.u_lim), b)[0]


def test_nested_feasibility_and_intervention():
    rng = np.random.default_rng(10300)
    w = C.load_wbar()
    levels = sorted(level_values().values())
    ts = [Tightening(w_bar=w, b_tot=b, m=20.0) for b in levels]
    qps = [[AxisQP(t.k_s, np.inf), AxisQP(t.k_l, C.TERMINAL_V_LAT)] for t in ts]
    checked = 0
    for k in range(N_CASES):
        ax = k % 2
        rho = np.array([rng.uniform(0.1, ts[0].rho_bar)])
        z0 = (np.array([rng.uniform(-20, 860), rng.uniform(-2, 15)]) if ax == 0
              else np.array([rng.uniform(-16, 16), rng.uniform(-4, 4)]))
        u = rng.uniform(-C.U_MAX, C.U_MAX)
        feas, transp = [], []
        for t, q in zip(ts, qps):
            b = axis_bounds(t, rho, ax)[0]
            f = _feasible(q[ax], z0, b)
            feas.append(f)
            transp.append(f and _exists_plan_starting_with(q[ax], z0, b, u))
        for i in range(len(ts) - 1):
            assert not (feas[i + 1] and not feas[i]), (k, feas)
            assert not (transp[i + 1] and not transp[i]), (k, transp)
        checked += 1
    assert checked == N_CASES
