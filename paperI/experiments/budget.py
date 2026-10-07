#!/usr/bin/env python3
"""RQ1 and RQ3: the two sides of the crossover, and the crossover map.

Side 1 (sensing):  gamma_u / gamma_a from the 674 real post-onset samples of
                   the parent's gamma campaign (results/gamma_campaign_samples.csv)
Side 2 (crypto):   Delta_auth = t_sign + R_tx + t_verify + t_proto per scheme
                   and transport (compute: constants.py; transport: transport.py)

Outputs (paperI/results/):
  gamma_ratio.csv          gamma_u/gamma_a at several quantiles, with block-
                           bootstrap intervals on the non-extreme quantiles
  dead_reckoning_fit.csv   e(tau) = v0*tau + b*tau^2/2 fitted to the jamming
                           flight (the authenticated-GNSS proxy)
  dauth.csv                Delta_auth decomposition per scheme x transport
  crossover.csv            C(theta), B(theta,m), benefit in metres, theta_cross
  crossover_curves.csv     C(theta) on a log grid for the figure
  parent_table.csv         re-derivation of the proposal's parent-constant table
"""
from __future__ import annotations

import csv
import math
import random

from constants import (E, GAMMA_SCENARIOS, H, L_LOC, MARGINS, OUT, PARENT_RES,
                       S_SLACK, SCHEME, SCHEMES, T_C, THETA_BENIGN, THETA_OP,
                       TESLA_KEY_BYTES, TESLA_MAC_BYTES, delta_theta)
from transport import (TRANSPORT, TRANSPORTS, background, rta_bound, tag_bytes,
                       tx_time, u0_from_hcrl)

R_GNSS = 10.0          # authenticated navigation messages per second [assumption]
TESLA_INTERVALS = (0.05, 0.1, 0.5, 1.0)   # disclosure interval, s     [swept]
TESLA_SYNC = 0.01      # loose-sync bound added to disclosure, s      [assumption]


def write(name, rows):
    with (OUT / name).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f"-> paperI/results/{name} ({len(rows)} rows)")


# --------------------------------------------------------------------------
# Side 1: gamma
# --------------------------------------------------------------------------

def load_samples():
    with (PARENT_RES / "gamma_campaign_samples.csv").open() as fh:
        return list(csv.DictReader(fh))


def quantile(xs, q):
    xs = sorted(xs)
    if q >= 1.0:
        return xs[-1]
    i = q * (len(xs) - 1)
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def block_bootstrap(xs, q, block=10, n=2000, seed=1):
    """Moving-block bootstrap: samples within a flight are autocorrelated."""
    rng = random.Random(seed)
    nb = max(1, len(xs) // block)
    out = []
    for _ in range(n):
        s = []
        for _ in range(nb):
            k = rng.randrange(0, len(xs) - block + 1)
            s += xs[k:k + block]
        out.append(quantile(s, q))
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n)]


def gamma_side():
    rows = load_samples()
    def series(flight, source):
        sel = [r for r in rows if r["flight"] == flight and r["source"] == source]
        sel.sort(key=lambda r: float(r["t_s"]))
        return [float(r["gamma_delta_m_s"]) for r in sel]
    spoof, jam = series("gps_spoofing", "ekf"), series("gps_jamming", "ekf")
    out = []
    for q in (0.50, 0.90, 0.95, 0.99, 1.00):
        gu, ga = quantile(spoof, q), quantile(jam, q)
        if q < 0.99:
            ul, uh = block_bootstrap(spoof, q)
            al, ah = block_bootstrap(jam, q)
            lo, hi = ul / ah, uh / al
        else:
            lo = hi = float("nan")
        out.append(dict(quantile=q, gamma_u=round(gu, 4), gamma_a=round(ga, 4),
                        ratio=round(gu / ga, 3) if ga > 0 else float("inf"),
                        ratio_lo95=round(lo, 3), ratio_hi95=round(hi, 3),
                        n_u=len(spoof), n_a=len(jam)))
    write("gamma_ratio.csv", out)

    # dead-reckoning fit on the jamming EKF flight, tau < 5 s (pre-saturation)
    pts = [(float(r["staleness_s"]), float(r["err_m"]) - float(r["err_at_onset_m"]))
           for r in rows if r["flight"] == "gps_jamming" and r["source"] == "ekf"
           and 0 < float(r["staleness_s"]) < 5.0]
    # least squares e = v0*t + 0.5*b*t^2  (no intercept)
    s11 = sum(t * t for t, _ in pts); s12 = sum(t * t * t / 2 for t, _ in pts)
    s22 = sum((t * t / 2) ** 2 for t, _ in pts)
    y1 = sum(t * e for t, e in pts); y2 = sum(t * t / 2 * e for t, e in pts)
    det = s11 * s22 - s12 * s12
    v0 = (y1 * s22 - y2 * s12) / det
    b = (s11 * y2 - s12 * y1) / det
    res = [e - (v0 * t + 0.5 * b * t * t) for t, e in pts]
    rmse = math.sqrt(sum(x * x for x in res) / len(res))
    fit = [dict(model="e=v0*tau+b*tau^2/2", n=len(pts), tau_max_s=5.0,
                v0_m_s=round(v0, 4), b_m_s2=round(b, 4), rmse_m=round(rmse, 3),
                gamma_at_0p5s=round(v0 + 0.5 * b * 0.5, 4),
                gamma_at_1s=round(v0 + 0.5 * b * 1.0, 4),
                gamma_at_2s=round(v0 + 0.5 * b * 2.0, 4),
                tag="derived (fit to measured jamming flight)")]
    write("dead_reckoning_fit.csv", fit)
    return out, fit[0]


