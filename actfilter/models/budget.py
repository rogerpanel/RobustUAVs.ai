"""Spend and call budgets with a reserve for a safe abort.

State: {spent, calls, stopped}. A call is admitted only if, after it, an abort
(costing `abort_reserve`) still fits: spent + cost + reserve <= max_spend and
calls + 1 <= max_calls. That is constraint tightening by the cost of the backup,
so the terminal state (stopped, within budget) stays reachable from every
admitted state. A call whose size is adjustable (units x price) is repaired by
shrinking the units to the largest admissible amount, the discrete analogue of
projecting onto the tightened set.

Tool spec (policy "tools" entry):
    {"model": "budget", "cost_fixed": 0.01}                         fixed price per call
    {"model": "budget", "cost_field": "amount"}                     the call states its cost
    {"model": "budget", "units_field": "max_tokens", "unit_price": 2e-5, "min_units": 64}
                                                                    adjustable; repaired by clipping
"""
from __future__ import annotations

import math

from ..core import Action, Reject, StateModel

EPS = 1e-12


class BudgetModel(StateModel):
    name = "budget"
    horizon = 1

    def __init__(self, max_spend: float, max_calls: int = 10**9, abort_reserve: float = 0.0):
        if not (max_spend >= 0 and abort_reserve >= 0 and max_calls >= 0):
            raise ValueError("budget limits must be non-negative")
        if abort_reserve > max_spend:
            raise ValueError("abort_reserve exceeds max_spend: no admissible state exists")
        self.max_spend, self.max_calls, self.reserve = float(max_spend), int(max_calls), float(abort_reserve)

    def initial_state(self):
        return {"spent": 0.0, "calls": 0, "stopped": False, "after_stop": False}

    def observe(self, state, obs):
        """A trusted ledger reading replaces the predicted spend (it may only be larger:
        the model's prediction is an upper bound only if the ledger confirms it)."""
        spent = _num(obs.get("spent"), "spent")
        return {**state, "spent": max(state["spent"], spent)}

    def parse(self, tool, args, spec):
        if "cost_fixed" in spec:
            return Action("spend", {"cost": float(spec["cost_fixed"])})
        if "cost_field" in spec:
            c = _num(args.get(spec["cost_field"]), spec["cost_field"])
            return Action("spend", {"cost": c})
        if "units_field" in spec:
            u = args.get(spec["units_field"])
            if isinstance(u, bool) or not isinstance(u, int) or u < 0:
                raise Reject(f"{spec['units_field']} must be a non-negative integer")
            price = float(spec["unit_price"])
            return Action("spend", {"cost": u * price, "units": u, "unit_price": price,
                                    "min_units": int(spec.get("min_units", 1))})
        raise Reject("tool spec names no cost")

    def render(self, action, args, spec):
        if "units" in action.fields and "units_field" in spec:
            args[spec["units_field"]] = action.fields["units"]
        return args

    def predict(self, s, a):
        s = dict(s)
        if a.kind == "abort":
            s["spent"] += a.fields["cost"]
            s["stopped"] = True
            return s
        if s["stopped"]:
            s["after_stop"] = True
        s["spent"] += a.fields["cost"]
        s["calls"] += 1
        return s

    def violations(self, s):
        v = []
        if s["spent"] > self.max_spend + EPS:
            v.append(f"spend {s['spent']:.6g} exceeds {self.max_spend:.6g}")
        if s["calls"] > self.max_calls:
            v.append(f"calls {s['calls']} exceed {self.max_calls}")
        if s["after_stop"]:
            v.append("spend after the session was stopped")
        return v

    def terminal(self, s):
        return s["stopped"]

    def backup(self, s):
        if s["stopped"]:
            return None
        return Action("abort", {"cost": self.reserve})

    def candidates(self, s, a):
        if a.kind != "spend" or "units" not in a.fields:
            return []
        room = self.max_spend - self.reserve - s["spent"]
        units = math.floor((room + EPS) / a.fields["unit_price"]) if a.fields["unit_price"] > 0 else 0
        units = min(units, a.fields["units"] - 1)
        if units < a.fields["min_units"]:
            return []
        return [Action("spend", {**a.fields, "units": units, "cost": units * a.fields["unit_price"]})]

    def summary(self, s):
        return {"spent": round(s["spent"], 9), "calls": s["calls"], "stopped": s["stopped"],
                "remaining_after_reserve": round(self.max_spend - self.reserve - s["spent"], 9)}


def _num(v, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
        raise Reject(f"{name} must be a finite non-negative number")
    return float(v)
