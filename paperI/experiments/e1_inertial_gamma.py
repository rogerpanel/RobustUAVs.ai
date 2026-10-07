#!/usr/bin/env python3
"""E1 -- inertial (dead-reckoning) gamma from real flight logs (RQ1).

Runbook section E1. The authenticated rate gamma_a currently comes from the
Whelan jamming flight, whose receiver never lost its fix (fix_type = 3 in all
496 post-onset samples, 11-14 satellites): it measures a degraded but still
fused estimator, not dead reckoning after GNSS is rejected. This script
measures the latter directly, by synthetic outage on the benign flight:

  1. take the benign Whelan flight; choose N onset times on a uniform grid
     over its airborne segment, keeping 10 s clear of both ends and leaving
     room for the full horizon after each onset;
  2. at each onset t0 freeze position and velocity at the EKF state, then
     integrate sensor_combined specific force, rotated body->NED with the
     logged attitude and corrected for gravity, for tau in [0, TAU_MAX];
     subtract the EKF accelerometer bias at t0 if the log carries one;
  3. use the GNSS-aided EKF position as ground truth and record
        e(tau)       = || p_DR(tau) - p_EKF(tau) ||   (horizontal by default,
                                                       matching the parent)
        gamma_d(tau) = (e(tau) - e(0)) / tau           (e(0) = 0 here);
  4. per tau bin (the same bins as results/gamma_campaign_bins.csv) report
     the supremum, p95 and median, plus a bootstrap interval for the
     supremum obtained by resampling onsets.

Input: data/raw/uav_attack_whelan/benign/, either ulog2csv per-topic CSVs
("<log>_<topic>_<inst>.csv", the form the dataset ships) or a .ulg file.
Needed topics: sensor_combined, vehicle_attitude, vehicle_local_position.
Optional: estimator_sensor_bias (accelerometer bias), vehicle_land_detected.

Output: paperI/results/e1_inertial_gamma.csv with columns
  tau_bin, n, gamma_sup, gamma_p95, gamma_med, provenance=measured
followed by n_onsets, sup_ci_lo, sup_ci_hi, bias_source, norm, segment_rule.

Known optimism, stated rather than hidden: the attitude used for the rotation
is the EKF's own, which stayed GNSS-aided throughout the benign flight. After a
real rejection, attitude error would also grow (slowly, being gravity- and
magnetometer-aided), so this measures a lower bound on post-rejection drift.

No data, no output: if the benign flight or a required topic is missing, the
script prints SKIPPED and writes nothing.

Usage:
    python3 e1_inertial_gamma.py [--raw DIR] [--out DIR] [--onsets 200]
                                 [--tau-max 20] [--norm horizontal|3d]
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

G = 9.80665
EDGE_S = 10.0
# The parent campaign's staleness bins (results/gamma_campaign_bins.csv),
# truncated to the horizon this experiment integrates over.
BINS = [(0.4, 1.0), (1.0, 2.0), (2.0, 5.0), (5.0, 10.0), (10.0, 20.0)]
N_BOOT = 1000
REQUIRED = ("sensor_combined", "vehicle_attitude", "vehicle_local_position")
OPTIONAL = ("estimator_sensor_bias", "vehicle_land_detected")


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------
def _read_csv(path: Path) -> dict[str, np.ndarray]:
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return {}
    out = {}
    for k in rows[0]:
        try:
            out[k] = np.array([float(r[k]) for r in rows])
        except (TypeError, ValueError):
            continue
    return out


def load_topics(flight_dir: Path) -> dict[str, dict[str, np.ndarray]]:
    topics: dict[str, dict[str, np.ndarray]] = {}
    ulgs = sorted(flight_dir.glob("*.ulg"))
    if ulgs:
        from pyulog import ULog
        ulog = ULog(str(ulgs[0]), list(REQUIRED + OPTIONAL))
        for d in ulog.data_list:
            if d.multi_id == 0:
                topics[d.name] = {k: np.asarray(v, dtype=float) for k, v in d.data.items()}
        return topics
    for name in REQUIRED + OPTIONAL:
        hits = sorted(flight_dir.glob(f"*_{name}_0.csv"))
        if hits:
            topics[name] = _read_csv(hits[0])
    return topics


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------
def quat_to_dcm(q: np.ndarray) -> np.ndarray:
    """PX4 vehicle_attitude.q = (w, x, y, z), rotation body(FRD) -> NED."""
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def interp_cols(t_src, cols, t_dst):
    return np.stack([np.interp(t_dst, t_src, c) for c in cols], axis=-1)


# --------------------------------------------------------------------------
# experiment
# --------------------------------------------------------------------------
def prepare(topics):
    sc, att, lp = (topics[k] for k in REQUIRED)
    t_imu = sc["timestamp"].copy()
    if "accelerometer_timestamp_relative" in sc:
        t_imu = t_imu + sc["accelerometer_timestamp_relative"]
    t_imu = t_imu * 1e-6
    f_body = np.stack([sc[f"accelerometer_m_s2[{i}]"] for i in range(3)], axis=-1)

    t_att = att["timestamp"] * 1e-6
    q = interp_cols(t_att, [att[f"q[{i}]"] for i in range(4)], t_imu)
    q /= np.linalg.norm(q, axis=1, keepdims=True)

    t_lp = lp["timestamp"] * 1e-6
    p_ekf = interp_cols(t_lp, [lp["x"], lp["y"], lp["z"]], t_imu)
    v_ekf = interp_cols(t_lp, [lp["vx"], lp["vy"], lp["vz"]], t_imu)

    bias = None
    bias_source = "none"
    sb = topics.get("estimator_sensor_bias")
    if sb and all(f"accel_bias[{i}]" in sb for i in range(3)):
        bias = interp_cols(sb["timestamp"] * 1e-6,
                           [sb[f"accel_bias[{i}]"] for i in range(3)], t_imu)
        bias_source = "estimator_sensor_bias"
    return t_imu, f_body, q, p_ekf, v_ekf, bias, bias_source, t_lp, lp


def airborne_window(topics, t_lp, lp, tau_max):
    ld = topics.get("vehicle_land_detected")
    if ld and "landed" in ld:
        t = ld["timestamp"] * 1e-6
        air = t[ld["landed"] < 0.5]
        if air.size:
            lo, hi, rule = air.min(), air.max(), "vehicle_land_detected.landed == 0"
        else:
            lo = hi = None
    else:
        lo = hi = None
    if lo is None:
        alt = -lp["z"]
        ground = np.median(alt[: max(5, len(alt) // 50)])
        idx = np.where(alt - ground > 1.0)[0]
        if not idx.size:
            return None, None, "no airborne segment found"
        lo, hi = t_lp[idx[0]], t_lp[idx[-1]]
        rule = "altitude > 1 m above initial ground level"
    return lo + EDGE_S, hi - EDGE_S - tau_max, rule


def dead_reckon(i0, i1, t, f_body, q, p_ekf, v_ekf, bias, norm):
    tt = t[i0:i1] - t[i0]
    fb = f_body[i0:i1] - (bias[i0] if bias is not None else 0.0)
    a = np.einsum("nij,nj->ni", np.stack([quat_to_dcm(qq) for qq in q[i0:i1]]), fb)
    a[:, 2] += G
    dt = np.diff(tt)
    v = np.vstack([v_ekf[i0], v_ekf[i0] + np.cumsum(0.5 * (a[1:] + a[:-1]) * dt[:, None], axis=0)])
    p = np.vstack([p_ekf[i0], p_ekf[i0] + np.cumsum(0.5 * (v[1:] + v[:-1]) * dt[:, None], axis=0)])
    d = p - p_ekf[i0:i1]
    e = np.hypot(d[:, 0], d[:, 1]) if norm == "horizontal" else np.linalg.norm(d, axis=1)
    return tt, e


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path,
                    default=REPO / "data" / "raw" / "uav_attack_whelan" / "benign")
    ap.add_argument("--out", type=Path, default=REPO / "paperI" / "results")
    ap.add_argument("--onsets", type=int, default=200)
    ap.add_argument("--tau-max", type=float, default=20.0)
    ap.add_argument("--norm", choices=("horizontal", "3d"), default="horizontal")
    a = ap.parse_args()

    if not a.raw.exists():
        print(f"[E1] SKIPPED: {a.raw} not found. Stage data with "
              "data/fetch_kaggle.py first. Nothing written.")
        return 0
    topics = load_topics(a.raw)
    missing = [k for k in REQUIRED if k not in topics]
    if missing:
        print(f"[E1] SKIPPED: benign flight lacks {', '.join(missing)} "
              f"(found: {', '.join(sorted(topics)) or 'none'}). The runbook's "
              "fallback is ulog2csv on the original .ulg. Nothing written.")
        return 0

    t, f_body, q, p_ekf, v_ekf, bias, bias_source, t_lp, lp = prepare(topics)
    lo, hi, rule = airborne_window(topics, t_lp, lp, a.tau_max)
    if lo is None or hi <= lo:
        print(f"[E1] SKIPPED: airborne segment too short for {a.tau_max:.0f} s "
              f"horizons with {EDGE_S:.0f} s edges ({rule}). Nothing written.")
        return 0

    onsets = np.linspace(lo, hi, a.onsets)
    per_onset = []  # list of (tau array, gamma array)
    for t0 in onsets:
        i0 = int(np.searchsorted(t, t0))
        i1 = int(np.searchsorted(t, t0 + a.tau_max))
        if i1 - i0 < 3:
            continue
        tt, e = dead_reckon(i0, i1, t, f_body, q, p_ekf, v_ekf, bias, a.norm)
        keep = tt > 0
        per_onset.append((tt[keep], e[keep] / tt[keep]))
    if not per_onset:
        print("[E1] SKIPPED: no usable onsets. Nothing written.")
        return 0

    rng = np.random.default_rng(0)
    rows = []
    for b_lo, b_hi in BINS:
        per = [g[(tt >= b_lo) & (tt < b_hi)] for tt, g in per_onset]
        allg = np.concatenate(per) if per else np.array([])
        if allg.size == 0:
            continue
        sups = np.array([x.max() if x.size else np.nan for x in per])
        sups = sups[np.isfinite(sups)]
        boot = [np.max(rng.choice(sups, size=sups.size, replace=True)) for _ in range(N_BOOT)]
        rows.append(dict(
            tau_bin=f"[{b_lo:g},{b_hi:g})", n=int(allg.size),
            gamma_sup=round(float(allg.max()), 4),
            gamma_p95=round(float(np.percentile(allg, 95)), 4),
            gamma_med=round(float(np.median(allg)), 4),
            provenance="measured",
            n_onsets=int(sups.size),
            sup_ci_lo=round(float(np.percentile(boot, 2.5)), 4),
            sup_ci_hi=round(float(np.percentile(boot, 97.5)), 4),
            bias_source=bias_source, norm=a.norm, segment_rule=rule))
        print(f"[E1] tau {rows[-1]['tau_bin']:>8}: sup {rows[-1]['gamma_sup']:.3f} "
              f"[{rows[-1]['sup_ci_lo']:.3f}, {rows[-1]['sup_ci_hi']:.3f}]  "
              f"p95 {rows[-1]['gamma_p95']:.3f}  med {rows[-1]['gamma_med']:.3f}  m/s")

    a.out.mkdir(parents=True, exist_ok=True)
    out = a.out / "e1_inertial_gamma.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"[E1] wrote {out} ({len(rows)} bins, {len(per_onset)} onsets, bias: {bias_source})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
