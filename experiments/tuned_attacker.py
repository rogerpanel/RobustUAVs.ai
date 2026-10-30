#!/usr/bin/env python3
"""Threshold-aware (tuned) attacker against the DATAMUt forwarding detector.

The campaign attacker of sweep_full.py draws its extra per-hop delay from
U[1,7] s or U[1,10] s whatever the threshold, so at theta = 0.25 s every
malicious hop is flagged and the measured undetected delay is zero. This
script gives the attacker the threshold and measures what it can hide.

Variants (extra delay added by a malicious forwarder, on top of the benign
forwarding jitter U[0.05, 0.18] s that every hop carries in the harness):
  tuned   extra = min(theta, s) - B_MAX - GUARD
          The attacker knows theta, the contact-window slack s and the benign
          jitter ceiling B_MAX, so its residual stays below theta. It caps at s
          because a delay past the slack misses the forwarding window
          (Lemma 1).
  naive   extra = 0.99 * theta
          The attacker knows theta but ignores the benign jitter (and, above
          the slack, the window). It shows what a careless tuning costs.

Per (scenario, theta, seed, policy) run, from the hop ledger:
  H            malicious hops observed
  undetected_s sum of residuals of unflagged malicious hops
  bound_s      H * min(theta, s), the Lemma 1 budget for those hops
Lemma 1 holds iff undetected_s <= bound_s in every run; the ratio measures
how much of the budget a threshold-aware attacker actually realises.

Outputs:
  results/tuned_attacker_perseed.csv
  results/tuned_attacker_summary.csv

Provenance: simulation-derived (patched third-party DATAMUt replay,
deterministic per seed). Usage: python3 experiments/tuned_attacker.py
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sweep_full import BINARY, EPS_DEFAULT, RESULTS, run_point  # noqa: E402

SLACK_S = 5.0
B_MAX = 0.18          # benign forwarding-jitter ceiling of the harness
GUARD = 0.005
SEEDS = 8


def extra_delay(variant: str, theta: float) -> float:
    if variant == "tuned":
        return max(min(theta, SLACK_S) - B_MAX - GUARD, 1e-6)
    return 0.99 * theta


def main() -> int:
    if not BINARY.exists():
        print("build the DATAMUt demo first (see README)")
        return 1
    perseed = []
    for variant in ("tuned", "naive"):
        for scen in ("1", "2", "3"):
            for theta in (float(x) for x in EPS_DEFAULT.split(",")):
                d = extra_delay(variant, theta)
                ps, hops, missed = run_point(scen, variant, theta, d, d, SEEDS)
                acc = defaultdict(lambda: {"H": 0, "flag": 0, "und": 0.0,
                                           "und_max_hop": 0.0, "tot": 0.0})
                for h in hops:
                    if h["malicious_sender"] != 1:
                        continue
                    a = acc[(h["seed"], h["policy"])]
                    r = float(h["residual_s"])
                    a["H"] += 1
                    a["tot"] += r
                    if h["suspicious"]:
                        a["flag"] += 1
                    else:
                        a["und"] += r
                        a["und_max_hop"] = max(a["und_max_hop"], r)
                rec = {(r["seed"], r["policy"]): r for r in ps}
                n_missed = defaultdict(int)
                for m in missed:
                    if m["malicious_sender"] == 1:
                        n_missed[(m["seed"], m["policy"])] += 1
                # runs whose malicious hops never forwarded (every delay missed its
                # window) leave no ledger rows; keep them with H = 0
                for r in ps:
                    acc[(r["seed"], r["policy"])]
                for key, a in sorted(acc.items()):
                    bound = a["H"] * min(theta, SLACK_S)
                    perseed.append({
                        "variant": variant, "scenario": scen, "theta_s": theta,
                        "seed": key[0], "policy": key[1],
                        "extra_delay_s": round(d, 4),
                        "H_malicious_hops": a["H"],
                        "flagged_malicious_hops": a["flag"],
                        "missed_windows_malicious": n_missed[key],
                        "undetected_s": round(a["und"], 4),
                        "max_undetected_hop_s": round(a["und_max_hop"], 4),
                        "total_residual_s": round(a["tot"], 4),
                        "bound_s": round(bound, 4),
                        "realised_fraction": round(a["und"] / bound, 4) if bound else "",
                        "within_bound": int(a["und"] <= bound + 1e-9),
                        "recall": rec.get(key, {}).get("recall", ""),
                        "provenance": "simulation-derived (DATAMUt replay)"})
                sub = [r for r in perseed if r["variant"] == variant
                       and r["scenario"] == scen and r["theta_s"] == theta]
                und = sorted(r["undetected_s"] for r in sub)
                if not und:
                    continue
                print(f"{variant:>5} scen={scen} theta={theta:>5}: extra={d:.3f} "
                      f"undetected median={und[len(und)//2]:.3f} max={und[-1]:.3f} "
                      f"bound={max(r['bound_s'] for r in sub):.3f} H={sum(r['H_malicious_hops'] for r in sub)} "
                      f"missed={sum(r['missed_windows_malicious'] for r in sub)} runs={len(sub)}")

    summary = []
    groups = defaultdict(list)
    for r in perseed:
        groups[(r["variant"], r["theta_s"])].append(r)
    for (variant, theta), rows in sorted(groups.items()):
        und = sorted(r["undetected_s"] for r in rows)
        fr = sorted(r["realised_fraction"] for r in rows if r["realised_fraction"] != "")
        H = sum(r["H_malicious_hops"] for r in rows)
        flagged = sum(r["flagged_malicious_hops"] for r in rows)
        summary.append({
            "variant": variant, "theta_s": theta, "runs": len(rows),
            "extra_delay_s": rows[0]["extra_delay_s"],
            "malicious_hops": H, "evasion_rate": round(1 - flagged / H, 4) if H else "",
            "undetected_median_s": und[len(und) // 2], "undetected_max_s": und[-1],
            "bound_per_run_max_s": max(r["bound_s"] for r in rows),
            "realised_fraction_median": fr[len(fr) // 2] if fr else "",
            "realised_fraction_max": fr[-1] if fr else "",
            "max_undetected_hop_s": max(r["max_undetected_hop_s"] for r in rows),
            "missed_windows_malicious": sum(r["missed_windows_malicious"] for r in rows),
            "all_within_bound": int(all(r["within_bound"] for r in rows))})

    for name, rows in (("tuned_attacker_perseed.csv", perseed),
                       ("tuned_attacker_summary.csv", summary)):
        with open(RESULTS / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"[tuned] {len(rows)} rows -> results/{name}")
    ok = all(r["all_within_bound"] for r in summary)
    print("Lemma 1 bound holds in every run" if ok else "BOUND VIOLATED in some run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
