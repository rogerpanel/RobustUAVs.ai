"""Kernel, budget and egress models: the safety property, repairs, and fail-closed paths."""
import json
import random

import pytest

from actfilter import audit
from actfilter.policy import from_dict

POLICY = {
    "models": {
        "spend": {"kind": "budget", "params": {"max_spend": 1.0, "max_calls": 50, "abort_reserve": 0.1}},
        "web": {"kind": "egress", "params": {"max_requests": 3, "allow": [
            {"host": "api.example.org", "path_prefix": "/v1/", "methods": ["GET", "POST"]},
            {"host": "docs.example.org", "path_prefix": "/", "methods": ["GET"]}]}},
    },
    "tools": {
        "call_llm": {"model": "spend", "units_field": "max_tokens", "unit_price": 0.001, "min_units": 10},
        "pay": {"model": "spend", "cost_field": "amount"},
        "fetch": {"model": "web", "url_field": "url", "method_field": "method"},
    },
    "passthrough": ["read_notes"],
}


def kernel(tmp_path=None):
    log = audit.AuditLog(tmp_path / "audit.jsonl") if tmp_path else None
    return from_dict(json.loads(json.dumps(POLICY)), log)


# ---------------------------------------------------------------- routing / fail closed
def test_unknown_tool_denied_passthrough_allowed():
    k = kernel()
    assert k.decide("s", "rm_everything", {}).kind == "deny"
    assert k.decide("s", "read_notes", {"x": 1}).kind == "allow"


@pytest.mark.parametrize("args", [{"amount": -1}, {"amount": "1"}, {"amount": float("nan")},
                                  {"amount": True}, {}])
def test_unparseable_cost_denied(args):
    assert kernel().decide("s", "pay", args).kind == "deny"


def test_malformed_proposal_denied():
    k = kernel()
    assert k.decide("s", "pay", ["not", "a", "dict"]).kind == "deny"
    assert k.decide("s", 42, {}).kind == "deny"


# ---------------------------------------------------------------- budget
def test_budget_reserve_tightening_and_projection():
    k = kernel()
    assert k.decide("s", "pay", {"amount": 0.5}).kind == "allow"             # 0.5 + 0.1 reserve <= 1
    d = k.decide("s", "pay", {"amount": 0.45})                                # 0.95 + 0.1 > 1: no repair for a fixed amount
    assert d.kind == "fallback" and d.args["action"] == "abort"
    assert k.decide("s", "pay", {"amount": 0.01}).kind in ("deny", "fallback")  # session stopped
    k2 = kernel()
    d = k2.decide("t", "call_llm", {"max_tokens": 2000})                      # 2.0 > 0.9 room
    assert d.kind == "project" and d.args["max_tokens"] == 900
    assert k2.decide("t", "call_llm", {"max_tokens": 5}).kind == "fallback"  # room 0 < min_units


def test_budget_never_exceeded_under_random_proposals():
    """The safety property: whatever is proposed, admitted spend never exceeds the limit and
    the reserve for a safe abort is always left."""
    rng = random.Random(7)
    for trial in range(300):
        k = kernel()
        for _ in range(rng.randint(1, 40)):
            if rng.random() < 0.5:
                d = k.decide("s", "pay", {"amount": rng.choice([0.0, 0.01, 0.1, 0.3, 0.9, 2.0])})
            else:
                d = k.decide("s", "call_llm", {"max_tokens": rng.randint(0, 3000)})
            st = k.state("s", "spend")
            assert st["spent"] <= 1.0 + 1e-9
            if not st["stopped"]:
                assert st["spent"] + 0.1 <= 1.0 + 1e-9
            if d.kind == "project":
                assert d.args["max_tokens"] >= 10


# ---------------------------------------------------------------- egress
@pytest.mark.parametrize("url,method,kind", [
    ("https://api.example.org/v1/items", "GET", "allow"),
    ("https://api.example.org/v1/items", "DELETE", "fallback"),
    ("https://api.example.org/admin", "GET", "fallback"),
    ("https://evil.example.net/v1/", "GET", "fallback"),
    ("http://docs.example.org/guide", "GET", "project"),
    ("https://user:pw@api.example.org/v1/", "GET", "deny"),
    ("https://api.example.org/v1/../admin", "GET", "deny"),
    ("https://api.example.org/v1/%2e%2e/admin", "GET", "deny"),
    ("https://api.example.org/v1/a b", "GET", "deny"),
    ("ftp://api.example.org/v1/", "GET", "deny"),
    ("https://api.example.org:8443/v1/", "GET", "fallback"),
    ("https://93.184.216.34/v1/", "GET", "fallback"),
])
def test_egress_allowlist(url, method, kind):
    d = kernel().decide("s", "fetch", {"url": url, "method": method})
    assert d.kind == kind, d.reason
    if kind == "project":
        assert d.args["url"].startswith("https://docs.example.org/")


def test_egress_request_budget():
    k = kernel()
    for _ in range(3):
        assert k.decide("s", "fetch", {"url": "https://docs.example.org/a"}).kind == "allow"
    assert k.decide("s", "fetch", {"url": "https://docs.example.org/a"}).kind == "fallback"
    assert k.decide("s", "fetch", {"url": "https://docs.example.org/a"}).kind == "deny"   # stopped


def test_sessions_are_independent():
    k = kernel()
    for _ in range(3):
        k.decide("a", "fetch", {"url": "https://docs.example.org/"})
    assert k.decide("b", "fetch", {"url": "https://docs.example.org/"}).kind == "allow"


# ---------------------------------------------------------------- audit
def test_audit_chain_detects_tampering(tmp_path):
    k = kernel(tmp_path)
    for amt in (0.1, 0.2, 5.0):
        k.decide("s", "pay", {"amount": amt})
    p = tmp_path / "audit.jsonl"
    assert audit.verify(p) == {"ok": True, "records": 3, "broken_at": None}
    lines = p.read_text().splitlines()
    rec = json.loads(lines[1]); rec["decision"] = "deny"; lines[1] = json.dumps(rec, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")
    v = audit.verify(p)
    assert not v["ok"] and v["broken_at"] == 2
