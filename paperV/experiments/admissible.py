"""Admissible set, tightening, terminal set and the independent plan checker (runbook P1.1).

Per aircraft and per axis (along-track s, lateral l) the nominal model is the ZOH double
integrator at DT. A plan from the estimate z_0 = x_hat is a sequence of nominal inputs
v_0..v_{N_P-1}; the tube controller u = v_k + K (x_hat - z_k) keeps the estimate within
eps_k of node k when |w| <= w_bar (Limon tube). Node k is constrained by

    beta_k = rho~_k + eps_k + b_tot,    rho~_k = min(max(rho, rho_floor) + L_rho k DT, rho_bar)

(the Paper III Thm 3 look-ahead, saturated at the declared envelope rho_bar of (A2)), so the
TRUE position p_hat - e with |e| <= rho + b_tot stays inside the corridor. Inputs are
tightened to |v_k| <= U_MAX - eps_u(k) (eps_u(0) = 0: the first input may use the full U_MAX,
since a plan re-anchored at the estimate carries no tube error yet; the tube controller's feedback
|K (x_hat - z_k)| <= eps_u(k) then keeps every executed input within U_MAX), speeds to V_MAX - eps_v(k).
Braking in the terminal set uses u_nom = U_MAX - eps_u(inf).

Terminal set X_f (loiter) at node N_P, with braking deceleration a = u_nom and
beta_inf = max(rho_bar, rho) + eps_inf + b_tot. With c the tightened face:
    s + k_s v_s <= S_HI - beta_inf,  s <= S_HI - beta_inf,  and mirrored at S_LO,
    l + k_l v_l <= m - beta_inf,     l <= m - beta_inf,     and mirrored at -m,   |v_l| <= TERMINAL_V_LAT,
with k = v_cap / (2 a) + DT / 2 (chord of v^2/(2a) on [0, v_cap], plus the discrete-braking
overshoot). Braking at a from any state of X_f keeps the nominal in the tightened corridor
for all time, so X_f is robust invariant under the tube controller (tests/test_terminal.py).

check_plan never trusts the solver: it re-simulates the inputs and checks every row exactly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

try:
    from . import constants as C
except ImportError:
    import constants as C


def _phi(kp=C.KP, kd=C.KD, dt=C.DT):
    A = np.array([[1.0, dt], [0.0, 1.0]]); B = np.array([[0.5 * dt * dt], [dt]])
    K = np.array([[-kp, -kd]])
    return A, B, K, A + B @ K


def tube_sequences(w_bar, n=4000, kp=C.KP, kd=C.KD):
    """eps_p, eps_v, eps_u after k = 0..n steps of xi+ = Phi xi + B w, |w| <= w_bar (Limon)."""
    _, B, K, Phi = _phi(kp, kd)
    ep, ev, eu = np.zeros(n + 1), np.zeros(n + 1), np.zeros(n + 1)
    M = B.copy()
    sp = sv = su = 0.0
    for k in range(1, n + 1):
        sp += abs(M[0, 0]); sv += abs(M[1, 0]); su += abs((K @ M)[0, 0])
        ep[k], ev[k], eu[k] = w_bar * sp, w_bar * sv, w_bar * su
        M = Phi @ M
    return ep, ev, eu


def kohler_sequences(w_bar, n=4000, kp=C.KP, kd=C.KD):
    """Contraction-rate tube: |[1 0] Phi^j B| <= c lambda^j  =>  eps_k = c w_bar (1 - lambda^k)/(1 - lambda)."""
    _, B, K, Phi = _phi(kp, kd)
    lam = float(max(abs(np.linalg.eigvals(Phi))))
    lam = min(0.999, lam + 1e-3)
    out = []
    for row in (np.array([[1.0, 0.0]]), np.array([[0.0, 1.0]]), K):
        M = B.copy(); c = 0.0
        for j in range(n):
            c = max(c, abs((row @ M)[0, 0]) / lam ** j)
            M = Phi @ M
        k = np.arange(n + 1)
        out.append(c * w_bar * (1 - lam ** k) / (1 - lam))
    return out[0], out[1], out[2], lam


@dataclass
class Tightening:
    """Every tightening quantity for one cell. Monotone non-decreasing in (b_tot, rho, w_bar)."""
    w_bar: float
    b_tot: float = 0.0
    m: float = 10.0
    gamma: float = C.GAMMA_SUP
    L: float = C.L_LOC
    delta_bar: float = C.DELTA_BAR_S
    n_p: int = C.N_P
    tightening: str = "limon"          # none | limon | kohler
    lookahead: bool = True
    fixed_margin: bool = False         # baseline: Paper III rho_0 + L_rho * 1 s, constant over the horizon
    lam: float = field(default=float("nan"), init=False)

    def __post_init__(self):
        if self.tightening == "limon":
            self.ep, self.ev, self.eu = tube_sequences(self.w_bar)
        elif self.tightening == "kohler":
            self.ep, self.ev, self.eu, self.lam = kohler_sequences(self.w_bar)
        elif self.tightening == "none":
            z = np.zeros(4001); self.ep, self.ev, self.eu = z, z.copy(), z.copy()
        else:
            raise ValueError(self.tightening)
        self.L_rho = C.l_rho(self.gamma, self.L)
        self.rho_floor = C.rho_floor(self.gamma, self.L)
        self.rho_bar = C.rho_bar(self.gamma, self.L, self.delta_bar)
        self.u_nom = C.U_MAX - self.eu[-1]
        self.eps_inf = self.ep[-1]
        self.a_brake = self.u_nom
        if self.a_brake > 0:
            self.k_s = C.V_MAX / (2 * self.a_brake) + C.DT / 2
            self.k_l = C.TERMINAL_V_LAT / (2 * self.a_brake) + C.DT / 2
        else:
            self.k_s = self.k_l = np.inf

    # ---------------------------------------------------------------- per-node bounds
    def rho_tilde(self, rho):
        """(n,) current rho -> (n, n_p + 1) predicted protection level at nodes 0..n_p."""
        rho = np.asarray(rho, float)
        k = np.arange(self.n_p + 1)
        if self.fixed_margin:
            r = np.repeat((np.maximum(rho, self.rho_floor) + self.L_rho * 1.0)[:, None], self.n_p + 1, 1)
            return r
        if self.lookahead:
            r = np.minimum(np.maximum(rho, self.rho_floor)[:, None] + self.L_rho * k * C.DT, self.rho_bar)
            return np.maximum(r, rho[:, None])
        return np.repeat(rho[:, None], self.n_p + 1, 1)

    def beta(self, rho):
        """(n, n_p + 1) position tightening at nodes 0..n_p for a plan created now."""
        ep = self.ep[np.arange(self.n_p + 1)]
        return self.rho_tilde(rho) + ep[None, :] + self.b_tot

    def beta_inf(self, rho):
        rho = np.asarray(rho, float)
        if self.fixed_margin:
            return np.maximum(rho, self.rho_floor) + self.L_rho * 1.0 + self.eps_inf + self.b_tot
        r = np.maximum(self.rho_bar, rho) if self.lookahead else rho
        return r + self.eps_inf + self.b_tot

    def vlim(self):
        """(n_p + 1,) speed bound at nodes 0..n_p."""
        return C.V_MAX - self.ev[np.arange(self.n_p + 1)]

    def ulim(self):
        """(n_p,) input bound on v_0..v_{n_p-1}: U_MAX - eps_u(k)."""
        return C.U_MAX - self.eu[np.arange(self.n_p)]

    def half_width(self, rho=None):
        """Tightened terminal half-width m - beta_inf (dispatchable iff > 0)."""
        rho = np.asarray([self.rho_floor] if rho is None else rho, float)
        return self.m - self.beta_inf(rho)

    def summary(self):
        return dict(w_bar=self.w_bar, b_tot=self.b_tot, m=self.m, gamma=self.gamma, L=self.L,
                    delta_bar=self.delta_bar, tightening=self.tightening, lookahead=self.lookahead,
                    L_rho=self.L_rho, rho_floor=self.rho_floor, rho_bar=self.rho_bar,
                    eps_p_inf=self.eps_inf, eps_v_inf=self.ev[-1], eps_u_inf=self.eu[-1], u_nom=self.u_nom,
                    k_s=self.k_s, k_l=self.k_l,
                    beta_inf=float(self.beta_inf(np.array([self.rho_floor]))[0]),
                    half_width=float(self.half_width()[0]))


# ------------------------------------------------------------------ condensed per-axis model
def condensed(n_p=C.N_P, dt=C.DT):
    """Position and velocity at nodes 1..n_p as affine functions of (p0, v0, inputs):
       p = Sp @ [p0, v0] + Gp @ v,   vel = Sv @ [p0, v0] + Gv @ v."""
    Sp = np.zeros((n_p, 2)); Sv = np.zeros((n_p, 2))
    Gp = np.zeros((n_p, n_p)); Gv = np.zeros((n_p, n_p))
    for k in range(1, n_p + 1):
        Sp[k - 1] = [1.0, k * dt]; Sv[k - 1] = [0.0, 1.0]
        for j in range(k):
            Gp[k - 1, j] = (k - 1 - j) * dt * dt + 0.5 * dt * dt
            Gv[k - 1, j] = dt
    return Sp, Sv, Gp, Gv


SP, SV, GP, GV = condensed()


def rollout_axis(z0, V, dt=C.DT):
    """z0 (..., 2) [p, v]; V (..., n) inputs -> positions and velocities (..., n + 1), exact ZOH."""
    n = V.shape[-1]
    p = np.empty(V.shape[:-1] + (n + 1,)); v = np.empty_like(p)
    p[..., 0], v[..., 0] = z0[..., 0], z0[..., 1]
    for k in range(n):
        p[..., k + 1] = p[..., k] + dt * v[..., k] + 0.5 * dt * dt * V[..., k]
        v[..., k + 1] = v[..., k] + dt * V[..., k]
    return p, v


@dataclass
class AxisBounds:
    """Constraint data for one aircraft-axis plan, nodes 1..n_p."""
    p_lo: np.ndarray
    p_hi: np.ndarray
    v_lim: np.ndarray
    u_lim: np.ndarray       # (n_p,) per-node input bound
    u_nom: float            # braking deceleration of X_f
    term_k: float           # chord coefficient of the terminal rows
    term_lo: float          # terminal faces (already tightened by beta_inf)
    term_hi: float
    term_vcap: float        # |v| cap at the terminal node (np.inf if none)


def axis_bounds(t: Tightening, rho, axis, m=None):
    """Bounds for every aircraft on one axis. axis 0 = along-track, 1 = lateral. Returns a list."""
    m = t.m if m is None else m
    beta = t.beta(rho)[:, 1:]                  # nodes 1..n_p
    binf = t.beta_inf(rho)
    vl = t.vlim()[1:]
    ul = t.ulim()
    out = []
    for i in range(len(beta)):
        if axis == 0:
            lo, hi = C.S_LO + beta[i], C.S_HI - beta[i]
            tl, th, k, vcap = C.S_LO + binf[i], C.S_HI - binf[i], t.k_s, np.inf
        else:
            lo, hi = -m + beta[i], m - beta[i]
            tl, th, k, vcap = -m + binf[i], m - binf[i], t.k_l, C.TERMINAL_V_LAT
        out.append(AxisBounds(lo, hi, vl, ul, t.u_nom, k, tl, th, vcap))
    return out


def check_plan(z0, V, b: AxisBounds, tol=1e-9):
    """Independent evaluator (A4). Returns (ok, worst_slack). Never uses solver output except V."""
    if not np.all(np.isfinite(V)) or b.u_nom <= 0:
        return False, -np.inf
    V = np.asarray(V, float); z0 = np.asarray(z0, float)
    n = len(V)
    if n == C.N_P:
        p, v = SP @ z0 + GP @ V, SV @ z0 + GV @ V           # same linear map as rollout_axis
    else:
        p, v = rollout_axis(z0, V); p, v = p[1:], v[1:]
    sl = [(b.u_lim - np.abs(V)).min(),
          (p - b.p_lo).min(), (b.p_hi - p).min(),
          (b.v_lim - np.abs(v)).min()]
    pT, vT = p[-1], v[-1]
    sl += [b.term_hi - (pT + b.term_k * max(vT, 0.0)), b.term_hi - pT,
           (pT + b.term_k * min(vT, 0.0)) - b.term_lo, pT - b.term_lo]
    if np.isfinite(b.term_vcap):
        sl.append(b.term_vcap - abs(vT))
    worst = float(min(sl))
    return worst >= -tol, worst


def in_terminal(z, b: AxisBounds, tol=1e-9):
    p, v = z
    ok = (p + b.term_k * max(v, 0.0) <= b.term_hi + tol and p <= b.term_hi + tol and
          p + b.term_k * min(v, 0.0) >= b.term_lo - tol and p >= b.term_lo - tol)
    if np.isfinite(b.term_vcap):
        ok = ok and abs(v) <= b.term_vcap + tol
    return ok


def brake_input(v, a):
    """Nominal loiter controller: brake at a, stopping exactly at the end of a step."""
    return -np.sign(v) * np.minimum(a, np.abs(v) / C.DT)


# ------------------------------------------------------------------ discrete task layer
def eligibility(rho, alpha, holder_of=None, t: Tightening | None = None):
    """Paper III combinatorics.eligibility with the runbook's look-aheads:
    acquire rho + L_rho N_P DT <= alpha, keep rho + L_rho DT <= alpha. Loaded read-only."""
    import sys
    sys.path.insert(0, str(C.REPO / "paperIII" / "experiments"))
    from certcmdp.combinatorics import eligibility as elig3
    L_rho = t.L_rho if t is not None else C.L_RHO
    n_p = t.n_p if t is not None else C.N_P
    return elig3(rho, alpha, holder_of=holder_of, lookahead=L_rho * n_p * C.DT, keep_lookahead=L_rho * C.DT)


IDLE = -1


def discrete_project(task_proposal, rho, alpha, prev, t: Tightening | None = None):
    """Minimal-deviation discrete filter: a proposal that is eligible is returned unchanged;
    otherwise keep the previous task if its keep rule holds, else idle. Transparent by construction."""
    task_proposal = np.asarray(task_proposal, int); prev = np.asarray(prev, int)
    el = eligibility(rho, alpha, holder_of=prev, t=t)
    out = np.full(len(task_proposal), IDLE)
    for i, j in enumerate(task_proposal):
        if j >= 0 and el[i, j]:
            out[i] = j
        elif prev[i] >= 0 and el[i, prev[i]]:
            out[i] = prev[i]
    return out


def lexicographic_discrete(task_proposal, rho, alpha, prev, t: Tightening | None = None):
    """Ablation: Paper III's lexicographic projection (not transparent)."""
    import sys
    sys.path.insert(0, str(C.REPO / "paperIII" / "experiments"))
    from certcmdp.combinatorics import lexicographic_projection
    el = eligibility(rho, alpha, holder_of=np.asarray(prev, int), t=t)
    return lexicographic_projection(el, np.asarray(task_proposal, int), prev=np.asarray(prev, int))
