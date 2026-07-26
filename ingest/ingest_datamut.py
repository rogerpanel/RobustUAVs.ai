#!/usr/bin/env python3
"""Ingest DATAMUt paper-exact demo output into the unified two-layer schema.

Parses the stdout log of `datamut_paper_exact_demo` (hop-level lines with
expected/observed send times and residual delays) plus the metrics CSVs, and
emits:
  events.jsonl        - one Event per hop (layer=network, sublayer=mesh)
  windows.jsonl       - one AttackWindow per (seed, scenario) covering the
                        malicious activity, with ground-truth attacker nodes
Usage:
  python3 ingest_datamut.py <run_log> <scenario_tag> <outdir> \
      [--theta 0.25] [--malicious n6,n10] [--delay-min 1.0] [--delay-max 7.0]
"""
import argparse, json, re, sys
from pathlib import Path

HOP_RE = re.compile(
    r"^\s*hop (?P<idx>\d+): (?P<frm>\S+) -> (?P<to>\S+) \| "
    r"intended_send=(?P<exp>[-\d.]+) local_next=(?P<local>\S+) "
    r"observed=(?P<obs>[-\d.]+) residual=(?P<res>[-\d.]+) "
    r"epsilon=(?P<eps>[-\d.]+) pathMatch=(?P<pm>\w+) suspicious=(?P<susp>\w+)")
PKT_RE = re.compile(r"^\[(?P<policy>\w+)\] packet (?P<pkt>\d+)")
SEED_RE = re.compile(r"^--- running seed (?P<seed>\d+) ---")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_log"); ap.add_argument("scenario_tag"); ap.add_argument("outdir")
    ap.add_argument("--theta", type=float, default=0.25)
    ap.add_argument("--malicious", default="")
    ap.add_argument("--delay-min", type=float, default=1.0)
    ap.add_argument("--delay-max", type=float, default=7.0)
    a = ap.parse_args()

    malicious = set(x for x in a.malicious.split(",") if x)
    outdir = Path(a.outdir); outdir.mkdir(parents=True, exist_ok=True)
    events, windows = [], []
    seed, policy, pkt = None, None, None
    # per (seed) accumulate window bounds + which events fall inside
    win_acc = {}

    for line in Path(a.run_log).read_text().splitlines():
        m = SEED_RE.match(line)
        if m: seed = m.group("seed"); continue
        m = PKT_RE.match(line)
        if m: policy, pkt = m.group("policy"), m.group("pkt"); continue
        m = HOP_RE.match(line)
        if not m: continue
        d = m.groupdict()
        eid = f"datamut_sim:{a.scenario_tag}:s{seed}:{policy}:p{pkt}:h{d['idx']}"
        frm = d["frm"]
        ev = {
            "event_id": eid,
            "source_dataset": "datamut_sim",
            "event_kind": "hop",
            "layer": "network",
            "sublayer": "mesh",
            "scenario_id": a.scenario_tag,
            "run_id": f"seed{seed}",
            "t_start": float(d["exp"]),
            "t_end": float(d["obs"]),
            "src_node": frm,
            "dst_node": d["to"],
            "protocol": f"dtn_twig/{policy.lower()}",
            "label_class": "time_delay" if frm in malicious else "benign",
            "label_native": "malicious_forwarder" if frm in malicious else "benign",
            "attacker_node": frm if frm in malicious else None,
            "metrics": {
                "residual_delay_s": float(d["res"]),
                "expected_send_s": float(d["exp"]),
                "observed_send_s": float(d["obs"]),
            },
            "detector": {
                "name": "datamut_paper_exact",
                "operating_point": float(d["eps"]),
                "suspicious": d["susp"] == "yes",
                "path_match": d["pm"] == "yes",
            },
            "native": {"policy": policy, "packet_id": int(pkt), "hop_index": int(d["idx"]),
                       "local_next_hop": d["local"]},
        }
        events.append(ev)
        key = (seed,)
        w = win_acc.setdefault(key, {"t0": float(d["exp"]), "t1": float(d["obs"]), "ids": []})
        w["t0"] = min(w["t0"], float(d["exp"])); w["t1"] = max(w["t1"], float(d["obs"]))
        if frm in malicious: w["ids"].append(eid)

    for (s,), w in sorted(win_acc.items()):
        windows.append({
            "window_id": f"datamut_sim:{a.scenario_tag}:s{s}:tda",
            "source_dataset": "datamut_sim",
            "scenario_id": a.scenario_tag, "run_id": f"seed{s}",
            "layer": "network", "sublayer": "mesh",
            "attack_class": "time_delay",
            "t_start": w["t0"], "t_end": w["t1"],
            "attacker_node": ";".join(sorted(malicious)) or None,
            "intensity": {"delay_min_s": a.delay_min, "delay_max_s": a.delay_max},
            "event_ids": w["ids"],
        })

    (outdir / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    (outdir / "windows.jsonl").write_text("\n".join(json.dumps(w) for w in windows) + "\n")
    n_mal = sum(1 for e in events if e["label_class"] == "time_delay")
    n_susp = sum(1 for e in events if e["detector"]["suspicious"])
    print(f"[datamut] {len(events)} hop events ({n_mal} malicious-origin, {n_susp} flagged "
          f"at theta={a.theta}s), {len(windows)} attack windows -> {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
