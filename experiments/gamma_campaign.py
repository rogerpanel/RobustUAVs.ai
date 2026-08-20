#!/usr/bin/env python3
"""
Campaign arm A: is gamma a constant, or gamma(covariates)?

A co-author asked us to test delta ~ gamma*Delta across UAVs, speeds, flight
modes, GNSS conditions, attack intensities and attack durations, noting that a
stable gamma would be a strong result and an unstable one would be a more
interesting paper. experiments/gamma_stability.py answered the coarsest version
(one scalar per flight, 2.6x across attack type). This goes further: it
estimates gamma at EVERY post-onset sample and regresses it on the conditions
prevailing at that instant.

WHAT THIS CAN AND CANNOT VARY
-----------------------------
From the released UAV Attack Dataset sample (3 flights, PX4 v1.11.3 / Pixhawk 4
/ Holybro S500):

  varied, well covered   : GNSS condition (satellites 14->4, HDOP 0.71->4.16,
                           noise_per_ms 99->171, fix_type 3->0)
                           attack type (jamming vs spoofing)
                           staleness horizon / attack duration (0..~70 s)
  varied, POORLY covered : airspeed. p90 of |v_xy| is 0.32-0.65 m/s and the
                           median is under 0.11 m/s. These are hover flights.
                           Speed bins above ~1 m/s hold few samples and their
                           medians are reported with counts so the reader can
                           discount them.
  NOT varied             : platform (one airframe), flight mode (hover only)

The output states this coverage explicitly. A factor we could not vary is
reported as not varied, never as "no effect found".

TWO ESTIMATORS, BOTH REPORTED
-----------------------------
  gamma_cum(t)  = e(t) / (t - onset). The secant rate: total position error
                  accrued over total staleness. This is the quantity the
                  certificate consumes, because Lemma 1 bounds accumulated
                  delay and the tube bound multiplies it by a single rate.
  gamma_inst(t) = local least-squares slope of e over a +/-W second window.
                  Diagnostic: it shows whether the growth is linear (the two
                  agree) or saturating (gamma_inst falls while gamma_cum does
                  not).

WHICH ESTIMATOR THE CERTIFICATE IS ENTITLED TO
----------------------------------------------
gamma_delta, and the distinction is not cosmetic. Onset is declared when the
error crosses a detection threshold, so e(onset) is already 0.6-9.3 m depending
on flight and signal. gamma_cum divides that pre-existing offset by tau, which
at sub-second tau yields rates up to 8.6 m/s -- an artifact of the threshold,
not a property of the attack. gamma_delta measures only the error accrued SINCE
onset, which is what Lemma 1's delay budget is responsible for. Aggregates below
use gamma_delta; gamma_cum stays in the per-sample file so the contrast can be
audited.

STATISTICAL HEALTH WARNING, STATED IN THE OUTPUT
------------------------------------------------
Samples within one flight are strongly autocorrelated, and there are only two
attack flights. Covariate effects below are therefore DESCRIPTIVE, not inferred:
we report binned medians with counts and an OLS fit for direction and magnitude,
and deliberately do not report p-values, which would be meaningless under this
dependence structure.

Writes:
  results/gamma_campaign_samples.csv   per-sample estimates + covariates
  results/gamma_campaign_bins.csv      binned medians per factor
  results/gamma_campaign_model.csv     OLS coefficients + R^2
  results/paper_figures/block_paperD_tab_gamma_campaign.tex
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "uav_attack_whelan"
RES = REPO / "results"
FIGS = RES / "paper_figures"

PRE_FRAC = 0.25          # pre-attack reference window, as in the calibration
US = 1e6
R_EARTH = 6_371_000.0
MIN_TAU = 0.4            # s; EKF runs at ~10 Hz so sub-second tau is observable
INST_WIN = 5.0           # s; half-width for the instantaneous slope

# Coverage of each factor, decided by the release and not by us.
COVERAGE = {
    "attack_type":   ("varied", "jamming and spoofing"),
    "gnss_condition": ("varied", "satellites 14->4, HDOP 0.71->4.16, fix 3->0"),
    "staleness":     ("varied", "0 to ~70 s post-onset"),
    "airspeed":      ("poor", "hover; p90 |v_xy| < 0.65 m/s"),
    "platform":      ("not varied", "one PX4 / Pixhawk 4 / Holybro S500"),
    "flight_mode":   ("not varied", "hover / loiter only"),
}


def load(p: Path) -> list[dict]:
    with p.open(newline="") as fh:
        return list(csv.DictReader(fh))


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def receiver_series(d: Path):
    """Raw receiver fix error vs the flight's own pre-attack median."""
    rows = load(d / "gps.csv")
    t, lat, lon, cov = [], [], [], []
    for r in rows:
        ts, la, lo = num(r["timestamp"]), num(r["lat"]), num(r["lon"])
        if None in (ts, la, lo):
            continue
        if abs(la) > 1000:          # lat/lon stored as 1e-7 deg ints
            la, lo = la * 1e-7, lo * 1e-7
        t.append(ts / US)
        lat.append(la)
        lon.append(lo)
        cov.append({"sats": num(r.get("satellites_used")),
                    "hdop": num(r.get("hdop")),
                    "noise": num(r.get("noise_per_ms")),
                    "fix": num(r.get("fix_type"))})
    t = np.asarray(t)
    lat, lon = np.asarray(lat), np.asarray(lon)
    n_pre = max(3, int(len(t) * PRE_FRAC))
    la0, lo0 = np.median(lat[:n_pre]), np.median(lon[:n_pre])
    x = np.radians(lon - lo0) * math.cos(math.radians(la0)) * R_EARTH
    y = np.radians(lat - la0) * R_EARTH
    return t, np.hypot(x, y), cov, n_pre


