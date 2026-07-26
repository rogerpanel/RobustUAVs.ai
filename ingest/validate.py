#!/usr/bin/env python3
"""Validate adapter outputs against schema/uavsec_schema.json.

Every ingest adapter's events.jsonl / windows.jsonl / pairings.jsonl MUST pass
this before commit (CLAUDE.md convention). File kind is chosen by filename:
    *events*.jsonl   -> #/$defs/Event
    *windows*.jsonl  -> #/$defs/AttackWindow
    *pairings*.jsonl -> #/$defs/CrossLayerPairing
or force it with --kind. Exit 0 only if every record in every file validates.

Usage:
  python3 ingest/validate.py data/staging/whelan/events.jsonl data/staging/whelan/windows.jsonl
  python3 ingest/validate.py --kind Event some.jsonl
  python3 ingest/validate.py data/staging/**/*.jsonl        (shell glob)
"""
import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "uavsec_schema.json"

KIND_BY_NAME = [("pairing", "CrossLayerPairing"),
                ("window", "AttackWindow"),
                ("event", "Event")]


def kind_for(path: Path, forced: str | None) -> str | None:
    if forced:
        return forced
    low = path.name.lower()
    for needle, kind in KIND_BY_NAME:
        if needle in low:
            return kind
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--kind", choices=["Event", "AttackWindow", "CrossLayerPairing"],
                    help="force the record kind instead of inferring from filename")
    ap.add_argument("--max-errors", type=int, default=5,
                    help="errors printed per file before truncating")
    a = ap.parse_args()

    schema = json.loads(SCHEMA_PATH.read_text())
    validators = {k: Draft202012Validator({"$ref": f"#/$defs/{k}",
                                           "$defs": schema["$defs"]})
                  for k in ("Event", "AttackWindow", "CrossLayerPairing")}

    failed = False
    for f in a.files:
        path = Path(f)
        kind = kind_for(path, a.kind)
        if kind is None:
            print(f"[validate] SKIP {path}: cannot infer kind from name (use --kind)")
            failed = True
            continue
        v = validators[kind]
        n = n_bad = 0
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if not line.strip():
                continue
            n += 1
            errs = list(v.iter_errors(json.loads(line)))
            if errs:
                n_bad += 1
                if n_bad <= a.max_errors:
                    e = errs[0]
                    loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
                    print(f"[validate] {path}:{lineno} ({kind}) {loc}: {e.message}")
        status = "OK " if n_bad == 0 else "FAIL"
        print(f"[validate] {status} {path}: {n - n_bad}/{n} valid {kind} records")
        failed |= n_bad > 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
