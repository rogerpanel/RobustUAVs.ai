"""Predictive safety filter and baselines (runbook P1.1).

PredictiveSafetyFilter(t).filter(x_hat, u_des, rho) -> FilterOut

Per aircraft and per axis the filter certifies a plan from the estimate:

  1. fast path: the shifted previous plan with v_0 = pi_nom passes check_plan -> transparent
     (exact by Lemma 1: a feasible plan starting with pi_nom exists)
  2. projection QP   min (v_0 - pi_nom)^2   s.t. tightened constraints and X_f   (OSQP, then
     Clarabel, then SciPy SLSQP); if v_0* ~ pi_nom, a QP with v_0 fixed to pi_nom is tried and an
     exact pi_nom plan is returned as transparent
  3. a plan is accepted only if check_plan (admissible.py, the independent evaluator of A4)
     passes; a solver failure, a check failure or solve_ms > DT * 1000 executes the latched tail
     of the last certified plan, then the loiter terminal controller once the tail is exhausted.

a^LLM enters only the cost. Solves use iteration limits, never wall-clock limits, so the
filter is deterministic; the DT timeout is checked and counted (it should never fire).

Baselines with the same interface: NoFilter, SimplexFilter, CBFOneStep, FixedMarginFilter.
    python3 filter.py --latency --n 20000 --seed 10001
"""
from __future__ import annotations

import argparse
import csv
import platform
import time
from dataclasses import dataclass

import clarabel
import numpy as np
import osqp
import scipy.sparse as sp
from scipy.optimize import minimize

try:
    from . import constants as C
    from .admissible import (Tightening, axis_bounds, check_plan, rollout_axis, brake_input, SP, SV, GP, GV)
except ImportError:
    import constants as C
    from admissible import (Tightening, axis_bounds, check_plan, rollout_axis, brake_input, SP, SV, GP, GV)

BUF = 1e-6           # [model] solver-side shrink of every inequality row; check_plan uses none
MU_REG = 1e-6        # [model] regulariser on v_1..v_{N_P-1} (plan smoothness only)
TRANSP_TOL = 1e-3    # [model] |v0* - pi_nom| below which the exact-transparency QP is tried
OSQP_KW = dict(eps_abs=1e-5, eps_rel=1e-5, max_iter=2000, polishing=True, verbose=False, warm_starting=True)
STATUS_RANK = {"transparent": 0, "projected": 1, "latched": 2, "loiter": 3, "infeasible_t0": 4}


@dataclass
class FilterOut:
    a_star: np.ndarray            # (n, 2) executed acceleration command
    v0: np.ndarray                # (n, 2) nominal first input (before tube feedback)
    intervened: np.ndarray        # (n,) bool, ||v0 - pi_nom||_inf > ETA_INTERVENE
    fallback: np.ndarray          # (n,) bool, latched tail or loiter executed
    solve_ms: np.ndarray          # (n,) wall time spent on this aircraft
    status: list                  # (n,) transparent | projected | latched | loiter | infeasible_t0
    slack: np.ndarray             # (n,) worst check_plan slack of the executed plan (nan if fallback)
    latched_steps_left: np.ndarray
    backend: list                 # (n,) fast | osqp | clarabel | slsqp | tail | loiter | none


