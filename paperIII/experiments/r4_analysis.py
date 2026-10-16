#!/usr/bin/env python3
"""R4 analysis: what the PX4 SITL run says about the certificate premise (Assumption 1(a)).

Reads only committed R4 results (the run of 2026-10-16, provenance=sitl):
  r4_sitl.csv, r4_sitl_summary.csv, r4_injections.csv   driver epoch log and summaries
  r4_soundness.csv, r4_soundness_violations.csv          ground-truth soundness oracle
  r4_px4_events.csv                                      PX4 arming / navigation / failsafe changes
and writes results/r4_analysis.csv (metric, value). Nothing is re-estimated or filtered.

Reacquisition transient: violations within 10 s after a GNSS reacquisition, grouped into
episodes (one per log and reacquisition). For each episode: peak error, peak excess over rho,
the span from the first to the last violating sample, and the time until the error first fell
back below rho. The pre-reacquisition envelope is rho at the largest staleness the driver saw
for that vehicle in that run, KAPPA * (THETA_BENIGN + max staleness); the in-sample latch check
counts how many violating samples lie below it. It is a consistency check on the run that
revealed the transient, not a validation of a latched certificate.

Usage:  python3 r4_analysis.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from certcmdp.certificate import OUT, KAPPA, THETA_BENIGN  # noqa: E402

REACQ_WINDOW = 10.0       # s, as in r4_sitl_fleet.soundness
RUN_GAP = 60.0            # s between violation episodes of one log that belong to different runs


def rd(name):
    p = OUT / name
    return list(csv.DictReader(p.open())) if p.exists() else []


def main() -> int:
    ep = rd("r4_sitl.csv")
    sm = rd("r4_sitl_summary.csv")
    inj = rd("r4_injections.csv")
    snd = rd("r4_soundness.csv")
    vio = [r for r in rd("r4_soundness_violations.csv") if r.get("log")]
    evs = rd("r4_px4_events.csv")
    if not (ep and snd):
        print("R4 results missing"); return 1
    M = {}
    M["vehicles"] = len({r["vehicle"] for r in ep})
    M["rates_hz"] = ";".join(sorted({r["rate_hz"] for r in ep}, key=float, reverse=True))
    M["run_s"] = round(max(float(r["t_s"]) for r in ep))
    for r in sm:
        k = "5" if float(r["rate_hz"]) == 5 else "2"
        for f in ("agent_epochs", "held_epochs", "executed_violations", "exposure_total"):
            M[f"{f}_{k}hz"] = r[f]
        M[f"coverage_{k}hz"] = round(float(r["certified_coverage"]), 4)
    M["injections_gnss_loss"] = sum(r["kind"] == "off" and r["phase"] == "on" for r in inj)
    M["injections_spoof_rejected"] = sum(r["kind"] == "wrong" and r["phase"] == "on"
                                         and r["result"].startswith("unsupported") for r in inj)
    M["injections_spoof"] = sum(r["kind"] == "wrong" and r["phase"] == "on" for r in inj)
    # staleness actually reached during the outages (driver view)
    maxst = {}
    for r in ep:
        key = (r["rate_hz"], r["vehicle"])
        maxst[key] = max(maxst.get(key, 0.0), float(r["staleness_s"]))
    lost = {k: v for k, v in maxst.items() if v > 1.0}
    M["outage_staleness_max_s"] = round(max(lost.values()), 2)
    M["outage_staleness_min_s"] = round(min(lost.values()), 2)
    M["negative_staleness_epochs"] = sum(float(r["staleness_s"]) < 0 for r in ep)
    M["negative_staleness_max_s"] = round(-min(float(r["staleness_s"]) for r in ep), 2)
    # soundness oracle
    checked = [r for r in snd if r["status"] == "checked"]
    M["logs_checked"] = len(checked)
    M["samples_checked"] = sum(int(r["samples"]) for r in checked)
    M["violations_total"] = sum(int(r["violations"]) for r in checked)
    M["reacquisitions"] = sum(int(r["reacquisitions"]) for r in checked)
    trans = [r for r in vio if r["since_reacq_s"] != "" and float(r["since_reacq_s"]) <= REACQ_WINDOW]
    floor = [r for r in vio if r not in trans]
    M["violations_transient"] = len(trans)
    M["violations_floor"] = len(floor)
    # episodes: per log, split where consecutive violations are more than RUN_GAP apart
    episodes = []
    for log in sorted({r["log"] for r in trans}):
        rr = sorted((r for r in trans if r["log"] == log), key=lambda r: float(r["t_s"]))
        cur = [rr[0]]
        for r in rr[1:]:
            if float(r["t_s"]) - float(cur[-1]["t_s"]) > RUN_GAP:
                episodes.append(cur); cur = []
            cur.append(r)
        episodes.append(cur)
    M["transient_episodes"] = len(episodes)
    M["transient_vehicles"] = len({e[0]["log"].split("/")[0] for e in episodes})
    for k, e in enumerate(episodes, 1):
        ts = [float(r["t_s"]) for r in e]
        M[f"ep{k}_log"] = e[0]["log"].split("/")[0]
        M[f"ep{k}_samples"] = len(e)
        M[f"ep{k}_peak_err_m"] = max(float(r["err_m"]) for r in e)
        M[f"ep{k}_peak_excess_m"] = max(float(r["excess_m"]) for r in e)
        M[f"ep{k}_rho_at_peak_m"] = next(float(r["rho_m"]) for r in e
                                         if float(r["err_m"]) == M[f"ep{k}_peak_err_m"])
        M[f"ep{k}_span_s"] = round(max(ts) - min(ts), 3)
        # first contiguous block (8 ms sample period): time until the error first falls below rho
        blk = [ts[0]]
        for t in ts[1:]:
            if t - blk[-1] > 0.0125:
                break
            blk.append(t)
        M[f"ep{k}_first_block_s"] = round(blk[-1] - blk[0] + 0.008, 3)
    # pre-reacquisition envelope from the driver's staleness for the transient vehicle, per run
    envs = []
    for e in episodes:
        veh = e[0]["log"].split("/")[0]
        cand = [v for (rate, vv), v in maxst.items() if vv == veh and v > 1.0]
        envs.append(min(cand) if cand else None)
    if all(x is not None for x in envs):
        env_min = KAPPA * (THETA_BENIGN + min(envs))
        M["envelope_min_m"] = round(env_min, 1)
        M["latch_covered"] = sum(float(r["err_m"]) <= env_min for e in episodes for r in e)
        M["latch_total"] = sum(len(e) for e in episodes)
    M["transient_peak_err_m"] = max(M[f"ep{k}_peak_err_m"] for k in range(1, len(episodes) + 1))
    M["transient_peak_excess_m"] = max(M[f"ep{k}_peak_excess_m"] for k in range(1, len(episodes) + 1))
    M["floor_m"] = round(KAPPA * THETA_BENIGN, 3)
    M["floor_peak_excess_m"] = max((float(r["excess_m"]) for r in floor), default=0.0)
    M["floor_vehicles"] = len({r["log"].split("/")[0] for r in floor})
    # vehicles grounded by a PX4 failsafe (disarmed before the end of the session)
    end = {r["log"]: float(r["duration_s"]) for r in checked}
    disarm = [r for r in evs if r["kind"] == "arming_state" and r["value"] == "1" and float(r["t_s"]) > 0]
    grounded = [r for r in disarm if float(r["t_s"]) < 0.5 * end.get(r["log"], 1e9) or
                end.get(r["log"], 0) < 0.5 * max(end.values())]
    M["grounded_vehicles"] = len({r["log"] for r in grounded})
    fs = [r for r in evs if r["kind"] == "failsafe" and r["value"] == "1"]
    M["failsafe_entries"] = len(fs)
    if grounded:
        veh = grounded[0]["log"].split("/")[0]
        M["grounded_vehicle"] = veh
        M["grounded_held_epochs"] = sum(int(r["held"]) for r in ep if r["vehicle"] == veh
                                        and float(r["t_s"]) > 120 if r["rate_hz"] == "5.0") + \
            sum(int(r["held"]) for r in ep if r["vehicle"] == veh and r["rate_hz"] == "2.0")
        M["grounded_on_site"] = sum(int(r["on_site"]) for r in ep if r["vehicle"] == veh
                                    and (r["rate_hz"] == "2.0" or float(r["t_s"]) > 120))
    with (OUT / "r4_analysis.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["metric", "value"])
        for k, v in M.items():
            w.writerow([k, v])
    for k, v in M.items():
        print(f"{k:<28} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