# --------------------------------------------------------------------------
# Side 2: Delta_auth
# --------------------------------------------------------------------------

def dauth_rows():
    can = TRANSPORT["can"]
    u0 = u0_from_hcrl(can)[2]
    rows = []
    for tr in TRANSPORTS:
        u = u0 if tr.key in ("can", "canfd") else 0.0
        bg = background(u, tr.frame_time) if u > 0 else []
        for sc in SCHEMES + ["tesla"]:
            if sc == "tesla":
                key, label = "tesla", "TESLA"
                t_sign = t_ver = SCHEME["mav2"].t_sign
                tail = 1.0
                protos = [(f"tesla@{ti:g}", ti + TESLA_SYNC) for ti in TESLA_INTERVALS]
                src_auth, pq = True, True
            else:
                key, label = sc.key, sc.label
                t_sign, t_ver, tail = sc.t_sign, sc.t_verify, sc.sign_tail_factor
                protos = [(sc.key, 0.0)]
                src_auth, pq = sc.source_auth, sc.pq
            b = tag_bytes(key)
            if tr.key.startswith("mav"):
                tx = tx_time(tr, b)
                feasible = R_GNSS * tx < 1.0
                R = tx / (1 - R_GNSS * tx) if feasible else math.inf  # M/D/1-free deterministic
            else:
                n = tr.extra_frames(b)
                feasible = u + R_GNSS * n * tr.frame_time < 1.0
                R = rta_bound(n, tr.frame_time, R_GNSS, bg) if feasible else math.inf
            for name, tp in protos:
                med = t_sign + R + t_ver + tp
                cert = t_sign * tail + R + t_ver + tp
                rows.append(dict(transport=tr.key, scheme=name, tag_bytes=b,
                                 t_sign_ms=round(t_sign * 1e3, 3),
                                 t_sign_tail_ms=round(t_sign * tail * 1e3, 3),
                                 R_tx_ms=round(R * 1e3, 3) if math.isfinite(R) else "inf",
                                 t_verify_ms=round(t_ver * 1e3, 3),
                                 t_proto_ms=round(tp * 1e3, 1),
                                 dauth_ms=round(med * 1e3, 3) if math.isfinite(med) else "inf",
                                 dauth_cert_ms=round(cert * 1e3, 3) if math.isfinite(cert) else "inf",
                                 rate_feasible=feasible, source_auth=src_auth, pq=pq))
    write("dauth.csv", rows)
    return rows


# --------------------------------------------------------------------------
# Crossover
# --------------------------------------------------------------------------

def crossover(rows):
    out = []
    for sc in GAMMA_SCENARIOS:
        for th in (THETA_BENIGN, THETA_OP, 1.0, S_SLACK):
            d = delta_theta(th)
            C = d * (sc.ratio - 1)
            for r in rows:
                if r["transport"] not in ("can", "canfd", "mav921k"):
                    continue
                da = r["dauth_cert_ms"]
                da = math.inf if da == "inf" else da / 1e3
                rho_u = d * sc.gamma_u * E
                rho_a = (d + da) * sc.gamma_a * E
                theta_cross = da / (H * (sc.ratio - 1)) if math.isfinite(da) else math.inf
                row = dict(gamma_scenario=sc.name, ratio=round(sc.ratio, 3),
                           theta=th, delta=d, C_s=round(C, 4),
                           transport=r["transport"], scheme=r["scheme"],
                           dauth_cert_s=round(da, 5) if math.isfinite(da) else "inf",
                           pays=da < C,
                           benefit_m=round(rho_u - rho_a, 3) if math.isfinite(rho_a) else "-inf",
                           rho_u_m=round(rho_u, 3),
                           rho_a_m=round(rho_a, 3) if math.isfinite(rho_a) else "inf",
                           theta_cross_s=round(theta_cross, 4) if math.isfinite(theta_cross) else "inf")
                for m in MARGINS:
                    B = m / (sc.gamma_a * E) - d
                    row[f"B_m{int(m)}_s"] = round(B, 4)
                    row[f"cert_u_m{int(m)}"] = rho_u <= m
                    row[f"cert_a_m{int(m)}"] = rho_a <= m
                out.append(row)
    write("crossover.csv", out)

    curves = []
    k = 0
    th = 0.1
    while th <= 10.0 + 1e-9:
        d = delta_theta(th)
        row = dict(theta=round(th, 5), delta=round(d, 5))
        for sc in GAMMA_SCENARIOS:
            row[f"C_{sc.name}"] = round(d * (sc.ratio - 1), 5)
            row[f"B10_{sc.name}"] = round(10 / (sc.gamma_a * E) - d, 5)
        curves.append(row)
        k += 1
        th = 0.1 * 10 ** (k / 40)
    write("crossover_curves.csv", curves)
    return out