class AxisQP:
    """One OSQP instance per (aircraft, axis); the matrix is fixed, bounds change each step."""

    def __init__(self, k_term, vcap, n_p=C.N_P):
        self.n = n_p
        I = np.eye(n_p)
        rows = [I, GP, GV, (GP[-1] + k_term * GV[-1])[None], GP[-1][None]]
        self.has_vcap = np.isfinite(vcap)
        if self.has_vcap:
            rows.append(GV[-1][None])
        self.Ad = np.vstack(rows)
        self.A = sp.csc_matrix(self.Ad)
        self.k = k_term
        pd = np.full(n_p, MU_REG); pd[0] = 1.0
        self.P = sp.diags(pd).tocsc()
        self.solver = osqp.OSQP()
        m = self.Ad.shape[0]
        self.solver.setup(P=self.P, q=np.zeros(n_p), A=self.A, l=-np.ones(m), u=np.ones(m), **OSQP_KW)

    def bounds(self, z0, b, v0_fixed=None):
        z0 = np.asarray(z0, float)
        sp_, sv_ = SP @ z0, SV @ z0
        lo = [-b.u_lim, b.p_lo - sp_, -b.v_lim - sv_,
              [b.term_lo - (sp_[-1] + self.k * sv_[-1])], [b.term_lo - sp_[-1]]]
        hi = [b.u_lim.copy(), b.p_hi - sp_, b.v_lim - sv_,
              [b.term_hi - (sp_[-1] + self.k * sv_[-1])], [b.term_hi - sp_[-1]]]
        if self.has_vcap:
            lo.append([-b.term_vcap - sv_[-1]]); hi.append([b.term_vcap - sv_[-1]])
        lo = np.concatenate(lo) + BUF; hi = np.concatenate(hi) - BUF
        if v0_fixed is not None:
            lo[0] = hi[0] = v0_fixed
        return lo, hi

    def solve(self, z0, b, u_des, v0_fixed=None):
        lo, hi = self.bounds(z0, b, v0_fixed)
        if np.any(lo > hi):
            return None, "infeasible_bounds"
        q = np.zeros(self.n); q[0] = -u_des
        self.solver.update(q=q, l=lo, u=hi)
        r = self.solver.solve(raise_error=False)
        st = r.info.status
        if r.x is None or not np.all(np.isfinite(r.x)):
            return None, st
        return np.asarray(r.x, float), st

    def clarabel(self, z0, b, u_des):
        lo, hi = self.bounds(z0, b)
        if np.any(lo > hi):
            return None, "infeasible_bounds"
        A = sp.vstack([self.A, -self.A]).tocsc()
        bb = np.concatenate([hi, -lo])
        q = np.zeros(self.n); q[0] = -u_des
        s = clarabel.DefaultSettings(); s.verbose = False; s.max_iter = 200
        sol = clarabel.DefaultSolver(sp.triu(self.P).tocsc(), q, A, bb, [clarabel.NonnegativeConeT(len(bb))], s).solve()
        x = np.asarray(sol.x, float)
        return (x if np.all(np.isfinite(x)) else None), str(sol.status)

    def slsqp(self, z0, b, u_des):
        lo, hi = self.bounds(z0, b)
        if np.any(lo > hi):
            return None, "infeasible_bounds"
        A = self.Ad
        cons = [{"type": "ineq", "fun": lambda x: hi - A @ x, "jac": lambda x: -A},
                {"type": "ineq", "fun": lambda x: A @ x - lo, "jac": lambda x: A}]
        x0 = np.zeros(self.n)
        r = minimize(lambda x: (x[0] - u_des) ** 2 + MU_REG * (x[1:] ** 2).sum(), x0, method="SLSQP",
                     jac=lambda x: np.concatenate([[2 * (x[0] - u_des)], 2 * MU_REG * x[1:]]),
                     constraints=cons, options=dict(maxiter=200, ftol=1e-12))
        return (np.asarray(r.x, float) if r.success else None), ("slsqp:" + ("ok" if r.success else r.message))


class _Plan:
    """A certified per-axis plan: nominal nodes and inputs, plus the loiter continuation."""
    __slots__ = ("p", "v", "V", "age", "a_brake")

    def __init__(self, z0, V, a_brake):
        self.V = np.asarray(V, float)
        self.p, self.v = rollout_axis(np.asarray(z0, float), self.V)
        self.age = 0
        self.a_brake = a_brake

    def nominal(self):
        """Nominal (z, v_input) at the current age; extends with the loiter brake past the tail."""
        n = len(self.V)
        if self.age < n:
            return self.p[self.age], self.v[self.age], self.V[self.age], "tail"
        # loiter: integrate the braking nominal from the terminal node
        p, v = self.p[-1], self.v[-1]
        for _ in range(self.age - n):
            u = brake_input(v, self.a_brake)
            p, v = p + C.DT * v + 0.5 * C.DT * C.DT * u, v + C.DT * u
        return p, v, float(brake_input(v, self.a_brake)), "loiter"

    def shifted(self, a_brake):
        """Inputs of the plan shifted by one step, with a braking input appended."""
        V = np.empty_like(self.V)
        V[:-1] = self.V[1:]
        V[-1] = brake_input(self.v[-1], a_brake)
        return V


