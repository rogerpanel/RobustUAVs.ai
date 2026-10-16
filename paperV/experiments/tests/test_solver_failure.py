"""Injected solver failures (rate 0.2) and timeouts (rate 0.05), plus bursts long enough to exhaust
the latched tail: 0 violations, the latched tail is used, and loiter is reached (runbook P1.3)."""
import numpy as np

import constants as C
import filter as F
from episode import EpisodeCfg, run_episode


def test_injected_failures(monkeypatch):
    rng = np.random.default_rng(10400)
    orig = F.PredictiveSafetyFilter._certify
    state = {"k": 0}

    def flaky(self, i, ax, z0, b, u):
        if self.plan[i][ax] is None:                 # dispatch (A5) is not what this test injects into
            return orig(self, i, ax, z0, b, u)
        state["k"] += 1
        burst = (state["k"] // 8) % 150 < 30 and i == 0          # ~30-step outages on aircraft 0
        r = rng.random()
        if burst or r < 0.2:
            return None, "injected_failure", "injected", np.nan
        if r < 0.25:
            self.counts["timeouts"] += 1
            return None, "timeout", "injected", np.nan
        return orig(self, i, ax, z0, b, u)

    monkeypatch.setattr(F.PredictiveSafetyFilter, "_certify", flaky)
    tot_tail = tot_loiter = 0
    for k, (planner, m, lev, b) in enumerate([("prop_press", 20.0, "b1", 5.463), ("scripted", 20.0, "b0", 0.0),
                                              ("prop_bangbang", 10.0, "b0", 0.0), ("prop_far", 20.0, "b2", 6.522)]):
        r = run_episode(EpisodeCfg(n_uav=4, m=m, b_tot_level=lev, b_tot_m=b, planner=planner, w_mode="vertex",
                                   e_mode="vertex", mission_seed=10400 + k))
        assert r["status"] == "ok"
        assert r["violations_corridor"] == 0, r
        assert not r["assumption_violated"]
        tot_tail += r["filter_counts"]["tail"]; tot_loiter += r["filter_counts"]["loiter"]
    assert tot_tail > 0 and tot_loiter > 0