def ekf_series(d: Path):
    """Estimator-output error: what the controller actually acts on."""
    rows = load(d / "local.csv")
    t, xs, ys, cov = [], [], [], []
    for r in rows:
        ts, x, y = num(r["timestamp"]), num(r["x"]), num(r["y"])
        if None in (ts, x, y):
            continue
        vx, vy = num(r.get("vx")) or 0.0, num(r.get("vy")) or 0.0
        ax, ay = num(r.get("ax")) or 0.0, num(r.get("ay")) or 0.0
        t.append(ts / US)
        xs.append(x)
        ys.append(y)
        cov.append({"speed": math.hypot(vx, vy),
                    "accel": math.hypot(ax, ay)})
    t = np.asarray(t)
    xs, ys = np.asarray(xs), np.asarray(ys)
    n_pre = max(3, int(len(t) * PRE_FRAC))
    err = np.hypot(xs - np.median(xs[:n_pre]), ys - np.median(ys[:n_pre]))
    return t, err, cov, n_pre


def find_onset(t, err, cov, n_pre) -> tuple[int | None, str]:
    """Fix loss where observable, otherwise sustained 3x pre-attack noise."""
    noise_p95 = float(np.percentile(err[:n_pre], 95))
    fixes = [c.get("fix") for c in cov]
    if any(f is not None for f in fixes):
        for i in range(n_pre, len(err)):
            if fixes[i] is not None and fixes[i] < 3:
                return i, "fix_loss"
    thr = max(3 * noise_p95, 0.5)
    for i in range(n_pre, len(err) - 2):
        if err[i] > thr and err[i + 1] > thr and err[i + 2] > thr:
            return i, "3x_noise_p95"
    return None, "none"


def nearest(t_src, t_tgt):
    """Index of the nearest source sample for each target sample."""
    idx = np.searchsorted(t_src, t_tgt)
    idx = np.clip(idx, 1, len(t_src) - 1)
    left = np.abs(t_tgt - t_src[idx - 1])
    right = np.abs(t_src[idx] - t_tgt)
    return np.where(left <= right, idx - 1, idx)


def per_sample(flight: str, source: str, d: Path) -> list[dict]:
    t, err, cov, n_pre = (receiver_series(d) if source == "receiver"
                          else ekf_series(d))
    onset_i, kind = find_onset(t, err, cov, n_pre)
    if onset_i is None:
        return []

    # Join the other file's covariates onto this time base, so every sample
    # carries both GNSS condition and kinematics regardless of which series
    # supplied the error.
    ot, oerr, ocov, _ = (ekf_series(d) if source == "receiver"
                         else receiver_series(d))
    j = nearest(ot, t)

    t0 = t[onset_i]
    out = []
    for i in range(onset_i, len(t)):
        tau = float(t[i] - t0)
        if tau < MIN_TAU:
            continue
        a, b = cov[i], ocov[j[i]]
        merged = {**b, **a}
        lo, hi = t[i] - INST_WIN, t[i] + INST_WIN
        sel = (t >= lo) & (t <= hi)
        g_inst = None
        if sel.sum() >= 4:
            tt = t[sel] - t[i]
            A = np.vstack([tt, np.ones_like(tt)]).T
            g_inst = float(np.linalg.lstsq(A, err[sel], rcond=None)[0][0])
        # Baseline-corrected rate. Onset fires when the error crosses a
        # threshold, so err[onset] > 0 by construction; dividing that offset by
        # a small tau would manufacture a spurious rate. gamma_delta measures
        # only the error accrued SINCE onset, and is the honest estimator at
        # short staleness. Both are reported.
        d_err = float(err[i]) - float(err[onset_i])
        out.append({
            "flight": flight, "source": source, "onset_kind": kind,
            "t_s": round(float(t[i] - t[0]), 2),
            "staleness_s": round(tau, 2),
            "err_m": round(float(err[i]), 4),
            "err_at_onset_m": round(float(err[onset_i]), 4),
            "gamma_cum_m_s": round(float(err[i]) / tau, 4),
            "gamma_delta_m_s": round(max(d_err, 0.0) / tau, 4),
            "gamma_inst_m_s": (round(g_inst, 4) if g_inst is not None else ""),
            "sats": _r(merged.get("sats")), "hdop": _r(merged.get("hdop"), 2),
            "noise_per_ms": _r(merged.get("noise")),
            "fix_type": _r(merged.get("fix")),
            "speed_m_s": _r(merged.get("speed"), 3),
            "accel_m_s2": _r(merged.get("accel"), 3),
        })
    return out


