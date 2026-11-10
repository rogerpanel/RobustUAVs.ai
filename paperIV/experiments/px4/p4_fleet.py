#!/usr/bin/env python3
"""Fleet driver for the Paper IV PX4 SITL study (runs inside the PX4 container).

Every mission is a fresh PX4 process: its parameters are written into the
instance's working directory before boot (sourced by the patched
px4-rc.params), so nothing is set over MAVLink during the mission. The driver
only uploads a two-item mission (take off to 25 m at the take-off point, then a
waypoint 700 m north), switches to mission mode, arms, waits on the PX4 clock
until the mission window has ended, kills the motors so that the logger closes
the ULog, and stops the process. Up to K instances run in parallel (instance i:
MAVLink on UDP 14540+i).

Each ULog is reduced right away by p4_ulog.extract; one JSON line per mission is
appended to <out>/<exp>/missions.jsonl, the 20 Hz cross-track and offset series
go to <out>/<exp>/series/<mid>.npz, and the ULog is kept for a sample of missions
(--keep-ulog sample: the first 10 of every experiment and all failures).
A run can be stopped and restarted: missions already in missions.jsonl are skipped.

Usage (inside the container):
  python3 p4_fleet.py --plan plans/e0.jsonl --exp e0 --px4 /src --out /repo/paperIV/results/px4 -k 8 --speed 8
  python3 p4_fleet.py --cem --exp e3 ...         (adaptive: CEM against the PX4 stack, see p4_plan.py)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import shutil
import signal
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p4_spec as S  # noqa: E402
import p4_ulog as U  # noqa: E402

T_CONNECT, T_READY = 60.0, 180.0
ARM_TRIES = 10


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


class Fleet:
    def __init__(self, a):
        self.a = a
        self.build = Path(a.px4) / "build" / "px4_sitl_default"
        self.out = Path(a.out) / a.exp
        (self.out / "series").mkdir(parents=True, exist_ok=True)
        (self.out / "ulg").mkdir(exist_ok=True)
        (self.out / "fail_logs").mkdir(exist_ok=True)
        self.jsonl = self.out / "missions.jsonl"
        self.done = {}
        if self.jsonl.exists():
            for line in self.jsonl.read_text().splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("status") == "ok":
                    self.done[r["mid"]] = r
        self.lock = asyncio.Lock()
        self.n_kept = sum(1 for _ in (self.out / "ulg").glob("*.ulg"))
        self.port_turn = 0
        self.t_start = time.time(); self.n_flown = 0

    # ------------------------------------------------------------------ one mission
    async def fly(self, i, spec):
        from mavsdk import System
        from mavsdk.action import ActionError
        from mavsdk.mission_raw import MissionItem
        root = self.build / "rootfs" / f"p4_{i}"
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True)
        (root / "p4_mission_params.txt").write_text(S.params_file(spec["params"]))
        env = dict(os.environ, PX4_SYS_AUTOSTART="10040", PX4_SIM_MODEL="sihsim_quadx",
                   PX4_SIM_SPEED_FACTOR=str(self.a.speed))
        logf = open(root / "out.log", "w")
        proc = await asyncio.create_subprocess_exec("../../bin/px4", "-i", str(i), "-d", "../../etc",
                                                    cwd=str(root), stdout=logf, stderr=asyncio.subprocess.STDOUT,
                                                    env=env, start_new_session=True)
        self.port_turn += 1
        grpc_port = 50100 + 20 * i + (self.port_turn % 20)
        drone = System(mavsdk_server_address=None, port=grpc_port)
        info = {"instance": i, "status": "error", "t_wall_start": time.time()}
        wall_cap = (S.T_OFF + S.T_END + 40.0) / self.a.speed * 4 + 120
        try:
            await drone.connect(system_address=f"udpin://0.0.0.0:{14540 + i}")

            async def connected():
                async for st in drone.core.connection_state():
                    if st.is_connected:
                        return
            await asyncio.wait_for(connected(), T_CONNECT)

            async def ready():
                async for h in drone.telemetry.health():
                    if h.is_global_position_ok and h.is_home_position_ok and getattr(h, "is_armable", True):
                        return
            await asyncio.wait_for(ready(), T_READY)

            async def home():
                async for hp in drone.telemetry.home():
                    return hp.latitude_deg, hp.longitude_deg
            lat0, lon0 = await asyncio.wait_for(home(), 30)
            latw = lat0 + math.degrees(S.LINE_N_M / 6371000.0)
            items = [MissionItem(0, 6, 22, 1, 1, 0.0, 0.0, 0.0, float("nan"),
                                 int(round(lat0 * 1e7)), int(round(lon0 * 1e7)), float(S.ALT_M), 0),
                     MissionItem(1, 6, 16, 0, 1, 0.0, 0.0, 0.0, float("nan"),
                                 int(round(latw * 1e7)), int(round(lon0 * 1e7)), float(S.ALT_M), 0)]
            await drone.mission_raw.upload_mission(items)

            # PX4 clock: attitude timestamps (boot time, us; equal to simulation time under lockstep)
            clock = {"us": 0, "armed": False, "arm_us": None, "disarm_us": None, "alt": 0.0}

            async def att():
                async for e in drone.telemetry.attitude_euler():
                    clock["us"] = int(e.timestamp_us)

            async def arm_watch():
                async for ar in drone.telemetry.armed():
                    if ar and not clock["armed"]:
                        clock["arm_us"] = clock["us"]
                    if (not ar) and clock["armed"]:
                        clock["disarm_us"] = clock["us"]
                    clock["armed"] = bool(ar)

            async def alt():
                async for p in drone.telemetry.position():
                    clock["alt"] = p.relative_altitude_m
            tasks = [asyncio.ensure_future(c) for c in (att(), arm_watch(), alt())]
            try:
                # mission mode first, then arm: from arming on, everything happens inside PX4
                try:
                    await drone.mission_raw.start_mission()
                    info["mode_before_arm"] = True
                except Exception as e:  # noqa: BLE001
                    info["mode_before_arm"] = f"refused: {e}"
                for k in range(ARM_TRIES):
                    try:
                        await drone.action.arm()
                        break
                    except ActionError as e:
                        if k == ARM_TRIES - 1:
                            raise RuntimeError(f"arming denied {ARM_TRIES} times ({e})")
                        await asyncio.sleep(2)
                t_w = time.time()
                while clock["arm_us"] is None and time.time() - t_w < 20:
                    await asyncio.sleep(0.05)
                if clock["arm_us"] is None:
                    raise RuntimeError("armed state never reported")
                # fallback if arming in mission mode did not start the mission
                await asyncio.sleep(max(0.5, 3.0 / self.a.speed))
                if clock["alt"] < 0.3:
                    t_w = time.time()
                    while clock["us"] - clock["arm_us"] < 3e6 and time.time() - t_w < 10:
                        await asyncio.sleep(0.05)
                    if clock["alt"] < 0.3:
                        await drone.mission_raw.start_mission()
                        info["mission_restarted_after_arm"] = True
                end_us = clock["arm_us"] + int((S.T_OFF + S.T_END + 1.5) * 1e6)
                t_w = time.time()
                while clock["us"] < end_us:
                    if clock["disarm_us"] is not None:
                        info["disarmed_early_at_s"] = (clock["disarm_us"] - clock["arm_us"]) * 1e-6
                        break
                    if time.time() - t_w > wall_cap:
                        raise RuntimeError("wall-clock cap reached (simulation stalled?)")
                    await asyncio.sleep(0.05)
                try:
                    await asyncio.wait_for(drone.action.kill(), 10)
                except Exception:  # noqa: BLE001
                    pass
                await asyncio.sleep(1.5)
                info["status"] = "flown"
            finally:
                for t in tasks:
                    t.cancel()
        except Exception as e:  # noqa: BLE001
            info["error"] = f"{type(e).__name__}: {e}"
        finally:
            try:
                drone._stop_mavsdk_server()
            except Exception:  # noqa: BLE001
                pass
            try:
                os.killpg(proc.pid, signal.SIGINT)
                await asyncio.wait_for(proc.wait(), 8)
            except Exception:  # noqa: BLE001
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                    await proc.wait()
                except Exception:  # noqa: BLE001
                    pass
            logf.close()
        info["wall_s"] = round(time.time() - info["t_wall_start"], 2)
        ulgs = sorted(root.glob("log/**/*.ulg"), key=lambda p: p.stat().st_mtime)
        info["ulg"] = str(ulgs[-1]) if ulgs else None
        return info, root

    async def run_one(self, i, spec):
        for attempt in range(1 + self.a.retries):
            info, root = await self.fly(i, spec)
            row = {k: spec[k] for k in ("mid", "exp", "seed", "anchor_s", "family", "attacker_id", "u", "phys",
                                        "twin", "benign_meta", "sources")}
            row.update(info); row["attempt"] = attempt
            if info["status"] == "flown" and info["ulg"]:
                try:
                    stats, series = await asyncio.get_running_loop().run_in_executor(None, U.extract, info["ulg"])
                    row.update(stats)
                    np.savez_compressed(self.out / "series" / f"{spec['mid']}.npz", **series) if series else None
                    row["status"] = "ok" if stats.get("ok") else "bad_log"
                    if row["status"] == "ok" and 3 not in (stats.get("nav_states") or []):
                        row["status"] = "not_flown"     # Descend/Termination before the window: retried
                except Exception as e:  # noqa: BLE001
                    row["status"] = "extract_error"; row["error"] = f"{type(e).__name__}: {e}"
                    traceback.print_exc()
            keep = self.a.keep_ulog == "all" or (self.a.keep_ulog == "sample" and
                                                 (self.n_kept < 10 or row["status"] != "ok"))
            if info.get("ulg") and keep:
                shutil.copy(info["ulg"], self.out / "ulg" / f"{spec['mid']}.ulg"); self.n_kept += 1
            if row["status"] != "ok":
                shutil.copy(root / "out.log", self.out / "fail_logs" / f"{spec['mid']}_a{attempt}.log")
            row.pop("ulg", None)
            async with self.lock:
                with self.jsonl.open("a") as fh:
                    fh.write(json.dumps(row, default=float) + "\n")
                if row["status"] == "ok":
                    self.done[spec["mid"]] = row
                self.n_flown += 1
                el = time.time() - self.t_start
                log(f"[{self.a.exp}] {spec['mid']} i{i} {row['status']} wall {row.get('wall_s')} s "
                    f"maxdev {row.get('maxdev', float('nan')):.2f} | {self.n_flown} flown, "
                    f"{60 * self.n_flown / max(el, 1):.1f}/min" + (f" | {row.get('error')}" if row.get("error") else ""))
            if row["status"] == "ok":
                return row
        return row

    async def run(self, specs):
        todo = [s for s in specs if s["mid"] not in self.done]
        log(f"[{self.a.exp}] {len(specs)} missions, {len(specs) - len(todo)} already done, {len(todo)} to fly "
            f"on {self.a.k} instances at speed {self.a.speed}")
        q: asyncio.Queue = asyncio.Queue()
        for s in todo:
            q.put_nowait(s)
        results = {}

        async def worker(i):
            while True:
                try:
                    s = q.get_nowait()
                except asyncio.QueueEmpty:
                    return
                results[s["mid"]] = await self.run_one(i, s)
        await asyncio.gather(*(worker(i) for i in range(self.a.k)))
        return {**{m: self.done[m] for m in (s["mid"] for s in specs) if m in self.done}, **results}


# ---------------------------------------------------------------------- CEM in SITL (E3)
def stealthy(row, cal, stack="ALL", fpr=0.05, gate=True):
    th = cal["stack"][str(fpr)] if stack == "ALL" else cal["single"][str(fpr)]
    dets = ("D1", "D2", "D3", "D4") if stack == "ALL" else (stack,)
    alarm = any(row["S" + d[1]] > th[d] for d in dets)
    if gate and row.get("anchor_s"):
        alarm |= row["SA"] > cal["anchor"]
    return not alarm


async def cem(fleet, a):
    cal = json.loads(Path(a.calibration).read_text())
    state_f = fleet.out / "cem_state.json"
    state = json.loads(state_f.read_text()) if state_f.exists() else {}
    rng = np.random.default_rng(a.cem_seed)
    for fi, fam in enumerate(a.families.split(",")):
        k = len(S.ATTACK_BOX[fam])
        st = state.get(fam) or {"gen": 0, "mu": [0.5] * k, "sd": [0.3] * k, "best": [-1.0, [0.5] * k], "hist": []}
        while st["gen"] < a.gens:
            g = st["gen"]
            r = np.random.default_rng([a.cem_seed, fi, g])
            U_ = np.clip(np.array(st["mu"]) + np.array(st["sd"]) * r.normal(size=(a.lam, k)), 0, 1)
            specs = []
            for c in range(a.lam):
                for j in range(a.K):
                    seed = 20000 + 1000 * fi + a.K * g + j          # block 2xxxx; candidates of a generation share seeds
                    specs.append(S.mission(f"e3_{fam}_g{g}_c{c}_k{j}", "e3", seed, anchor=a.anchor,
                                           family=fam, u=U_[c].tolist()))
            res = await fleet.run(specs)
            J = np.zeros(a.lam)
            for c in range(a.lam):
                vals = []
                for j in range(a.K):
                    row = res.get(f"e3_{fam}_g{g}_c{c}_k{j}")
                    if row and row.get("status") == "ok":
                        vals.append(row["maxdev_after"] * stealthy(row, cal, "ALL", a.fpr))
                J[c] = float(np.mean(vals)) if vals else 0.0
            order = np.argsort(J)[::-1]
            if J[order[0]] > st["best"][0]:
                st["best"] = [float(J[order[0]]), U_[order[0]].tolist()]
            E = U_[order[:a.elite]]
            st["mu"] = E.mean(0).tolist(); st["sd"] = np.maximum(E.std(0), 0.02).tolist()
            st["hist"].append({"gen": g, "J": J.tolist(), "U": U_.tolist()})
            st["gen"] = g + 1
            state[fam] = st
            state_f.write_text(json.dumps(state, indent=1))
            log(f"[e3] {fam} gen {g}: best J {J[order[0]]:.3f} (overall {st['best'][0]:.3f})")
    return state


def load_plan(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan"); ap.add_argument("--exp", required=True)
    ap.add_argument("--px4", default="/src"); ap.add_argument("--out", default="/repo/paperIV/results/px4")
    ap.add_argument("-k", type=int, default=8); ap.add_argument("--speed", type=float, default=8.0)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--keep-ulog", default="sample", choices=("all", "sample", "none"))
    ap.add_argument("--limit", type=int, default=0, help="fly only the first N missions of the plan")
    ap.add_argument("--cem", action="store_true"); ap.add_argument("--calibration")
    ap.add_argument("--families", default=",".join(S.FAMILIES)); ap.add_argument("--gens", type=int, default=10)
    ap.add_argument("--lam", type=int, default=8); ap.add_argument("--K", type=int, default=16)
    ap.add_argument("--elite", type=int, default=3); ap.add_argument("--fpr", type=float, default=0.05)
    ap.add_argument("--anchor", type=float, default=5.0); ap.add_argument("--cem-seed", type=int, default=2027)
    a = ap.parse_args()
    fleet = Fleet(a)
    if a.cem:
        asyncio.run(cem(fleet, a))
    else:
        specs = load_plan(a.plan)
        if a.limit:
            specs = specs[:a.limit]
        res = asyncio.run(fleet.run(specs))
        bad = [m for m, r in res.items() if r.get("status") != "ok"]
        log(f"[{a.exp}] finished: {len(res) - len(bad)} ok, {len(bad)} not ok" + (f" (e.g. {bad[:5]})" if bad else ""))


if __name__ == "__main__":
    main()