# --------------------------------------------------------------------------
# Horizon-matched crossover (time-varying gamma)
# --------------------------------------------------------------------------

def envelope(flight, source="ekf"):
    """Running maximum of the error accrued since onset, as a function of
    staleness: delta(tau) = sup_{tau' <= tau} [e(tau') - e(onset)]. Linear
    interpolation between samples, delta(0) = 0."""
    rows = [r for r in load_samples() if r["flight"] == flight and r["source"] == source]
    pts = sorted((float(r["staleness_s"]), float(r["err_m"]) - float(r["err_at_onset_m"]))
                 for r in rows)
    env, m = [(0.0, 0.0)], 0.0
    for t, e in pts:
        m = max(m, e)
        env.append((t, m))
    def f(tau):
        if tau <= 0:
            return 0.0
        for (t0, e0), (t1, e1) in zip(env[:-1], env[1:]):
            if t0 <= tau <= t1:
                return e0 + (e1 - e0) * (tau - t0) / (t1 - t0) if t1 > t0 else e1
        return env[-1][1]
    return f, env[-1][0]


def horizon_matched(rows):
    du, tu = envelope("gps_spoofing")
    da, ta = envelope("gps_jamming")
    out, curve = [], []
    th = 0.1
    k = 0
    while th <= 5.0 + 1e-9:
        d = delta_theta(th)
        curve.append(dict(theta=round(th, 4), delta=round(d, 4),
                          du=round(du(d), 4), da=round(da(d), 4)))
        k += 1
        th = 0.1 * 10 ** (k / 40)
    write("horizon_envelopes.csv", curve)
    for r in rows:
        if r["transport"] not in ("can", "canfd"):
            continue
        dauth = r["dauth_cert_ms"]
        if dauth == "inf":
            continue
        dauth /= 1e3
        # smallest theta on a fine grid at which authentication pays
        theta_cross = None
        for i in range(1, 5001):
            th = i * 0.001
            d = delta_theta(th)
            if d + dauth > min(tu, ta):
                break
            if da(d + dauth) < du(d):
                theta_cross = th
                break
        for th in (THETA_BENIGN, THETA_OP, 0.5, 1.0, 2.0):
            d = delta_theta(th)
            gain = (du(d) - da(d + dauth)) * E
            out.append(dict(transport=r["transport"], scheme=r["scheme"],
                            dauth_cert_ms=round(dauth * 1e3, 2), theta=th, delta=d,
                            delta_u_m=round(du(d), 3), delta_a_m=round(da(d + dauth), 3),
                            benefit_tube_m=round(gain, 3), pays=gain > 0,
                            theta_cross_s=round(theta_cross, 3) if theta_cross else "none<=5"))
    write("horizon_crossover.csv", out)


def parent_table():
    """Re-derive the proposal's Section 4 table and the authenticated m_min."""
    gu = 1.625
    rows = []
    d = delta_theta(THETA_OP)
    for m in MARGINS:
        th_star = m / (gu * E * H)
        rows.append(dict(m=m, theta_star_s=round(th_star, 3),
                         certified_at_0p25=d * gu * E <= m,
                         B_noauthgain_s=round(m / (gu * E) - d, 3)))
    rows.append(dict(m="gamma_req@10", theta_star_s=round(10 / (d * E), 3),
                     certified_at_0p25="", B_noauthgain_s=""))
    rows.append(dict(m="m_min_unauth", theta_star_s=round(d * gu * E, 3),
                     certified_at_0p25="", B_noauthgain_s=""))
    write("parent_table.csv", rows)


def main():
    g, fit = gamma_side()
    for r in g:
        print(r)
    print(fit)
    rows = dauth_rows()
    for r in rows:
        if r["transport"] == "can":
            print({k: r[k] for k in ("scheme", "t_sign_ms", "R_tx_ms", "t_verify_ms",
                                     "t_proto_ms", "dauth_ms", "dauth_cert_ms")})
    crossover(rows)
    horizon_matched(rows)
    parent_table()


if __name__ == "__main__":
    main()
