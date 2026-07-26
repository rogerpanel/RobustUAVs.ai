#!/usr/bin/env python3
"""Ingest HCRL UAVCAN attack dataset (Kim et al.) into the schema.

Files are candump-style text ('typeN_label.bin'):
    Label (timestamp)  can0  CANID  [dlc]  BB BB ...
Labels observed: 'Normal' and 'Attack' (per-scenario attack type comes from the
scenario documentation: Flooding / Fuzzy / Replay across type1..type10).

Frames -> Event(event_kind=frame, layer=network, sublayer=intra_bus).
Contiguous 'Attack' runs (with gap tolerance) -> AttackWindow records.

Usage:
  python3 ingest_hcrl.py <label_file> <outdir> --scenario type1 \
      [--attack-class dos_flooding] [--limit N] [--gap 1.0]
"""
import argparse, json, re, sys
from pathlib import Path

LINE_RE = re.compile(
    r"^(?P<label>\w+)\s+\((?P<ts>[\d.]+)\)\s+(?P<iface>\S+)\s+"
    r"(?P<canid>[0-9A-Fa-f]+)\s+\[(?P<dlc>\d+)\]\s*(?P<data>[0-9A-Fa-f ]*)$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("label_file"); ap.add_argument("outdir")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--attack-class", default="other",
                    choices=["dos_flooding", "fuzzing", "replay", "other"])
    ap.add_argument("--limit", type=int, default=0, help="cap frame events (0 = all); windows always use the full file")
    ap.add_argument("--gap", type=float, default=1.0, help="max gap (s) inside one attack window")
    a = ap.parse_args()
    outdir = Path(a.outdir); outdir.mkdir(parents=True, exist_ok=True)

    events, windows = [], []
    cur = None  # open attack window [t0, t1, count]
    n_frames = n_attack = 0

    with open(a.label_file, errors="ignore") as fh:
        for lineno, line in enumerate(fh):
            m = LINE_RE.match(line.strip())
            if not m: continue
            d = m.groupdict()
            ts = float(d["ts"]); is_attack = d["label"] != "Normal"
            n_frames += 1; n_attack += is_attack

            if (not a.limit) or len(events) < a.limit:
                # UAVCAN v0 frame: source node id = low 7 bits of the 29-bit CAN id
                canid = int(d["canid"], 16)
                events.append({
                    "event_id": f"hcrl_uavcan:{a.scenario}:l{lineno}",
                    "source_dataset": "hcrl_uavcan",
                    "event_kind": "frame",
                    "layer": "network",
                    "sublayer": "intra_bus",
                    "scenario_id": a.scenario, "run_id": None,
                    "t_start": ts, "t_end": None,
                    "src_node": f"node{canid & 0x7F}",
                    "dst_node": "bus",
                    "protocol": "uavcan_v0",
                    "label_class": a.attack_class if is_attack else "benign",
                    "label_native": d["label"],
                    "attacker_node": f"node{canid & 0x7F}" if is_attack else None,
                    "metrics": {"bytes": int(d["dlc"])},
                    "detector": {"name": None},
                    "native": {"can_id_hex": d["canid"], "dlc": int(d["dlc"]),
                               "data_hex": d["data"].strip(), "iface": d["iface"]},
                })

            if is_attack:
                if cur and ts - cur[1] <= a.gap:
                    cur[1] = ts; cur[2] += 1
                else:
                    if cur: windows.append(cur)
                    cur = [ts, ts, 1]
            # Normal frames do not close windows; only time gaps do.
    if cur: windows.append(cur)

    win_records = [{
        "window_id": f"hcrl_uavcan:{a.scenario}:w{i}",
        "source_dataset": "hcrl_uavcan",
        "scenario_id": a.scenario, "run_id": None,
        "layer": "network", "sublayer": "intra_bus",
        "attack_class": a.attack_class,
        "t_start": t0, "t_end": t1,
        "attacker_node": None,
        "intensity": {"rate_pps": round(n / max(t1 - t0, 1e-6), 2)},
        "event_ids": [],
    } for i, (t0, t1, n) in enumerate(windows)]

    (outdir / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    (outdir / "windows.jsonl").write_text("\n".join(json.dumps(w) for w in win_records) + "\n")
    print(f"[hcrl] {a.scenario}: {n_frames} frames scanned ({n_attack} attack), "
          f"{len(events)} events emitted, {len(win_records)} attack windows -> {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
