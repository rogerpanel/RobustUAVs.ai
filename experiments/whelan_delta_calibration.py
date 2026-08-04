#!/usr/bin/env python3
"""Empirical delta calibration from the real Whelan sample (3 live flights).

Purpose: replace (or bracket) the kinematic worst case delta_pos =
v_max * Delta(theta) with a measured position-error growth rate
gamma  [m per second of GNSS degradation/staleness], from real PX4 flights
on the same airframe family the autonomy anchor models.

Two error sources — an EXPLICIT switch, never silently chosen
(certificate-semantics decision, see docs/certified_regime_analysis.md):
  receiver : gps.csv (vehicle_gps_position) lat/lon vs the flight's own
             pre-attack median. Under spoofing this is the RECEIVER's
             (false) fix — the perturbation entering the estimator.
  ekf      : local.csv (vehicle_local_position) x/y vs pre-attack median.
             The estimator OUTPUT the controller acts on — filtered error.

Per attack flight we report:
  noise_p95_m   : p95 self-referenced error in the pre-attack window
  onset_s       : jamming = first fix_type < 3; spoofing = first sustained
                  exceedance of 3x the pre-attack noise p95
  peak_m, t_peak_s, mean_final_half_m
  gamma_lsq     : least-squares slope of error vs (t - onset) after onset
  gamma_peak    : peak_m / (t_peak - onset)  (conservative secant rate)

CAVEATS (report with the numbers, always):
  * n = 3 flights, hover/loiter regime (|v| ~ 0.05 m/s): a calibration
    sample, not a distribution. Cruise-speed staleness error can approach
    the kinematic bound; TEXBAT re-calibration and more flights pending.
  * Self-referenced to the first 25% (true attack intervals are TODO).
  * EKF errors are what the controller consumes; receiver errors are what
    the attack injects. gamma differs by an order of magnitude between them.

Output: results/whelan_delta_calibration.csv  (provenance: real-corpus,
3-flight live sample, self-referenced).
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "uav_attack_whelan"
OUT = REPO / "results" / "whelan_delta_calibration.csv"
PRE_FRAC = 0.25
US = 1e6
R_EARTH = 6_371_000.0


def load_csv(p: Path):
    with open(p, newline="") as fh:
        return list(csv.DictReader(fh))


def f(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def receiver_series(flight_dir: Path):
    rows = load_csv(flight_dir / "gps.csv")
    t, lat, lon, fix = [], [], [], []
    for r in rows:
        ts, la, lo = f(r["timestamp"]), f(r["lat"]), f(r["lon"])
        if None in (ts, la, lo):
            continue
        if abs(la) > 1000:
            la, lo = la * 1e-7, lo * 1e-7
        t.append(ts / US)
        lat.append(la)
        lon.append(lo)
        fix.append(f(r.get("fix_type")) or 0)
    t = np.asarray(t) - t[0]
    lat, lon, fix = map(np.asarray, (lat, lon, fix))
    n_pre = max(3, int(len(t) * PRE_FRAC))
    la0, lo0 = np.median(lat[:n_pre]), np.median(lon[:n_pre])
    x = np.radians(lon - lo0) * math.cos(math.radians(la0)) * R_EARTH
    y = np.radians(lat - la0) * R_EARTH
    return t, np.hypot(x, y), fix, n_pre


def ekf_series(flight_dir: Path):
    rows = load_csv(flight_dir / "local.csv")
    t, xs, ys = [], [], []
    for r in rows:
        ts, x, y = f(r["timestamp"]), f(r["x"]), f(r["y"])
        if None in (ts, x, y):
            continue
        t.append(ts / US)
        xs.append(x)
        ys.append(y)
    t = np.asarray(t) - t[0]
    xs, ys = np.asarray(xs), np.asarray(ys)
    n_pre = max(3, int(len(t) * PRE_FRAC))
    err = np.hypot(xs - np.median(xs[:n_pre]), ys - np.median(ys[:n_pre]))
    return t, err, None, n_pre


def analyse(flight, source, t, err, fix, n_pre):
    noise_p95 = float(np.percentile(err[:n_pre], 95))
    # onset
    onset_i = None
    if fix is not None and np.any(fix[n_pre:] < 3):
        onset_i = n_pre + int(np.argmax(fix[n_pre:] < 3))
        onset_kind = "fix_loss"
    else:
        thr = max(3 * noise_p95, 0.5)
        for i in range(n_pre, len(err) - 2):
            if err[i] > thr and err[i + 1] > thr and err[i + 2] > thr:
                onset_i = i
                break
        onset_kind = "3x_noise_p95"
    row = {"flight": flight, "source": source, "n_samples": len(err),
           "duration_s": round(float(t[-1]), 1),
           "noise_p95_m": round(noise_p95, 3),
           "onset_kind": onset_kind}
    peak_i = int(np.argmax(err))
    row["peak_m"] = round(float(err[peak_i]), 3)
    row["t_peak_s"] = round(float(t[peak_i]), 1)
    half = len(err) // 2
    row["mean_final_half_m"] = round(float(err[half:].mean()), 3)
    if onset_i is None or onset_i >= len(err) - 3:
        row.update(onset_s=None, gamma_lsq_m_s=None, gamma_peak_m_s=None)
        return row
    row["onset_s"] = round(float(t[onset_i]), 1)
    tt = t[onset_i:] - t[onset_i]
    ee = err[onset_i:]
    A = np.vstack([tt, np.ones_like(tt)]).T
    slope = float(np.linalg.lstsq(A, ee, rcond=None)[0][0])
    row["gamma_lsq_m_s"] = round(slope, 4)
    dt_peak = float(t[peak_i] - t[onset_i])
    row["gamma_peak_m_s"] = round(float(err[peak_i]) / dt_peak, 4) \
        if dt_peak > 1 else None
    return row


def main() -> int:
    rows = []
    for flight in ("benign", "gps_jamming", "gps_spoofing"):
        d = RAW / flight
        if not d.exists():
            print(f"[whelan-cal] missing {d}; run staging first")
            return 1
        for source, loader in (("receiver", receiver_series),
                               ("ekf", ekf_series)):
            t, err, fix, n_pre = loader(d)
            rows.append(analyse(flight, source, t, err, fix, n_pre))

    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[whelan-cal] -> {OUT}")
    for r in rows:
        print("  " + " ".join(f"{k}={v}" for k, v in r.items()))

    # the gamma the composition consumes: conservative = max over attack
    # flights and sources of the available rates
    gammas = [v for r in rows if r["flight"] != "benign"
              for v in (r.get("gamma_lsq_m_s"), r.get("gamma_peak_m_s"))
              if v is not None]
    print(f"\n[whelan-cal] gamma_emp_conservative = max = "
          f"{max(gammas):.4f} m/s  (n={len(gammas)} rates from 2 attack "
          f"flights x 2 sources; hover regime, 3-flight sample)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
