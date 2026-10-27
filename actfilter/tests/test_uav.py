"""The UAV model is a thin adapter: decisions must equal Paper V's filter run directly."""
import numpy as np
import pytest

from actfilter.policy import from_dict

pytest.importorskip("osqp")
pytest.importorskip("clarabel")

POLICY = {"models": {"fleet": {"kind": "uav", "params": {"n": 2, "m": 20.0, "b_tot": 0.0}}},
          "tools": {"command": {"model": "fleet", "accel_field": "accel"}}}


def obs(x):
    return {"x_hat": x.tolist(), "rho": [1.0, 1.0]}


def test_requires_fresh_observation():
    k = from_dict(POLICY)
    d = k.decide("s", "command", {"accel": [[0, 0], [0, 0]]})
    assert d.kind == "deny" and "fresh" in d.reason
    k.observe("s", "fleet", obs(np.zeros((2, 4))))
    assert k.decide("s", "command", {"accel": [[0, 0], [0, 0]]}).kind in ("allow", "project")
    assert k.decide("s", "command", {"accel": [[0, 0], [0, 0]]}).kind == "deny"   # one command per estimate


def test_matches_paper_v_filter_and_projects_unsafe_commands():
    from actfilter.models.uav import _paperv
    C, A, P = _paperv()
    k = from_dict(POLICY)
    ref = P.PredictiveSafetyFilter(A.Tightening(w_bar=C.load_wbar(), b_tot=0.0, m=20.0), n=2)
    rng = np.random.default_rng(3)
    x = np.zeros((2, 4)); x[:, 0] = [20.0, 60.0]
    kinds = set()
    for step in range(30):
        u = rng.uniform(-4, 4, size=(2, 2))
        u[0, 1] = 4.0                                    # aircraft 0 keeps pushing toward the corridor edge
        k.observe("s", "fleet", {"x_hat": x.tolist(), "rho": [1.0, 1.0]})
        d = k.decide("s", "command", {"accel": u.tolist()})
        r = ref.filter(x, u, np.array([1.0, 1.0]))
        a = np.asarray(d.args["accel"])
        np.testing.assert_allclose(a, r.a_star, atol=1e-9)
        kinds.add(d.kind)
        x[:, 2:] += a * C.DT; x[:, :2] += x[:, 2:] * C.DT    # crude plant, enough to move the state
        assert abs(x[0, 1]) <= 20.0                     # lateral corridor half-width m
    assert "project" in kinds


@pytest.mark.parametrize("bad", [[[0, 0]], [[0, 0], [0, float("nan")]], "fast", [[0, 0], [0, 0], [0, 0]]])
def test_malformed_commands_denied(bad):
    k = from_dict(POLICY)
    k.observe("s", "fleet", obs(np.zeros((2, 4))))
    assert k.decide("s", "command", {"accel": bad}).kind == "deny"
