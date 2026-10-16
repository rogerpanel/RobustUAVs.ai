"""Admissible-set construction (new in Paper V).

Tightening for aircraft i at prediction node k of a plan created at time s:

  beta_i[k] = rhotilde_i((k+1) Ts) + b_tot + eps_p((k+1) Ts) + bulge         k < Np
  beta_i[Np] = rho_bar + b_tot + eps_p(inf)                                  (loiter terminal set)

  rhotilde_i(tau) = min( max(rho_i(s), rho_floor) + L_rho * tau , rho_bar )   (Paper III Thm 3 look-ahead;
        valid under A2: growth <= L_rho between re-anchors, re-anchor resets to <= rho_floor, cap rho_bar)
  eps_p(n dt) = w_bar * sum_{j<n} |[1 0] Phi^j B|        (tube of the tube controller u = v + K(x - z))
  bulge = u_nom Ts^2 / 8                                  (inter-node chord deviation of the nominal)

A halfspace a^T p <= c becomes a^T z_k <= c - ||a||_1 beta[k] (box error sets);
separation n^T (z_i - z_j) >= d_sep + ||n||_1 (beta_i + beta_j), which implies ||p_i - p_j|| >= d_sep.
Speeds |z_v| <= v_max - eps_v; nominal accel |v| <= u_max - eps_u(inf).
Everything here is monotone non-decreasing in (b_tot, rho, w_bar) -> nestedness.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import ConvexHull, HalfspaceIntersection

from constants import (DT, TS, SUB, NP, U_MAX, V_MAX, KP, KD, W_BAR_NOM, rho_floor, rho_bar,
                       kappa_rho, GAMMA_SUP, DELTA_BAR_S)
from plant import di_matrices


def tube_sequences(w_bar, n_max=4000, kp=KP, kd=KD):
    """Per-axis bounds after n inner steps of the error system xi+ = Phi xi + B d, |d|<=w_bar."""
    A, B = di_matrices(DT)
    K = np.array([[-kp, -kd]])
    Phi = A + B @ K
    ep, ev, eu = [0.0], [0.0], [0.0]
    M = B.copy()
    sp = sv = su = 0.0
    for _ in range(n_max):
        sp += abs(M[0, 0]); sv += abs(M[1, 0]); su += abs((K @ M)[0, 0])
        ep.append(w_bar * sp); ev.append(w_bar * sv); eu.append(w_bar * su)
        M = Phi @ M
    rad = max(abs(np.linalg.eigvals(Phi)))
    return np.array(ep), np.array(ev), np.array(eu), rad


@dataclass
class TighteningConfig:
    w_bar: float = W_BAR_NOM
    b_tot: float = 0.0
    gamma: float = GAMMA_SUP
    delta_bar: float = DELTA_BAR_S
    lookahead: bool = True

    def __post_init__(self):
        self.ep, self.ev, self.eu, self.spec_rad = tube_sequences(self.w_bar)
        self.L_rho = kappa_rho(self.gamma)
        self.rho_floor = rho_floor(self.gamma)
        self.rho_bar = rho_bar(self.gamma, self.delta_bar)
        self.u_nom = U_MAX - self.eu[-1]
        self.bulge = max(self.u_nom, 0.0) * TS * TS / 8.0
        k = np.arange(1, NP + 1)
        self.ep_k = self.ep[k * SUB]                   # eps at end of each interval
        self.ep_inf, self.ev_inf = self.ep[-1], self.ev[-1]

    def _ep_at(self, idx):
        return self.ep[np.minimum(idx, len(self.ep) - 1)]

    def beta(self, rho_now, age=0):
        """rho_now (N,) -> beta (N, Np+1). age = inner steps since the error tube was last
        re-anchored (0 for a plan started from the navigation state; >0 for a continuation
        plan started from the latched nominal)."""
        rho_now = np.asarray(rho_now, float)
        tau = np.arange(1, NP + 1) * TS
        if self.lookahead:
            rt = np.minimum(np.maximum(rho_now, self.rho_floor)[:, None] + self.L_rho * tau[None, :], self.rho_bar)
            rt = np.maximum(rt, rho_now[:, None])     # never below the current certificate
        else:                                        # ablation: no look-ahead (current rho only)
            rt = np.repeat(rho_now[:, None], NP, 1)
        ep_k = self._ep_at(age + np.arange(1, NP + 1) * SUB)
        b = rt + self.b_tot + ep_k[None, :] + self.bulge
        bterm = np.maximum(self.rho_bar, rho_now) + self.b_tot + self.ep_inf + self.bulge
        return np.concatenate([b, bterm[:, None]], 1)

    def vlim(self, age=0):
        """Per node 0..Np nominal speed bound (node Np is the terminal v=0 anyway)."""
        idx = np.minimum(age + (np.minimum(np.arange(NP + 1) + 1, NP)) * SUB, len(self.ev) - 1)
        return V_MAX - self.ev[idx]

    def summary(self):
        return dict(w_bar=self.w_bar, b_tot=self.b_tot, gamma=self.gamma, L_rho=self.L_rho,
                    rho_floor=self.rho_floor, rho_bar=self.rho_bar, eps_p_inf=self.ep_inf,
                    eps_v_inf=self.ev_inf, eps_u_inf=self.eu[-1], u_nom=self.u_nom, bulge=self.bulge,
                    spectral_radius=self.spec_rad, beta_terminal=self.rho_bar + self.b_tot + self.ep_inf + self.bulge)


def tightened_area(geo, beta):
    """Area of the keep-in polytope shrunk by beta (box error): {p : a^T p <= c - ||a||_1 beta}."""
    l1 = np.abs(geo.H).sum(1)
    cc = geo.c - l1 * beta
    hs = np.hstack([geo.H, -cc[:, None]])            # A x + b <= 0 form
    # interior point: centre of mass of starts/goals, check feasibility
    pt = np.array([np.mean(geo.c[:2] * [1, -1]) * 0 + (geo.c[0] - geo.c[1]) / 2.0, 0.0])
    if np.any(geo.H @ pt - cc >= -1e-9):
        return 0.0
    try:
        hi = HalfspaceIntersection(hs, pt)
        return float(ConvexHull(hi.intersections).volume)
    except Exception:
        return 0.0
