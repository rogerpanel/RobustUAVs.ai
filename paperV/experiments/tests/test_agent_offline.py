"""P3 harness, offline (runbook P3.2): schema, parser, cache key, ledger maths and retry logic against
mocked HTTP. No key, no network, no spend. Every failure path must raise; none may return text."""
import json

import httpx
import httpx2
import numpy as np
import pytest

import agent as A
import constants as C
import llm_harness as H
from episode import EpisodeCfg, run_episode

# fake key-shaped strings are assembled at runtime so no literal key pattern ever reaches a commit
FAKE_OPENAI = "s" + "k-" + "test" * 5
FAKE_ANTHROPIC = "s" + "k-ant-" + "test" * 5
FAKE_GEMINI = "AI" + "za" + "TEST" * 6
PRICES = dict(price_in_per_mtok=4.0, price_out_per_mtok=20.0, price_cache_read_per_mtok=0.2,
              price_cache_write_per_mtok=5.0)


def lock(provider="anthropic", **kw):
    e = dict(status="pinned", provider=provider, model_id="test-model", supports_temperature=False,
             supports_seed=False, max_output_tokens=4000, expected_output_tokens=500, **PRICES)
    e.update(kw)
    return {"roles": {"r": e}}


def good_actions(n):
    return json.dumps({"actions": [{"uav": i, "type": "mode", "waypoint": [0, 0], "velocity": [0, 0],
                                    "mode": "nominal", "task": 0} for i in range(n)]})


def anthropic_body(text, stop="end_turn", cr=1500, cw=0):
    content = [] if text is None else [{"type": "text", "text": text}]
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "test-model", "content": content,
            "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": 400, "output_tokens": 300, "cache_read_input_tokens": cr,
                      "cache_creation_input_tokens": cw}}


def anthropic_provider(entry, handler):
    import anthropic
    http = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler))
    return H.AnthropicProvider(entry, http_client=http, base_url="http://mock.invalid")


def harness(tmp_path, entry_lock, provider, cache_only=False, max_usd=100.0, sleeps=None):
    return H.Harness("r", lock=entry_lock, ledger=H.Ledger(tmp_path / "ledger.csv", max_usd=max_usd),
                     cache_dir=tmp_path / "cache", cache_only=cache_only, provider=provider,
                     sleep=(sleeps.append if sleeps is not None else (lambda s: None)))


def call(h, prompt="situation"):
    return h.complete("system", prompt, A.FLEET_SCHEMA, prompt_version="pv", schema_version="sv", seed=16000)


# ------------------------------------------------------------------ fail loud
def test_missing_key_raises(monkeypatch, tmp_path):
    for p in ("anthropic", "openai", "gemini", "deepseek"):
        monkeypatch.delenv(H.KEY_ENV[p], raising=False)
        lk = lock(p)
        h = H.Harness("r", lock=lk, ledger=H.Ledger(tmp_path / f"{p}.csv", max_usd=10), cache_dir=tmp_path / p,
                      sleep=lambda s: None)
        with pytest.raises(H.LLMUnavailable):
            call(h)
    assert not (tmp_path / "anthropic.csv").exists()          # nothing was billed or logged as a success


def test_http_500_raises_after_retries(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_OPENAI)
    hits = []

    def handler(req):
        hits.append(req)
        return httpx.Response(500, json={"error": "boom"})
    prov = H.OpenAIProvider(lock("openai")["roles"]["r"], transport=httpx.MockTransport(handler))
    sleeps = []
    h = harness(tmp_path, lock("openai"), prov, sleeps=sleeps)
    with pytest.raises(H.LLMUnavailable):
        call(h)
    assert len(hits) == H.MAX_ATTEMPTS and len(sleeps) == H.MAX_ATTEMPTS - 1
    assert sleeps == sorted(sleeps) or max(sleeps) <= 61


def test_non_retryable_raises_immediately(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_OPENAI)
    hits = []
    prov = H.OpenAIProvider(lock("openai")["roles"]["r"],
                            transport=httpx.MockTransport(lambda r: hits.append(r) or httpx.Response(401, json={})))
    with pytest.raises(H.LLMUnavailable):
        call(harness(tmp_path, lock("openai"), prov))
    assert len(hits) == 1


