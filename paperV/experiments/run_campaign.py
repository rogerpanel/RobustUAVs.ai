"""Campaign runner: episode-level JSONL checkpoints, resume and sharding (runbook §2).

Each finished episode appends one line to results/campaign/<id>/shard_<k>.jsonl.gz (gzip member
per line, flush + fsync). --resume skips every (cell_id, mission_seed, repeat) already done
(status api_error / incomplete do not count). --shard k/K keeps the cells with
sha256(cell_id, mission_seed) mod K == k. Raw campaign directories are not committed.

Phases
  p1-timing     seconds per episode per filter backend (results/p1_timing.csv)
  p1-property   Theorem 1 property campaign (2,000 episodes x 12 aircraft; --quick 200)
  p2            A0 / random / A6 oracle evaluation on held-out missions (block 14xxx)
  p2-budget     A6 attack-budget curve (b_att epochs x hijacked aircraft) and the stealth monitor (11xxx on A0)
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import itertools
import json
import os
import platform
import subprocess
import sys
import time
from multiprocessing import Pool

import numpy as np

try:
    from . import constants as C
    from .budget import level_values, levels as budget_rows
    from .episode import EpisodeCfg, run_episode
except ImportError:
    import constants as C
    from budget import level_values, levels as budget_rows
    from episode import EpisodeCfg, run_episode


# ------------------------------------------------------------------ JSONL store
def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(type(o))


def _clean(rec):
    out = {}
    for k, v in rec.items():
        if isinstance(v, float) and not np.isfinite(v):
            v = None
        out[k] = v
    return out


class Store:
    def __init__(self, cid, shard=(0, 1)):
        self.dir = C.RESULTS / "campaign" / cid
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"shard_{shard[0]}.jsonl.gz"

    def done_keys(self):
        keys = set()
        for f in self.dir.glob("shard_*.jsonl.gz"):
            try:
                with gzip.open(f, "rt") as fh:
                    for line in fh:
                        try:
                            r = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if r.get("status") not in ("api_error", "incomplete"):
                            keys.add((r["cell_id"], r["mission_seed"], r.get("repeat", 0)))
            except (EOFError, OSError):
                continue                      # torn tail of an interrupted shard
        return keys

    def append(self, rec):
        line = json.dumps(_clean(rec), default=_json_default) + "\n"
        with open(self.path, "ab") as fh:
            fh.write(gzip.compress(line.encode()))
            fh.flush(); os.fsync(fh.fileno())


def shard_of(cell_id, seed, K):
    return int(hashlib.sha256(f"{cell_id}|{seed}".encode()).hexdigest(), 16) % K


def _run(cfg):
    try:
        return run_episode(cfg)
    except Exception as e:                       # never silently: the record says incomplete and why
        return dict(cell_id=cfg.cell_id(), mission_seed=cfg.mission_seed, repeat=cfg.repeat, status="incomplete",
                    error=f"{type(e).__name__}: {e}", campaign_id=cfg.campaign_id)


def execute(cfgs, cid, par, resume, shard, label=""):
    store = Store(cid, shard)
    done = store.done_keys() if resume else set()
    todo = [c for c in cfgs if shard_of(c.cell_id(), c.mission_seed, shard[1]) == shard[0]
            and (c.cell_id(), c.mission_seed, c.repeat) not in done]
    print(f"[{cid}] {len(cfgs)} episodes in grid, {len(todo)} to run (shard {shard[0]}/{shard[1]}, par {par})",
          flush=True)
    t0 = time.perf_counter()
    n = 0
    try:
        from .adaptive import quiet
    except ImportError:
        from adaptive import quiet
    with Pool(par, initializer=quiet) as pool:
        for rec in pool.imap_unordered(_run, todo, chunksize=1):
            store.append(rec)
            n += 1
            if n % 20 == 0 or n == len(todo):
                el = time.perf_counter() - t0
                print(f"  [{cid}] {n}/{len(todo)} done, {el:.0f} s elapsed", flush=True)
    return store


def git_sha():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=C.REPO, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def meta_update(key, value):
    p = C.RESULTS / "run_meta.json"
    meta = json.loads(p.read_text()) if p.exists() else {}
    meta[key] = value
    p.write_text(json.dumps(meta, indent=1, default=_json_default))


def env_meta():
    import osqp, clarabel, scipy
    cpu = platform.machine()
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip(); break
    except OSError:
        pass
    return dict(python=sys.version.split()[0], numpy=np.__version__, scipy=scipy.__version__,
                osqp=osqp.__version__, clarabel=clarabel.__version__, cpu=cpu, nproc=os.cpu_count(),
                host=platform.node(), git_sha=git_sha())


# ------------------------------------------------------------------ dispatchable cells
def dispatchable(level, m, gamma=C.GAMMA_SUP, delta_bar=C.DELTA_BAR_S):
    for r in budget_rows(gamma=gamma, delta_bar=delta_bar):
        if r["level"] == level and r["m"] == m:
            return bool(r["dispatchable"])
    raise KeyError((level, m))


# ------------------------------------------------------------------ phases
STYLES = ("uniform", "far", "bangbang", "flap", "press", "garbage")


def phase_p1_property(a):
    lv = level_values()
    cells = [(lev, lv[lev], m) for lev in ("b0", "b1", "b2", "b3") for m in (10.0, 20.0) if dispatchable(lev, m)]
    combos = list(itertools.product(STYLES, cells, ("uniform", "vertex"), ("random", "vertex")))
    n_ep = 200 if a.quick else a.episodes
    cfgs = []
    for i in range(n_ep):
        style, (lev, b, m), wm, em = combos[i % len(combos)]
        cfgs.append(EpisodeCfg(n_uav=C.N_UAV, m=m, b_tot_level=lev, b_tot_m=b, planner="prop_" + style, w_mode=wm,
                               e_mode=em, mission_seed=10000 + i // 2, repeat=i % 2, campaign_id=a.campaign_id,
                               attacker="property", goal=style))
    t0 = time.perf_counter()
    execute(cfgs, a.campaign_id, a.par, a.resume, a.shard)
    meta_update("p1_property", dict(episodes=n_ep, cells=[c[0] + f"@m{c[2]:g}" for c in cells],
                                    seed_block="10000-10999", wall_s=round(time.perf_counter() - t0, 1),
                                    env=env_meta()))


def phase_p1_timing(a):
    rows = []
    lv = level_values()
    n = 2 if a.quick else 6
    for flt in ("psf", "none", "simplex", "cbf1", "fixed_margin"):
        for planner in ("scripted", "prop_press"):
            ws = []
            for k in range(n):
                r = run_episode(EpisodeCfg(m=20.0, b_tot_level="b1", b_tot_m=lv["b1"], filter=flt, planner=planner,
                                           e_mode="vertex", mission_seed=10950 + k))
                ws.append(r["wall_s"])
            rows.append(dict(filter=flt, planner=planner, episodes=n, n_uav=C.N_UAV, s_per_episode_mean=np.mean(ws),
                             s_per_episode_max=np.max(ws), aircraft_steps_per_episode=C.N_UAV * 875,
                             provenance="measured"))
            print(rows[-1], flush=True)
    p = C.RESULTS / "p1_timing.csv"
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    meta_update("p1_timing", dict(env=env_meta()))
    print("wrote", p)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True)
    ap.add_argument("--campaign-id", default=None)
    ap.add_argument("--episodes", type=int, default=2000)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--par", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--planners", default="scripted,random,oracle:best,oracle:heldout")
    ap.add_argument("--btot", default="b0,b1,b2,b3")
    ap.add_argument("--margins", default="10,20")
    ap.add_argument("--gamma", default="1.625,15")
    ap.add_argument("--missions", type=int, default=300)
    ap.add_argument("--seed-block", type=int, default=14000)
    ap.add_argument("--filters", default="psf,none,simplex,cbf1,fixed_margin")
    ap.add_argument("--goals", default="G1,G2,G3,G4")
    ap.add_argument("--log-steps", default="events")
    ap.add_argument("--stage", default=None, help="p2-budget: monitor | curve")
    a = ap.parse_args(argv)
    k, K = (int(x) for x in a.shard.split("/"))
    a.shard = (k, K)
    a.campaign_id = a.campaign_id or a.phase.replace("-", "_")
    if a.phase == "p1-property":
        phase_p1_property(a)
    elif a.phase == "p1-timing":
        phase_p1_timing(a)
    elif a.phase in ("p2", "p2-budget"):
        try:
            from . import campaigns_p2 as P2
        except ImportError:
            import campaigns_p2 as P2
        P2.run(a)
    else:
        raise SystemExit(f"unknown phase {a.phase}")


if __name__ == "__main__":
    main()
