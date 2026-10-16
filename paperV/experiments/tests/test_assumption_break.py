"""Outside the assumptions the run is flagged; the theorem is silent there, so violations are allowed."""
import constants as C
from episode import EpisodeCfg, run_episode


def test_mismatch_beyond_wbar_flagged():
    w = C.load_wbar()
    r = run_episode(EpisodeCfg(n_uav=2, m=20.0, w_mode="vertex", w_level=3 * w, planner="prop_press",
                               e_mode="vertex", mission_seed=10600, horizon_s=30.0))
    assert r["assumption_violated"] is True


def test_jumps_flagged():
    r = run_episode(EpisodeCfg(n_uav=2, m=20.0, within=False, mission_seed=10601, horizon_s=30.0))
    assert r["assumption_violated"] is True


def test_inside_not_flagged():
    r = run_episode(EpisodeCfg(n_uav=2, m=20.0, mission_seed=10602, horizon_s=30.0))
    assert r["assumption_violated"] is False
