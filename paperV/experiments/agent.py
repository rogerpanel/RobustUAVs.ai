"""Planner side: the action schema, pi_nom, and the non-LLM planners (runbook P1.1, P2.1).

Per-aircraft action (JSON):
  {"uav": i, "type": "waypoint", "waypoint": [x, y]}     world coordinates
  {"uav": i, "type": "velocity", "velocity": [vx, vy]}   world frame, m/s
  {"uav": i, "type": "mode", "mode": "nominal" | "loiter" | "rtl"}
  {"uav": i, "type": "task", "task": j}                  fly to task site j (eligibility-filtered)
Malformed or out-of-schema actions become {"type": "mode", "mode": "loiter"} (hold) and are
counted as parse_fail: planner behaviour, logged and reported, never an API failure.

pi_nom(x_hat, a) is the tracking law that turns the latest action into the nominal input the
filter compares against; speeds are capped at V_MAX. The filter never reads anything else.

The fail-loud LLM planner of P3 (LLMPlanner) is added to this module in P3.
"""
from __future__ import annotations

import math

import numpy as np

try:
    from . import constants as C
    from .admissible import discrete_project, IDLE
except ImportError:
    import constants as C
    from admissible import discrete_project, IDLE

A_DEC = 0.8          # [model] m/s^2 planned deceleration of pi_nom toward a stopping target
TYPES = ("waypoint", "velocity", "mode", "task")
MODES = ("nominal", "loiter", "rtl")

ACTION_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["uav", "type"],
    "additionalProperties": False,
    "properties": {
        "uav": {"type": "integer", "minimum": 0},
        "type": {"enum": list(TYPES)},
        "waypoint": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
        "velocity": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
        "mode": {"enum": list(MODES)},
        "task": {"type": "integer", "minimum": 0},
    },
    "allOf": [
        {"if": {"properties": {"type": {"const": t}}}, "then": {"required": [t]}} for t in TYPES
    ],
}
HOLD = {"type": "mode", "mode": "loiter"}


def _finite_pair(x):
    return (isinstance(x, (list, tuple)) and len(x) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in x))


def validate(action, n, n_tasks=len(C.WAYPOINTS_S)):
    """Fast validator equivalent to ACTION_SCHEMA plus range checks (tests/test_agent_schema.py
    checks the equivalence). Returns (action, ok); a failure becomes HOLD for that aircraft."""
    try:
        if not isinstance(action, dict) or set(action) - {"uav", "type", "waypoint", "velocity", "mode", "task"}:
            raise ValueError
        i = action["uav"]
        if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < n:
            raise ValueError
        t = action["type"]
        if t == "waypoint":
            ok = _finite_pair(action["waypoint"])
        elif t == "velocity":
            ok = _finite_pair(action["velocity"])
        elif t == "mode":
            ok = action["mode"] in MODES
        elif t == "task":
            j = action["task"]
            ok = isinstance(j, int) and not isinstance(j, bool) and 0 <= j < n_tasks
        else:
            ok = False
        if not ok:
            raise ValueError
        return action, True
    except Exception:
        i = action.get("uav") if isinstance(action, dict) else None
        i = i if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < n else None
        return (dict(HOLD, uav=i) if i is not None else None), False


def actions_for_fleet(raw, n):
    """List of raw actions -> one validated action per aircraft (missing -> HOLD) and the parse-fail count."""
    if not isinstance(raw, list):
        return [dict(HOLD, uav=i) for i in range(n)], n
    out = [None] * n
    fails = 0
    for a in raw:
        v, ok = validate(a, n)
        fails += int(not ok)
        if ok and out[v["uav"]] is None:
            out[v["uav"]] = v
        elif not ok and v is not None and out[v["uav"]] is None:
            out[v["uav"]] = v                      # HOLD for the aircraft the bad action named
    for i in range(n):
        if out[i] is None:                         # no action at all for this aircraft
            out[i] = dict(HOLD, uav=i)
            fails += 1
    return out, fails


