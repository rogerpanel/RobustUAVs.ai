#!/usr/bin/env python3
"""Why did PX4 enter Descend/Termination before the mission window? (PX4_PREREG.md, deviation 1)

Reads every ULog the fleet kept (results/px4/<run>/ulg/*.ulg: the first missions of each run
and every failed attempt, including the retried missions that were not flown) and the PX4
console logs of failed attempts (<run>/fail_logs/*.log). For each ULog whose vehicle never
reached nav_state 3 (mission) inside the window, it reports:

  * the navigation-state sequence after arming, with times;
  * the time of the first failsafe after arming and the failsafe_flags fields that were set
    at that moment (when the topic is logged);
  * EKF2 status at that moment (tilt/yaw alignment, GNSS, external-vision fusion);
  * the largest roll/pitch before the failsafe (a vehicle that tips at take-off);
  * the vehicle commands received (arm, mode, mission start) and their results;
  * every logged PX4 message of level WARNING or worse.

Nothing is inferred beyond the logs: the most frequent flags and messages are printed, and
the per-mission table is written to results/px4/px4_unflown_diagnosis.csv. Missions that
did fly are counted, not diagnosed (they serve as the comparison group for the flags).

Usage: python3 p4_unflown_diag.py [run ...]      (default: every run directory with ULogs)
"""
from __future__ import annotations

import collections
import csv
import math
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PX = HERE.parents[1] / "results" / "px4"
NAV = {0: "manual", 1: "altctl", 2: "posctl", 3: "mission", 4: "loiter", 5: "rtl", 10: "acro", 12: "descend",
       13: "termination", 14: "offboard", 15: "stab", 17: "takeoff", 18: "land", 19: "follow", 20: "precland",
       21: "orbit", 22: "vtol_takeoff"}
LEVELS = {0: "EMERG", 1: "ALERT", 2: "CRIT", 3: "ERROR", 4: "WARN", 5: "NOTICE", 6: "INFO", 7: "DEBUG"}


def topic(ul, name):
    for d in ul.data_list:
        if d.name == name and d.multi_id == 0:
            return d.data
    return None


def at(data, t_us, field):
    """Value of field at time t_us (last sample at or before t_us), or None."""
    if data is None or field not in data:
        return None
    i = np.searchsorted(data["timestamp"], t_us, side="right") - 1
    return None if i < 0 else data[field][i]


def diagnose(path: Path) -> dict | None:
    from pyulog import ULog
    ul = ULog(str(path))
    vs = topic(ul, "vehicle_status")
    if vs is None:
        return {"mid": path.stem, "file": str(path), "why": "no vehicle_status"}
    armed = np.nonzero(vs["arming_state"] == 2)[0]
    if not len(armed):
        return {"mid": path.stem, "file": str(path), "why": "never armed"}
    t_arm = int(vs["timestamp"][armed[0]])
    toff = float(ul.initial_parameters.get("BEN_TOFF", 15.0))
    tend = float(ul.initial_parameters.get("BEN_T_END", 60.0))
    rel = (vs["timestamp"].astype(np.int64) - t_arm) * 1e-6
    inw = (rel >= toff) & (rel <= toff + tend)
    flew = bool((vs["nav_state"][inw] == 3).any())
    after = rel >= 0
    seq, last = [], None
    for k in np.nonzero(after)[0]:
        n = int(vs["nav_state"][k])
        if n != last:
            seq.append(f"{NAV.get(n, n)}@{rel[k]:.1f}")
            last = n
    out = {"mid": path.stem, "file": str(path.relative_to(PX)) if PX in path.parents else str(path),
           "flew": flew, "nav_sequence": " ".join(seq[:12])}
    fs = np.nonzero(after & (vs["failsafe"] > 0))[0] if "failsafe" in vs else []
    t_fs = int(vs["timestamp"][fs[0]]) if len(fs) else None
    out["t_failsafe_s"] = None if t_fs is None else round((t_fs - t_arm) * 1e-6, 2)
    tq = t_fs if t_fs is not None else t_arm + int(5e6)

    ff = topic(ul, "failsafe_flags")
    if ff is not None:
        on = []
        for f, col in ff.items():
            if f == "timestamp" or f.startswith("mode_req"):
                continue
            boolean = col.dtype == np.bool_ or (col.dtype == np.uint8 and set(np.unique(col).tolist()) <= {0, 1})
            if boolean and bool(at(ff, tq + int(0.5e6), f)):   # flags evaluated just after the failsafe
                on.append(f)
        out["failsafe_flags_set"] = " ".join(sorted(on))
    else:
        out["failsafe_flags_set"] = "(failsafe_flags not logged)"

    es = topic(ul, "estimator_status_flags")
    for f, alt in (("cs_tilt_align", None), ("cs_yaw_align", None), ("cs_gps", "cs_gnss_pos"),
                   ("cs_ev_pos", "cs_aux_gpos"), ("cs_inertial_dead_reckoning", None)):
        v = at(es, tq, f)
        if v is None and alt:                      # field names of PX4 >= v1.16
            v = at(es, tq, alt)
        out[f] = None if v is None else int(v)

    att = topic(ul, "vehicle_attitude")
    if att is not None:
        m = (att["timestamp"] >= t_arm) & (att["timestamp"] <= tq)
        if m.any():
            q0, q1, q2, q3 = (att[f"q[{i}]"][m] for i in range(4))
            roll = np.degrees(np.arctan2(2 * (q0 * q1 + q2 * q3), 1 - 2 * (q1 * q1 + q2 * q2)))
            pitch = np.degrees(np.arcsin(np.clip(2 * (q0 * q2 - q3 * q1), -1, 1)))
            out["max_tilt_deg_before_fs"] = round(float(max(np.max(np.abs(roll)), np.max(np.abs(pitch)))), 1)

    vld = topic(ul, "vehicle_land_detected")
    v = at(vld, tq, "landed")
    out["landed_at_fs"] = None if v is None else int(v)

    vc = topic(ul, "vehicle_command")
    ack = topic(ul, "vehicle_command_ack")
    cmds = []
    if vc is not None:
        for k in range(len(vc["timestamp"])):
            t = (int(vc["timestamp"][k]) - t_arm) * 1e-6
            if -30 <= t <= toff:
                cmds.append(f"{int(vc['command'][k])}({vc['param1'][k]:.0f},{vc['param2'][k]:.0f})@{t:.1f}")
    out["commands"] = " ".join(cmds[:15])
    if ack is not None:
        bad = [f"{int(ack['command'][k])}:r{int(ack['result'][k])}@{(int(ack['timestamp'][k]) - t_arm) * 1e-6:.1f}"
               for k in range(len(ack["timestamp"])) if int(ack["result"][k]) != 0
               and -30 <= (int(ack["timestamp"][k]) - t_arm) * 1e-6 <= toff]
        out["rejected_commands"] = " ".join(bad[:10])
    msgs = []
    for m in ul.logged_messages:
        lvl = m.log_level if isinstance(m.log_level, int) else 6
        if lvl <= 4:
            msgs.append(f"[{LEVELS.get(lvl, lvl)} {(m.timestamp - t_arm) * 1e-6:.1f}] {m.message}")
    out["messages"] = " | ".join(msgs[:12])
    return out


