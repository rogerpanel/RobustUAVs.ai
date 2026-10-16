"""Seed discipline and common random numbers (runbook P1.3)."""
import hashlib
import re

import numpy as np

import constants as C
from episode import EpisodeCfg, run_episode
from plant import FleetPlant


def _traj_hash(seed, **kw):
    p = FleetPlant(4, seed, 20.0, kw)
    h = hashlib.sha256()
    for k in range(200):
        U = np.tile([[0.5, -0.2]], (4, 1)) * np.sin(0.05 * k)
        P = p.step(U)
        h.update(np.round(P, 12).tobytes()); h.update(np.round(p.rho, 12).tobytes())
    return h.hexdigest()


def test_same_seed_same_trajectory():
    assert _traj_hash(10001) == _traj_hash(10001)
    assert _traj_hash(10001) != _traj_hash(10002)


def test_crn_wind_and_rho_shared_across_cells():
    """Wind and rho depend on the mission seed only, not on the filter, planner or budget."""
    a = FleetPlant(4, 10003, 20.0, dict(b_adv=0.0))
    b = FleetPlant(4, 10003, 10.0, dict(b_adv=5.0))
    for k in range(300):
        wa = a.nature.disturbance(a.layout, a.X[:, :2]); wb = b.nature.disturbance(b.layout, b.X[:, :2])
        assert np.array_equal(wa, wb)
        assert np.array_equal(a.cert.step(), b.cert.step())


def test_episode_records_reproducible():
    cfg = dict(n_uav=2, m=20.0, mission_seed=10004, horizon_s=20.0)
    r1 = run_episode(EpisodeCfg(**cfg)); r2 = run_episode(EpisodeCfg(**cfg))
    for k in ("violations_corridor", "interventions", "fallback_steps", "min_true_margin", "progress_pct"):
        assert r1[k] == r2[k]


def test_no_wall_clock_rng():
    for f in C.HERE.glob("*.py"):
        src = f.read_text()
        assert "time.time()" not in src, f
        assert not re.search(r"default_rng\(\s*\)", src), f
        assert "np.random.seed(" not in src, f