# ------------------------------------------------------------------ pi_nom
class Tracker:
    """pi_nom with per-aircraft mission state (next waypoint, hold point, task)."""

    def __init__(self, layout, t=None):
        self.lay, self.n = layout, layout.n
        self.t = t
        self.next_wp = np.zeros(self.n, int)       # autopilot's next mission waypoint (estimate-based)
        self.hold = [None] * self.n
        self.task = np.full(self.n, IDLE)
        self.task_alpha = np.full(len(layout.waypoints), layout.m)   # alert limit of each site = corridor m
        self.vd = np.zeros((self.n, 2))
        self.mode = ["nominal"] * self.n

    def to_corridor(self, i, xy):
        o, h = self.lay.origin[i], self.lay.heading[i]
        d = np.asarray(xy, float) - o
        c, s = math.cos(h), math.sin(h)
        return np.array([c * d[0] + s * d[1], -s * d[0] + c * d[1]])

    def vec_to_corridor(self, i, v):
        h = self.lay.heading[i]; c, s = math.cos(h), math.sin(h)
        return np.array([c * v[0] + s * v[1], -s * v[0] + c * v[1]])

    def advance(self, X):
        """Advance mission waypoints when the estimate crosses a gate."""
        for i in range(self.n):
            while self.next_wp[i] < len(self.lay.waypoints) and X[i, 0] >= self.lay.waypoints[self.next_wp[i]] - C.R_REACH:
                self.next_wp[i] += 1

    @staticmethod
    def _goto(p, v, target, stop, cruise=C.V_CRUISE):
        d = target - p; dist = float(np.linalg.norm(d))
        if dist < 1e-9:
            vd = np.zeros(2)
        else:
            sp = min(cruise, math.sqrt(2 * A_DEC * dist)) if stop else cruise
            vd = d / dist * sp
        return vd

    def _hold(self, i, p, v):
        """Brake to the stopping point fixed when the hold began, then keep station there."""
        if self.hold[i] is None:
            self.hold[i] = p + v * np.abs(v) / (2 * A_DEC)
        vd = self._goto(p, v, self.hold[i], stop=True)
        self.vd[i] = vd
        return np.clip(C.K_V * (vd - v), -C.U_MAX, C.U_MAX)

    def project_tasks(self, actions, rho, lexicographic=False):
        """Discrete layer: task proposals filtered by Paper III eligibility (minimal deviation)."""
        prop = np.array([a["task"] if a["type"] == "task" else IDLE for a in actions])
        if np.all(prop == IDLE):
            return actions, 0
        prev = self.task.copy()
        if lexicographic:
            try:
                from .admissible import lexicographic_discrete
            except ImportError:
                from admissible import lexicographic_discrete
            out = lexicographic_discrete(prop, rho, self.task_alpha, prev, self.t)
        else:
            out = discrete_project(prop, rho, self.task_alpha, prev, self.t)
        changed = 0
        acts = []
        for i, a in enumerate(actions):
            if a["type"] == "task":
                if out[i] != prop[i]:
                    changed += 1
                a = dict(a, task=int(out[i])) if out[i] != IDLE else dict(HOLD, uav=i)
            acts.append(a)
        self.task = np.where(prop != IDLE, out, self.task)
        return acts, changed

    def u_des(self, actions, X):
        """(n, 2) nominal input in the corridor frame; also stores the requested velocity vd."""
        U = np.zeros((self.n, 2))
        for i, a in enumerate(actions):
            p, v = X[i, :2], X[i, 2:]
            typ = a["type"]
            holding = (typ == "mode" and (a["mode"] == "loiter" or
                                          (a["mode"] == "nominal" and self.next_wp[i] >= len(self.lay.waypoints))))
            if not holding:
                self.hold[i] = None
            if typ == "mode" and a["mode"] == "loiter":
                U[i] = self._hold(i, p, v); self.mode[i] = "loiter"
                continue
            if typ == "velocity":
                vd = np.clip(self.vec_to_corridor(i, a["velocity"]), -C.V_MAX, C.V_MAX); self.mode[i] = "velocity"
            elif typ == "waypoint":
                vd = self._goto(p, v, self.to_corridor(i, a["waypoint"]), stop=True); self.mode[i] = "waypoint"
            elif typ == "task":
                vd = self._goto(p, v, np.array([self.lay.waypoints[a["task"]], 0.0]), stop=True); self.mode[i] = "task"
            elif a["mode"] == "rtl":
                vd = self._goto(p, v, np.zeros(2), stop=True); self.mode[i] = "rtl"
            else:                                             # nominal: follow the mission
                k = self.next_wp[i]
                if k >= len(self.lay.waypoints):
                    U[i] = self._hold(i, p, v); self.mode[i] = "done"
                    continue
                last = k == len(self.lay.waypoints) - 1
                tgt = np.array([self.lay.waypoints[k] + (0.0 if last else C.R_REACH), 0.0])
                vd = self._goto(p, v, tgt, stop=False)
                vd[1] = np.clip(-C.KP / C.KD * p[1], -C.V_MAX, C.V_MAX)    # lateral: return to the centreline
                self.mode[i] = "nominal"
            sp = np.abs(vd).max()
            if sp > C.V_MAX:
                vd = vd * C.V_MAX / sp
            self.vd[i] = vd
            U[i] = np.clip(C.K_V * (vd - v), -C.U_MAX, C.U_MAX)
        return U

    def benign_u(self, X):
        """pi_nom of the scripted A0 action at the same state (denial attribution, runbook §8)."""
        saved = (self.hold[:], self.vd.copy(), self.mode[:])
        U = self.u_des([{"uav": i, "type": "mode", "mode": "nominal"} for i in range(self.n)], X)
        self.hold, self.vd, self.mode = saved[0], saved[1], saved[2]
        return U


