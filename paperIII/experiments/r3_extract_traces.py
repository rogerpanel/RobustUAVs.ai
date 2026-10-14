#!/usr/bin/env python3
"""R3 step 1 -- extract per-epoch staleness traces from the measured flights.

For every flight of the Whelan UAV Attack Dataset staged by
`data/fetch_kaggle.py --copy` under data/raw/uav_attack_whelan/ (any depth;
a flight is a directory holding a .ulg file or ulog2csv per-topic CSVs), on a
0.5 s grid from the first to the last GNSS message:

  staleness(t) = t - (time of the last GNSS fix with fix_type >= 3 that the
                      estimator was fusing, at or before t)

"Fusing" uses estimator_status_flags.cs_gps when logged, else bit 2 (CS_GPS)
of estimator_status.control_mode_flags, else the fix alone (recorded in the
`fused_source` column so the weaker definition is never silent). The flight
label (benign / jamming / spoofing / ...) is taken from the directory path.

No data, no output: if no flight is found the script prints SKIPPED and
writes nothing (ground rule: never fabricate a trace).
Outputs: results/r3_staleness_traces.csv (flight, label, t_s, staleness_s,
fix_type, sats, fused_source, provenance=measured) and
results/r3_trace_summary.csv (one row per flight).
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from certcmdp.certificate import OUT  # noqa: E402
import os  # noqa: E402

REPO = HERE.parents[1]
DEFAULT_ROOT = Path(os.environ.get("R3_ROOT") or REPO / "data" / "raw" / "uav_attack_whelan")
DT = 0.5
GPS_TOPICS = ("vehicle_gps_position", "sensor_gps")
FLAG_TOPICS = ("estimator_status_flags", "estimator_status", "vehicle_land_detected")
LABELS = ("benign", "jamming", "jam", "spoof", "gps_spoof", "attack")


def _read_csv(path: Path) -> dict[str, np.ndarray]:
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    if not rows:
        return out
    for k in rows[0]:
        try:
            out[k] = np.array([float(r[k]) for r in rows])
        except (TypeError, ValueError):
            continue
    return out


GPS_SUFFIXES = tuple(f"_{t}_0.csv" for t in GPS_TOPICS)


def find_flights(root: Path) -> list[tuple[str, Path, str, str]]:
    """Every flight under root, whatever the staging layout: one .ulg file, or one
    ulog2csv log prefix ("<log>_vehicle_gps_position_0.csv" plus sibling topics)
    when no .ulg of the same name exists (a .ulg and its CSV export are one
    flight). fetch_kaggle.py stages files flat as symlinks into the kagglehub
    cache, so the label is read from the symlink's TARGET path, which keeps the
    dataset's own folder names (benign / jamming / spoofing ...)."""
    out = []
    ulg_stems = set()
    for p in sorted(root.rglob("*.ulg")):
        ulg_stems.add((p.parent, p.stem))
        out.append((str(p.relative_to(root)), p, "ulg", str(p.resolve())))
    seen = set()
    for suf in GPS_SUFFIXES:
        for p in sorted(root.rglob(f"*{suf}")):
            prefix = p.name[: -len(suf)]
            key = (p.parent, prefix)
            if key in seen or key in ulg_stems:
                continue
            seen.add(key)
            out.append((str((p.parent / prefix).relative_to(root)), p.parent / prefix, "csv", str(p.resolve())))
    return out


def load_flight(path: Path, kind: str) -> dict[str, dict[str, np.ndarray]]:
    topics: dict[str, dict[str, np.ndarray]] = {}
    if kind == "ulg":
        from pyulog import ULog
        u = ULog(str(path), list(GPS_TOPICS + FLAG_TOPICS))
        for x in u.data_list:
            if x.multi_id == 0:
                topics[x.name] = {k: np.asarray(v, float) for k, v in x.data.items()}
        return topics
    for name in GPS_TOPICS + FLAG_TOPICS:
        f = path.parent / f"{path.name}_{name}_0.csv"
        if f.exists():
            topics[name] = _read_csv(f)
    return topics


FOLDER_LABELS = (("benign", "benign"), ("normal", "benign"), ("jamming", "jamming"),
                 ("spoof", "spoofing"), ("dos", "dos"))


def label_of(name: str, origin: str = "") -> str:
    """Label from the flight's own folder in the dataset (e.g. ".../GPS Jamming/x.ulg"),
    falling back to the file name. Matching the whole path is wrong here: every path
    contains "UAVAttackData", and "Live GPS Spoofing and Jamming" holds all three
    live flights."""
    for text in (Path(origin).parent.name if origin else "", Path(name).name):
        t = text.lower()
        for key, lab in FOLDER_LABELS:
            if key in t:
                return lab
    return "unlabelled"