class PredictiveSafetyFilter:
    name = "psf"

    def __init__(self, t: Tightening, n=C.N_UAV, timeout_ms=C.DT * 1000):
        self.t, self.n = t, n
        self.timeout_ms = timeout_ms
        self.qp = [[AxisQP(t.k_s, np.inf, t.n_p), AxisQP(t.k_l, C.TERMINAL_V_LAT, t.n_p)] for _ in range(n)]
        self.plan = [[None, None] for _ in range(n)]
        self.started = False
        self.counts = dict(fast=0, osqp=0, clarabel=0, slsqp=0, tail=0, loiter=0, timeouts=0, check_fail=0)
        self.Kp, self.Kd = C.KP, C.KD

    # ------------------------------------------------------------ one axis
    def _certify(self, i, ax, z0, b, u):
        """Returns (V, status, backend, slack) or (None, reason, backend, nan)."""
        pl = self.plan[i][ax]
        if pl is not None and abs(u) <= b.u_lim[0]:                    # 1. fast path
            V = pl.shifted(self.t.a_brake); V[0] = u
            ok, sl = check_plan(z0, V, b)
            if ok:
                self.counts["fast"] += 1
                return V, "transparent", "fast", sl
        qp = self.qp[i][ax]
        last = "none"
        for backend in ("osqp", "clarabel", "slsqp"):                   # 2. projection
            x, st = qp.solve(z0, b, u) if backend == "osqp" else getattr(qp, backend)(z0, b, u)
            last = f"{backend}:{st}"
            if x is None:
                if "infeasible" in str(st).lower() and "dual" not in str(st).lower():
                    break                                                # primal infeasible: no plan exists
                continue
            x = np.clip(x, -b.u_lim, b.u_lim)
            ok, sl = check_plan(z0, x, b)
            if not ok:
                self.counts["check_fail"] += 1
                continue
            self.counts[backend] += 1
            if abs(x[0] - u) <= TRANSP_TOL and abs(u) <= b.u_lim[0]:   # exact transparency
                Vt = x.copy(); Vt[0] = u
                okt, slt = check_plan(z0, Vt, b)
                if not okt:
                    xt, _ = qp.solve(z0, b, u, v0_fixed=u)
                    if xt is not None:
                        Vt = np.clip(xt, -b.u_lim, b.u_lim); Vt[0] = u
                        okt, slt = check_plan(z0, Vt, b)
                if okt:
                    return Vt, "transparent", backend, slt
            return x, "projected", backend, sl
        return None, last, last.split(":")[0], np.nan

    # ------------------------------------------------------------ fleet step
    def filter(self, x_hat, u_des, rho):
        n = self.n
        bs = [axis_bounds(self.t, rho, 0), axis_bounds(self.t, rho, 1)]
        a_star = np.zeros((n, 2)); v0 = np.zeros((n, 2))
        fb = np.zeros(n, bool); sl_out = np.full(n, np.nan); ms = np.zeros(n)
        status, backend = [], []
        left = np.zeros(n, int)
        for i in range(n):
            t0 = time.perf_counter()
            st_i, be_i, worst = "transparent", [], np.inf
            for ax in (0, 1):
                z0 = x_hat[i, [ax, 2 + ax]]
                V, st, be, sl = self._certify(i, ax, z0, bs[ax][i], float(u_des[i, ax]))
                el = (time.perf_counter() - t0) * 1000
                if V is not None and el > self.timeout_ms:
                    self.counts["timeouts"] += 1
                    V, st = None, "timeout"
                if V is not None:
                    pl = _Plan(z0, V, self.t.a_brake)
                    self.plan[i][ax] = pl
                    a_star[i, ax] = v0[i, ax] = V[0]
                    pl.age = 1
                    worst = min(worst, sl) if np.isfinite(sl) else worst
                    if st == "loiter":                                    # Simplex reject
                        fb[i] = True
                    if STATUS_RANK[st] > STATUS_RANK[st_i]:
                        st_i = st
                    be_i.append(be)
                    continue
                pl = self.plan[i][ax]
                if pl is None:                                            # no certified plan yet (A5 fails)
                    st_i = "infeasible_t0"; be_i.append("none")
                    a_star[i, ax] = v0[i, ax] = brake_input(z0[1], max(self.t.a_brake, 0.0))
                    fb[i] = True
                    continue
                pz, pv, vin, kind = pl.nominal()
                a_star[i, ax] = vin - self.Kp * (z0[0] - pz) - self.Kd * (z0[1] - pv)
                v0[i, ax] = vin
                pl.age += 1
                fb[i] = True
                self.counts[kind] += 1
                be_i.append(kind)
                s = "latched" if kind == "tail" else "loiter"
                if STATUS_RANK[s] > STATUS_RANK[st_i]:
                    st_i = s
                left[i] = max(left[i], len(pl.V) - pl.age + 1)
            ms[i] = (time.perf_counter() - t0) * 1000
            status.append(st_i); backend.append("+".join(be_i))
            sl_out[i] = worst if np.isfinite(worst) else np.nan
        self.started = True
        inter = np.abs(v0 - u_des).max(1) > C.ETA_INTERVENE
        return FilterOut(a_star, v0, inter, fb, ms, status, sl_out, left, backend)


