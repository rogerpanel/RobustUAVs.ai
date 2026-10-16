#!/usr/bin/env python3
"""R4 -- PX4 SITL multi-vehicle vignette (RQ5; closed-loop soundness check).

Prerequisite: K PX4 SITL instances already running (see run_server_paperIII.sh,
stage r4), instance i reachable on udp://:14540+i.

Driver (asyncio, MAVSDK-Python < 4, the gRPC API; one mavsdk_server per vehicle,
connected once and reused for every rate, stopped at the end):
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
         results/r4_sitl_summary.csv, results/r4_soundness.csv,
         results/r4_soundness_violations.csv (every violating sample with its GNSS context),
         results/r4_px4_events.csv (PX4 warnings, arming, navigation-state and failsafe changes)
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
# R4b (pre-registered in paperIII/R4B_PROTOCOL.md before the run): fresh outages on other
# vehicles, at other times and lengths; spoofing is omitted because SIH rejects it.
SCHEDULE_B = [(2, 35, 15, "off"), (4, 75, 25, "off"), (5, 120, 12, "off"), (0, 160, 20, "off"), (1, 200, 8, "off")]
# R4c (pre-registered in paperIII/R4C_PROTOCOL.md before the run): the latched certificate with
# theta calibrated for the SITL receiver on the R4 and R4b logs, and a third, fresh outage schedule.
SCHEDULE_C = [(3, 30, 18, "off"), (5, 70, 22, "off"), (0, 110, 14, "off"), (2, 150, 26, "off"), (4, 195, 10, "off")]
GAP_S = 1.0                       # a fix after more than GAP_S of receiver staleness is a reacquisition
N_CONV = 3                        # consecutive fixes the estimate must agree with to release the latch
T_CONNECT, T_READY = 90.0, 240.0      # s; a stage that exceeds its timeout fails with its name
ARM_TRIES = 20                        # arming attempts, 3 s apart


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


THETA = THETA_BENIGN    # benign residual ceiling, s; R4c replaces it by the SITL receiver's calibrated value


def rho_now(staleness):
    return KAPPA * (THETA + staleness)


def conv_m():
    """The benign floor: agreement threshold between estimate and fix for releasing the latch."""
    return KAPPA * THETA


class Latch:
    """The estimator-sourced staleness rule of RQ8, as a latch on rho (R4b).

    At a reacquisition (a fix after more than GAP_S of receiver staleness) rho is held at its
    pre-reacquisition value, rho_now(staleness just before the fix). The latch is released once
    the estimate agrees with the receiver fix to within the benign floor on N_CONV consecutive
    fixes, i.e. once the estimator has fused the fix. Only signals available on board are used.
    """

    def __init__(self):
        self.value = None
        self.n = 0

    def on_fix(self, stale_before, innov_m):
        if stale_before > GAP_S:
            self.value = max(self.value or 0.0, rho_now(stale_before))
            self.n = 0
        if self.value is not None:
            self.n = self.n + 1 if innov_m <= conv_m() else 0
            if self.n >= N_CONV:
                self.value, self.n = None, 0

    def rho(self, rho_rx):
        return max(rho_rx, self.value) if self.value is not None else rho_rx


class Vehicle:
    def __init__(self, i):
        self.i = i
        self.last_fix_t = None
        self.fix_type = 0
        self.ned = np.zeros(2)
        self.drone = None
        self.est_ll = None              # estimator position (lat, lon), deg
        self.armed = True
        self.latch = Latch()


async def connect(i):
    from mavsdk import System
    v = Vehicle(i)
    v.drone = System(mavsdk_server_address=None, port=50051 + i)
    await v.drone.connect(system_address=f"udpin://0.0.0.0:{14540 + i}")

    async def wait():
        async for st in v.drone.core.connection_state():
            if st.is_connected:
                return
    try:
        await asyncio.wait_for(wait(), T_CONNECT)
    except asyncio.TimeoutError:
        raise RuntimeError(f"vehicle {i}: no MAVLink heartbeat on udp port {14540 + i} within {T_CONNECT:.0f} s")
    log(f"vehicle {i}: connected")
    return v


async def watch(v):
    async def gps():
        async for g in v.drone.telemetry.gps_info():
            v.fix_type = int(g.fix_type.value) if hasattr(g.fix_type, "value") else int(g.fix_type)

    async def raw():
        async for g in v.drone.telemetry.raw_gps():
            if v.fix_type >= 3:
                now = time.monotonic()
                if v.est_ll is not None:
                    stale_before = (now - v.last_fix_t) if v.last_fix_t else 0.0
                    innov = float(latlon_dist(v.est_ll[0], v.est_ll[1], g.latitude_deg, g.longitude_deg))
                    v.latch.on_fix(stale_before, innov)
                v.last_fix_t = now

    async def pos():
        async for p in v.drone.telemetry.position_velocity_ned():
            v.ned = np.array([p.position.north_m, p.position.east_m])

    async def est():
        async for p in v.drone.telemetry.position():
            v.est_ll = (p.latitude_deg, p.longitude_deg)

    async def armed():
        async for a in v.drone.telemetry.armed():
            v.armed = bool(a)
    return [asyncio.ensure_future(c) for c in (gps(), raw(), pos(), est(), armed())]


async def takeoff(v):
    from mavsdk.offboard import PositionNedYaw
    d = v.drone
    await d.param.set_param_int("SYS_FAILURE_EN", 1)

    async def ready():
        async for h in d.telemetry.health():
            if h.is_global_position_ok and h.is_home_position_ok and getattr(h, "is_armable", True):
                return
    try:
        await asyncio.wait_for(ready(), T_READY)
    except asyncio.TimeoutError:
        raise RuntimeError(f"vehicle {v.i}: no global position / home / armable within {T_READY:.0f} s")
    # PX4 can still deny arming for a few seconds after the health flags settle (preflight checks
    # re-run at 1 Hz); R4c attempt 1 aborted on one such COMMAND_DENIED. Retry, then fail by name.
    from mavsdk.action import ActionError
    for k in range(ARM_TRIES):
        try:
            await d.action.arm()
            break
        except ActionError as e:
            if k == ARM_TRIES - 1:
                raise RuntimeError(f"vehicle {v.i}: arming denied {ARM_TRIES} times ({e})")
            log(f"vehicle {v.i}: arming denied ({e}); retry {k + 1} in 3 s")
            await asyncio.sleep(3)
    await d.offboard.set_position_ned(PositionNedYaw(0.0, 0.0, ALT, 0.0))
    await d.offboard.start()
    log(f"vehicle {v.i}: armed, offboard started")


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


async def session(n_veh, rates, duration, on_rate_done, revision="a"):
    """Connect and take off once, fly every rate over the same connections, then land
    and stop the mavsdk_server processes (they hold UDP and gRPC ports)."""
    vs, tasks = [], []
    try:
        for i in range(n_veh):
            vs.append(await connect(i))
        for v in vs:
            tasks += await watch(v)
        await asyncio.gather(*(takeoff(v) for v in vs))
        await asyncio.sleep(10)
        for rate in rates:
            log(f"rate {rate:g} Hz: flying {duration:.0f} s")
            rows, inj = await run(vs, rate, duration, f"rate{rate:g}", revision)
            log(f"rate {rate:g} Hz: done, {len(rows)} rows")
            on_rate_done(rate, rows, inj)
    finally:
        for v in vs:
            try:
                await v.drone.offboard.stop()
                await v.drone.action.land()
            except Exception:  # noqa: BLE001
                pass
        for tk in tasks:
            tk.cancel()
        for v in vs:
            stop = getattr(v.drone, "_stop_mavsdk_server", None)
            if stop:
                stop()
        log("landed; mavsdk_server processes stopped")


async def run(vs, rate, duration, tag, revision="a"):
    from mavsdk.offboard import PositionNedYaw
    n_veh = len(vs)
    schedule = {"b": SCHEDULE_B, "c": SCHEDULE_C}.get(revision, SCHEDULE)
    t0 = time.monotonic()
    dt = 1.0 / rate
    assign = np.full(n_veh, C.IDLE)
    rows, inj_log, prev_rho = [], [], None
    active = set()
    k = 0
    while (now := time.monotonic()) - t0 < duration:
        t = now - t0
        for (vi, s, du, kind) in schedule:
            if vi >= n_veh:
                continue
            key = (vi, s)
            if s <= t < s + du and key not in active:
                active.add(key); inj_log.append((t, vi, kind, "on", await inject(vs[vi], kind, True)))
            elif t >= s + du and key in active:
                active.discard(key); inj_log.append((t, vi, kind, "off", await inject(vs[vi], kind, False)))
        t_obs = time.monotonic()            # after the injection calls, which can take seconds
        stale = np.array([max(0.0, t_obs - v.last_fix_t) if v.last_fix_t else 1e3 for v in vs])
        rho_rx = rho_now(stale)
        if revision in ("b", "c"):         # latched certificate; a disarmed aircraft holds nothing
            rho = np.array([np.inf if not v.armed else v.latch.rho(r) for v, r in zip(vs, rho_rx)])
        else:
            rho = rho_rx
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
                r["jump_next"] = int(np.isfinite(rho[i]) and rho[i] - prev_rho[i] > KAPPA * dt + 1e-6)
        for i in range(n_veh):
            rows.append({"rate_hz": rate, "epoch": k, "t_s": round(t, 3), "vehicle": i,
                         "staleness_s": round(float(stale[i]), 3),
                         "rho_m": round(float(rho[i]), 3) if np.isfinite(rho[i]) else "inf",
                         "rho_rx_m": round(float(rho_rx[i]), 3), "armed": int(vs[i].armed),
                         "task": int(ex[i]), "alpha": float(a_exec[i]) if held[i] else "",
                         "held": int(held[i]), "violation": int(viol[i]),
                         "on_site": int(held[i] and np.linalg.norm(pos[i] - SITES[ex[i]]) <= R_CAP),
                         "infeasible_next": "", "jump_next": "", "provenance": "sitl", "run": tag})
        prev_rho, assign = rho, ex
        k += 1
        await asyncio.sleep(max(0.0, dt - (time.monotonic() - now)))
    for (vi, s, du, kind) in schedule:            # leave no failure injected into the next rate
        if (vi, s) in active:
            inj_log.append((time.monotonic() - t0, vi, kind, "off", await inject(vs[vi], kind, False)))
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


def _deg(x):
    """ULog GNSS latitude/longitude: int 1e-7 deg (PX4 v1.14) or float deg (later versions)."""
    x = np.asarray(x, dtype=float)
    return x * 1e-7 if np.nanmax(np.abs(x)) > 1000 else x


def latched_rho(tgps, fix, gps_lat, gps_lon, t_est, est_lat, est_lon, t, rho_rx):
    """Replay the Latch rule over the logged GNSS messages and return the latched rho at the
    estimate timestamps t. Innovation = distance between each fix and the estimate at that time."""
    lat_e = np.interp(tgps, t_est, est_lat); lon_e = np.interp(tgps, t_est, est_lon)
    innov = latlon_dist(lat_e, lon_e, gps_lat, gps_lon)
    L, last, vals = Latch(), None, []
    for k in range(len(tgps)):
        if fix[k]:
            L.on_fix((tgps[k] - last) if last is not None else 0.0, float(innov[k]))
            last = tgps[k]
        vals.append(L.value if L.value is not None else 0.0)
    vals = np.array(vals)
    j = np.searchsorted(tgps, t, side="right") - 1
    held = np.where(j >= 0, vals[np.maximum(j, 0)], 0.0)
    return np.maximum(rho_rx, held)


def soundness(log_root: Path):
    """Per log: every estimate sample against rho, for two certificates computed from the logged
    GNSS stream: the receiver certificate (rho from the age of the newest receiver fix) and the
    latched certificate of R4b (the Latch rule replayed from the log). Writes the summary rows
    and every violating sample with its variant and GNSS context."""
    from pyulog import ULog
    rows, samples, events = [], [], []
    ulgs = sorted(log_root.rglob("*.ulg"))
    for f in ulgs:
        u = ULog(str(f))
        D = {d.name: d.data for d in u.data_list if d.multi_id == 0}
        gp, gt = D.get("vehicle_global_position"), D.get("vehicle_global_position_groundtruth")
        gps = D.get("vehicle_gps_position") or D.get("sensor_gps")
        name = str(f.relative_to(log_root))
        if gp is None or gps is None:
            continue
        t = gp["timestamp"] * 1e-6
        t0 = float(t[0])
        if gt is None:
            rows.append({"log": name, "duration_s": round(float(t[-1] - t0), 1), "samples": 0,
                         "status": "groundtruth not logged", "violations": "", "max_excess_m": "",
                         "max_err_m": "", "violations_fresh_fix": "", "violations_10s_after_reacq": "",
                         "provenance": "sitl"})
            continue
        tg = gt["timestamp"] * 1e-6
        lat_t = np.interp(t, tg, gt["lat"]); lon_t = np.interp(t, tg, gt["lon"])
        err = latlon_dist(gp["lat"], gp["lon"], lat_t, lon_t)
        tgps = gps["timestamp"] * 1e-6
        fix = gps["fix_type"] >= 3
        tf = tgps[fix]
        idx = np.searchsorted(tf, t, side="right") - 1
        stale = np.where(idx >= 0, t - tf[np.maximum(idx, 0)], np.inf)
        rho = rho_now(stale)
        rho_l = None
        for la, lo in (("lat", "lon"), ("latitude_deg", "longitude_deg")):   # PX4 v1.14 / v1.15+
            if la in gps and lo in gps:
                rho_l = latched_rho(tgps, fix, _deg(gps[la]), _deg(gps[lo]), t, gp["lat"], gp["lon"], t, rho)
                break
        # reacquisitions: GNSS message with a fix after one without
        reacq = tgps[1:][fix[1:] & ~fix[:-1]]
        if len(reacq):
            ir = np.searchsorted(reacq, t, side="right") - 1
            since_reacq = np.where(ir >= 0, t - reacq[np.maximum(ir, 0)], np.inf)
        else:                                # no GNSS loss in this log
            since_reacq = np.full_like(t, np.inf)
        for m in getattr(u, "logged_messages", []):
            lvl = int(getattr(m, "log_level", 6))
            if lvl <= 4:                         # emergency .. warning
                events.append({"log": name, "t_s": round(m.timestamp * 1e-6 - t0, 3), "kind": f"msg{lvl}",
                               "value": str(m.message)[:200]})
        vst = D.get("vehicle_status")
        if vst is not None:
            for fld in ("arming_state", "nav_state", "failsafe"):
                if fld in vst:
                    x = vst[fld]
                    ch = np.flatnonzero(np.r_[True, x[1:] != x[:-1]])
                    for j in ch:
                        events.append({"log": name, "t_s": round(vst["timestamp"][j] * 1e-6 - t0, 3),
                                       "kind": fld, "value": int(x[j])})
        row = {"log": name, "duration_s": round(float(t[-1] - t0), 1), "status": "checked",
               "reacquisitions": int(len(reacq)), "provenance": "sitl"}
        for variant, rr in (("receiver", rho), ("latched", rho_l)):
            sfx = "" if variant == "receiver" else "_latched"
            if rr is None:
                row["violations" + sfx] = "not available (no GNSS lat/lon in log)"
                continue
            ok = np.isfinite(rr)
            exc = err - rr
            bad = ok & (exc > 0)
            for j in np.flatnonzero(bad):
                samples.append({"log": name, "variant": variant, "t_s": round(float(t[j] - t0), 3),
                                "err_m": round(float(err[j]), 3), "rho_m": round(float(rr[j]), 3),
                                "excess_m": round(float(exc[j]), 3), "staleness_s": round(float(stale[j]), 3),
                                "since_reacq_s": round(float(since_reacq[j]), 3) if np.isfinite(since_reacq[j]) else "",
                                "provenance": "sitl"})
            row["samples" + sfx] = int(ok.sum())
            row["violations" + sfx] = int(bad.sum())
            row["max_excess_m" + sfx] = float(exc[ok].max()) if ok.any() else ""
            row["max_err_m" + sfx] = float(err[ok].max()) if ok.any() else ""
            row["violations_fresh_fix" + sfx] = int((bad & (stale < 1.0)).sum())
            row["violations_10s_after_reacq" + sfx] = int((bad & (since_reacq <= 10.0)).sum())
        rows.append(row)
        print(rows[-1], flush=True)
    return rows, samples, events


CAL_STALE, CAL_REACQ = 1.0, 10.0   # benign: fresh fix (staleness < 1 s), more than 10 s after any reacquisition


def calibrate(dirs):
    """R4c calibration of the benign floor for the SITL receiver, from earlier runs' ULogs.

    A sample is benign when its staleness is below CAL_STALE s and it lies more than CAL_REACQ s
    after any GNSS reacquisition. theta_sitl is the largest benign residual err / KAPPA - staleness,
    i.e. the smallest theta for which every benign sample satisfies err <= KAPPA (theta + staleness).
    This is the parent's definition of theta (the measured benign ceiling), applied to the SITL
    receiver. Logs without ground truth or without any fix contribute nothing."""
    from pyulog import ULog
    rows, best = [], (-np.inf, "")
    for d in dirs:
        for f in sorted(Path(d).rglob("*.ulg")):
            u = ULog(str(f))
            D = {x.name: x.data for x in u.data_list if x.multi_id == 0}
            gp, gt = D.get("vehicle_global_position"), D.get("vehicle_global_position_groundtruth")
            gps = D.get("vehicle_gps_position") or D.get("sensor_gps")
            if gp is None or gt is None or gps is None:
                continue
            t = gp["timestamp"] * 1e-6
            tg = gt["timestamp"] * 1e-6
            err = latlon_dist(gp["lat"], gp["lon"], np.interp(t, tg, gt["lat"]), np.interp(t, tg, gt["lon"]))
            tgps = gps["timestamp"] * 1e-6
            fix = gps["fix_type"] >= 3
            tf = tgps[fix]
            if not len(tf):
                continue
            idx = np.searchsorted(tf, t, side="right") - 1
            stale = np.where(idx >= 0, t - tf[np.maximum(idx, 0)], np.inf)
            reacq = tgps[1:][fix[1:] & ~fix[:-1]]
            if len(reacq):
                ir = np.searchsorted(reacq, t, side="right") - 1
                since = np.where(ir >= 0, t - reacq[np.maximum(ir, 0)], np.inf)
            else:
                since = np.full_like(t, np.inf)
            ok = (stale < CAL_STALE) & (since > CAL_REACQ)
            if not ok.any():
                continue
            res = err[ok] / KAPPA - stale[ok]
            name = f"{Path(d).name}/{f.relative_to(d)}"
            rows.append({"log": name, "benign_samples": int(ok.sum()), "max_residual_s": round(float(res.max()), 4),
                         "q999_residual_s": round(float(np.quantile(res, 0.999)), 4),
                         "max_err_m": round(float(err[ok].max()), 3)})
            if res.max() > best[0]:
                best = (float(res.max()), name)
    out = [{"metric": "theta_parent_s", "value": THETA_BENIGN},
           {"metric": "theta_sitl_s", "value": round(best[0], 4)},
           {"metric": "theta_sitl_from_log", "value": best[1]},
           {"metric": "floor_parent_m", "value": round(KAPPA * THETA_BENIGN, 3)},
           {"metric": "floor_sitl_m", "value": round(KAPPA * best[0], 3)},
           {"metric": "benign_samples", "value": sum(r["benign_samples"] for r in rows)},
           {"metric": "logs", "value": len(rows)}]
    return out, rows


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
    ap.add_argument("--revision", choices=("a", "b", "c"), default="a",
                    help="a: receiver certificate, first schedule (R4); b: latched certificate, "
                         "arming check, fresh schedule (R4b, R4B_PROTOCOL.md); c: as b with theta "
                         "calibrated for the SITL receiver and a third schedule (R4c, R4C_PROTOCOL.md)")
    ap.add_argument("--calibrate", type=Path, nargs="+", default=None,
                    help="R4c: calibrate theta for the SITL receiver from these rootfs dirs and exit")
    ap.add_argument("--theta-file", type=Path, default=None, help="use theta_sitl_s from this calibration CSV")
    a = ap.parse_args()
    if a.calibrate:
        out, rows = calibrate(a.calibrate)
        write("r4c_calibration.csv", out)
        write("r4c_calibration_logs.csv", rows or [{"log": "", "benign_samples": 0}])
        for r in out:
            log(r)
        return
    global THETA
    if a.revision == "c":
        if not a.theta_file:
            raise SystemExit("revision c needs --theta-file (the R4c calibration)")
        cal = {r["metric"]: r["value"] for r in csv.DictReader(a.theta_file.open())}
        THETA = float(cal["theta_sitl_s"])
        log(f"theta = {THETA} s (calibrated for the SITL receiver; parent {THETA_BENIGN} s)")
    pre = {"b": "r4b", "c": "r4c"}.get(a.revision, "r4")
    if not a.soundness_only:
        rows, inj = [], []

        def done(rate, r, il):                    # results are written after every rate
            rows.extend(r); inj.extend((rate,) + x for x in il)
            write(f"{pre}_sitl.csv", rows)
            write(f"{pre}_sitl_summary.csv", summarise(rows))
            write(f"{pre}_injections.csv", [{"rate_hz": x[0], "t_s": round(x[1], 2), "vehicle": x[2], "kind": x[3],
                                         "phase": x[4], "result": x[5]} for x in inj])
            for s in summarise(rows):
                log(s)
        asyncio.run(session(a.vehicles, a.rate, a.duration, done, a.revision))
    if a.logs:
        sr, samples, events = soundness(a.logs)
        write(f"{pre}_soundness.csv", sr or [{"log": "", "samples": 0, "status": "no ULog found",
                                          "violations": "", "max_excess_m": "", "max_err_m": "",
                                          "provenance": "sitl"}])
        write(f"{pre}_soundness_violations.csv", samples or [{"log": "", "variant": "", "t_s": "", "err_m": "", "rho_m": "",
                                                          "excess_m": "", "staleness_s": "",
                                                          "since_reacq_s": "", "provenance": "sitl"}])
        write(f"{pre}_px4_events.csv", events or [{"log": "", "t_s": "", "kind": "", "value": ""}])


if __name__ == "__main__":
    main()