def airborne_window(topics):
    """[first take-off, last landing] from vehicle_land_detected, or None."""
    ld = topics.get("vehicle_land_detected")
    if not ld or "landed" not in ld or "timestamp" not in ld:
        return None
    t = ld["timestamp"] * 1e-6
    air = ld["landed"] < 0.5
    if not air.any():
        return None
    i0 = int(np.argmax(air))
    i1 = len(air) - 1 - int(np.argmax(air[::-1]))
    t1 = t[i1 + 1] if i1 + 1 < len(t) else t[-1]
    return float(t[i0]), float(t1)


def staleness_trace(topics):
    gps = next((topics[t] for t in GPS_TOPICS if t in topics), None)
    if gps is None or "timestamp" not in gps or "fix_type" not in gps:
        return None
    tg = gps["timestamp"] * 1e-6
    good = gps["fix_type"] >= 3
    src = "fix_only"
    if "estimator_status_flags" in topics and "cs_gps" in topics["estimator_status_flags"]:
        f = topics["estimator_status_flags"]
        fused = np.interp(tg, f["timestamp"] * 1e-6, f["cs_gps"]) > 0.5
        good, src = good & fused, "cs_gps"
    elif "estimator_status" in topics and "control_mode_flags" in topics["estimator_status"]:
        f = topics["estimator_status"]
        bit = (f["control_mode_flags"].astype(np.int64) >> 2) & 1
        fused = np.interp(tg, f["timestamp"] * 1e-6, bit) > 0.5
        good, src = good & fused, "control_mode_flags_bit2"
    win = airborne_window(topics)
    lo, hi = (max(tg[0], win[0]), min(tg[-1], win[1])) if win else (tg[0], tg[-1])
    if hi - lo < 10 * DT:                         # no usable airborne window: whole log
        lo, hi, win = tg[0], tg[-1], None
    t = np.arange(lo, hi, DT)
    tgood = tg[good]
    if tgood.size == 0:
        stale = t - tg[0]
    else:
        idx = np.searchsorted(tgood, t, side="right") - 1
        last = np.where(idx >= 0, tgood[np.maximum(idx, 0)], tg[0])
        stale = t - last
    j = np.clip(np.searchsorted(tg, t, side="right") - 1, 0, tg.size - 1)
    sats = gps.get("satellites_used", np.full(tg.size, np.nan))
    return t - t[0], stale, gps["fix_type"][j], sats[j], src + ("|airborne" if win else "|whole_log")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    a = ap.parse_args()
    flights = find_flights(a.root) if a.root.exists() else []
    print(f"{len(flights)} flights found under {a.root}")
    if not flights:
        print(f"SKIPPED: no flights under {a.root}. Stage with data/fetch_kaggle.py --copy.")
        return 0
    rows, summ = [], []
    for name, path, kind, origin in flights:
        tr = staleness_trace(load_flight(path, kind))
        if tr is None:
            print(f"  {name}: no GNSS topic, skipped")
            continue
        t, st, fx, sats, src = tr
        lab = label_of(name, origin)
        for i in range(t.size):
            rows.append({"flight": name, "label": lab, "t_s": round(float(t[i]), 3),
                         "staleness_s": round(float(st[i]), 4), "fix_type": int(fx[i]),
                         "sats": ("" if np.isnan(sats[i]) else int(sats[i])),
                         "fused_source": src, "provenance": "measured"})
        ep = np.diff(np.r_[0, (st > 1.0).astype(int)]) == 1
        summ.append({"flight": name, "label": lab, "source_path": origin.split("/datasets/")[-1], "duration_s": float(t[-1]), "epochs": int(t.size),
                     "staleness_p50_s": float(np.median(st)), "staleness_p99_s": float(np.percentile(st, 99)),
                     "staleness_max_s": float(st.max()), "frac_epochs_stale_gt1s": float(np.mean(st > 1.0)),
                     "n_episodes_gt1s": int(ep.sum()), "min_fix_type": int(fx.min()),
                     "fused_source": src, "provenance": "measured"})
        print(summ[-1])
    if not rows:
        print("SKIPPED: flights found but none had a GNSS topic. Nothing written.")
        return 0
    for name, rr in (("r3_staleness_traces.csv", rows), ("r3_trace_summary.csv", summ)):
        with (OUT / name).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rr[0])); w.writeheader(); w.writerows(rr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
