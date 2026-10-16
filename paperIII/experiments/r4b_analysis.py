#!/usr/bin/env python3
"""R4b / R4c analysis: the pre-registered outcomes of R4B_PROTOCOL.md and R4C_PROTOCOL.md.

R4b primary  latched violations within 10 s after a reacquisition = 0.
R4c primary  latched violations anywhere (the floor is now calibrated) = 0, with theta from
             r4c_calibration.csv; informative if the receiver certificate (same theta) violates
             within 10 s after a reacquisition.

Primary      violations of Assumption 1(a) under the latched certificate within 10 s after a
             reacquisition, summed over logs; the rule passes only if this is 0.
Informative  the same count under the receiver certificate on the same flights.
Secondary    floor exceedances, executed infeasible assignments, coverage, epochs in which the
             latched rho exceeded the receiver rho (the rule's cost), grounded or GNSS-less vehicles.
Episodes     violations within 10 s after a reacquisition, grouped per log and reacquisition
             (gap > 60 s between samples starts a new episode), reported per variant.
Nothing is re-estimated or filtered; the verdict is the protocol's, applied mechanically.

Usage:  python3 r4b_analysis.py [--run r4c]   -> results/<run>_analysis.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from certcmdp.certificate import OUT, KAPPA, THETA_BENIGN  # noqa: E402

WIN, GAP = 10.0, 60.0


def rd(name):
    p = OUT / name
    return list(csv.DictReader(p.open())) if p.exists() else []


def episodes(rows):
    out = []
    for log in sorted({r["log"] for r in rows}):
        rr = sorted((r for r in rows if r["log"] == log), key=lambda r: float(r["t_s"]))
        cur = [rr[0]]
        for r in rr[1:]:
            if float(r["t_s"]) - float(cur[-1]["t_s"]) > GAP:
                out.append(cur); cur = []
            cur.append(r)
        out.append(cur)
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--run", choices=("r4b", "r4c"), default="r4b")
    run = ap.parse_args().run
    snd = [r for r in rd(f"{run}_soundness.csv") if r["status"] == "checked"]
    vio = [r for r in rd(f"{run}_soundness_violations.csv") if r.get("log")]
    ep = rd(f"{run}_sitl.csv")
    sm = rd(f"{run}_sitl_summary.csv")
    if not (snd and ep):
        print(f"{run} results missing"); return 1
    M = {"run": run}
    M["primary_latched_transient"] = sum(int(r["violations_10s_after_reacq_latched"]) for r in snd)
    M["latched_all"] = sum(int(r["violations_latched"]) for r in snd)
    M["receiver_transient"] = sum(int(r["violations_10s_after_reacq"]) for r in snd)
    M["receiver_all"] = sum(int(r["violations"]) for r in snd)
    primary = M["latched_all"] if run == "r4c" else M["primary_latched_transient"]
    M["verdict"] = "pass" if primary == 0 else "fail"
    if run == "r4c":
        cal = {r["metric"]: r["value"] for r in rd("r4c_calibration.csv")}
        M["theta_sitl_s"] = cal.get("theta_sitl_s", ""); M["floor_sitl_m"] = cal.get("floor_sitl_m", "")
        M["calibration_samples"] = cal.get("benign_samples", ""); M["calibration_logs"] = cal.get("logs", "")
    M["informative"] = int(M["receiver_transient"] > 0)
    M["reacquisitions"] = sum(int(r["reacquisitions"]) for r in snd)
    M["samples_checked"] = sum(int(r["samples"]) for r in snd)
    for var in ("receiver", "latched"):
        tr = [r for r in vio if r["variant"] == var and r["since_reacq_s"] != "" and float(r["since_reacq_s"]) <= WIN]
        fl = [r for r in vio if r["variant"] == var and r not in tr]
        es = episodes(tr) if tr else []
        M[f"{var}_episodes"] = len(es)
        M[f"{var}_transient_peak_err_m"] = max((float(r["err_m"]) for r in tr), default=0.0)
        M[f"{var}_transient_peak_excess_m"] = max((float(r["excess_m"]) for r in tr), default=0.0)
        M[f"{var}_transient_since_min_s"] = min((float(r["since_reacq_s"]) for r in tr), default="")
        M[f"{var}_transient_since_max_s"] = max((float(r["since_reacq_s"]) for r in tr), default="")
        M[f"{var}_floor_violations"] = len(fl)
        M[f"{var}_floor_peak_excess_m"] = max((float(r["excess_m"]) for r in fl), default=0.0)
        for k, e in enumerate(es, 1):
            M[f"{var}_ep{k}"] = (f"log {e[0]['log'].split('/')[0]}, {len(e)} samples, peak err "
                                f"{max(float(r['err_m']) for r in e):.2f} m, peak excess "
                                f"{max(float(r['excess_m']) for r in e):.2f} m, since reacq "
                                f"{min(float(r['since_reacq_s']) for r in e):.2f}-{max(float(r['since_reacq_s']) for r in e):.2f} s")
    M["floor_m"] = float(M["floor_sitl_m"]) if run == "r4c" else round(KAPPA * THETA_BENIGN, 3)
    for r in sm:
        k = "5" if float(r["rate_hz"]) == 5 else "2"
        M[f"executed_violations_{k}hz"] = r["executed_violations"]
        M[f"coverage_{k}hz"] = round(float(r["certified_coverage"]), 4)
    M["agent_epochs"] = len(ep)
    M["latch_epochs"] = sum(r["rho_m"] != "inf" and float(r["rho_m"]) > float(r["rho_rx_m"]) + 1e-9 for r in ep)
    M["disarmed_epochs"] = sum(r["armed"] == "0" for r in ep)
    # vehicles that never held a fix after takeoff (staleness only grows over a whole run)
    nofix = []
    for v in sorted({r["vehicle"] for r in ep}):
        for rate in sorted({r["rate_hz"] for r in ep}):
            st = [float(r["staleness_s"]) for r in ep if r["vehicle"] == v and r["rate_hz"] == rate]
            if st and min(st) > 1.0:
                nofix.append(v)
    M["vehicles_without_fix"] = ";".join(sorted(set(nofix)))
    M["vehicles_without_fix_held"] = sum(int(r["held"]) for r in ep if r["vehicle"] in set(nofix))
    short = [r for r in snd if float(r["duration_s"]) < 0.5 * max(float(x["duration_s"]) for x in snd)]
    M["short_logs"] = ";".join(r["log"].split("/")[0] for r in short)
    with (OUT / f"{run}_analysis.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["metric", "value"])
        for k, v in M.items():
            w.writerow([k, v])
    for k, v in M.items():
        print(f"{k:<34} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
