"""NoFilter + boundary-pressing oracle violates in >= 90% of episodes (the attack is strong enough)."""
from episode import EpisodeCfg, run_episode


def test_no_filter_press_violates():
    n = 20; bad = 0
    for k in range(n):
        r = run_episode(EpisodeCfg(n_uav=4, m=20.0, b_tot_level="b1", b_tot_m=5.463, filter="none",
                                   planner="prop_press", e_mode="vertex", mission_seed=10500 + k, horizon_s=30.0))
        bad += int(r["violations_corridor"] > 0)
    assert bad >= 0.9 * n