def console(path: Path) -> list:
    keep = re.compile(r"WARN|ERROR|fail|Fail|FAIL|terminat|Terminat|descend|Descend|reject|denied", re.I)
    return [l.strip() for l in path.read_text(errors="replace").splitlines() if keep.search(l)][:20]


def main():
    try:
        import pyulog  # noqa: F401
    except ImportError:
        raise SystemExit("pyulog is needed: pip3 install pyulog (the fleet's container image has it)")
    runs = sys.argv[1:] or sorted(p.name for p in PX.iterdir() if (p / "ulg").is_dir())
    rows, n_flew = [], collections.Counter()
    for run in runs:
        for f in sorted((PX / run / "ulg").glob("*.ulg")):
            try:
                r = diagnose(f)
            except Exception as e:  # noqa: BLE001  a corrupt log is reported, not skipped silently
                r = {"mid": f.stem, "file": str(f), "why": f"unreadable: {type(e).__name__}: {e}"}
            r["run"] = run
            if r.get("flew"):
                n_flew[run] += 1
                continue
            logs = sorted((PX / run / "fail_logs").glob(f"{f.stem}_a*.log"))
            r["console"] = " | ".join(console(logs[-1])) if logs else ""
            rows.append(r)
    keys = ["run", "mid", "nav_sequence", "t_failsafe_s", "failsafe_flags_set", "cs_tilt_align", "cs_yaw_align",
            "cs_gps", "cs_ev_pos", "cs_inertial_dead_reckoning", "max_tilt_deg_before_fs", "landed_at_fs",
            "commands", "rejected_commands", "messages", "console", "why", "file"]
    with open(PX / "px4_unflown_diagnosis.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    print(f"ULogs of missions that flew (not diagnosed): {dict(n_flew)}")
    print(f"ULogs of missions that did not fly: {len(rows)} -> results/px4/px4_unflown_diagnosis.csv")
    if not rows:
        return
    for key, label in (("failsafe_flags_set", "failsafe flags set at the failsafe"),
                       ("nav_sequence", "navigation sequences")):
        c = collections.Counter(r.get(key) or "" for r in rows)
        print(f"\nmost frequent {label}:")
        for v, n in c.most_common(6):
            print(f"  {n:4d}  {v}")
    c = collections.Counter()
    for r in rows:
        for m in set(re.sub(r"\[\w+ -?[\d.]+\] ", "", x) for x in (r.get("messages") or "").split(" | ") if x):
            c[m] += 1
    print("\nmost frequent PX4 warnings (missions containing each):")
    for v, n in c.most_common(10):
        print(f"  {n:4d}  {v}")
    t = [r["t_failsafe_s"] for r in rows if r.get("t_failsafe_s") is not None]
    if t:
        print(f"\nfirst failsafe after arming: median {np.median(t):.1f} s, range {min(t):.1f}-{max(t):.1f} s")
    tl = [r["max_tilt_deg_before_fs"] for r in rows if r.get("max_tilt_deg_before_fs") is not None]
    if tl:
        print(f"largest tilt before it: median {np.median(tl):.0f} deg, max {max(tl):.0f} deg")


if __name__ == "__main__":
    main()