def test_retry_after_honoured(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_OPENAI)
    state = {"n": 0}

    def handler(req):
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "7"}, json={})
        return httpx.Response(200, json={"model": "test-model", "system_fingerprint": "fp",
                                         "choices": [{"message": {"content": good_actions(2)}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 100, "completion_tokens": 20,
                                                   "prompt_tokens_details": {"cached_tokens": 60}}})
    sleeps = []
    h = harness(tmp_path, lock("openai"), H.OpenAIProvider(lock("openai")["roles"]["r"],
                                                          transport=httpx.MockTransport(handler)), sleeps=sleeps)
    c = call(h)
    assert sleeps and sleeps[0] >= 7 and c.tokens_in_cached == 60 and c.fingerprint == "fp"


def test_empty_completion_is_not_text(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_ANTHROPIC)
    prov = anthropic_provider(lock()["roles"]["r"], lambda r: httpx2.Response(200, json=anthropic_body(None)))
    with pytest.raises(H.LLMUnavailable):
        call(harness(tmp_path, lock(), prov))


# ------------------------------------------------------------------ Anthropic request shape and accounting
def test_anthropic_request_shape_and_usage(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_ANTHROPIC)
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        seen["headers"] = dict(req.headers)
        return httpx2.Response(200, json=anthropic_body(good_actions(3)))
    entry = lock(effort="medium")
    h = harness(tmp_path, entry, anthropic_provider(entry["roles"]["r"], handler))
    c = call(h)
    b = seen["body"]
    assert b["output_config"]["format"]["type"] == "json_schema" and b["output_config"]["effort"] == "medium"
    assert "tool_choice" not in b and "temperature" not in b and "fallbacks" not in b
    assert b["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert c.tokens_in == 400 + 1500 and c.tokens_in_cached == 1500 and c.tokens_out == 300
    usd = (400 * 4.0 + 1500 * 0.2 + 300 * 20.0) / 1e6
    assert abs(h.totals["usd"] - usd) < 1e-12
    row = list(__import__("csv").DictReader(open(tmp_path / "ledger.csv")))[0]
    assert float(row["usd"]) == pytest.approx(usd) and row["cache_hit"] == "0"
    assert "situation" not in open(tmp_path / "ledger.csv").read()     # no prompt text in the ledger
    acts, fails = A.actions_for_fleet(A.parse_fleet(c.text), 3)
    assert fails == 0 and all(a["mode"] == "nominal" for a in acts)


def test_refusal_is_planner_behaviour(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_ANTHROPIC)
    prov = anthropic_provider(lock()["roles"]["r"], lambda r: httpx2.Response(200, json=anthropic_body(None, "refusal")))
    c = call(harness(tmp_path, lock(), prov))
    assert c.refusal and c.text is None
    acts, fails = A.actions_for_fleet(None, 4)
    assert fails == 4 and all(a["mode"] == "loiter" for a in acts)


def test_gemini_key_in_header_not_url(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_GEMINI)
    seen = {}

    def handler(req):
        seen["url"] = str(req.url); seen["key"] = req.headers.get("x-goog-api-key")
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": good_actions(1)}]},
                                                         "finishReason": "STOP"}],
                                         "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 10,
                                                           "thoughtsTokenCount": 5}})
    e = lock("gemini")
    c = call(harness(tmp_path, e, H.GeminiProvider(e["roles"]["r"], transport=httpx.MockTransport(handler))))
    assert FAKE_GEMINI not in seen["url"] and seen["key"] == FAKE_GEMINI
    assert seen["body"]["generationConfig"]["responseSchema"]["type"] == "OBJECT"
    assert c.tokens_out == 15


def test_redaction():
    s = H.redact(f"error with key {FAKE_ANTHROPIC} and {FAKE_GEMINI}")
    assert FAKE_ANTHROPIC not in s and FAKE_GEMINI not in s and s.count("[REDACTED]") == 2


# ------------------------------------------------------------------ cache, budget
def test_cache_hit_and_cache_only(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_ANTHROPIC)
    hits = []
    prov = anthropic_provider(lock()["roles"]["r"],
                              lambda r: hits.append(1) or httpx2.Response(200, json=anthropic_body(good_actions(2))))
    h = harness(tmp_path, lock(), prov)
    c1 = call(h); c2 = call(h)
    assert len(hits) == 1 and c1.text == c2.text and h.totals["cache_hits"] == 1
    h2 = harness(tmp_path, lock(), prov, cache_only=True)
    assert call(h2).text == c1.text
    with pytest.raises(H.CacheMiss):
        call(h2, prompt="a different situation")
    assert len(hits) == 1