class NoFilter:
    name = "none"

    def __init__(self, t=None, n=C.N_UAV):
        self.n = n; self.counts = {}

    def filter(self, x_hat, u_des, rho):
        n = self.n
        return FilterOut(np.asarray(u_des, float).copy(), np.asarray(u_des, float).copy(), np.zeros(n, bool),
                         np.zeros(n, bool), np.zeros(n), ["transparent"] * n, np.full(n, np.nan), np.zeros(n, int),
                         ["none"] * n)


class SimplexFilter(PredictiveSafetyFilter):
    """Accept/reject: pi_nom is accepted iff a certified plan starts with it; otherwise the
    aircraft brakes in place (loiter on reject). No projection, no latched tail."""
    name = "simplex"

    def _certify(self, i, ax, z0, b, u):
        V, st, be, sl = super()._certify(i, ax, z0, b, u)
        if V is not None and st == "transparent":
            return V, st, be, sl
        Vb = np.zeros(self.t.n_p); v = z0[1]
        for k in range(self.t.n_p):
            Vb[k] = brake_input(v, max(self.t.a_brake, 1e-9)); v = v + C.DT * Vb[k]
        return Vb, "loiter", "reject", np.nan


class CBFOneStep:
    """Myopic one-step discrete CBF on each corridor face, h = (tightened face) - p:
    h(x+) >= (1 - GAMMA_CBF) h(x); closest input to pi_nom inside the box; no look-ahead in speed."""
    name = "cbf1"
    GAMMA_CBF = 0.2   # [model]

    def __init__(self, t: Tightening, n=C.N_UAV):
        self.t, self.n = t, n; self.counts = {}

    def filter(self, x_hat, u_des, rho):
        n = self.n
        beta1 = self.t.beta(rho)[:, 1]
        a = np.zeros((n, 2)); st = []
        for i in range(n):
            s_i = "transparent"
            for ax in (0, 1):
                p, v = x_hat[i, ax], x_hat[i, 2 + ax]
                lo_face = (C.S_LO if ax == 0 else -self.t.m) + beta1[i]
                hi_face = (C.S_HI if ax == 0 else self.t.m) - beta1[i]
                g = 1 - self.GAMMA_CBF
                # p + DT v + DT^2/2 u <= hi - g (hi - p)   and   >= lo + g (p - lo)
                c = 0.5 * C.DT * C.DT
                u_hi = ((hi_face - g * (hi_face - p)) - p - C.DT * v) / c
                u_lo = ((lo_face + g * (p - lo_face)) - p - C.DT * v) / c
                lo_u, hi_u = max(-C.U_MAX, u_lo), min(C.U_MAX, u_hi)
                if lo_u > hi_u:
                    uu = float(-np.sign(v) * C.U_MAX); s_i = "projected"
                else:
                    uu = float(np.clip(u_des[i, ax], lo_u, hi_u))
                    if abs(uu - u_des[i, ax]) > C.ETA_INTERVENE:
                        s_i = "projected"
                a[i, ax] = uu
            st.append(s_i)
        inter = np.abs(a - u_des).max(1) > C.ETA_INTERVENE
        return FilterOut(a, a.copy(), inter, np.zeros(n, bool), np.zeros(n), st, np.full(n, np.nan),
                         np.zeros(n, int), ["cbf"] * n)


