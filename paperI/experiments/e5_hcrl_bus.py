#!/usr/bin/env python3
"""E5 (HCRL part) -- bus validation from the raw HCRL UAVCAN capture.

Runbook section E5. Replaces three modelling inputs of transport.py with
measurements from a real DroneCAN bus (Pixhawk 4 testbed, Kim et al.):

  1. benign frame rate, DLC histogram, and the fraction of multi-frame
     transfers (from the DroneCAN tail byte: bit7 SOT, bit6 EOT);
  2. a LOWER BOUND on the bus bitrate from the minimum spacing between
     consecutive frames (a frame cannot start before the previous one ends);
  3. the base load U0 recomputed from the measured DLC mix instead of the
     8-byte worst case.

Input format (same as ingest/ingest_hcrl.py): candump-style text lines
    Label (timestamp)  can0  CANID  [dlc]  BB BB ...
in files data/raw/hcrl_uavcan/*_label.bin (one per scenario type1..type10).

Output: paperI/results/e5_hcrl_bus.csv, one row per scenario plus 'pooled',
every row tagged provenance=measured.

No data, no output: if no label file is found the script prints SKIPPED and
writes nothing, so a missing capture can never leave a fabricated or stale
result behind. run_all.sh treats that as a skip, not a failure.

Usage:
    python3 e5_hcrl_bus.py [--raw DIR] [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from transport import can_ext_frame_bits  # noqa: E402  (frame model under test)

LINE_RE = re.compile(
    r"^(?P<label>\w+)\s+\((?P<ts>[\d.]+)\)\s+(?P<iface>\S+)\s+"
    r"(?P<canid>[0-9A-Fa-f]+)\s+\[(?P<dlc>\d+)\]\s*(?P<data>[0-9A-Fa-f ]*)$")

STANDARD_RATES = (125e3, 250e3, 500e3, 1e6)   # classic CAN, bit/s
# Ignore spacings below this percentile when bounding the bitrate: candump
# timestamps are taken in software, so a few pairs can be compressed by
# kernel batching. The minimum itself is reported alongside, unfiltered.
SPACING_PCTL = 0.001


def parse(path: Path):
    """Yield (is_normal, t, dlc, data_bytes) for every well-formed line."""
    with path.open(errors="ignore") as fh:
        for line in fh:
            m = LINE_RE.match(line.strip())
            if not m:
                continue
            d = m.groupdict()
            data = bytes.fromhex(d["data"].replace(" ", "")) if d["data"].strip() else b""
            yield d["label"] == "Normal", float(d["ts"]), int(d["dlc"]), data


def quantile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    if not s:
        return math.nan
    i = min(len(s) - 1, max(0, int(math.floor(q * (len(s) - 1)))))
    return s[i]


def analyse(path: Path) -> dict:
    frames = list(parse(path))
    if not frames:
        raise ValueError(f"{path.name}: no parseable frames")
    frames.sort(key=lambda r: r[1])

    normal = [f for f in frames if f[0]]
    dlc_hist = Counter(f[2] for f in normal)

    # benign frame rate over the span the Normal frames occupy
    span = normal[-1][1] - normal[0][1] if len(normal) > 1 else 0.0
    rate = len(normal) / span if span > 0 else math.nan

    # DroneCAN tail byte = last data byte. A transfer begins at SOT; it is
    # single-frame when that same frame also carries EOT.
    starts = single = 0
    for _, _, dlc, data in normal:
        if dlc == 0 or not data:
            continue
        tail = data[-1]
        sot, eot = bool(tail & 0x80), bool(tail & 0x40)
        if sot:
            starts += 1
            single += eot
    multiframe_frac = (starts - single) / starts if starts else math.nan

    # bitrate lower bound: gap after an 8-byte frame can be no shorter than
    # that frame's own on-wire length (no stuffing = the most permissive).
    bits8 = can_ext_frame_bits(8, worst_stuff=False)
    gaps = [b[1] - a[1] for a, b in zip(frames, frames[1:])
            if a[2] == 8 and b[1] > a[1]]
    gmin = min(gaps) if gaps else math.nan
    gq = quantile(gaps, SPACING_PCTL)
    lb = bits8 / gq if gaps else math.nan

    # base load from the measured DLC mix (per-frame bits at each DLC)
    tot = sum(dlc_hist.values())
    mean_bits_worst = sum(n * can_ext_frame_bits(d, True) for d, n in dlc_hist.items()) / tot
    mean_bits_nom = sum(n * can_ext_frame_bits(d, False) for d, n in dlc_hist.items()) / tot
    mean_dlc = sum(d * n for d, n in dlc_hist.items()) / tot

    return dict(
        scenario=path.name.split("_")[0],
        n_frames=len(frames), n_benign=len(normal),
        rate_fps=rate, mean_dlc=mean_dlc,
        dlc_hist=";".join(f"{d}:{dlc_hist[d]}" for d in sorted(dlc_hist)),
        multiframe_frac=multiframe_frac, n_transfers=starts,
        n_gaps_after_8B=len(gaps), min_gap_us=gmin * 1e6, gap_p001_us=gq * 1e6,
        bitrate_lower_bound=lb,
        mean_frame_bits_worst=mean_bits_worst, mean_frame_bits_nominal=mean_bits_nom,
    )


def bitrate_verdict(lb: float) -> tuple[float | None, str]:
    """Return (bitrate, verdict). A measured bitrate is returned only when the
    lower bound excludes every standard rate except one."""
    if not math.isfinite(lb):
        return None, "no 8-byte frame pairs"
    consistent = [r for r in STANDARD_RATES if r >= lb * 0.98]  # 2 % timestamp slack
    if len(consistent) == 1:
        return consistent[0], f"measured: lower bound {lb/1e3:.0f} kbit/s leaves only {consistent[0]/1e3:.0f} kbit/s"
    if not consistent:
        return None, f"lower bound {lb/1e3:.0f} kbit/s exceeds 1 Mbit/s: timestamps unreliable"
    return None, (f"inconclusive: lower bound {lb/1e3:.0f} kbit/s is consistent with "
                  + ", ".join(f"{r/1e3:.0f}" for r in consistent) + " kbit/s")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=REPO / "data" / "raw" / "hcrl_uavcan")
    ap.add_argument("--out", type=Path, default=REPO / "paperI" / "results")
    a = ap.parse_args()

    files = sorted(a.raw.glob("*_label.bin")) if a.raw.exists() else []
    if not files:
        print(f"[E5] SKIPPED: no *_label.bin under {a.raw}. "
              "Stage data with data/fetch_kaggle.py first. Nothing written.")
        return 0

    rows = []
    for f in files:
        r = analyse(f)
        rows.append(r)
        print(f"[E5] {r['scenario']}: {r['n_benign']} benign frames, "
              f"{r['rate_fps']:.1f} fps, mean DLC {r['mean_dlc']:.2f}, "
              f"multi-frame {r['multiframe_frac']:.3f}, bitrate >= {r['bitrate_lower_bound']/1e3:.0f} kbit/s")

    # pooled row: the tightest bitrate bound over all scenarios, and the DLC mix
    # weighted by benign frame counts
    lb = max(r["bitrate_lower_bound"] for r in rows if math.isfinite(r["bitrate_lower_bound"]))
    nb = sum(r["n_benign"] for r in rows)
    pooled = dict(
        scenario="pooled", n_frames=sum(r["n_frames"] for r in rows), n_benign=nb,
        rate_fps=math.nan,
        mean_dlc=sum(r["mean_dlc"] * r["n_benign"] for r in rows) / nb,
        dlc_hist="", multiframe_frac=(
            sum(r["multiframe_frac"] * r["n_transfers"] for r in rows if math.isfinite(r["multiframe_frac"]))
            / max(1, sum(r["n_transfers"] for r in rows))),
        n_transfers=sum(r["n_transfers"] for r in rows),
        n_gaps_after_8B=sum(r["n_gaps_after_8B"] for r in rows),
        min_gap_us=min(r["min_gap_us"] for r in rows),
        gap_p001_us=min(r["gap_p001_us"] for r in rows),
        bitrate_lower_bound=lb,
        mean_frame_bits_worst=sum(r["mean_frame_bits_worst"] * r["n_benign"] for r in rows) / nb,
        mean_frame_bits_nominal=sum(r["mean_frame_bits_nominal"] * r["n_benign"] for r in rows) / nb,
    )
    rows.append(pooled)

    br, verdict = bitrate_verdict(lb)
    print(f"[E5] bitrate: {verdict}")
    for r in rows:
        r["bitrate_measured"] = br if br is not None else ""
        r["bitrate_verdict"] = verdict
        r["provenance"] = "measured"

    a.out.mkdir(parents=True, exist_ok=True)
    out = a.out / "e5_hcrl_bus.csv"
    cols = list(rows[0].keys())
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 6) if isinstance(v, float) and math.isfinite(v) else v)
                        for k, v in r.items()})
    print(f"[E5] wrote {out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
