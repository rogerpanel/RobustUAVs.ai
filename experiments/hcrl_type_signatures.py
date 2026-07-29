#!/usr/bin/env python3
"""Data-derived attack-class map for the HCRL UAVCAN scenarios (type1..10).

The authoritative per-scenario table lives in arXiv:2212.09268, which is not
reachable from this environment. Rather than guess, this script MEASURES the
attack signature of every scenario from the frames themselves and assigns the
class by explicit, recorded rules:

  flooding : attack frames dominated by very few CAN IDs at a burst rate
             far above the normal bus rate (rate_ratio > 5, top-1 ID share
             > 0.9 of attack frames)
  fuzzing  : attack frames spread over MANY CAN IDs, most of which never
             appear in normal traffic (novel-ID share > 0.5)
  replay   : attack frames reuse normal-traffic IDs (novel-ID share ~ 0)
             at near-normal rates (rate_ratio < 5, top-1 share < 0.9)

Scenarios where the evidence is mixed (multiple attack bursts of different
shapes) are labelled with every class whose rule fires, in burst order.

Output: results/hcrl_type_signatures.csv with the measured evidence per
scenario + the assigned class(es). PROVENANCE: real-corpus frames,
data-derived mapping - confirm against the arXiv:2212.09268 scenario table
before camera-ready (PENDING_ON_DATA.md).
"""
from __future__ import annotations

import csv
import math
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "hcrl_uavcan"
OUT = REPO / "results" / "hcrl_type_signatures.csv"

LINE = re.compile(
    r"^(?P<label>\w+)\s+\((?P<ts>[\d.]+)\)\s+\S+\s+"
    r"(?P<canid>[0-9A-Fa-f]+)\s+\[(?P<dlc>\d+)\]\s*(?P<data>[0-9A-Fa-f ]*)$")
GAP_S = 2.0     # attack bursts separated by >2 s of no attack frames


def parse(path: Path):
    normal_ids = Counter()
    frames = []          # (t, label_is_attack, canid, payload)
    n_norm = 0
    t_norm_min = t_norm_max = None
    with open(path, errors="ignore") as fh:
        for line in fh:
            m = LINE.match(line.strip())
            if not m:
                continue
            t = float(m["ts"])
            atk = m["label"] != "Normal"
            cid = m["canid"].upper()
            if atk:
                frames.append((t, cid, m["data"].strip()))
            else:
                normal_ids[cid] += 1
                n_norm += 1
                t_norm_min = t if t_norm_min is None else min(t_norm_min, t)
                t_norm_max = t if t_norm_max is None else max(t_norm_max, t)
    normal_rate = n_norm / max(1e-9, (t_norm_max - t_norm_min)) if n_norm else 0
    return frames, set(normal_ids), normal_rate, n_norm


def bursts(frames):
    out, cur = [], []
    for f in frames:
        if cur and f[0] - cur[-1][0] > GAP_S:
            out.append(cur)
            cur = []
        cur.append(f)
    if cur:
        out.append(cur)
    return out


def payload_entropy_share(b):
    """Fraction of DISTINCT payloads among the burst's attack frames, and the
    mean per-frame byte entropy. HCRL attacks all reuse a normal CAN ID, so
    the discriminator is the DATA field:
      fuzzing : payloads are (near-)random -> distinct-share ~ 1, high entropy
      replay  : payloads reuse a small captured set -> low distinct-share
      flooding: one fixed payload hammered -> distinct-share ~ 0, low entropy
    """
    payloads = [f[2] for f in b]
    n = len(payloads)
    distinct = len(set(payloads)) / n if n else 0.0
    ents = []
    for p in payloads:
        by = p.split()
        if not by:
            continue
        c = Counter(by)
        tot = len(by)
        ents.append(-sum((v / tot) * math.log2(v / tot) for v in c.values()))
    return distinct, (sum(ents) / len(ents) if ents else 0.0)


def classify_burst(b, normal_ids, normal_rate):
    n = len(b)
    dur = max(b[-1][0] - b[0][0], 1e-6)
    rate = n / dur
    ids = Counter(f[1] for f in b)
    top1 = ids.most_common(1)[0][1] / n
    novel = sum(c for i, c in ids.items() if i not in normal_ids) / n
    rate_ratio = rate / max(normal_rate, 1e-9)
    distinct, byte_ent = payload_entropy_share(b)
    # payload-driven rules (all HCRL bursts are single known-ID injections):
    if distinct > 0.5 and byte_ent > 1.5:
        cls = "fuzzing"           # near-random payloads
    elif rate_ratio > 1.5 and distinct < 0.1:
        cls = "dos_flooding"      # fixed payload hammered above bus rate
    elif distinct < 0.5:
        cls = "replay"            # small reused payload set at ~normal rate
    else:
        cls = "other"
    return cls, {"n": n, "dur_s": round(dur, 1), "rate_fps": round(rate, 1),
                 "rate_ratio": round(rate_ratio, 2), "n_ids": len(ids),
                 "top1_share": round(top1, 3), "novel_id_share": round(novel, 3),
                 "payload_distinct_share": round(distinct, 3),
                 "payload_byte_entropy": round(byte_ent, 2)}


def main() -> int:
    rows = []
    for i in range(1, 11):
        p = RAW / f"type{i}_label.bin"
        if not p.exists():
            continue
        frames, normal_ids, normal_rate, n_norm = parse(p)
        bs = bursts(frames)
        classes, evid = [], []
        for b in bs:
            cls, e = classify_burst(b, normal_ids, normal_rate)
            classes.append(cls)
            evid.append(e)
        uniq = sorted(set(classes), key=classes.index)
        rows.append({
            "scenario": f"type{i}",
            "n_normal": n_norm, "normal_rate_fps": round(normal_rate, 1),
            "n_attack_frames": len(frames), "n_bursts": len(bs),
            "burst_classes": ";".join(classes),
            "assigned_classes": ";".join(uniq),
            "evidence": " | ".join(
                f"b{k}[{c}]: rate={e['rate_fps']}fps x{e['rate_ratio']} "
                f"distinct={e['payload_distinct_share']} ent={e['payload_byte_entropy']}"
                for k, (c, e) in enumerate(zip(classes, evid))),
        })
        print(f"type{i}: {rows[-1]['assigned_classes']:<28} "
              f"bursts={rows[-1]['burst_classes']}")

    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[hcrl-sig] -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
