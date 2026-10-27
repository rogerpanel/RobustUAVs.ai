"""Predictive action filter: the kernel every front-end calls.

A host agent proposes a tool call. The kernel turns it into a typed action of
one state model, and admits it only if, after the action, the model's safe-stop
(backup) policy can still reach a terminal state within the horizon without
leaving the safe set -- the discrete analogue of the terminal-set condition of
a predictive safety filter. Otherwise it tries the model's repair candidates in
order of closeness, then the backup action itself, then denies.

    decide(session, tool, args) -> Decision(kind, args, reason, certificate)

    kind = allow     execute the call unchanged
           project   execute the call with the returned (repaired) args
           fallback  do not execute the call; the model's safe-stop action is returned
           deny      do not execute anything

Anything the kernel cannot parse into a typed action is denied (fail closed).
Tools not named in the policy are denied unless the policy lists them as
passthrough. The kernel never executes a tool itself: the host executes what the
decision allows, and the kernel advances its state by the admitted action.
"""
from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field
from typing import Any, Optional


class Reject(ValueError):
    """The proposal cannot be turned into a typed action. Always a deny."""


@dataclass
class Action:
    """A typed action of one state model. `fields` are model-specific and validated."""
    kind: str
    fields: dict = field(default_factory=dict)


@dataclass
class Decision:
    kind: str                       # allow | project | fallback | deny
    args: Optional[dict]            # args to execute (allow/project), backup args (fallback), None (deny)
    reason: str
    model: Optional[str] = None
    certificate: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"decision": self.kind, "args": self.args, "reason": self.reason,
                "model": self.model, "certificate": self.certificate}


class StateModel:
    """One domain's admissible-action set. Subclasses implement the eight methods.

    The soundness argument needs three properties of a subclass, which its tests check:
      1. predict over-approximates what the action can do (conservative);
      2. backup is defined in every state reachable through admitted actions and
         reaches a terminal state within `horizon` steps while staying safe;
      3. terminal states are safe and closed under backup (a safe place to stop).
    """
    name = "model"
    horizon = 1

    def initial_state(self) -> Any:
        raise NotImplementedError

    def parse(self, tool: str, args: dict, spec: dict) -> Action:
        """Typed action from a tool call, or raise Reject."""
        raise NotImplementedError

    def render(self, action: Action, args: dict, spec: dict) -> dict:
        """Tool args for an action (the original args with the model's fields written back)."""
        raise NotImplementedError

    def predict(self, state: Any, action: Action) -> Any:
        raise NotImplementedError

    def violations(self, state: Any) -> list:
        raise NotImplementedError

    def terminal(self, state: Any) -> bool:
        raise NotImplementedError

    def backup(self, state: Any) -> Optional[Action]:
        raise NotImplementedError

    def candidates(self, state: Any, action: Action) -> list:
        """Repairs of `action`, closest first. Default: none."""
        return []

    # ------------------------------------------------------------------ generic
    def recoverable(self, state: Any) -> tuple[bool, list]:
        """Roll the backup policy from `state`; True if it reaches a terminal state within
        the horizon with every visited state safe. Returns the visited trace for the certificate."""
        s, trace = state, []
        for _ in range(self.horizon + 1):
            v = self.violations(s)
            trace.append({"state": self.summary(s), "violations": v})
            if v:
                return False, trace
            if self.terminal(s):
                return True, trace
            b = self.backup(s)
            if b is None:
                return False, trace
            s = self.predict(s, b)
        return False, trace

    def admissible(self, state: Any, action: Action) -> tuple[bool, dict]:
        nxt = self.predict(state, action)
        v = self.violations(nxt)
        if v:
            return False, {"next": self.summary(nxt), "violations": v}
        ok, trace = self.recoverable(nxt)
        return ok, {"next": self.summary(nxt), "backup_trace": trace,
                    **({} if ok else {"violations": ["safe stop not reachable within horizon"]})}

    def summary(self, state: Any) -> Any:
        return state


class Kernel:
    """Routes tool calls to state models by policy and keeps one state per (session, model)."""

    def __init__(self, models: dict, tools: dict, passthrough=(), audit=None):
        self.models = models            # name -> StateModel
        self.tools = tools              # tool name -> {"model": name, ...spec}
        self.passthrough = set(passthrough)
        self.audit = audit
        self._state: dict = {}
        self._lock = threading.Lock()
        self.stats: dict = {}

    def state(self, session: str, model: str):
        key = (session, model)
        if key not in self._state:
            self._state[key] = self.models[model].initial_state()
        return self._state[key]

    def observe(self, session: str, model: str, observation: dict) -> dict:
        """Replace part of a model's state with a trusted observation (telemetry, ledger)."""
        if model not in self.models:
            raise Reject(f"unknown model {model!r}")
        with self._lock:
            m = self.models[model]
            new = m.observe(self.state(session, model), observation) if hasattr(m, "observe") else None
            if new is None:
                raise Reject(f"model {model!r} accepts no observations")
            self._state[(session, model)] = new
            return {"model": model, "state": m.summary(new)}

    def decide(self, session: str, tool: str, args: Any) -> Decision:
        with self._lock:
            d = self._decide(session, tool, args)
            self.stats[d.kind] = self.stats.get(d.kind, 0) + 1
            if self.audit is not None:
                self.audit.append(session=session, tool=tool, args=args, decision=d.to_dict())
            return d

    def _decide(self, session, tool, args) -> Decision:
        if not isinstance(tool, str) or not isinstance(args, dict):
            return Decision("deny", None, "malformed proposal: tool must be a string, args an object")
        if tool in self.passthrough:
            return Decision("allow", args, "passthrough tool (policy)")
        spec = self.tools.get(tool)
        if spec is None:
            return Decision("deny", None, f"tool {tool!r} is not in the policy (default deny)")
        mname = spec["model"]
        m = self.models[mname]
        try:
            a = m.parse(tool, args, spec)
        except Reject as e:
            return Decision("deny", None, f"unparseable: {e}", mname)
        s = self.state(session, mname)
        if hasattr(m, "decide_direct"):          # models with their own certified solver (UAV QP)
            d, new = m.decide_direct(s, a, args, spec)
            self._state[(session, mname)] = new
            return d
        ok, cert = m.admissible(s, a)
        if ok:
            self._state[(session, mname)] = m.predict(s, a)
            return Decision("allow", args, "admissible", mname, cert)
        tried = [cert]
        for c in m.candidates(s, a):
            ok, cc = m.admissible(s, c)
            tried.append(cc)
            if ok:
                self._state[(session, mname)] = m.predict(s, c)
                return Decision("project", m.render(c, copy.deepcopy(args), spec),
                                "repaired to the nearest admissible action", mname,
                                {**cc, "rejected_original": cert})
        b = m.backup(s)
        if b is not None:
            ok, cb = m.admissible(s, b)
            if ok:
                self._state[(session, mname)] = m.predict(s, b)
                return Decision("fallback", {"action": b.kind, **b.fields},
                                "no admissible repair; safe-stop action instead", mname,
                                {**cb, "rejected_original": cert, "candidates_tried": len(tried) - 1})
        return Decision("deny", None, "no admissible action, including the safe stop", mname,
                        {"rejected_original": cert})
