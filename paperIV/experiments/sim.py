"""Vectorised lateral closed-loop simulator for the Paper IV pilot.

One rollout = one 60 s mission of a small multirotor holding its lateral
(cross-track) position inside a corridor while it cruises. The lateral channel
is a drag-damped double integrator under PD control on the *estimated* state;
the estimator is a 3-state Kalman filter [p, v, b_acc] driven by the
accelerometer and corrected by GNSS (10 Hz) and, under condition C2', by a
trusted re-anchoring fix every T_ANCHOR seconds.

Perturbation sources (each can be switched on/off without changing the random
number stream, so that runs with different source sets share realisations and
superposition can be tested exactly):
  env    Dryden lateral turbulence (MIL-F-8785C, low altitude), acts on the
         airframe through drag; the accelerometer measures it.
  gnss   white noise + Gauss-Markov drift + outages + jamming-noise episodes.
  fault  accelerometer bias step / bias-drift faults + actuator loss of
         effectiveness; accelerometer white noise and nominal bias walk.
  attack an additive GNSS position offset d(t) from one of five disguise
         families (see ATTACK_FAMILIES).

Four detectors observe only O = (GNSS fixes, accelerometer, commands, anchor):
  D1 SIG   signature/rule monitor: GNSS jump between consecutive fixes.
  D2 CHI2  PX4-class innovation gate: NIS above gate for 3 consecutive fixes;
           plus an anchor gate on the trusted fix.
  D3 SAV   SAVIOR-style model-based residual CUSUM: an observer driven by the
           commanded acceleration with a no-wind model, corrected by GNSS.
  D4 INV   IMU-GNSS kinematic invariant: quadratic fit of the GNSS-minus-
           double-integrated-IMU residual over 4 s; alarms on the curvature
           (an acceleration discrepancy) for 5 consecutive fixes.
Each detector reports one per-rollout statistic S_D; it alarms iff S_D > theta_D.
The anchor gate (statistic SA) is calibrated separately and added to every
stack whenever condition C2' holds.
"""
from __future__ import annotations

import os

import numpy as np
from scipy.linalg import solve_discrete_lyapunov

from constants import *  # noqa: F401,F403

ATTACK_FAMILIES = ("none", "step", "ramp", "fault_mimic", "gnss_mimic", "weather_mimic")
# parameter boxes, each parameter mapped from [0,1]
ATTACK_BOX = {
    "step":          [("amp", 0.0, 20.0), ("t0", 10.0, 40.0)],
    "ramp":          [("rate", 0.0, 2.0), ("t0", 10.0, 40.0), ("cap", 0.0, 40.0)],
    "fault_mimic":   [("beta0", 0.0, 0.5), ("sig_beta", 0.0, 0.05), ("t0", 10.0, 40.0),
                      ("cap", 0.0, 40.0)],
    "gnss_mimic":    [("amp", 0.0, 20.0), ("tau", 5.0, 120.0), ("t0", 10.0, 40.0),
                      ("slope", 0.0, 0.5)],
    "weather_mimic": [("amp", 0.0, 20.0), ("lag_s", 0.0, 10.0), ("t0", 10.0, 40.0),
                      ("bias", 0.0, 10.0)],
}


def decode(family, u):
    """Map u in [0,1]^k to the named physical parameters."""
    u = np.clip(np.asarray(u, float), 0.0, 1.0)
    return {name: lo + (hi - lo) * u[..., i] for i, (name, lo, hi) in enumerate(ATTACK_BOX[family])}


def _dryden_ss(w20_kt, dt):
    sig, L = dryden_lateral(w20_kt)
    tau = L / V_AIR
    a = np.exp(-dt / tau)
    A = np.array([[a, 0.0], [1 - a, a]])
    B = np.array([[1 - a], [0.0]])
    C = np.array([[np.sqrt(3.0), 1 - np.sqrt(3.0)]])
    Pss = solve_discrete_lyapunov(A, B @ B.T)
    var = float((C @ Pss @ C.T)[0, 0])
    return A, B, C, sig / np.sqrt(var), Pss, sig


def _inv_weights(n, dt_g):
    """Least-squares row that returns the 2nd derivative of a quadratic fit."""
    t = (np.arange(n) - (n - 1) / 2.0) * dt_g
    X = np.stack([np.ones(n), t, 0.5 * t * t], 1)
    return np.linalg.pinv(X)[2]