def progress(X, U, next_wp, waypoints):
    """Along-track metres the next step would make toward the next waypoint under input U."""
    tgt = np.where(next_wp < len(waypoints), np.asarray(waypoints)[np.minimum(next_wp, len(waypoints) - 1)], np.nan)
    sgn = np.where(np.isnan(tgt), 0.0, np.sign(np.nan_to_num(tgt) - X[:, 0]))
    return sgn * (X[:, 2] * C.DT + 0.5 * C.DT * C.DT * U[:, 0])


# ------------------------------------------------------------------ planners
class Planner:
    name = "base"
    per_step = False          # True: queried every DT (property-test adversaries); else every PLAN_PERIOD
    kind = "scripted"

    def reset(self, layout, rng):
        self.lay, self.rng, self.n = layout, rng, layout.n

    def propose(self, obs):
        raise NotImplementedError


class ScriptedAgent(Planner):
    """A0: benign heuristic planner that flies the mission."""
    name = "scripted"

    def propose(self, obs):
        return [{"uav": i, "type": "mode", "mode": "nominal"} for i in range(self.n)]


class RandomPlanner(Planner):
    """Uniform random in-schema actions every PLAN_PERIOD (independent sanity population)."""
    name = "random"
    kind = "random"

    def propose(self, obs):
        out = []
        for i in range(self.n):
            t = TYPES[self.rng.integers(len(TYPES))]
            o = self.lay.origin[i]
            if t == "waypoint":
                a = {"type": t, "waypoint": [float(o[0] + self.rng.uniform(C.S_LO - 100, C.S_HI + 100)),
                                             float(o[1] + self.rng.uniform(-3 * self.lay.m - 20, 3 * self.lay.m + 20))]}
            elif t == "velocity":
                a = {"type": t, "velocity": [float(v) for v in self.rng.uniform(-C.V_MAX, C.V_MAX, 2)]}
            elif t == "mode":
                a = {"type": t, "mode": MODES[self.rng.integers(len(MODES))]}
            else:
                a = {"type": t, "task": int(self.rng.integers(len(C.WAYPOINTS_S)))}
            out.append(dict(a, uav=i))
        return out


class PropertyPlanner(Planner):
    """Adversarial action sequences for the Theorem 1 property test (queried every DT).

    style  uniform   : uniform random in-schema actions every step
           far       : waypoints far outside the corridor
           bangbang  : velocity setpoints +-V_MAX, switching randomly
           flap      : mode nominal <-> rtl every step
           press     : boundary-pressing oracle: velocity toward the nearest tightened face
           garbage   : NaN / malformed fields (mapped to hold, counted as parse_fail)
    """
    per_step = True
    kind = "random"

    def __init__(self, style):
        self.style = style
        self.name = "prop_" + style
        self.k = 0

    def propose(self, obs):
        X = obs["X"]; n = self.n; r = self.rng; out = []
        self.k += 1
        for i in range(n):
            o = self.lay.origin[i]
            if self.style == "uniform":
                return RandomPlanner.propose(self, obs)
            if self.style == "far":
                a = {"type": "waypoint", "waypoint": [float(o[0] + r.uniform(-2000, 3000)),
                                                      float(o[1] + r.choice([-1, 1]) * r.uniform(50, 2000))]}
            elif self.style == "bangbang":
                a = {"type": "velocity", "velocity": [float(r.choice([-1, 1]) * C.V_MAX),
                                                      float(r.choice([-1, 1]) * C.V_MAX)]}
            elif self.style == "flap":
                a = {"type": "mode", "mode": "nominal" if self.k % 2 else "rtl"}
            elif self.style == "press":
                sl = self.lay.slack(X[:, :2])[i]
                j = int(np.argmin(sl))
                d = [(0, 1), (0, -1), (1, 0), (-1, 0)][j]
                a = {"type": "velocity", "velocity": [float(C.V_MAX * d[0]), float(C.V_MAX * d[1] + r.uniform(-1, 1))]}
            elif self.style == "garbage":
                a = r.choice([{"type": "waypoint", "waypoint": [float("nan"), 1.0]},
                              {"type": "velocity", "velocity": [1e400, 0.0]},
                              {"type": "warp", "to": "moon"},
                              {"type": "mode", "mode": "land_now"},
                              {"type": "task", "task": 99}, "not an action", None])
                if isinstance(a, dict):
                    a = dict(a)
                out.append(dict(a, uav=i) if isinstance(a, dict) else a)
                continue
            out.append(dict(a, uav=i))
        return out


PLANNERS = {"scripted": ScriptedAgent, "random": RandomPlanner}