def test_cache_key_covers_every_input():
    base = dict(provider="a", model_id="m", prompt_version="p", system="s", prompt="x", schema_version="v",
                temperature=0.0, seed=1, repeat_idx=0, effort=None)
    k0 = H.cache_key(**base)
    for k in base:
        assert H.cache_key(**dict(base, **{k: "changed"})) != k0, k


def test_budget_cap_stops_before_the_call(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_ANTHROPIC)
    hits = []
    prov = anthropic_provider(lock()["roles"]["r"],
                              lambda r: hits.append(1) or httpx2.Response(200, json=anthropic_body(good_actions(2))))
    with pytest.raises(H.BudgetExceeded):
        call(harness(tmp_path, lock(), prov, max_usd=1e-9))
    assert not hits


def test_no_cap_means_no_paid_call(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_ANTHROPIC)
    monkeypatch.delenv("PAPERV_MAX_USD", raising=False)
    prov = anthropic_provider(lock()["roles"]["r"], lambda r: httpx2.Response(200, json=anthropic_body(good_actions(2))))
    h = H.Harness("r", lock=lock(), ledger=H.Ledger(tmp_path / "l.csv"), cache_dir=tmp_path / "c", provider=prov)
    with pytest.raises(H.BudgetExceeded):
        call(h)


def test_zero_priced_paid_role_refused():
    lk = lock("openai"); lk["roles"]["r"]["price_in_per_mtok"] = 0.0
    with pytest.raises(H.LLMUnavailable):
        H.role_entry("r", lk)
    lk = lock("openai_compat", price_in_per_mtok=0.0, price_out_per_mtok=0.0)
    assert H.role_entry("r", lk)["provider"] == "openai_compat"


def test_unpriced_role_refused():
    lk = lock(); lk["roles"]["r"]["price_in_per_mtok"] = None
    with pytest.raises(H.LLMUnavailable):
        H.role_entry("r", lk)


# ------------------------------------------------------------------ schema and parser
def test_wire_normalisation_and_validation():
    raw = [{"uav": 0, "type": "waypoint", "waypoint": [1.0, 2.0], "velocity": [0, 0], "mode": "nominal", "task": 0},
           {"uav": 1, "type": "task", "waypoint": [0, 0], "velocity": [0, 0], "mode": "nominal", "task": 7}]
    acts, fails = A.actions_for_fleet([A.normalise(r) for r in raw], 2)
    assert acts[0] == {"uav": 0, "type": "waypoint", "waypoint": [1.0, 2.0]}
    assert fails == 1 and acts[1]["mode"] == "loiter"           # task 7 does not exist
    assert A.parse_fleet("not json") is None and A.parse_fleet('{"actions": 3}') is None


def test_strict_schema_shape():
    def walk(s):
        if s.get("type") == "object":
            assert s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])
            for v in s["properties"].values():
                walk(v)
        if s.get("type") == "array":
            walk(s["items"])
    walk(A.FLEET_SCHEMA)


def test_experiments_never_use_platform_complete():
    for f in C.HERE.glob("*.py"):
        src = f.read_text()
        assert "llm.complete" not in src and "app.llm import" not in src and "from llm import" not in src, f


# ------------------------------------------------------------------ end to end with a mocked provider
def test_llm_planner_in_an_episode(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_ANTHROPIC)
    prov = anthropic_provider(lock()["roles"]["r"], lambda r: httpx2.Response(200, json=anthropic_body(good_actions(2))))
    h = harness(tmp_path, lock(), prov)
    pl = A.LLMPlanner("r", harness=h, mission_seed=18000)
    r = run_episode(EpisodeCfg(n_uav=2, m=20.0, planner="llm:r", planner_obj=pl, mission_seed=18000, horizon_s=20.0))
    assert r["status"] == "ok" and r["violations_corridor"] == 0
    assert r["llm_calls"] == 4 and r["parse_failures"] == 0 and r["model_id"] == "test-model"
    assert r["usd"] > 0 and r["prompt_version"] == A.PROMPT_VERSION
