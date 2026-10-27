"""Pre-tool hook: a thin, deny-by-default router from an agent host to the kernel service.

    python3 -m actfilter.hook --format claude  [--url http://127.0.0.1:8765]
    python3 -m actfilter.hook --format hermes

Reads the host's hook JSON on stdin, asks the kernel, writes the host's decision JSON
on stdout. If the kernel cannot be reached, answers slowly, or replies with anything
unexpected, the call is denied (exit code 2, which both hosts treat as a block).

Formats
  claude  Claude Code / Claude Agent SDK PreToolUse:
          in  {"session_id", "tool_name", "tool_input", ...}
          out {"hookSpecificOutput": {"hookEventName": "PreToolUse",
               "permissionDecision": "allow"|"deny", "permissionDecisionReason": "...",
               "updatedInput": {...}}}
  hermes  Hermes Agent shell hook (Claude-compatible shapes it accepts):
          out {} (allow) | {"decision": "modify", "tool_input": {...}} | {"decision": "block", "reason": "..."}

A `fallback` decision blocks the proposed call and puts the safe-stop action in the reason,
so the agent sees what the kernel would execute instead.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

TIMEOUT_S = 5.0


def ask(url: str, session: str, tool: str, args) -> dict:
    req = urllib.request.Request(url.rstrip("/") + "/v1/decide", method="POST",
                                 data=json.dumps({"session": session, "tool": tool, "args": args}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        d = json.loads(r.read())
    if d.get("decision") not in ("allow", "project", "fallback", "deny"):
        raise ValueError("unexpected kernel reply")
    return d


def render(fmt: str, d: dict) -> dict:
    kind, reason = d["decision"], d.get("reason") or ""
    if kind == "fallback":
        reason = f"{reason}; safe-stop action: {json.dumps(d.get('args'))}"
    if fmt == "claude":
        out = {"hookEventName": "PreToolUse",
               "permissionDecision": "allow" if kind in ("allow", "project") else "deny",
               "permissionDecisionReason": f"actfilter: {kind}: {reason}"}
        if kind == "project":
            out["updatedInput"] = d["args"]
        return {"hookSpecificOutput": out}
    if kind == "allow":
        return {}
    if kind == "project":
        return {"decision": "modify", "tool_input": d["args"]}
    return {"decision": "block", "reason": f"actfilter: {kind}: {reason}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=("claude", "hermes"), required=True)
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    a = ap.parse_args(argv)
    try:
        ev = json.loads(sys.stdin.read() or "{}")
        tool = ev.get("tool_name")
        args = ev.get("tool_input", {})
        session = str(ev.get("session_id") or ev.get("session") or "default")
        if not isinstance(tool, str):
            raise ValueError("no tool_name in hook input")
        d = ask(a.url, session, tool, args)
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"actfilter: denied, kernel unavailable or input malformed ({type(e).__name__})",
              file=sys.stderr)
        return 2                                    # fail closed
    print(json.dumps(render(a.format, d)))
    return 0 if d["decision"] in ("allow", "project") else 2


if __name__ == "__main__":
    sys.exit(main())
