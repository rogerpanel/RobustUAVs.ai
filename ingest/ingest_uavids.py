#!/usr/bin/env python3
"""Ingest UAVIDS-2025 flow CSVs (Zeng et al., NS-3.24 swarm mesh) into the schema.

Each row is one aggregated flow -> Event(event_kind=flow, layer=network,
sublayer=mesh). Flows carry a duration but no absolute start time, so
t_start=0.0 and t_end=FlowDuration within the file's own relative clock.
One AttackWindow is emitted per attack class present in the file.

Usage: python3 ingest_uavids.py <csv> <outdir> [--part 0] [--limit N]
"""
import argparse, csv, json, sys
from collections import defaultdict
from pathlib import Path

LABEL_MAP = {
    "Normal Traffic": "benign",
    "Sybil Attack": "sybil",
    "Blackhole Attack": "blackhole",
    "Wormhole Attack": "wormhole",
    "Flooding Attack": "dos_flooding",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path"); ap.add_argument("outdir")
    ap.add_argument("--part", default="0", help="dataset shard tag (file suffix)")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    outdir = Path(a.outdir); outdir.mkdir(parents=True, exist_ok=True)

    events = []
    groups = defaultdict(lambda: {"ids": [], "t1": 0.0})
    with open(a.csv_path, newline="") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            if a.limit and i >= a.limit: break
            native_label = row["label"].strip()
            cls = LABEL_MAP.get(native_label, "other")
            dur = float(row["FlowDuration/s"])
            eid = f"uavids_2025:part{a.part}:flow{row['FlowID']}"
            core = {"FlowID", "FlowDuration/s", "SrcAddr", "DstAddr", "Protocol", "label"}
            events.append({
                "event_id": eid,
                "source_dataset": "uavids_2025",
                "event_kind": "flow",
                "layer": "network",
                "sublayer": "mesh",
                "scenario_id": f"part{a.part}",
                "run_id": None,
                "t_start": 0.0, "t_end": dur,
                "src_node": f"{row['SrcAddr']}:{row['SrcPort']}",
                "dst_node": f"{row['DstAddr']}:{row['DstPort']}",
                "protocol": row["Protocol"].lower(),
                "label_class": cls,
                "label_native": native_label,
                "attacker_node": None,
                "metrics": {
                    "duration_s": dur,
                    "bytes": float(row["TxBytes"]) + float(row["RxBytes"]),
                    "packets": float(row["TxPackets"]) + float(row["RxPackets"]),
                    "mean_delay_s": float(row["MeanDelay/s"]),
                    "mean_jitter_s": float(row["MeanJitter/s"]),
                    "packet_drop_rate": float(row["PacketDropRate"]),
                    "avg_hop_count": float(row["AverageHopCount"]),
                },
                "detector": {"name": None},
                "native": {k: v for k, v in row.items() if k not in core},
            })
            g = groups[cls]
            g["ids"].append(eid); g["t1"] = max(g["t1"], dur)

    windows = []
    for cls, g in sorted(groups.items()):
        if cls == "benign": continue
        windows.append({
            "window_id": f"uavids_2025:part{a.part}:{cls}",
            "source_dataset": "uavids_2025",
            "scenario_id": f"part{a.part}", "run_id": None,
            "layer": "network", "sublayer": "mesh",
            "attack_class": cls,
            "t_start": 0.0, "t_end": g["t1"],
            "attacker_node": None,
            "intensity": {},
            "event_ids": g["ids"][:50],
        })

    (outdir / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    (outdir / "windows.jsonl").write_text("\n".join(json.dumps(w) for w in windows) + "\n")
    from collections import Counter
    dist = Counter(e["label_class"] for e in events)
    print(f"[uavids] {len(events)} flow events {dict(dist)}, {len(windows)} windows -> {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