def FixedMarginFilter(t: Tightening, n=C.N_UAV):
    """Paper III's fixed margin rho_0 + L_rho * 1 s, no tube, no look-ahead structure."""
    tf = Tightening(w_bar=t.w_bar, b_tot=t.b_tot, m=t.m, gamma=t.gamma, L=t.L, delta_bar=t.delta_bar,
                    n_p=t.n_p, tightening="none", lookahead=True, fixed_margin=True)
    f = PredictiveSafetyFilter(tf, n)
    f.name = "fixed_margin"
    return f


FILTERS = {"psf": PredictiveSafetyFilter, "none": NoFilter, "simplex": SimplexFilter, "cbf1": CBFOneStep,
           "fixed_margin": FixedMarginFilter}


def make_filter(name, t, n=C.N_UAV):
    return FILTERS[name](t, n)


# ------------------------------------------------------------------ latency benchmark (P1.2)
def latency(n_samples, seed, m=20.0, b_tot=0.0):
    """Per-axis QP solve time on random states drawn inside the tightened corridor, with
    random (often inadmissible) proposals; fast path disabled so every sample solves."""
    rng = np.random.default_rng(seed)
    t = Tightening(w_bar=C.load_wbar(), b_tot=b_tot, m=m)
    qp = [AxisQP(t.k_s, np.inf), AxisQP(t.k_l, C.TERMINAL_V_LAT)]
    rows = []
    for k in range(n_samples):
        rho = np.array([rng.uniform(t.rho_floor * 0.5, t.rho_bar)])
        ax = k % 2
        b = axis_bounds(t, rho, ax)[0]
        if ax == 0:
            z0 = np.array([rng.uniform(0, 700), rng.uniform(0, C.V_MAX * 0.9)])
        else:
            hw = max(t.m - t.beta_inf(rho)[0], 0.0)
            z0 = np.array([rng.uniform(-hw, hw), rng.uniform(-1.0, 1.0)])
        u = rng.uniform(-C.U_MAX, C.U_MAX)
        t0 = time.perf_counter()
        x, st = qp[ax].solve(z0, b, u)
        ms = (time.perf_counter() - t0) * 1000
        ok = x is not None and check_plan(z0, np.clip(x, -b.u_lim, b.u_lim), b)[0]
        rows.append((k, ax, ms, st, int(ok)))
    return rows, t


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--latency", action="store_true")
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=10001)
    a = ap.parse_args()
    if a.latency:
        if not (10000 <= a.seed <= 10999):
            raise SystemExit("latency seeds come from block 10xxx")
        rows, t = latency(a.n, a.seed)
        ms = np.array([r[2] for r in rows]); ok = np.array([r[4] for r in rows])
        cpu = platform.processor() or platform.machine()
        try:
            for line in open("/proc/cpuinfo"):
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip(); break
        except OSError:
            pass
        out = C.RESULTS / "p1_latency.csv"
        with out.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["backend", "n", "p50_ms", "p99_ms", "p999_ms", "max_ms", "certified_frac", "n_p", "cpu",
                        "provenance"])
            w.writerow(["osqp", len(ms), f"{np.percentile(ms, 50):.4f}", f"{np.percentile(ms, 99):.4f}",
                        f"{np.percentile(ms, 99.9):.4f}", f"{ms.max():.4f}", f"{ok.mean():.4f}", t.n_p, cpu, "measured"])
        print(f"wrote {out}: p50 {np.percentile(ms, 50):.3f} ms, p99.9 {np.percentile(ms, 99.9):.3f} ms, "
              f"max {ms.max():.3f} ms, certified {ok.mean():.3f}")
