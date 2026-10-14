#!/usr/bin/env python3
"""R5 (part 1) -- floor sensitivity to a MEASURED GNSS degradation marginal.

The pilot's delta_gnss marginal is simulated (Gauss-Markov drift, white noise,
outages of mean 5 s, 10 s jamming-noise episodes): median 1.3 m, max 3.9 m.
The parent artifact holds measured navigation error during real GPS jamming
(results/gamma_campaign_samples.csv, flight gps_jamming: two episodes, a
3x-noise episode and a fix loss, 496 one-second samples). Spoofing samples are
excluded: spoofing is adversarial and belongs to delta_adv.

Construction (stated, conservative):
  e_meas(D)  = largest measured error at staleness <= D seconds (monotone
               envelope over both episodes; provenance = measured);
  per mission, an episode occurs with the simulator's probabilities
  (outage P_OUTAGE with exponential duration of mean OUTAGE_MEAN_S, jamming
  noise P_JAMNOISE for JAMNOISE_S); the measured-envelope GNSS deviation is
  max(simulated GNSS deviation, e_meas(D)) -- never smaller than the pilot's.
  A stress variant sets every episode to the measured 45 s duration.
The certified floor 1 - pbar_RA(s) is recomputed on the E4 grid with the
pilot's env and fault marginals and the pooled delta_adv (R1 if present).

Outputs: results/r5_gnss_envelope.csv, results/r5_floor_sensitivity.csv
Usage:   python3 r5_measured_gnss.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from constants import *  # noqa: F401,F403
import run_pilot as RP
import depbounds as db

RES = RP.RES
PARENT = Path(__file__).resolve().parents[2] / "results"


def envelope():
    rows = [r for r in csv.DictReader((PARENT / "gamma_campaign_samples.csv").open())
            if r["flight"] == "gps_jamming"]
    s = np.array([float(r["staleness_s"]) for r in rows]); e = np.array([float(r["err_m"]) for r in rows])
    order = np.argsort(s)
    s, e = s[order], np.maximum.accumulate(e[order])
    return s, e, len(rows)


def e_meas(D, s, e):
    idx = np.searchsorted(s, D, side="right") - 1
    return np.where(idx >= 0, e[np.maximum(idx, 0)], 0.0)


def main():
    s, e, n_samp = envelope()
    grid = np.array([0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 45])
    with (RES / "r5_gnss_envelope.csv").open("w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["staleness_s", "err_envelope_m", "n_samples", "provenance"])
        for D in grid:
            w.writerow([D, round(float(e_meas(D, s, e)), 3), n_samp, "measured"])
    z = np.load(RES / "e3_marginals.npz")
    env, env_lo, gn, fa = z["env"], z["env_lo"], z["gnss"], z["fault"]
    rng = np.random.default_rng(5501)                       # R5 seed block 55xx
    n = len(gn)
    out = rng.random(n) < P_OUTAGE
    jam = rng.random(n) < P_JAMNOISE
    D = np.maximum(np.where(out, rng.exponential(OUTAGE_MEAN_S, n), 0.0), np.where(jam, JAMNOISE_S, 0.0))
    gn_meas = np.maximum(gn, e_meas(D, s, e))
    D45 = np.where(out | jam, 45.0, 0.0)
    gn_long = np.maximum(gn, e_meas(D45, s, e))
    dr = RES / "r1_delta_adv.csv"
    if dr.exists():
        dadv = {float(r["fpr"]): max(float(r["delta_pooled_m"]), float(r["delta_pilot_m"]))
                for r in csv.DictReader(dr.open())}
        src = "R1 pooled"
    else:
        dadv = {float(r["fpr"]): float(r["delta_adv_cal_m"]) for r in csv.DictReader((RES / "e4_delta_adv.csv").open())}
        src = "pilot"
    rows = []
    for fpr in RP.OPS:
        for m in (5.0, 10.0, 20.0):
            for tn in (0.0, 0.25):
                s_av = m - dadv[fpr] - RP.net_tube(tn)
                vals = {}
                for name, g in (("sim", gn), ("measured_env", gn_meas), ("measured_45s", gn_long)):
                    vals[name] = 1.0 if s_av <= 0 else db.ra_bound([g, fa, env], s_av, N=1000)
                rows.append({"fpr": fpr, "m": m, "theta_net": tn, "delta_adv": round(dadv[fpr], 3),
                             "delta_adv_source": src, "s_available_m": round(s_av, 3),
                             **{f"floor_{k}": round(1 - v, 5) for k, v in vals.items()},
                             "gnss_p99_sim": round(float(np.quantile(gn, .99)), 3),
                             "gnss_p99_measured_env": round(float(np.quantile(gn_meas, .99)), 3),
                             "gnss_p99_measured_45s": round(float(np.quantile(gn_long, .99)), 3),
                             "provenance": "measured+sim"})
                print({k: rows[-1][k] for k in ("fpr", "m", "theta_net", "floor_sim", "floor_measured_env",
                                                "floor_measured_45s")}, flush=True)
    with (RES / "r5_floor_sensitivity.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