def _r(v, nd=0):
    if v is None:
        return ""
    return round(float(v), nd) if nd else int(round(float(v)))


def binned(rows, key, edges, label, val="gamma_delta_m_s"):
    """Median gamma_cum per bin of `key`, with counts so sparse bins show."""
    out = []
    vals = [(r, r[key]) for r in rows if r[key] != ""]
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = [r[val] for r, v in vals if lo <= float(v) < hi]
        if sel:
            out.append({"factor": label, "bin": f"[{lo:g},{hi:g})",
                        "n": len(sel),
                        "gamma_median": round(float(np.median(sel)), 4),
                        "gamma_p95": round(float(np.percentile(sel, 95)), 4),
                        "gamma_max": round(float(max(sel)), 4)})
    return out


def main() -> int:
    if not RAW.exists():
        raise SystemExit(f"missing {RAW.relative_to(REPO)}; stage the corpus first")

    rows: list[dict] = []
    for flight in ("gps_jamming", "gps_spoofing"):
        d = RAW / flight
        if not d.exists():
            print(f"  SKIP {flight}: not staged")
            continue
        for source in ("receiver", "ekf"):
            got = per_sample(flight, source, d)
            print(f"  {flight:<14} {source:<9} {len(got):>5} post-onset samples")
            rows.extend(got)
    if not rows:
        raise SystemExit("no post-onset samples; nothing to characterise")

    RES.mkdir(exist_ok=True)
    with (RES / "gamma_campaign_samples.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"-> results/gamma_campaign_samples.csv ({len(rows)} rows)")

    # ---- binned medians, per factor ------------------------------------
    bins: list[dict] = []
    bins += binned(rows, "sats", [0, 5, 8, 11, 20], "satellites in view")
    bins += binned(rows, "hdop", [0, 1, 1.5, 2.5, 10], "HDOP")
    bins += binned(rows, "noise_per_ms", [90, 110, 130, 150, 200], "receiver noise")
    bins += binned(rows, "staleness_s", [0.4, 1, 2, 5, 10, 20, 40, 200], "staleness (s)")
    bins += binned(rows, "speed_m_s", [0, 0.2, 0.5, 1.0, 10], "airspeed (m/s)")
    for a in ("gps_jamming", "gps_spoofing"):
        sel = [r["gamma_delta_m_s"] for r in rows if r["flight"] == a]
        bins.append({"factor": "attack type", "bin": a, "n": len(sel),
                     "gamma_median": round(float(np.median(sel)), 4),
                     "gamma_p95": round(float(np.percentile(sel, 95)), 4),
                     "gamma_max": round(float(max(sel)), 4)})
    for s in ("receiver", "ekf"):
        sel = [r["gamma_delta_m_s"] for r in rows if r["source"] == s]
        bins.append({"factor": "error signal", "bin": s, "n": len(sel),
                     "gamma_median": round(float(np.median(sel)), 4),
                     "gamma_p95": round(float(np.percentile(sel, 95)), 4),
                     "gamma_max": round(float(max(sel)), 4)})
    # Overall summary, emitted here rather than reconstructed downstream: a
    # consumer computing max/median across bins hits the zero-median tail bins
    # and gets a division guard instead of an answer.
    _all = [r["gamma_delta_m_s"] for r in rows]
    bins.append({"factor": "OVERALL", "bin": "all post-onset samples",
                 "n": len(_all),
                 "gamma_median": round(float(np.median(_all)), 4),
                 "gamma_p95": round(float(np.percentile(_all, 95)), 4),
                 "gamma_max": round(float(max(_all)), 4)})
    for name, (status, note) in COVERAGE.items():
        bins.append({"factor": f"COVERAGE:{name}", "bin": status, "n": "",
                     "gamma_median": "", "gamma_p95": "", "gamma_max": note})
    with (RES / "gamma_campaign_bins.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["factor", "bin", "n",
                                           "gamma_median", "gamma_p95", "gamma_max"])
        w.writeheader()
        w.writerows(bins)
    print("-> results/gamma_campaign_bins.csv")

    # ---- descriptive OLS ------------------------------------------------
    feats = ["sats", "hdop", "noise_per_ms", "staleness_s", "speed_m_s"]
    use = [r for r in rows if all(r[k] != "" for k in feats)]
    model_rows = []
    r2 = float("nan")
    if len(use) > 20:
        X = np.array([[float(r[k]) for k in feats] for r in use])
        y = np.array([r["gamma_delta_m_s"] for r in use])
        # standardise so coefficients are comparable across units
        mu, sd = X.mean(0), X.std(0)
        sd[sd == 0] = 1.0
        Xs = np.hstack([(X - mu) / sd, np.ones((len(X), 1))])
        beta, *_ = np.linalg.lstsq(Xs, y, rcond=None)
        pred = Xs @ beta
        ss_res = float(((y - pred) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        for k, b in zip(feats + ["intercept"], beta):
            model_rows.append({"term": k, "std_coef_m_s": round(float(b), 4)})
        model_rows.append({"term": "R2", "std_coef_m_s": round(r2, 4)})
        model_rows.append({"term": "n_samples", "std_coef_m_s": len(use)})
        model_rows.append({"term": "NOTE", "std_coef_m_s":
                           "descriptive only; samples autocorrelated within "
                           "2 flights, no p-values reported"})
    with (RES / "gamma_campaign_model.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["term", "std_coef_m_s"])
        w.writeheader()
        w.writerows(model_rows)
    print("-> results/gamma_campaign_model.csv")

    # ---- LaTeX block ----------------------------------------------------
    show = [b for b in bins if not b["factor"].startswith("COVERAGE")
            and b["factor"] != "OVERALL"]
    lines = ["% AUTO-GENERATED by experiments/gamma_campaign.py. Do not hand-edit.\n",
             "% PROVENANCE: real-corpus, per-sample estimates from 2 attack flights.\n",
             "% Coverage: platform and flight mode NOT varied; airspeed poorly\n"
             "% covered (hover). See results/gamma_campaign_bins.csv.\n",
             "\\begin{tabular}{@{}llrrr@{}}\n\\toprule\n",
             "Factor & Bin & $n$ & median $\\gamma$ & max $\\gamma$\\\\\n\\midrule\n"]
    # Bin labels come from data and reach LaTeX verbatim, so escape them.
    # An unescaped underscore in "gps_jamming" is a maths-mode error, not a
    # typo the reader can ignore.
    pretty = {"gps_jamming": "GPS jamming", "gps_spoofing": "GPS spoofing",
              "receiver": "raw receiver fix", "ekf": "EKF-filtered"}

    def tex(v):
        v = pretty.get(str(v), str(v))
        return (v.replace("\\", "").replace("_", "\\_").replace("&", "\\&")
                 .replace("%", "\\%").replace("#", "\\#"))

    last = None
    for b in show:
        fac = b["factor"] if b["factor"] != last else ""
        last = b["factor"]
        lines.append(f"{tex(fac)} & {tex(b['bin'])} & {b['n']} & "
                     f"{b['gamma_median']:.2f} & {b['gamma_max']:.2f}\\\\\n")
    lines.append("\\bottomrule\n\\end{tabular}\n")
    FIGS.mkdir(parents=True, exist_ok=True)
    (FIGS / "block_paperD_tab_gamma_campaign.tex").write_text("".join(lines))
    print("-> results/paper_figures/block_paperD_tab_gamma_campaign.tex")

    # ---- summary --------------------------------------------------------
    allg = [r["gamma_delta_m_s"] for r in rows]
    print(f"\ngamma_delta (baseline-corrected) over {len(allg)} post-onset samples:")
    print(f"  median {np.median(allg):.3f}   p95 {np.percentile(allg, 95):.3f}"
          f"   max {max(allg):.3f}   min {min(allg):.3f} m/s")
    print(f"  spread (max/median) = {max(allg)/np.median(allg):.1f}x")
    if model_rows:
        print(f"\ndescriptive OLS on standardised covariates, R^2 = {r2:.3f}")
        for m in model_rows:
            if m["term"] not in ("R2", "n_samples", "NOTE"):
                print(f"    {m['term']:<14} {m['std_coef_m_s']:+.4f}")
    print("\nCoverage:")
    for name, (status, note) in COVERAGE.items():
        print(f"  {name:<16} {status:<11} {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
