#!/usr/bin/env python3
"""Ingest UAV-CAS (Mishra et al., IEEE DataPort 10.21227/zgrg-z865) into the schema.

The last of the six Option-C adapters. UAV-CAS is the AERPAW-calibrated
Containernet swarm digital twin: 99,492 flows from 1,024 configurations of a
9-axis design space, five canonical attack families plus nine collaborative
('+'-joined) compositions. Two aligned representations, both supported here:

  * UAV-CAS_stat.csv  — 59 columns: 11 meta (config_idx .. src_ip/dst_ip),
    47 per-flow features (25 flow-level + 22 Fwd/Bwd), Label.
  * UAV-CAS_ts.csv    — per-flow packet sequences: packet_time, packet_size,
    [packet_flag,] packet_dir, Label. The list columns are stringified Python
    lists -> parsed with ast.literal_eval.
  * *_cfg.csv variants — Label carries the verbatim 9-axis config string after
    a '|' separator ("<canonical>|<config_string>"); we split on the first '|'.

Column layout verified against the authors' generators (build_stat_csv.py /
build_ts_csv.py v2, github.com/Sripathm2/Collaborative-UAV-Dataset).

Mapping decisions:
  * Every row -> Event(event_kind=flow, layer=network, sublayer=mesh).
  * scenario_id: stat -> "cfg<config_idx>" (the config index); ts -> the
    embedded config string when present (plain ts files carry no config).
  * Attack classes: DoS/DDoS -> dos_flooding, Blackhole -> blackhole,
    Wormhole -> wormhole, Replay -> replay, '+'-joined -> collaborative
    (the schema's class for the nine compositions); Label kept verbatim in
    label_native.
  * Clocks: stat rows carry only a duration -> t_start=0.0, t_end=duration
    (per-flow relative clock, as in ingest_uavids). ts rows carry real packet
    timestamps sharing a capture clock -> t is re-based per scenario group
    (t0 = earliest packet in the group), preserving intra-scenario alignment
    for cross-layer window work.
  * Losslessness: unmapped stat columns go to native verbatim. For ts rows the
    full packet lists go to native unless --drop-native-lists is set (bulk
    runs on the 2.5 GB corpus may want the summary metrics only).
  * One AttackWindow per (scenario, native base label) with the time bounds of
    its member events and peak packets/s as intensity.

Usage:
  python3 ingest_uavcas.py UAV-CAS_stat.csv data/staging/uavcas_stat
  python3 ingest_uavcas.py UAV-CAS_ts_cfg.csv data/staging/uavcas_ts [--limit N]
  (kind is auto-detected from the header; force with --kind stat|ts)
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# real flood flows carry thousands of packets in one stringified-list cell
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

LABEL_MAP = {
    "Benign": "benign",
    "DoS": "dos_flooding",
    "DDoS": "dos_flooding",
    "Blackhole": "blackhole",
    "Wormhole": "wormhole",
    "Replay": "replay",
}

STAT_META = ["config_idx", "num_drones", "num_bs", "payload", "pathloss",
             "modulation", "mission", "tx_power", "noise", "src_ip", "dst_ip"]


def split_label(raw: str):
    """'<canonical>[|<config_string>]' -> (canonical, config_or_None).
    Neither side contains '|' (authors' guarantee)."""
    if "|" in raw:
        base, cfg = raw.split("|", 1)
        return base.strip(), cfg.strip()
    return raw.strip(), None


def map_class(base: str) -> str:
    if "+" in base:
        return "collaborative"
    return LABEL_MAP.get(base, "other")


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ------------------------------- stat mode --------------------------------

def ingest_stat(rows, limit):
    events = []
    for i, row in enumerate(rows):
        if limit and i >= limit:
            break
        base, cfg = split_label(row["Label"])
        scen = f"cfg{row['config_idx']}"
        dur = _f(row["Flow Duration"]) or 0.0
        core = {"config_idx", "src_ip", "dst_ip", "Label", "Flow Duration",
                "Total Packets", "Total Length of Packets"}
        native = {k: v for k, v in row.items() if k not in core}
        if cfg is not None:
            native["config_string"] = cfg
        events.append({
            "event_id": f"uav_cas:{scen}:stat_row{i}",
            "source_dataset": "uav_cas",
            "event_kind": "flow",
            "layer": "network",
            "sublayer": "mesh",
            "scenario_id": scen,
            "run_id": None,
            "t_start": 0.0, "t_end": dur,
            "src_node": row["src_ip"], "dst_node": row["dst_ip"],
            "protocol": None,
            "label_class": map_class(base),
            "label_native": row["Label"],
            "attacker_node": None,
            "metrics": {
                "duration_s": dur,
                "bytes": _f(row["Total Length of Packets"]),
                "packets": _f(row["Total Packets"]),
                "rate_pps": _f(row["Flow Packets/s"]),
            },
            "detector": {"name": None},
            "native": native,
        })
    return events


# -------------------------------- ts mode ---------------------------------

def ingest_ts(rows, limit, drop_lists):
    """Two passes: first find each scenario group's earliest packet time so
    ts events share a per-scenario relative clock, then emit events."""
    parsed = []
    t0_by_group = {}
    for i, row in enumerate(rows):
        if limit and i >= limit:
            break
        base, cfg = split_label(row["Label"])
        try:
            ts = ast.literal_eval(row["packet_time"])
            sz = ast.literal_eval(row["packet_size"])
            dr = ast.literal_eval(row["packet_dir"])
        except (ValueError, SyntaxError) as e:
            print(f"[uavcas] WARN row {i}: bad list column ({e}); skipped")
            continue
        fl = None
        if "packet_flag" in row and row["packet_flag"]:
            try:
                fl = ast.literal_eval(row["packet_flag"])
            except (ValueError, SyntaxError):
                fl = None
        if not ts:
            continue
        group = cfg  # None for plain ts files -> one shared group
        t0_by_group[group] = min(t0_by_group.get(group, ts[0]), ts[0])
        parsed.append((i, base, cfg, ts, sz, fl, dr, row["Label"]))

    events = []
    for i, base, cfg, ts, sz, fl, dr, raw_label in parsed:
        t0 = t0_by_group[cfg]
        native = {"n_fwd_packets": sum(1 for d in dr if d == 0),
                  "n_bwd_packets": sum(1 for d in dr if d == 1)}
        if cfg is not None:
            native["config_string"] = cfg
        if not drop_lists:
            native.update({"packet_time": ts, "packet_size": sz,
                           "packet_dir": dr})
            if fl is not None:
                native["packet_flag"] = fl
        dur = ts[-1] - ts[0]
        events.append({
            "event_id": f"uav_cas:{cfg or 'ts'}:ts_row{i}",
            "source_dataset": "uav_cas",
            "event_kind": "flow",
            "layer": "network",
            "sublayer": "mesh",
            "scenario_id": cfg,
            "run_id": None,
            "t_start": round(ts[0] - t0, 6),
            "t_end": round(ts[-1] - t0, 6),
            "src_node": None, "dst_node": None,   # ts rows carry no IPs
            "protocol": None,
            "label_class": map_class(base),
            "label_native": raw_label,
            "attacker_node": None,
            "metrics": {
                "duration_s": round(dur, 6),
                "bytes": float(sum(sz)),
                "packets": float(len(ts)),
                "rate_pps": round(len(ts) / dur, 3) if dur > 0 else None,
            },
            "detector": {"name": None},
            "native": native,
        })
    return events


# -------------------------------- windows ---------------------------------

def build_windows(events):
    """One AttackWindow per (scenario, native base label), spanning its
    member events; peak flow rate as intensity."""
    groups = defaultdict(list)
    for e in events:
        if e["label_class"] == "benign":
            continue
        base = split_label(e["label_native"])[0]
        groups[(e["scenario_id"], base)].append(e)

    windows = []
    for (scen, base), evs in sorted(groups.items(), key=lambda kv: str(kv[0])):
        rates = [e["metrics"]["rate_pps"] for e in evs
                 if e["metrics"]["rate_pps"] is not None]
        windows.append({
            "window_id": f"uav_cas:{scen or 'ts'}:{base}",
            "source_dataset": "uav_cas",
            "scenario_id": scen, "run_id": None,
            "layer": "network", "sublayer": "mesh",
            "attack_class": evs[0]["label_class"],
            "t_start": min(e["t_start"] for e in evs),
            "t_end": max(e["t_end"] if e["t_end"] is not None else e["t_start"]
                         for e in evs),
            "attacker_node": None,
            "intensity": {"rate_pps": max(rates) if rates else None},
            "event_ids": [e["event_id"] for e in evs][:50],
        })
    return windows


# ---------------------------------- main -----------------------------------

def detect_kind(header) -> str:
    if "packet_time" in header:
        return "ts"
    if "config_idx" in header:
        return "stat"
    raise SystemExit(f"[uavcas] cannot detect stat/ts from header {header[:5]}; "
                     "pass --kind")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("outdir")
    ap.add_argument("--kind", choices=["stat", "ts"],
                    help="force input kind (default: detect from header)")
    ap.add_argument("--limit", type=int, default=0, help="cap rows (0 = all)")
    ap.add_argument("--drop-native-lists", action="store_true",
                    help="ts mode: omit the raw packet lists from native "
                         "(keeps events.jsonl small on the full corpus)")
    a = ap.parse_args()
    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    with open(a.csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        kind = a.kind or detect_kind(reader.fieldnames or [])
        if kind == "stat":
            events = ingest_stat(reader, a.limit)
        else:
            events = ingest_ts(reader, a.limit, a.drop_native_lists)

    windows = build_windows(events)

    (outdir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n")
    (outdir / "windows.jsonl").write_text(
        "\n".join(json.dumps(w) for w in windows) + "\n" if windows else "")
    dist = Counter(e["label_class"] for e in events)
    n_scen = len({e["scenario_id"] for e in events})
    print(f"[uavcas] {kind}: {len(events)} flow events {dict(dist)} across "
          f"{n_scen} scenario(s), {len(windows)} windows -> {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
