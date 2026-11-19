#!/usr/bin/env python3
"""Rerun plans for the PX4 missions that were never flown (PX4_PREREG.md, deviation 4).

Deviation 1 excluded the missions in which PX4 entered Descend/Termination before the
mission window (nav_state 3 never reached). The driver has retried such missions since
then (E3 re-evaluation and E5 have no exclusions), but the earlier runs still have gaps.
This script writes, per earlier run directory, a plan that flies every planned mission
without a valid flight again, with the same seed and parameters, plus whatever keeps
each attack-only deviation inside ONE run:

  * an excluded attacked mission is rerun together with its benign twin;
  * an excluded twin is rerun together with every attacked mission that shares it;
  * an excluded member of an E0 replay pair is rerun together with the other member.

Specs are rebuilt from the run's own mission records (seed, anchor, family, u or phys,
sources) with p4_spec, and every rebuilt spec is checked against the record (benign
envelope and attack parameters), so the rerun cannot silently differ from the original.

  python3 p4_rerun.py                  # all earlier runs: e0 e1 e2 e3eval e4neg
  python3 p4_rerun.py e2               # one run
Writes plans/rerun_<run>.jsonl; the fleet then flies it with --exp rerun_<run>, into
results/px4/rerun_<run>/. E3 (the CEM search) is not rerun: its missions steered the
search, and deviation 2 already re-selected its attackers on valid missions only.
"""
from __future__ import annotations

import gzip
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p4_spec as S  # noqa: E402

PX = HERE.parents[1] / "results" / "px4"
RUNS = ("e0", "e1", "e2", "e3eval", "e4neg")


def records(run: str) -> dict:
    """Last record per mission id; a record with status ok wins over later failed attempts."""
    d = PX / run
    f = d / "missions.jsonl"
    lines = f.read_text().splitlines() if f.exists() else gzip.open(d / "missions.jsonl.gz", "rt").read().splitlines()
    out = {}
    for line in lines:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        prev = out.get(r["mid"])
        if prev is None or prev.get("status") != "ok" or r.get("status") == "ok":
            out[r["mid"]] = r
    return out


def flown(r) -> bool:
    return r.get("status") == "ok" and 3 in (r.get("nav_states") or [])


def attacked(r) -> bool:
    return r.get("family") not in (None, "none")


def twin_mid(r) -> str:
    return f"twin_{r['exp']}_a{r['anchor_s']}_s{r['seed']}"


def _close(a, b, tol=1e-6) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)
    return a == b


def rebuild(r: dict) -> dict:
    """The mission spec of record r, rebuilt with p4_spec and checked against the record."""
    kw = dict(anchor=r["anchor_s"], sources=tuple(r.get("sources") or ("env", "gnss", "fault")))
    if attacked(r):
        if r.get("u") is not None:
            spec = S.mission(r["mid"], r["exp"], r["seed"], family=r["family"], u=r["u"],
                             attacker_id=r.get("attacker_id"), **kw)
        else:
            spec = S.mission(r["mid"], r["exp"], r["seed"], family=r["family"], phys=r["phys"],
                             attacker_id=r.get("attacker_id"), **kw)
    else:
        spec = S.mission(r["mid"], r["exp"], r["seed"], **kw)
        spec["twin"] = r.get("twin")
    for k in ("seed", "anchor_s", "family", "attacker_id", "u", "phys", "twin", "benign_meta", "sources"):
        if not _close(spec.get(k), r.get(k)):
            raise SystemExit(f"{r['mid']}: rebuilt spec differs from the record in '{k}': "
                             f"{spec.get(k)!r} vs {r.get(k)!r}")
    return spec


def plan(run: str) -> tuple[list, dict]:
    R = records(run)
    bad = {m for m, r in R.items() if not flown(r)}
    users = {}                                   # twin mid -> attacked missions that use it
    for m, r in R.items():
        if attacked(r):
            users.setdefault(twin_mid(r), []).append(m)
    todo = set()
    for m in bad:
        r = R[m]
        todo.add(m)
        if attacked(r):
            todo.add(twin_mid(r))
        todo.update(users.get(m, ()))           # m is a twin: rerun everything that pairs with it
        if r["exp"] == "e0_replay":
            todo.add(m.replace("e0_replay_", "e0_"))
        elif r["exp"] == "e0" and f"e0_replay_s{r['seed']}" in R:
            todo.add(f"e0_replay_s{r['seed']}")
    missing = sorted(m for m in todo if m not in R)
    if missing:
        raise SystemExit(f"{run}: missions referenced but never planned: {missing[:5]}")
    specs = [rebuild(R[m]) for m in sorted(todo)]
    summary = {"run": run, "planned": len(R), "not_flown": len(bad),
               "not_flown_attacked": sum(attacked(R[m]) for m in bad),
               "not_flown_twin_or_benign": sum(not attacked(R[m]) for m in bad),
               "to_fly": len(specs), "added_for_pairing": len(specs) - len(bad)}
    return specs, summary


def main():
    out = HERE / "plans"; out.mkdir(exist_ok=True)
    tot = 0
    for run in (sys.argv[1:] or RUNS):
        specs, s = plan(run)
        (out / f"rerun_{run}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in specs))
        tot += len(specs)
        print(f"rerun_{run}: {s['not_flown']} of {s['planned']} missions not flown "
              f"({s['not_flown_attacked']} attacked, {s['not_flown_twin_or_benign']} twin/benign); "
              f"{s['to_fly']} to fly ({s['added_for_pairing']} added to keep pairs in one run) "
              f"-> plans/rerun_{run}.jsonl")
    print(f"total: {tot} missions")


if __name__ == "__main__":
    main()
