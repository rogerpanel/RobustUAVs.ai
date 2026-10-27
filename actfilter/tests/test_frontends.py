"""Service, hook client and MCP proxy, end to end through real processes."""
import json
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from actfilter.service import create_app
from actfilter.tests.test_kernel import POLICY

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def policy_file(tmp_path):
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(POLICY))
    return p


def test_service_endpoints(policy_file, tmp_path):
    c = TestClient(create_app(str(policy_file), str(tmp_path / "audit.jsonl")))
    assert c.get("/v1/health").json()["ok"]
    d = c.post("/v1/decide", json={"session": "s", "tool": "call_llm", "args": {"max_tokens": 5000}}).json()
    assert d["decision"] == "project" and d["args"]["max_tokens"] == 900
    assert c.post("/v1/decide", json={"tool": "nope", "args": {}}).json()["decision"] == "deny"
    assert c.get("/v1/stats").json()["decisions"] == {"project": 1, "deny": 1}
    assert c.get("/v1/audit/verify").json()["ok"]
    assert c.post("/v1/observe", json={"session": "s", "model": "web", "observation": {}}).status_code == 422


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture()
def server(policy_file):
    port = _free_port()
    env = {"ACTFILTER_POLICY": str(policy_file), "PATH": "/usr/bin:/bin:/usr/local/bin",
           "PYTHONPATH": str(ROOT)}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "actfilter.service:app", "--host", "127.0.0.1",
                             "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=env)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
            break
        except OSError:
            time.sleep(0.1)
    yield url
    proc.terminate(); proc.wait(5)


def run_hook(fmt, event, url):
    return subprocess.run([sys.executable, "-m", "actfilter.hook", "--format", fmt, "--url", url],
                          input=json.dumps(event), capture_output=True, text=True, cwd=ROOT, timeout=30)


def test_hook_claude_and_hermes(server):
    ev = {"session_id": "h1", "tool_name": "call_llm", "tool_input": {"max_tokens": 5000}}
    r = run_hook("claude", ev, server)
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert r.returncode == 0 and out["permissionDecision"] == "allow" and out["updatedInput"]["max_tokens"] == 900
    r = run_hook("hermes", {"session_id": "h2", "tool_name": "fetch",
                            "tool_input": {"url": "https://evil.example.net/x"}}, server)
    assert r.returncode == 2 and json.loads(r.stdout)["decision"] == "block"
    r = run_hook("hermes", {"session_id": "h3", "tool_name": "fetch",
                            "tool_input": {"url": "https://docs.example.org/x"}}, server)
    assert r.returncode == 0 and json.loads(r.stdout) == {}


def test_hook_fails_closed_without_kernel():
    r = run_hook("claude", {"tool_name": "call_llm", "tool_input": {}}, f"http://127.0.0.1:{_free_port()}")
    assert r.returncode == 2 and r.stdout == ""


FAKE_SERVER = textwrap.dedent("""
    import json, sys
    for line in sys.stdin:
        m = json.loads(line)
        if m.get("method") == "tools/call":
            res = {"content": [{"type": "text", "text": json.dumps(m["params"]["arguments"])}]}
        else:
            res = {"echo": m.get("method")}
        print(json.dumps({"jsonrpc": "2.0", "id": m.get("id"), "result": res}), flush=True)
""")


def test_mcp_proxy(server, tmp_path):
    fake = tmp_path / "fake_server.py"; fake.write_text(FAKE_SERVER)
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "call_llm", "arguments": {"max_tokens": 5000}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "fetch", "arguments": {"url": "https://evil.example.net/"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "unknown", "arguments": {}}}]
    p = subprocess.run([sys.executable, "-m", "actfilter.mcp_proxy", "--url", server, "--session", "m",
                        "--", sys.executable, str(fake)],
                       input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True, text=True,
                       cwd=ROOT, timeout=30)
    out = {r["id"]: r["result"] for r in map(json.loads, p.stdout.splitlines())}
    assert out[1] == {"echo": "tools/list"}                                       # passed through
    assert json.loads(out[2]["content"][0]["text"]) == {"max_tokens": 900}         # repaired, then forwarded
    assert out[3]["isError"] and "fallback" in out[3]["content"][0]["text"]        # never reached the server
    assert out[4]["isError"] and "deny" in out[4]["content"][0]["text"]
