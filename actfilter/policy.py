"""Policy: which state models exist and which host tool maps to which model.

    {
      "models": {"spend": {"kind": "budget", "params": {"max_spend": 5.0, "abort_reserve": 0.2}},
                 "web":   {"kind": "egress", "params": {"allow": [...], "max_requests": 50}}},
      "tools":  {"call_llm": {"model": "spend", "units_field": "max_tokens", "unit_price": 2e-5},
                 "fetch":    {"model": "web", "url_field": "url"}},
      "passthrough": ["read_file"]
    }

The policy file is read once at start-up and never written by the kernel. Deploy it
read-only to the agent (a different user, or a read-only mount): an agent that can
edit its guard's policy has no guard.
"""
from __future__ import annotations

import json
from pathlib import Path

from .core import Kernel
from .models import build


def load(path, audit=None) -> Kernel:
    pol = json.loads(Path(path).read_text())
    return from_dict(pol, audit)


def from_dict(pol: dict, audit=None) -> Kernel:
    models = {name: build(m["kind"], m.get("params", {})) for name, m in pol.get("models", {}).items()}
    tools = pol.get("tools", {})
    for t, spec in tools.items():
        if spec.get("model") not in models:
            raise ValueError(f"tool {t!r} names unknown model {spec.get('model')!r}")
    overlap = set(pol.get("passthrough", [])) & set(tools)
    if overlap:
        raise ValueError(f"tools both filtered and passthrough: {sorted(overlap)}")
    return Kernel(models, tools, pol.get("passthrough", []), audit)
