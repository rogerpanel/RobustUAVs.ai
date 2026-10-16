"""Theorem 1 property test (runbook P1.3).

For adversarial planners (uniform random, far waypoints, bang-bang velocity, mode flapping,
boundary pressing, garbage), mismatch drawn uniformly from the w_bar box or at its vertices,
estimate offsets random or at the worst vertex, rho processes inside (A2), and every
dispatchable (m, b_tot) cell: 0 true-state corridor violations and no actuator saturation.

pytest runs PAPERV_PROPERTY_EPISODES examples (default 12, hypothesis shrinks a counterexample);
the full gate (2,000 episodes x 12 aircraft) is `run_campaign.py --phase p1-property`.
"""
from hypothesis import given, settings, strategies as st, HealthCheck

from conftest import PROPERTY_EPISODES
from episode import EpisodeCfg, run_episode

STYLES = ("uniform", "far", "bangbang", "flap", "press", "garbage")
CELLS = (("b0", 0.0, 10.0), ("b0", 0.0, 20.0), ("b1", 5.463, 20.0), ("b2", 6.522, 20.0), ("b3", 12.752, 20.0))


@settings(max_examples=PROPERTY_EPISODES, deadline=None, derandomize=True,
          suppress_health_check=[HealthCheck.too_slow])
@given(style=st.sampled_from(STYLES), cell=st.sampled_from(CELLS), w_mode=st.sampled_from(("uniform", "vertex")),
       e_mode=st.sampled_from(("random", "vertex")), seed=st.integers(10700, 10999))
def test_theorem1(style, cell, w_mode, e_mode, seed):
    lev, b, m = cell
    r = run_episode(EpisodeCfg(n_uav=4, m=m, b_tot_level=lev, b_tot_m=b, planner="prop_" + style,
                               w_mode=w_mode, e_mode=e_mode, mission_seed=seed))
    assert r["status"] == "ok"
    assert not r["assumption_violated"], r
    assert r["violations_corridor"] == 0, (style, cell, w_mode, e_mode, seed, r["min_true_margin"])
    assert r["sat_steps"] == 0
