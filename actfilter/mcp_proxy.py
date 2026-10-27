"""MCP stdio proxy: put the kernel in front of any MCP server without changing host or server.

    python3 -m actfilter.mcp_proxy --url http://127.0.0.1:8765 --session s1 -- <server command ...>

The host is configured to launch this proxy instead of the server. Messages pass through
unchanged in both directions except `tools/call` requests from the host, which are sent
to the kernel first:

    allow     forwarded unchanged
    project   forwarded with params.arguments replaced by the repaired arguments
    fallback  not forwarded; the host receives a tool error naming the safe-stop action
    deny      not forwarded; the host receives a tool error with the reason

If the kernel is unreachable the call is denied. Messages are newline-delimited JSON-RPC
(the MCP stdio transport); a line that is not JSON is dropped, not forwarded.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading

from .hook import ask


def tool_error(req_id, text: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id,
            "result": {"content": [{"type": "text", "text": text}], "isError": True}}


def handle(msg: dict, url: str, session: str):
    """Returns ("forward", msg) or ("reply", response)."""
    if msg.get("method") != "tools/call" or "id" not in msg:
        return "forward", msg
    params = msg.get("params") or {}
    tool, args = params.get("name"), params.get("arguments") or {}
    try:
        d = ask(url, session, tool, args)
    except Exception as e:  # noqa: BLE001 -- any failure to get a verdict is a deny
        return "reply", tool_error(msg["id"], f"actfilter: denied, kernel unavailable ({type(e).__name__})")
    if d["decision"] == "allow":
        return "forward", msg
    if d["decision"] == "project":
        return "forward", {**msg, "params": {**params, "arguments": d["args"]}}
    extra = f"; safe-stop action: {json.dumps(d.get('args'))}" if d["decision"] == "fallback" else ""
    return "reply", tool_error(msg["id"], f"actfilter: {d['decision']}: {d.get('reason')}{extra}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--session", default="default")
    ap.add_argument("server", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = a.server[1:] if a.server and a.server[0] == "--" else a.server
    if not cmd:
        ap.error("give the MCP server command after --")
    child = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    out_lock = threading.Lock()

    def write_host(line: str):
        with out_lock:
            sys.stdout.write(line if line.endswith("\n") else line + "\n")
            sys.stdout.flush()

    def pump_server():
        for line in child.stdout:
            write_host(line)

    threading.Thread(target=pump_server, daemon=True).start()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        how, payload = handle(msg, a.url, a.session)
        if how == "forward":
            child.stdin.write(json.dumps(payload) + "\n")
            child.stdin.flush()
        else:
            write_host(json.dumps(payload))
    child.stdin.close()
    return child.wait()


if __name__ == "__main__":
    sys.exit(main())
