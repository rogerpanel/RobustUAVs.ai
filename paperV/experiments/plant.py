"""Seeded, controllable fleet plant for Paper V.

Per aircraft a planar double integrator at DT (exact zero-order-hold discretisation):
    x = (px, py, vx, vy),   x+ = A x + B sat(u) + B d,   |d|_inf <= w_true   (accel mismatch)
The navigation state x is what the control loop closes on. The TRUE position is
    p_true = p + e,   e = e_cert + e_adv,  |e_cert|_inf <= rho_i(t),  |e_adv|_inf <= b_adv
(separation of estimation and control: the certificate error and the covert sensing
offset enter the safety check, not the dynamics -- the additive-tightening model of the
Paper V plan, matching Paper IV's delta_adv semantics as a sup true deviation).

All randomness flows from numpy Generators derived from one episode seed (CRN).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from constants import (DT, U_MAX, V_MAX, LANE, GOAL_X, D_SEP, residual_pools, kappa_rho,
                       DELTA_BAR_S, GAMMA_SUP)


def di_matrices(h):
    """Per-axis double integrator, ZOH with step h. State (p, v)."""
    A = np.array([[1.0, h], [0.0, 1.0]])
    B = np.array([[0.5 * h * h], [h]])
    return A, B


# ---------------------------------------------------------------- geometry
@dataclass
class Geometry:
    N: int
    H: np.ndarray            # (nh, 2) unit outward normals
    c: np.ndarray            # (nh,)    a^T p <= c
    starts: np.ndarray       # (N, 2)
    goals: np.ndarray        # (N, 2)
    speeds: np.ndarray       # (N,) benign cruise speeds

    def slack(self, P):
        """(N, nh) signed slack c - a^T p  (>=0 inside)."""
        return self.c[None, :] - P @ self.H.T


def make_geometry(N, cruise=10.0, cruise_slow=8.5):
    ys = (np.arange(N) - (N - 1) / 2.0) * LANE
    half = (N - 1) / 2.0 * LANE + 30.0
    x_lo, x_hi = -30.0, GOAL_X + 60.0
    cham = 20.0
    s2 = np.sqrt(0.5)
    H = np.array([[1, 0], [-1, 0], [0, 1], [0, -1], [s2, s2], [s2, -s2]], float)
    c = np.array([x_hi, -x_lo, half, half, s2 * (x_hi + half - cham), s2 * (x_hi + half - cham)])
    starts = np.stack([np.zeros(N), ys], 1)
    perm = np.arange(N)
    for i in range(0, N - 1, 2):          # pairwise lane swap -> crossing traffic
        perm[i], perm[i + 1] = i + 1, i
    goals = np.stack([np.full(N, GOAL_X), ys[perm]], 1)
    speeds = np.where(np.arange(N) % 2 == 0, cruise, cruise_slow)
    return Geometry(N, H, c, starts, goals, speeds)


# ---------------------------------------------------------------- certificate process
class RhoProcess:
    """Paper III-style protection-level generator rho_i(t) = L_rho * staleness.

    staleness = benign residual + dead-reckoning clock + relay offset   (Paper III
    CertificateProcess, rates from ThreatProfile). within=True enforces assumption (A2):
    staleness capped at DELTA_BAR (rho <= rho_bar) and no relay jumps (J=0). within=False
    is the negative control: Paper III defaults (10 s cap, relay jumps from the
    hidden-residual pool) -- outside the theorem's scope.
    """

    def __init__(self, N, rng, gamma=GAMMA_SUP, within=True, delta_bar=DELTA_BAR_S,
                 jam_rate=0.010, jam_mean=6.0, relay_rate=0.010, relay_mean=10.0,
                 fault_rate=0.002, fault_mean=4.0, reanchor=2.0, stale_cap=10.0, rate_mult=1.0):
        self.N, self.rng, self.within = N, rng, within
        self.kap = kappa_rho(gamma)
        self.ben, self.hid = residual_pools()
        self.benign = rng.choice(self.ben, N)
        self.dr = np.zeros(N); self.relay = np.zeros(N)
        self.jam_left = np.zeros(N); self.fault_left = np.zeros(N)
        self.relay_left = np.zeros(N); self.reanchor_left = np.zeros(N)
        self.p = dict(jam_rate=jam_rate * rate_mult, jam_mean=jam_mean, relay_rate=relay_rate * rate_mult,
                      relay_mean=relay_mean, fault_rate=fault_rate * rate_mult, fault_mean=fault_mean,
                      reanchor=reanchor)
        self.cap = delta_bar if within else stale_cap
        self.n_jumps = 0

    def rho(self):
        return self.kap * (self.benign + self.dr + self.relay)

    def step(self, dt):
        p, rng, N = self.p, self.rng, self.N
        u = rng.random((4, N))
        jon = (u[0] < p["jam_rate"] * dt) & (self.jam_left <= 0)
        self.jam_left[jon] = rng.exponential(p["jam_mean"], int(jon.sum()))
        fon = (u[1] < p["fault_rate"] * dt) & (self.fault_left <= 0)
        self.fault_left[fon] = rng.exponential(p["fault_mean"], int(fon.sum()))
        if not self.within:
            ron = (u[2] < p["relay_rate"] * dt) & (self.relay_left <= 0)
            if ron.any():
                k = int(ron.sum())
                self.relay[ron] = rng.choice(self.hid, size=(k, 2)).sum(1)
                self.relay_left[ron] = rng.exponential(p["relay_mean"], k)
                self.n_jumps += k
        deg = (self.jam_left > 0) | (self.fault_left > 0)
        cap_dr = np.maximum(self.cap - self.benign - self.relay, 0.0) if self.within else self.cap
        was = self.dr > 0
        self.dr = np.where(deg, np.minimum(self.dr + dt, cap_dr), self.dr)
        ended = was & ~deg & (self.reanchor_left <= 0)
        self.reanchor_left = np.where(ended, p["reanchor"], self.reanchor_left)
        self.reanchor_left = np.where(deg, 0.0, self.reanchor_left)
        rel = (self.reanchor_left > 0) & ~deg
        self.reanchor_left = np.where(rel, self.reanchor_left - dt, self.reanchor_left)
        done = rel & (self.reanchor_left <= 0)
        if done.any():
            self.dr[done] = 0.0
            self.benign[done] = rng.choice(self.ben, int(done.sum()))
        self.relay_left = np.maximum(self.relay_left - dt, 0.0)
        self.relay = np.where(self.relay_left > 0, self.relay, 0.0)
        self.jam_left = np.maximum(self.jam_left - dt, 0.0)
        self.fault_left = np.maximum(self.fault_left - dt, 0.0)
        return self.rho()


# ---------------------------------------------------------------- nature (disturbance + estimate error)
def outward_dirs(geo: Geometry, P):
    """Per aircraft: unit direction of its most binding constraint (wall normal or
    toward the nearest neighbour), from the navigation positions P (N,2)."""
    N = P.shape[0]
    sl = geo.slack(P)
    jw = sl.argmin(1)
    dirs = geo.H[jw].copy()
    best = sl[np.arange(N), jw]
    if N > 1:
        D = P[None, :, :] - P[:, None, :]           # D[i,j] = p_j - p_i
        dist = np.linalg.norm(D, axis=2) + np.eye(N) * 1e9
        jn = dist.argmin(1)
        dn = dist[np.arange(N), jn]
        half_slack = 0.5 * (dn - D_SEP)
        use = half_slack < best
        nv = D[np.arange(N), jn] / np.maximum(dn[:, None], 1e-9)
        dirs[use] = nv[use]
    return dirs


class Nature:
    """Mismatch disturbance d and estimate offset e for the whole fleet.

    mode 'random': Gauss-Markov gust accel (tau 2 s) clipped at w_true; e uniform in box.
    mode 'adversarial': d = w_true*sign(outward), e = (rho+b_adv)*sign(outward) -- the
       box-worst case, which is exactly what the ||a||_1-scaled tightening covers.
    mode 'zero': no disturbance, e = 0.
    """

    def __init__(self, N, rng, mode, w_true, b_adv):
        self.N, self.rng, self.mode, self.w, self.b = N, rng, mode, w_true, b_adv
        self.g = np.zeros((N, 2))

    def disturbance(self, geo, P):
        if self.mode == "zero" or self.w == 0:
            return np.zeros((self.N, 2))
        if self.mode == "adversarial":
            return self.w * np.sign(outward_dirs(geo, P))
        a = np.exp(-DT / 2.0)
        self.g = a * self.g + np.sqrt(1 - a * a) * self.rng.standard_normal((self.N, 2)) * (0.6 * self.w)
        return np.clip(self.g, -self.w, self.w)

    def offset(self, geo, P, rho):
        if self.mode == "zero":
            return np.zeros((self.N, 2))
        mag = rho + self.b
        if self.mode == "adversarial":
            return mag[:, None] * np.sign(outward_dirs(geo, P))
        return self.rng.uniform(-1, 1, (self.N, 2)) * mag[:, None]


# ---------------------------------------------------------------- violation check
def check_true(geo: Geometry, Ptrue):
    """Return per-aircraft (corridor_violation, separation_violation, corridor_margin, sep_margin)."""
    sl = geo.slack(Ptrue).min(1)
    N = Ptrue.shape[0]
    if N > 1:
        D = np.linalg.norm(Ptrue[None] - Ptrue[:, None], axis=2) + np.eye(N) * 1e9
        dmin = D.min(1)
    else:
        dmin = np.full(N, np.inf)
    return sl < 0.0, dmin < D_SEP, sl, dmin - D_SEP


def plant_step(X, U, d):
    """X (N,4) [px,py,vx,vy]; U actuator command (N,2) (saturated here); d (N,2)."""
    Us = np.clip(U, -U_MAX, U_MAX)
    a = Us + d
    P = X[:, :2] + DT * X[:, 2:] + 0.5 * DT * DT * a
    V = X[:, 2:] + DT * a
    return np.concatenate([P, V], 1), Us
