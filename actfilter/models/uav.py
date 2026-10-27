"""UAV fleet corridor: the kernel's front door to Paper V's predictive safety filter.

The filter is Paper V's own PredictiveSafetyFilter (paperV/experiments/filter.py),
imported, never copied: per aircraft and axis it certifies a 20-step plan in the
tightened corridor with a loiter terminal set, projects the LLM's command by QP
when it must, and falls back to the latched tail or the loiter controller when no
plan certifies. This module only adapts it to the kernel's protocol.

The state estimate comes from telemetry through `observe`, never from the agent.
Each control step needs a fresh observation; a command without one is denied,
because the filter's guarantee is relative to the estimate it was given.

Tool spec: {"model": "uav", "accel_field": "accel"}   args: {"accel": [[ax, ay], ...]} (m/s^2, n x 2)
Model params: {"n": 4, "m": 20.0, "b_tot": 0.0}
Observation: {"x_hat": [[s, l, vs, vl], ...], "rho": [...]}   (along-track, lateral, velocities; rho in m)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from ..core import Action, Decision, Reject, StateModel

PAPERV = Path(__file__).resolve().parents[2] / "paperV" / "experiments"


def _paperv():
    if str(PAPERV) not in sys.path:
        sys.path.insert(0, str(PAPERV))
    import admissible  # noqa: WPS433  (Paper V's modules, read-only)
    import constants
    import filter as psf
    return constants, admissible, psf


class UAVCorridorModel(StateModel):
    name = "uav"
    horizon = 20

    def __init__(self, n: int = 4, m: float = 20.0, b_tot: float = 0.0):
        import numpy as np
        C, A, P = _paperv()
        self.np, self.C, self.P = np, C, P
        self.n = int(n)
        self.tightening = A.Tightening(w_bar=C.load_wbar(), b_tot=float(b_tot), m=float(m))
        self.horizon = C.N_P
        self.dt = C.DT

    def initial_state(self):
        return {"filter": self.P.PredictiveSafetyFilter(self.tightening, n=self.n),
                "x_hat": None, "rho": None, "fresh": False, "step": 0}

    def observe(self, s, obs):
        np = self.np
        x = np.asarray(obs.get("x_hat"), dtype=float)
        rho = np.asarray(obs.get("rho"), dtype=float)
        if x.shape != (self.n, 4) or rho.shape != (self.n,):
            raise Reject(f"observation needs x_hat {self.n}x4 and rho of length {self.n}")
        if not (np.isfinite(x).all() and np.isfinite(rho).all()) or (rho < 0).any():
            raise Reject("observation must be finite with rho >= 0")
        return {**s, "x_hat": x, "rho": rho, "fresh": True}

    def parse(self, tool, args, spec):
        u = args.get(spec.get("accel_field", "accel"))
        try:
            arr = self.np.asarray(u, dtype=float)
        except (TypeError, ValueError):
            raise Reject("accel must be an n x 2 array of numbers")
        if arr.shape != (self.n, 2) or not self.np.isfinite(arr).all():
            raise Reject(f"accel must be a finite {self.n} x 2 array")
        return Action("command", {"accel": arr})

    def render(self, action, args, spec):
        args[spec.get("accel_field", "accel")] = [[float(v) for v in row] for row in action.fields["accel"]]
        return args

    def decide_direct(self, s, a, args, spec):
        """One filter step. Returns (Decision, new_state)."""
        if not s["fresh"]:
            return Decision("deny", None, "no fresh state estimate for this control step "
                            "(POST /v1/observe first)", self.name), s
        out = s["filter"].filter(s["x_hat"], a.fields["accel"], s["rho"])
        a_star = Action("command", {"accel": out.a_star})
        statuses = list(out.status)
        cert = {"status": statuses, "backend": list(out.backend),
                "slack_m": [None if not math.isfinite(v) else round(float(v), 6) for v in out.slack],
                "intervened": [bool(v) for v in out.intervened],
                "solve_ms": [round(float(v), 4) for v in out.solve_ms],
                "horizon_steps": self.horizon, "dt_s": self.dt,
                "source": "paperV/experiments/filter.py:PredictiveSafetyFilter"}
        new = {**s, "fresh": False, "step": s["step"] + 1}
        if any(st in ("latched", "loiter", "infeasible_t0") for st in statuses):
            return Decision("fallback", self.render(a_star, dict(args), spec),
                            "no certified plan for at least one aircraft; latched tail or loiter "
                            "command instead", self.name, cert), new
        if any(out.intervened):
            return Decision("project", self.render(a_star, dict(args), spec),
                            "command projected onto the certified set", self.name, cert), new
        return Decision("allow", args, "command certified as proposed", self.name, cert), new

    # The generic discrete interface is not used for this model: decide_direct replaces it.
    def predict(self, s, a):
        raise NotImplementedError

    def violations(self, s):
        return []

    def terminal(self, s):
        return True

    def backup(self, s):
        return None

    def summary(self, s):
        return {"step": s["step"], "fresh": s["fresh"],
                "counts": dict(s["filter"].counts) if s.get("filter") else None}
