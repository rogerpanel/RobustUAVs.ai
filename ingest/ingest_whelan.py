#!/usr/bin/env python3
"""Ingest the UAV Attack Dataset (Whelan et al., IEEE DataPort 10.21227/00dg-0d12).

This is the *bridge* dataset: real + SITL/HITL PX4 flights (Pixhawk 4, Holybro
S500, PX4 v1.11.3) under GPS spoofing, GPS jamming, and MAVLink ping-DoS. It is
the ONLY source that couples a concrete network/RF event to *measured* GNSS
degradation on the same PX4 family UAV-EW-Bench models -- so it produces the
schema's only `pairing_basis="measured_same_platform"` records and is the
empirical ground for the theta->delta mapping (replacing the staleness_v0
placeholder in W3).

Two entry points, same output:
  1. Raw ULOG:  a .ulg file  (parsed with pyulog)
  2. ulog2csv:  a directory of per-topic CSVs named "<log>_<topic>_<inst>.csv"
     (the form the dataset ships; produced by PX4's ulog2csv)

Per flight we emit:
  * telemetry_sample Events from the GPS topic (layer=autonomy, sublayer=gnss),
    carrying satellites_used, fix_type, and -- when a benign reference track is
    supplied -- the position error pos_error_m that grounds delta.
  * one AttackWindow spanning the labelled attack interval (class from --attack
    or inferred from the filename), on the layer/sublayer of the attack:
    gps_spoofing/gps_jamming -> autonomy/gnss; ping_dos -> network/c2_link.

The position-error signal:
  pos_error_m is the horizon-plane distance between the (possibly spoofed) GPS
  fix and a benign reference position. Preference order for the reference:
    (a) --ref-track CSV of the matching benign flight (best), else
    (b) the flight's own pre-attack median position (self-reference), else
    (c) omitted (pos_error_m=None) -- we never fabricate it.
This is the raw material W3 turns into delta(theta); this adapter only measures
and records it, it does not model the mapping.

Usage:
  # directory of ulog2csv CSVs:
  python3 ingest_whelan.py --csv-dir path/to/flight_csvs OUTDIR \
      --flight-id spoof_live_01 --attack gps_spoofing \
      --attack-start 42.0 --attack-end 190.0 [--ref-track benign_csvs/]
  # raw ULOG:
  python3 ingest_whelan.py --ulog path/to/flight.ulg OUTDIR \
      --flight-id spoof_live_01 --attack gps_spoofing
  # batch a whole tree (infers class + id from paths; see --manifest):
  python3 ingest_whelan.py --manifest flights.json OUTDIR
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path
from statistics import median

# ----- unified attack taxonomy mapping (source label -> schema class) -----
ATTACK_MAP = {
    "gps_spoofing": ("gps_spoofing", "autonomy", "gnss"),
    "spoof": ("gps_spoofing", "autonomy", "gnss"),
    "gps_jamming": ("gps_jamming", "autonomy", "gnss"),
    "jam": ("gps_jamming", "autonomy", "gnss"),
    "ping_dos": ("dos_flooding", "network", "c2_link"),
    "dos": ("dos_flooding", "network", "c2_link"),
    "benign": ("benign", "autonomy", "gnss"),
    "normal": ("benign", "autonomy", "gnss"),
}

# GPS topics in preference order; first present wins.
GPS_TOPICS = ["vehicle_gps_position", "sensor_gps", "vehicle_global_position"]

# PX4 timestamps are microseconds since boot.
US = 1_000_000.0


def infer_attack(name: str) -> str:
    low = name.lower()
    for key in ("spoof", "jam", "ping_dos", "dos", "benign", "normal"):
        if key in low:
            return key
    return "benign"


def _to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# --------------------------- ULOG / CSV loading ---------------------------

def load_gps_from_ulog(ulg_path: Path):
    """Return (topic_name, list-of-dict rows) for the first present GPS topic."""
    from pyulog import ULog
    ulog = ULog(str(ulg_path))
    available = {d.name: d for d in ulog.data_list}
    for topic in GPS_TOPICS:
        if topic in available:
            d = available[topic]
            n = len(d.data["timestamp"])
            rows = [{k: d.data[k][i] for k in d.data} for i in range(n)]
            return topic, rows
    return None, []


def load_gps_from_csv_dir(csv_dir: Path):
    """Find the ulog2csv file for the first present GPS topic.

    Also accepts the staged-corpus convention (docs/data_staging_layout.md):
    a plain `gps.csv` holding the vehicle_gps_position export."""
    for topic in GPS_TOPICS:
        hits = sorted(csv_dir.glob(f"*{topic}*.csv"))
        if hits:
            with open(hits[0], newline="") as fh:
                rows = list(csv.DictReader(fh))
            return topic, rows
    plain = csv_dir / "gps.csv"
    if plain.exists():
        with open(plain, newline="") as fh:
            rows = list(csv.DictReader(fh))
        return "vehicle_gps_position", rows
    return None, []


def has_ping_dos_signal(csv_dir: Path) -> bool:
    """A ping-DoS shows up as MAVLink/link-load topics rather than GPS."""
    return bool(list(csv_dir.glob("*mavlink*")) or
                list(csv_dir.glob("*telemetry_status*")))


# --------------------------- position-error signal ------------------------

def latlon_to_m(lat0, lon0, lat, lon):
    """Local equirectangular metres from (lat0,lon0). Good for small extents."""
    R = 6_371_000.0
    dlat = math.radians(lat - lat0)
    dlon = math.radians(lon - lon0)
    x = dlon * math.cos(math.radians(lat0)) * R
    y = dlat * R
    return x, y


def gps_latlon(row):
    """Extract (lat, lon) in degrees; PX4 logs them as 1e-7 deg ints in some
    topics and as floats in others."""
    lat = _to_float(row.get("lat"))
    lon = _to_float(row.get("lon"))
    if lat is None or lon is None:
        return None
    # integer-encoded 1e-7 degrees?  (|lat|>1000 can't be degrees)
    if abs(lat) > 1000:
        lat, lon = lat * 1e-7, lon * 1e-7
    return lat, lon


def reference_latlon(ref_dir: Path):
    """Median (lat,lon) of the benign reference track, or None."""
    topic, rows = load_gps_from_csv_dir(ref_dir)
    pts = [gps_latlon(r) for r in rows]
    pts = [p for p in pts if p]
    if not pts:
        return None
    return median(p[0] for p in pts), median(p[1] for p in pts)


# ------------------------------- core ingest ------------------------------

def ingest_flight(rows, topic, flight_id, attack_key, outdir: Path,
                  attack_start=None, attack_end=None,
                  ref_latlon=None, self_ref_until=None):
    cls, layer, sublayer = ATTACK_MAP[attack_key]
    events = []

    # t0 = first valid timestamp; PX4 clocks are us since boot, so every
    # per-flight cutoff (attack_start/end, self_ref_until) is relative to it.
    t0 = None
    for r in rows:
        t = _to_float(r.get("timestamp"))
        if t is not None:
            t0 = t
            break

    # establish reference position for pos_error_m
    ref = ref_latlon
    if ref is None and self_ref_until is not None and t0 is not None:
        pre = []
        for r in rows:
            t = _to_float(r.get("timestamp"))
            if t is None:
                continue
            if (t - t0) / US <= self_ref_until:
                p = gps_latlon(r)
                if p:
                    pre.append(p)
        if pre:
            ref = (median(p[0] for p in pre), median(p[1] for p in pre))
    for i, r in enumerate(rows):
        t_us = _to_float(r.get("timestamp"))
        if t_us is None:
            continue
        if t0 is None:
            t0 = t_us
        t_rel = (t_us - t0) / US

        in_attack = (attack_start is not None and attack_end is not None
                     and attack_start <= t_rel <= attack_end)
        pos_err = None
        latlon = gps_latlon(r)
        if ref and latlon:
            x, y = latlon_to_m(ref[0], ref[1], latlon[0], latlon[1])
            pos_err = round(math.hypot(x, y), 3)

        sats = _to_float(r.get("satellites_used"))
        jam = _to_float(r.get("jamming_indicator"))
        noise = _to_float(r.get("noise_per_ms"))

        events.append({
            "event_id": f"uav_attack_whelan:{flight_id}:{topic}:{i}",
            "source_dataset": "uav_attack_whelan",
            "event_kind": "telemetry_sample",
            "layer": "autonomy",
            "sublayer": "gnss",
            "scenario_id": flight_id,
            "run_id": None,
            "t_start": round(t_rel, 4),
            "t_end": None,
            "src_node": f"uav_{flight_id}",
            "dst_node": None,
            "protocol": "gnss+px4",
            "label_class": cls if in_attack else "benign",
            "label_native": f"{attack_key}" if in_attack else "benign",
            "attacker_node": None,
            "metrics": {
                "pos_error_m": pos_err,
                "satellites_used": sats,
                "js_db": None,   # Whelan gives raw RF, not a J/S label; leave null
            },
            "detector": {"name": None},
            "native": {"topic": topic, "fix_type": r.get("fix_type"),
                       "jamming_indicator": jam, "noise_per_ms": noise,
                       "lat": latlon[0] if latlon else None,
                       "lon": latlon[1] if latlon else None},
        })

    # attack window
    windows = []
    if attack_start is not None and attack_end is not None and cls != "benign":
        win_cls, win_layer, win_sublayer = ATTACK_MAP[attack_key]
        # peak measured pos error inside the window = empirical delta anchor
        peaks = [e["metrics"]["pos_error_m"] for e in events
                 if e["label_class"] != "benign"
                 and e["metrics"]["pos_error_m"] is not None]
        windows.append({
            "window_id": f"uav_attack_whelan:{flight_id}:{win_cls}",
            "source_dataset": "uav_attack_whelan",
            "scenario_id": flight_id, "run_id": None,
            "layer": win_layer, "sublayer": win_sublayer,
            "attack_class": win_cls,
            "t_start": attack_start, "t_end": attack_end,
            "attacker_node": None,
            "intensity": {},
            "event_ids": [e["event_id"] for e in events
                          if e["label_class"] != "benign"][:50],
            "measured_pos_error_max_m": max(peaks) if peaks else None,
            "measured_pos_error_n": len(peaks),
        })

    return events, windows


def write_out(outdir: Path, events, windows, tag):
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n")
    (outdir / "windows.jsonl").write_text(
        "\n".join(json.dumps(w) for w in windows) + "\n")
    n_att = sum(1 for e in events if e["label_class"] != "benign")
    n_pe = sum(1 for e in events if e["metrics"]["pos_error_m"] is not None)
    peak = max((w.get("measured_pos_error_max_m") or 0) for w in windows) if windows else 0
    print(f"[whelan] {tag}: {len(events)} samples ({n_att} in-attack, "
          f"{n_pe} with pos_error_m), {len(windows)} windows"
          + (f", peak pos_error={peak:.1f} m" if peak else "") + f" -> {outdir}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv-dir", help="dir of ulog2csv per-topic CSVs")
    src.add_argument("--ulog", help="raw .ulg file")
    src.add_argument("--manifest", help="JSON list of flights to batch")
    ap.add_argument("--flight-id")
    ap.add_argument("--attack", help="gps_spoofing|gps_jamming|ping_dos|benign "
                                     "(inferred from name if omitted)")
    ap.add_argument("--attack-start", type=float)
    ap.add_argument("--attack-end", type=float)
    ap.add_argument("--ref-track", help="dir of benign reference-flight CSVs")
    ap.add_argument("--self-ref-until", type=float,
                    help="use own pre-attack median (s) as reference if no ref-track")
    a = ap.parse_args(argv)
    outdir = Path(a.outdir)

    # ---- batch mode ----
    if a.manifest:
        flights = json.loads(Path(a.manifest).read_text())
        # Refuse fabricated windows: an attack flight must carry real numeric
        # attack_start/attack_end (from the dataset docs) unless it is
        # explicitly marked "calibration": true (self-referenced pos_error
        # only; emits benign-labelled samples and NO attack windows).
        def _todo(v):
            return v is None or isinstance(v, str)
        bad = [fl["flight_id"] for fl in flights
               if (fl.get("attack") or "benign") not in ("benign", "normal")
               and not fl.get("calibration")
               and (_todo(fl.get("attack_start")) or _todo(fl.get("attack_end")))]
        if bad:
            print("[whelan] REFUSING to run: attack_start/attack_end are unset "
                  "or TODO for: " + ", ".join(bad) + "\n  Fill the real "
                  "intervals from the dataset documentation (or mark the "
                  "entry \"calibration\": true for interval-free pos_error "
                  "calibration). No intervals are ever fabricated.")
            return 2
        all_e, all_w = [], []
        for fl in flights:
            key = (fl.get("attack") or infer_attack(fl.get("flight_id", ""))).lower()
            key = key if key in ATTACK_MAP else infer_attack(key)
            ref = reference_latlon(Path(fl["ref_track"])) if fl.get("ref_track") else None
            cdir = Path(fl["csv_dir"])
            topic, rows = load_gps_from_csv_dir(cdir)
            if not rows:
                print(f"[whelan] WARN no GPS topic in {cdir}; skipping"); continue
            self_ref = fl.get("self_ref_until")
            if self_ref is None and fl.get("self_ref_frac"):
                ts = [_to_float(r.get("timestamp")) for r in rows]
                ts = [t for t in ts if t is not None]
                if ts:
                    self_ref = float(fl["self_ref_frac"]) * (max(ts) - min(ts)) / US
            start = fl.get("attack_start")
            end = fl.get("attack_end")
            if fl.get("calibration"):        # interval-free: no windows
                start = end = None
            e, w = ingest_flight(rows, topic, fl["flight_id"], key, outdir,
                                 start, end,
                                 ref_latlon=ref,
                                 self_ref_until=self_ref)
            if fl.get("calibration") and key not in ("benign", "normal"):
                # Flight-level ground truth (the dataset's folder label) is
                # documented; the per-sample interval is not. Label the CLASS
                # honestly and flag the missing interval - never a window.
                cls = ATTACK_MAP[key][0]
                for ev in e:
                    ev["label_class"] = cls
                    ev["label_native"] = f"{key}|interval_todo_calibration"
            all_e += e; all_w += w
        write_out(outdir, all_e, all_w, f"manifest({len(flights)} flights)")
        return 0

    # ---- single-flight mode ----
    attack_key = (a.attack or infer_attack(a.flight_id or a.csv_dir or a.ulog or "")).lower()
    if attack_key not in ATTACK_MAP:
        attack_key = infer_attack(attack_key)
    fid = a.flight_id or Path(a.csv_dir or a.ulog).stem

    if a.ulog:
        topic, rows = load_gps_from_ulog(Path(a.ulog))
    else:
        topic, rows = load_gps_from_csv_dir(Path(a.csv_dir))
    if not rows:
        print("[whelan] no GPS topic found; nothing to ingest"); return 1

    ref = reference_latlon(Path(a.ref_track)) if a.ref_track else None
    e, w = ingest_flight(rows, topic, fid, attack_key, outdir,
                         a.attack_start, a.attack_end,
                         ref_latlon=ref, self_ref_until=a.self_ref_until)
    write_out(outdir, e, w, fid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
