"""Tamper-evident decision log: one JSON line per decision, each carrying the
SHA-256 of the previous line, so deleting or editing a record breaks the chain.

The log records hashes of the proposed and executed arguments, not the arguments
themselves, so it can be kept even where tool inputs are sensitive.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

GENESIS = "0" * 64


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


class AuditLog:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._prev = self._last_hash()

    def _last_hash(self) -> str:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return GENESIS
        last = self.path.read_text().strip().splitlines()[-1]
        return hashlib.sha256(last.encode()).hexdigest()

    def append(self, session, tool, args, decision) -> None:
        rec = {"ts": round(time.time(), 6), "session": session, "tool": tool,
               "args_sha256": _h(args), "decision": decision["decision"],
               "out_sha256": _h(decision.get("args")), "reason": decision.get("reason"),
               "model": decision.get("model"), "certificate_sha256": _h(decision.get("certificate")),
               "prev": self._prev}
        line = json.dumps(rec, sort_keys=True)
        with self._lock, self.path.open("a") as fh:
            fh.write(line + "\n")
            self._prev = hashlib.sha256(line.encode()).hexdigest()


def verify(path) -> dict:
    """Walk the chain. Returns {ok, records, broken_at}."""
    p = Path(path)
    if not p.exists():
        return {"ok": True, "records": 0, "broken_at": None}
    prev = GENESIS
    lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            return {"ok": False, "records": len(lines), "broken_at": i}
        if rec.get("prev") != prev:
            return {"ok": False, "records": len(lines), "broken_at": i}
        prev = hashlib.sha256(ln.encode()).hexdigest()
    return {"ok": True, "records": len(lines), "broken_at": None}
