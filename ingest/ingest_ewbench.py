#!/usr/bin/env python3
"""Ingest UAV-EW-Bench-2026 per_flight.csv into the unified two-layer schema.

Each row is one flight -> one Event (event_kind=flight, layer=autonomy,
sublayer=mission) carrying js_db and the DO-326A completion outcome. Jamming
AttackWindows are emitted per (defense, js_db, seed) group so a network-layer
window can later be paired against the matching autonomy group.

Usage:
  python3 ingest_ewbench.py <per_flight.csv> <outdir> [--limit N]
"""
import argparse, csv, json, sys
from collections import defaultdict
from pathlib import Path

MISSION_S = 600.0  # nominal per-flight mission duration used as relative window


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("per_flight_csv"); ap.add_argument("outdir")
    ap.add_argument("--limit", type=int, default=0, help="cap events for a demo run (0 = all)")
    a = ap.parse_args()
    outdir = Path(a.outdir); outdir.mkdir(parents=True, exist_ok=True)

    events = []
    groups = defaultdict(lambda: {"n": 0, "completed": 0, "ids": []})
    with open(a.per_flight_csv) as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            if a.limit and i >= a.limit: break
            js = float(row["js_db"]); completed = int(row["completed"])
            eid = (f"uav_ew_bench_2026:{row['defense']}:js{js:.4f}:"
                   f"seed{row['seed']}:f{row['flight_id']}")
            events.append({
                "event_id": eid,
                "source_dataset": "uav_ew_bench_2026",
                "event_kind": "flight",
                "layer": "autonomy",
                "sublayer": "mission",
                "scenario_id": f"{row['mission']}/{row['receiver']}",
                "run_id": f"seed{row['seed']}",
                "t_start": 0.0, "t_end": MISSION_S,
                "src_node": f"uav_{row['flight_id']}", "dst_node": None,
                "protocol": "gnss+px4",
                "label_class": "gps_jamming" if js > 0 else "benign",
                "label_native": f"js_db={js}",
                "attacker_node": None,
                "metrics": {"js_db": js, "mission_completed": completed},
                "detector": {"name": None},
                "native": {"defense": row["defense"], "mission": row["mission"],
                           "receiver": row["receiver"], "flight_id": int(row["flight_id"]),
                           "seed": int(row["seed"])},
            })
            g = groups[(row["defense"], js, row["seed"])]
            g["n"] += 1; g["completed"] += completed; g["ids"].append(eid)

    windows = []
    for (defense, js, seed), g in sorted(groups.items()):
        windows.append({
            "window_id": f"uav_ew_bench_2026:{defense}:js{js:.4f}:seed{seed}",
            "source_dataset": "uav_ew_bench_2026",
            "scenario_id": defense, "run_id": f"seed{seed}",
            "layer": "autonomy", "sublayer": "gnss",
            "attack_class": "gps_jamming" if js > 0 else "benign",
            "t_start": 0.0, "t_end": MISSION_S,
            "attacker_node": None,
            "intensity": {"js_db": js},
            "event_ids": g["ids"][:50],   # keep windows light; full list derivable
            "empirical_mcr": g["completed"] / g["n"] if g["n"] else None,
            "n_flights": g["n"],
        })

    (outdir / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    (outdir / "windows.jsonl").write_text("\n".join(json.dumps(w) for w in windows) + "\n")
    print(f"[ewbench] {len(events)} flight events, {len(windows)} jamming windows -> {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
