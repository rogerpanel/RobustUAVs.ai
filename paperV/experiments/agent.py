"""Planner interface (the 'LLM' slot) and non-LLM planners.

Every planner emits, each filter tick, one JSON action per aircraft:
  {"uav": i, "mode": "goto",  "waypoint": [x, y], "speed": s}
  {"uav": i, "mode": "hold"}
  {"uav": i, "mode": "velocity", "velocity": [vx, vy]}
  {"uav": i, "mode": "accel", "accel": [ax, ay]}      (action-space adversaries only)
pi_nom maps an action and the navigation state to the desired acceleration u_des
that the filter compares against. The filter never reads anything else from the planner.
"""
from __future__ import annotations

import hashlib
import json
import time

import numpy as np

from constants import U_MAX, V_MAX, R_GOAL

SCHEMA_MODES = ("goto", "hold", "velocity", "accel")
K_V = 1.0          # [model] velocity-tracking gain of pi_nom
A_DEC = 2.0        # [model] planned deceleration near a waypoint


def validate(action, N):
    """Schema check; invalid actions become 'hold' (fail-safe parse)."""
    try:
        i = int(action["uav"]); m = action["mode"]
        assert 0 <= i < N and m in SCHEMA_MODES
        if m == "goto":
            w = [float(v) for v in action["waypoint"]]; assert len(w) == 2
            float(action.get("speed", 10.0))
        elif m == "velocity":
            assert len(action["velocity"]) == 2
        elif m == "accel":
            assert len(action["accel"]) == 2
        return action, True
    except Exception:
        return {"uav": int(action.get("uav", 0)) if isinstance(action, dict) else 0, "mode": "hold"}, False


class Tracker:
    """pi_nom: action -> u_des, with per-aircraft hold points."""

    def __init__(self, N):
        self.hold = [None] * N

    def u_des(self, actions, X):
        """Returns u_des; also stores self.vd, the velocity each action asks for (used only for
        the denial decomposition): goto/velocity -> commanded velocity, hold -> brake target,
        accel -> velocity reached by holding the proposed acceleration for 1 s."""
        N = X.shape[0]
        U = np.zeros((N, 2))
        self.vd = np.zeros((N, 2))
        for a in actions:
            i = a["uav"]; p, v = X[i, :2], X[i, 2:]
            m = a["mode"]
            if m != "hold":
                self.hold[i] = None
            if m == "accel":
                U[i] = np.asarray(a["accel"], float)
                self.vd[i] = np.clip(v + np.clip(U[i], -U_MAX, U_MAX) * 1.0, -V_MAX, V_MAX)
                continue
            if m == "velocity":
                vd = np.clip(np.asarray(a["velocity"], float), -V_MAX, V_MAX)
            else:
                if m == "hold":
                    if self.hold[i] is None:
                        self.hold[i] = p + v * np.abs(v) / (2 * A_DEC)   # brake point
                    wp, s = self.hold[i], 3.0
                else:
                    wp, s = np.asarray(a["waypoint"], float), float(a.get("speed", 10.0))
                d = wp - p; dist = np.linalg.norm(d)
                sp = min(s, np.sqrt(2 * A_DEC * max(dist - 0.5, 0.0)))
                vd = d / max(dist, 1e-9) * sp
            U[i] = K_V * (vd - v)
            self.vd[i] = vd
        return np.clip(U, -U_MAX, U_MAX)


class Planner:
    name = "base"

    def reset(self, geo, rng):
        self.geo, self.rng = geo, rng

    def propose(self, obs):
        raise NotImplementedError


class BenignPlanner(Planner):
    """A0: scripted mission planner -- go to the goal at the assigned cruise speed, then hold."""
    name = "benign"

    def propose(self, obs):
        acts = []
        for i in range(self.geo.N):
            if obs["done"][i]:
                acts.append({"uav": i, "mode": "hold"})
            else:
                acts.append({"uav": i, "mode": "goto", "waypoint": self.geo.goals[i].tolist(),
                             "speed": float(self.geo.speeds[i])})
        return acts


class RandomPlanner(Planner):
    """Random waypoints in the arena bounding box (resampled every 5 s), random speed."""
    name = "random"

    def reset(self, geo, rng):
        super().reset(geo, rng)
        self.wp = None; self.next_t = 0.0

    def propose(self, obs):
        N = self.geo.N
        if obs["t"] >= self.next_t:
            xh, xl = self.geo.c[0], -self.geo.c[1]; yh = self.geo.c[2]
            self.wp = np.stack([self.rng.uniform(xl, xh, N), self.rng.uniform(-yh, yh, N)], 1)
            self.sp = self.rng.uniform(2, V_MAX, N)
            self.next_t = obs["t"] + 5.0
        return [{"uav": i, "mode": "goto", "waypoint": self.wp[i].tolist(), "speed": float(self.sp[i])}
                for i in range(N)]


class StallPlanner(Planner):
    """In-envelope denial: behaves benignly, then (at a random onset) proposes safe holds forever."""
    name = "stall"

    def reset(self, geo, rng):
        super().reset(geo, rng)
        self.onset = rng.uniform(5.0, 30.0)
        self.benign = BenignPlanner(); self.benign.reset(geo, rng)

    def propose(self, obs):
        if obs["t"] < self.onset:
            return self.benign.propose(obs)
        return [{"uav": i, "mode": "hold"} for i in range(self.geo.N)]


class MockLLMPlanner(Planner):
    """Stub for future real-LLM runs: JSON-in/JSON-out with a sha256 completion cache and
    usage logging. `backend` is any callable(prompt:str)->str. The default backend is a
    deterministic mock that returns the benign plan (or, with inject=True, a hold for all
    aircraft -- the in-envelope denial an injected instruction would cause)."""
    name = "mockllm"

    def __init__(self, backend=None, model_id="mock-0", inject=False):
        self.backend = backend or self._mock
        self.model_id, self.inject = model_id, inject
        self.cache, self.usage = {}, []

    def _mock(self, prompt):
        obs = json.loads(prompt)
        if self.inject:
            return json.dumps([{"uav": i, "mode": "hold"} for i in range(len(obs["goals"]))])
        return json.dumps([{"uav": i, "mode": "goto", "waypoint": g, "speed": 10.0}
                           for i, g in enumerate(obs["goals"])])

    def propose(self, obs):
        prompt = json.dumps({"t": round(obs["t"], 2), "pos": np.round(obs["X"][:, :2], 1).tolist(),
                             "goals": self.geo.goals.tolist(), "done": [bool(d) for d in obs["done"]]})
        key = hashlib.sha256(f"{self.model_id}|{prompt}".encode()).hexdigest()
        t0 = time.perf_counter()
        if key not in self.cache:
            self.cache[key] = self.backend(prompt)
        out = self.cache[key]
        self.usage.append({"key": key[:12], "chars_in": len(prompt), "chars_out": len(out),
                           "latency_s": time.perf_counter() - t0})
        try:
            acts = json.loads(out)
        except Exception:
            acts = []
        got = {}
        for a in acts if isinstance(acts, list) else []:
            a, _ = validate(a, self.geo.N); got[a["uav"]] = a
        return [got.get(i, {"uav": i, "mode": "hold"}) for i in range(self.geo.N)]


def reached(X, geo):
    return np.linalg.norm(X[:, :2] - geo.goals, axis=1) <= R_GOAL
