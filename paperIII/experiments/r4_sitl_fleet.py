#!/usr/bin/env python3
"""R4 -- PX4 SITL multi-vehicle vignette (RQ5; closed-loop soundness check).

Prerequisite: K PX4 SITL instances already running (see run_server_paperIII.sh,
stage r4), instance i reachable on udp://:14540+i.

Driver (asyncio, MAVSDK-Python < 4, the gRPC API; one mavsdk_server per vehicle):
  1. arm, take off to 15 m, start offboard;
  2. every 1/rate s: read each vehicle's GNSS stream (raw_gps timestamps and
     gps_info fix type), compute staleness = time since the last fix with
     fix_type >= 3, and rho_i = KAPPA * (THETA_BENIGN + staleness)
     (certificate.rho_of_staleness, benign floor added);
  3. allocate with the exact projection, predictive acquisition and release
     (lookahead = keep_lookahead = KAPPA / rate), proposal = keep-or-nearest;
  4. send offboard position setpoints: the assigned site, or a holding slot;
  5. inject GNSS loss with the SITL failure injection (SYS_FAILURE_EN = 1,
     `failure gps off`) on scheduled vehicles; a spoofing ramp is attempted
     with failure type WRONG and logged as unsupported if PX4 refuses it.
Logged per epoch and vehicle: staleness, rho, executed task and its alert
limit, violation (rho > alpha at execution), exposure (feasible at decision,
infeasible at the next epoch), whether the next-epoch change was a jump
(rise > KAPPA / rate), on-site flag.

Soundness check (after the run, from each instance's ULog, PX4 clock only):
horizontal distance between vehicle_global_position and
vehicle_global_position_groundtruth, against rho computed from the logged GNSS
messages at the same instant. Every sample is reported; nothing is filtered.
If the ground-truth topic is not in the log, the check is reported as
"not available" (never estimated).

Outputs: results/r4_sitl.csv (epoch log, provenance=sitl),
         results/r4_sitl_summary.csv, results/r4_soundness.csv
Usage:   python3 r4_sitl_fleet.py --vehicles 6 --rate 5 --duration 240
         python3 r4_sitl_fleet.py --soundness-only --logs <dir with rootfs/*/log>
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from certcmdp.certificate import OUT, KAPPA, THETA_BENIGN  # noqa: E402
from certcmdp import combinatorics as C  # noqa: E402

SITES = np.array([[60.0, 40.0], [-50.0, 70.0], [80.0, -60.0], [-70.0, -50.0]])   # NED, m
ALPHA = np.array([2.0, 5.0, 10.0, 20.0])                                          # alert limits
ALT = -15.0
R_CAP = 5.0
# (vehicle, start_s, duration_s, kind)
SCHEDULE = [(1, 40, 20, "off"), (3, 90, 30, "off"), (2, 140, 15, "wrong"), (0, 170, 10, "off")]


def rho_now(staleness):
    return KAPPA * (THETA_BENIGN + staleness)


class Vehicle:
    def __init__(self, i):
        self.i = i
        self.last_fix_t = None
        self.fix_type = 0
        self.ned = np.zeros(2)
        self.drone = None


async def connect(i):
    from mavsdk import System
    v = Vehicle(i)
    v.drone = System(mavsdk_server_address=None, port=50051 + i)
    await v.drone.connect(system_address=f"udp://:{14540 + i}")
    async for st in v.drone.core.connection_state():
        if st.is_connected:
            break
    return v


async def watch(v):
    async def gps():
        async for g in v.drone.telemetry.gps_info():
            v.fix_type = int(g.fix_type.value) if hasattr(g.fix_type, "value") else int(g.fix_type)

    async def raw():
        async for _ in v.drone.telemetry.raw_gps():
            if v.fix_type >= 3:
                v.last_fix_t = time.monotonic()

    async def pos():
        async for p in v.drone.telemetry.position_velocity_ned():
            v.ned = np.array([p.position.north_m, p.position.east_m])
    return [asyncio.ensure_future(x()) for x in (gps(), raw(), pos())]


async def takeoff(v):
    from mavsdk.offboard import PositionNedYaw
    d = v.drone
    await d.param.set_param_int("SYS_FAILURE_EN", 1)
    async for h in d.telemetry.health():
        if h.is_global_position_ok and h.is_home_position_ok:
            break
    await d.action.arm()
    await d.offboard.set_position_ned(PositionNedYaw(0.0, 0.0, ALT, 0.0))
    await d.offboard.start()


async def inject(v, kind, on):
    """SITL failure injection; for GNSS loss on simulators whose GPS driver does
    not implement it (SIH), fall back to SIM_GPS_USED = 0 satellites (no fix)."""
    from mavsdk.failure import FailureUnit, FailureType
    ft = {"off": FailureType.OFF, "wrong": FailureType.WRONG}[kind] if on else FailureType.OK
    try:
        await v.drone.failure.inject(FailureUnit.SENSOR_GPS, ft, 0)
        return "failure_inject"
    except Exception as e:  # noqa: BLE001  (PX4 may not implement every failure type)
        if kind != "off":
            return f"unsupported:{type(e).__name__}"
        try:
            await v.drone.param.set_param_int("SIM_GPS_USED", 0 if on else 10)
            return "SIM_GPS_USED"
        except Exception as e2:  # noqa: BLE001
            return f"unsupported:{type(e).__name__},{type(e2).__name__}"


async def run(n_veh, rate, duration, tag):
    from mavsdk.offboard import PositionNedYaw
    vs = [await connect(i) for i in range(n_veh)]
    tasks = []
    for v in vs:
        tasks += await watch(v)
    await asyncio.gather(*(takeoff(v) for v in vs))
    await asyncio.sleep(10)
    t0 = time.monotonic()
    dt = 1.0 / rate
    assign = np.full(n_veh, C.IDLE)
    rows, inj_log, prev_rho = [], [], None
    active = set()
    k = 0
    while (now := time.monotonic()) - t0 < duration:
        t = now - t0
        for (vi, s, du, kind) in SCHEDULE:
            if vi >= n_veh:
                continue
            key = (vi, s)
            if s <= t < s + du and key not in active:
                active.add(key); inj_log.append((t, vi, kind, "on", await inject(vs[vi], kind, True)))
            elif t >= s + du and key in active:
                active.discard(key); inj_log.append((t, vi, kind, "off", await inject(vs[vi], kind, False)))
        stale = np.array([(now - v.last_fix_t) if v.last_fix_t else 1e3 for v in vs])
        rho = rho_now(stale)
        pos = np.stack([v.ned for v in vs])
        d = np.linalg.norm(pos[:, None, :] - SITES[None, :, :], axis=-1)
        prop = np.where(assign >= 0, assign, d.argmin(1))
        el = C.eligibility(rho, ALPHA, holder_of=assign, lookahead=KAPPA * dt, keep_lookahead=KAPPA * dt)
        ex = C.lexicographic_projection(el, prop, prev=assign)
        held = ex >= 0
        a_exec = np.where(held, ALPHA[np.maximum(ex, 0)], np.inf)
        viol = held & (rho > a_exec)
        for v, j in zip(vs, ex):
            tgt = SITES[j] if j >= 0 else np.array([10.0 * v.i, -10.0])
            await v.drone.offboard.set_position_ned(PositionNedYaw(float(tgt[0]), float(tgt[1]), ALT, 0.0))
        if prev_rho is not None:
            for r in rows[-n_veh:]:
                i = r["vehicle"]
                r["infeasible_next"] = int(r["held"] and rho[i] > r["alpha"])
                r["jump_next"] = int(rho[i] - prev_rho[i] > KAPPA * dt + 1e-6)
        for i in range(n_veh):
            rows.append({"rate_hz": rate, "epoch": k, "t_s": round(t, 3), "vehicle": i,
                         "staleness_s": round(float(stale[i]), 3), "rho_m": round(float(rho[i]), 3),
                         "task": int(ex[i]), "alpha": float(a_exec[i]) if held[i] else "",
                         "held": int(held[i]), "violation": int(viol[i]),
                         "on_site": int(held[i] and np.linalg.norm(pos[i] - SITES[ex[i]]) <= R_CAP),
                         "infeasible_next": "", "jump_next": "", "provenance": "sitl", "run": tag})
        prev_rho, assign = rho, ex
        k += 1
        await asyncio.sleep(max(0.0, dt - (time.monotonic() - now)))
    for v in vs:
        try:
            await v.drone.offboard.stop()
            await v.drone.action.land()
        except Exception:  # noqa: BLE001
            pass
    for tk in tasks:
        tk.cancel()
    return rows, inj_log


def summarise(rows):
    out = []
    for rate in sorted({r["rate_hz"] for r in rows}):
        rr = [r for r in rows if r["rate_hz"] == rate and r["infeasible_next"] != ""]
        held = [r for r in rr if r["held"]]
        exp_all = sum(r["infeasible_next"] for r in held)
        exp_nojump = sum(r["infeasible_next"] for r in held if not r["jump_next"])
        out.append({"rate_hz": rate, "agent_epochs": len(rr), "held_epochs": len(held),
                    "executed_violations": sum(r["violation"] for r in rr),
                    "exposure_total": exp_all, "exposure_without_jump": exp_nojump,
                    "certified_coverage": float(np.mean([r["on_site"] and not r["violation"] for r in rr]))
                    if rr else "", "provenance": "sitl"})
    return out


def latlon_dist(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    x = dl * np.cos(0.5 * (p1 + p2))
    y = p2 - p1
    return R * np.hypot(x, y)


def soundness(log_root: Path):
    from pyulog import ULog
    rows = []
    ulgs = sorted(log_root.rglob("*.ulg"))
    for f in ulgs:
        u = ULog(str(f))
        D = {d.name: d.data for d in u.data_list if d.multi_id == 0}
        gp, gt = D.get("vehicle_global_position"), D.get("vehicle_global_position_groundtruth")
        gps = D.get("vehicle_gps_position") or D.get("sensor_gps")
        if gp is None or gps is None:
            continue
        if gt is None:
            rows.append({"log": str(f.relative_to(log_root)), "samples": 0, "status": "groundtruth not logged",
                         "violations": "", "max_excess_m": "", "max_err_m": "", "provenance": "sitl"})
            continue
        t = gp["timestamp"] * 1e-6
        tg = gt["timestamp"] * 1e-6
        lat_t = np.interp(t, tg, gt["lat"]); lon_t = np.interp(t, tg, gt["lon"])
        err = latlon_dist(gp["lat"], gp["lon"], lat_t, lon_t)
        tf = gps["timestamp"][gps["fix_type"] >= 3] * 1e-6
        idx = np.searchsorted(tf, t, side="right") - 1
        stale = np.where(idx >= 0, t - tf[np.maximum(idx, 0)], np.inf)
        rho = rho_now(stale)
        ok = np.isfinite(rho)
        exc = err[ok] - rho[ok]
        rows.append({"log": str(f.relative_to(log_root)), "samples": int(ok.sum()), "status": "checked",
                     "violations": int((exc > 0).sum()), "max_excess_m": float(exc.max()) if ok.any() else "",
                     "max_err_m": float(err[ok].max()) if ok.any() else "", "provenance": "sitl"})
        print(rows[-1])
    return rows


def write(name, rows):
    if not rows:
        return
    with (OUT / name).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vehicles", type=int, default=6)
    ap.add_argument("--rate", type=float, nargs="+", default=[5.0, 2.0])
    ap.add_argument("--duration", type=float, default=240.0)
    ap.add_argument("--logs", type=Path, default=None, help="PX4 rootfs dir holding the instance logs")
    ap.add_argument("--soundness-only", action="store_true")
    a = ap.parse_args()
    if not a.soundness_only:
        rows, inj = [], []
        for rate in a.rate:
            r, il = asyncio.run(run(a.vehicles, rate, a.duration, f"rate{rate:g}"))
            rows += r; inj += [(rate,) + x for x in il]
        write("r4_sitl.csv", rows)
        write("r4_sitl_summary.csv", summarise(rows))
        write("r4_injections.csv", [{"rate_hz": x[0], "t_s": round(x[1], 2), "vehicle": x[2], "kind": x[3],
                                     "phase": x[4], "result": x[5]} for x in inj])
        for s in summarise(rows):
            print(s)
    if a.logs:
        sr = soundness(a.logs)
        write("r4_soundness.csv", sr or [{"log": "", "samples": 0, "status": "no ULog found",
                                          "violations": "", "max_excess_m": "", "max_err_m": "",
                                          "provenance": "sitl"}])


if __name__ == "__main__":
    main()
