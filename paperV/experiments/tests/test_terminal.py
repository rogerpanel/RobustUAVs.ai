"""X_f is robust invariant under the loiter (braking) controller plus the tube feedback (runbook P1.3).

10^5 random nominal states in X_f per axis, disturbance at the vertices of the w_bar box
(constant worst sign, and random vertex switching). Starting with the estimate on the nominal,
the estimate must stay inside the corridor shrunk by rho_bar + b_tot for 600 steps (60 s), with
|u| <= U_MAX and |v| <= V_MAX, so the true position stays inside for every |e| <= rho_bar + b.
"""
import numpy as np

import constants as C
from admissible import Tightening, axis_bounds, brake_input

N = 100_000
STEPS = 600


def _sample_terminal(rng, b, n, vcap):
    out_p, out_v = [], []
    while sum(len(x) for x in out_p) < n:
        v = rng.uniform(-vcap, vcap, 4 * n)
        p = rng.uniform(b.term_lo, b.term_hi, 4 * n)
        ok = ((p + b.term_k * np.maximum(v, 0) <= b.term_hi) & (p <= b.term_hi) &
              (p + b.term_k * np.minimum(v, 0) >= b.term_lo) & (p >= b.term_lo))
        out_p.append(p[ok]); out_v.append(v[ok])
    return np.concatenate(out_p)[:n], np.concatenate(out_v)[:n]


def _run(axis, m, b_tot, switching, seed):
    rng = np.random.default_rng(seed)
    t = Tightening(w_bar=C.load_wbar(), b_tot=b_tot, m=m)
    assert t.half_width()[0] > 0
    b = axis_bounds(t, np.array([t.rho_bar]), axis)[0]
    vcap = C.TERMINAL_V_LAT if axis == 1 else C.V_MAX - t.ev[-1]
    zp, zv = _sample_terminal(rng, b, N, vcap)
    xp, xv = zp.copy(), zv.copy()
    lo_face = (C.S_LO if axis == 0 else -m) + t.rho_bar + b_tot
    hi_face = (C.S_HI if axis == 0 else m) - t.rho_bar - b_tot
    sign = rng.choice([-1.0, 1.0], N)
    worst = np.inf
    for k in range(STEPS):
        v_nom = brake_input(zv, t.a_brake)
        u = v_nom - C.KP * (xp - zp) - C.KD * (xv - zv)
        assert np.all(np.abs(u) <= C.U_MAX + 1e-9)
        if switching:
            sign = rng.choice([-1.0, 1.0], N)
        w = t.w_bar * sign
        xp, xv = xp + C.DT * xv + 0.5 * C.DT ** 2 * (u + w), xv + C.DT * (u + w)
        zp, zv = zp + C.DT * zv + 0.5 * C.DT ** 2 * v_nom, zv + C.DT * v_nom
        worst = min(worst, float(np.min(np.minimum(hi_face - xp, xp - lo_face))))
        assert np.all(np.abs(xv) <= C.V_MAX + 1e-9)
    return worst


def test_lateral_invariant():
    for m, b in ((20.0, 0.0), (20.0, 6.522), (10.0, 0.0)):
        for sw in (False, True):
            assert _run(1, m, b, sw, 10100 + int(m) + int(10 * b)) >= -1e-9


def test_along_track_invariant():
    for sw in (False, True):
        assert _run(0, 20.0, 5.463, sw, 10150) >= -1e-9