def simulate(N, seed, *, w20=None, gnss=True, fault=True, attack="none",
             aparams=None, attack_seed=None, anchor=T_ANCHOR, env_on=True,
             w20_attacker=W20_KT["moderate"], terminal=True, noise=True):
    """Run N rollouts. Returns a dict of per-rollout arrays.

    w20     : scalar or (N,) array of W20 in knots for the airframe wind
              (None -> moderate); env_on=False removes wind from the airframe
              while keeping the realisation (the weather-mimic attacker still
              sees it).
    aparams : dict of (N,) or scalar physical attack parameters (see decode).
    anchor  : re-anchoring interval in s, or None to violate C2'.
    terminal: close the final interval with a trusted fix (C2'); False leaves
              the last segment before mission end unchecked (ablation E2c).
    noise   : False zeroes every *additive* benign input (wind force, GNSS
              white/Gauss-Markov/jamming noise, IMU noise and bias, anchor noise)
              while keeping the *parametric* ones (GNSS outage schedule, actuator
              LoE, anchor schedule). Used for the attack-only counterfactual, so
              that the superposition of Lemma 2 is tested on the same
              time-varying system.
    """
    _cf = os.environ.get("P4_COUNT_FILE")
    if _cf:                                   # runtime mission counter (all processes)
        with open(_cf, "a") as _fh:
            _fh.write(f"{N}\n")
    rng = np.random.default_rng(seed)
    arng = np.random.default_rng(10_000_019 + seed if attack_seed is None else attack_seed)
    dt, g_every = DT, GNSS_EVERY
    dtg = dt * g_every
    aparams = aparams or {}
    bc = lambda x: np.broadcast_to(np.asarray(x, float), (N,)).copy()

    # -- wind: per-rollout W20 -> per-rollout scaling; one shared filter shape
    w20a = bc(W20_KT["moderate"] if w20 is None else w20)
    A_w, B_w, C_w, scale0, Pss, _ = _dryden_ss(W20_KT["moderate"], dt)
    sig_mod = dryden_lateral(W20_KT["moderate"])[0]
    sig_roll = np.array([dryden_lateral(x)[0] for x in w20a]) if np.ndim(w20) else \
        np.full(N, dryden_lateral(float(w20a[0]))[0])
    gain_w = scale0 * sig_roll / sig_mod
    xw = rng.multivariate_normal(np.zeros(2), Pss, size=N)  # stationary init (unit)

    # -- benign fault draws
    bias_step_on = rng.random(N) < P_BIAS_STEP
    bias_step_t = rng.uniform(5, 55, N)
    bias_step_mag = rng.normal(0, BIAS_STEP_SD, N)
    drift_on = rng.random(N) < P_BIAS_DRIFT
    loe_on = rng.random(N) < P_LOE
    loe_t = rng.uniform(5, 55, N)
    loe_mag = rng.uniform(*LOE_RANGE, N)
    out_on = rng.random(N) < P_OUTAGE
    out_t = rng.uniform(5, 50, N)
    out_d = rng.exponential(OUTAGE_MEAN_S, N)
    jam_on = rng.random(N) < P_JAMNOISE
    jam_t = rng.uniform(5, 50, N)
    phi_gm = np.exp(-dtg / GM_TAU)
    e_gm = rng.normal(0, GM_SIGMA, N)
    b_true = rng.normal(0, 0.02, N)

    # -- attack setup
    fam = attack
    P = {k: bc(v) for k, v in aparams.items()}
    t0 = P.get("t0", np.full(N, np.inf))
    d = np.zeros(N); dd = np.zeros(N); beta = np.zeros(N)
    gm_a = np.zeros(N)
    if fam == "gnss_mimic":
        phi_a = np.exp(-dtg / np.maximum(P["tau"], 1e-3))
    if fam == "weather_mimic":
        lag_steps = np.round(P["lag_s"] / dt).astype(int)
        wbuf = np.zeros((N, int(10.0 / dt) + 2))

    # -- state
    p = np.zeros(N); v = np.zeros(N)
    xh = np.zeros((N, 3))
    Pk = np.zeros((N, 3, 3)); Pk[:, 0, 0] = 1.0; Pk[:, 1, 1] = 0.1; Pk[:, 2, 2] = 0.02 ** 2
    F = np.array([[1, dt, -0.5 * dt * dt], [0, 1, -dt], [0, 0, 1]])
    Bu = np.array([0.5 * dt * dt, dt, 0.0])
    Q = np.diag([0.25 * dt ** 4 * KF_QV, dt * dt * KF_QV, dt * KF_QB])
    # D3 observer
    po = np.zeros(N); vo = np.zeros(N); g3 = np.zeros(N)
    # D4 buffers
    n_inv = int(round(INV_WINDOW_S / dtg))
    w_inv = _inv_weights(n_inv, dtg)
    rho_buf = np.zeros((N, n_inv)); fill = np.zeros(N, int)
    vi = np.zeros(N); pi = np.zeros(N)
    inv_run = np.zeros(N, int)
    # stats
    S1 = np.zeros(N); S2 = np.zeros(N); S3 = np.zeros(N); S4 = np.zeros(N); SA = np.zeros(N)
    nis_buf = np.full((N, CONSEC_CHI2), 0.0); nis_fill = np.zeros(N, int)
    c2_run_min = np.full((N, CONSEC_INV), 0.0)
    z_prev = np.full(N, np.nan)
    maxdev = np.zeros(N); maxdev_after = np.zeros(N)
    first_alarm = {}

    anchor_every = None if anchor is None else int(round(anchor / dt))
    for k in range(N_STEPS):
        t = k * dt
        # ---------- random draws (always, to keep streams aligned)
        n_w = rng.normal(size=N); n_acc = rng.normal(size=N); n_b = rng.normal(size=N)
        n_g = rng.normal(size=N); n_gm = rng.normal(size=N); n_a = rng.normal(size=N)
        na1 = arng.normal(size=N)
        # ---------- wind
        xw = xw @ A_w.T + np.outer(n_w, B_w[:, 0])
        w = gain_w * (xw @ C_w[0])
        w_air = w if (env_on and noise) else 0.0
        # ---------- controller on the estimate
        u_cmd = np.clip(-KP * xh[:, 0] - KD * xh[:, 1], -U_MAX, U_MAX)
        u_act = u_cmd * np.where(fault & loe_on & (t >= loe_t), 1.0 - loe_mag, 1.0)
        a = u_act + C_DRAG * (w_air - v)
        v = v + a * dt
        p = p + v * dt
        # ---------- IMU
        if fault and noise:
            sig_rw = SIG_BIAS_RW * np.where(drift_on, BIAS_DRIFT_MULT, 1.0)
            b_true = b_true + sig_rw * np.sqrt(dt) * n_b
            step_now = bias_step_on & (np.abs(t - bias_step_t) < dt / 2)
            b_true = b_true + np.where(step_now, bias_step_mag, 0.0)
            a_m = a + b_true + SIG_ACC * n_acc
        else:
            a_m = a.copy()
        # ---------- KF propagate
        xh = xh @ F.T + np.outer(a_m, Bu)
        Pk = F @ Pk @ F.T + Q
        # ---------- D3 observer propagate (commanded accel, no-wind model)
        vo = vo + (u_cmd - C_DRAG * vo) * dt
        po = po + vo * dt
        # ---------- D4 integrator
        vi = vi + a_m * dt; pi = pi + vi * dt
        # ---------- attack offset
        on = t >= t0
        if fam == "step":
            d = np.where(on, P["amp"], 0.0)
        elif fam == "ramp":
            d = np.where(on, np.minimum(P["rate"] * (t - t0), P["cap"]), 0.0)
        elif fam == "fault_mimic":
            beta = beta + P["sig_beta"] * np.sqrt(dt) * na1
            acc = np.where(on, P["beta0"] + beta, 0.0)
            dd = dd + acc * dt
            d = np.minimum(np.where(on, d + dd * dt, 0.0), P["cap"])
            dd = np.where(d >= P["cap"], 0.0, dd)
        elif fam == "gnss_mimic":
            if k % g_every == 0:
                gm_a = phi_a * gm_a + np.sqrt(1 - phi_a ** 2) * na1
            d = np.where(on, P["amp"] * np.abs(gm_a) + P["slope"] * np.maximum(t - t0, 0), 0.0)
        elif fam == "weather_mimic":
            wbuf = np.roll(wbuf, 1, axis=1); wbuf[:, 0] = w
            wl = wbuf[np.arange(N), np.minimum(lag_steps, wbuf.shape[1] - 1)]
            d = np.where(on, P["amp"] * wl / max(sig_mod, 1e-6) + P["bias"] *
                         np.minimum((t - t0) / 10.0, 1.0), 0.0)
        # ---------- GNSS epoch
        if k % g_every == 0:
            outage = gnss & out_on & (t >= out_t) & (t < out_t + out_d)
            valid = ~outage
            sg = SIG_GNSS_WHITE * np.where(gnss & jam_on & (t >= jam_t) & (t < jam_t + JAMNOISE_S),
                                           JAMNOISE_MULT, 1.0)
            if gnss and noise:
                e_gm = phi_gm * e_gm + np.sqrt(1 - phi_gm ** 2) * GM_SIGMA * n_gm
                z = p + e_gm + sg * n_g + d
            else:
                z = p + d
            # D1 jump
            jump = np.abs(z - z_prev)
            S1 = np.where(valid & ~np.isnan(jump), np.maximum(S1, np.nan_to_num(jump)), S1)
            z_prev = np.where(valid, z, np.nan)
            # KF update (masked)
            nu = z - xh[:, 0]
            S = Pk[:, 0, 0] + KF_R
            nis = nu * nu / S
            K = Pk[:, :, 0] / S[:, None]
            m = valid[:, None]
            xh = xh + np.where(m, K * nu[:, None], 0.0)
            Pk = Pk - np.where(m[:, :, None], K[:, :, None] * Pk[:, 0, :][:, None, :], 0.0)
            # D2 consecutive gate
            nis_buf = np.where(m, np.concatenate([nis_buf[:, 1:], nis[:, None]], 1), nis_buf)
            nis_fill = np.where(valid, nis_fill + 1, nis_fill)
            S2 = np.where(valid & (nis_fill >= CONSEC_CHI2), np.maximum(S2, nis_buf.min(1)), S2)
            # D3 observer residual + CUSUM, then correction
            r3 = z - po
            g3 = np.where(valid, np.maximum(0.0, g3 + r3 * r3 / 1.0 - (1.0 + CUSUM_KAPPA)), g3)
            S3 = np.maximum(S3, g3)
            po = np.where(valid, po + 0.3 * r3, po); vo = np.where(valid, vo + 0.2 * r3 / dtg, vo)
            # D4 invariant
            rho = z - pi
            rho_buf = np.where(m, np.concatenate([rho_buf[:, 1:], rho[:, None]], 1), rho_buf)
            fill = np.where(valid, fill + 1, 0)
            c2 = np.abs(rho_buf @ w_inv)
            c2 = np.where(fill >= n_inv, c2, 0.0)
            c2_run_min = np.where(m, np.concatenate([c2_run_min[:, 1:], c2[:, None]], 1), 0.0)
            S4 = np.maximum(S4, c2_run_min.min(1))
        # ---------- anchor (trusted, uncorrupted)
        # C2': every interval is closed by a trusted fix, including the last one
        if anchor_every and k > 0 and (k % anchor_every == 0 or (terminal and k == N_STEPS - 1)):
            y = p + (SIG_ANCHOR * n_a if noise else 0.0)
            nu = y - xh[:, 0]
            S = Pk[:, 0, 0] + SIG_ANCHOR ** 2
            SA = np.maximum(SA, nu * nu / S)
            K = Pk[:, :, 0] / S[:, None]
            xh = xh + K * nu[:, None]
            Pk = Pk - K[:, :, None] * Pk[:, 0, :][:, None, :]
        ap = np.abs(p)
        maxdev = np.maximum(maxdev, ap)
        maxdev_after = np.where(t >= t0, np.maximum(maxdev_after, ap), maxdev_after)

    return {"maxdev": maxdev, "maxdev_after": maxdev_after,
            "S1": S1, "S2": S2, "S3": S3, "S4": S4, "SA": SA}


DETECTORS = ("D1", "D2", "D3", "D4")


def alarms(out, th, stack):
    """Boolean alarm per rollout for a detector stack, e.g. ('D2','D4').
    D2 always carries the anchor gate."""
    a = np.zeros_like(out["S1"], bool)
    for d in stack:
        a |= out["S" + d[1]] > th[d]
    return a
