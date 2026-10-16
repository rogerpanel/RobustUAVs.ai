"""Predictive safety filter (joint fleet QP; OSQP first stage, Clarabel IPM second stage)
with latched-tail fallback.

    min  sum_i ||v_i0 - u_des_i||^2 + mu sum_{i,k>=1} ||v_ik||^2
    s.t. z_i0 = x_i (navigation state), z_{k+1} = A_Ts z_k + B_Ts v_k
         a^T p_ik <= c - ||a||_1 beta_i[k]                 (keep-in polytope, every node)
         n_ijk^T (p_ik - p_jk) >= d_sep + ||n||_1 (beta_i + beta_j)   (linearised separation,
                                                     both ends of every interval -> chord-safe)
         |v_ik| <= u_nom, |z_ik,v| <= v_max - eps_v,  z_iNp,v = 0   (loiter terminal set)

The planner's proposal u_des enters ONLY the cost. Every returned plan is re-simulated
and checked by an independent evaluator (assumption A4) without the solver buffer; a plan
that fails the check is treated as a solver failure.

Each tick: (1) re-anchored problem from the navigation state (error tube reset, age 0);
(2) if (1) fails, a continuation problem from the latched nominal state with tightening
indexed by the error-tube age and the latched plan's own separation normals -- the shifted
latched plan + loiter is an exactly feasible candidate, so (2) is recursively feasible;
(3) if both fail (solver/time budget), the fleet executes the tail of the last certified
plan (latched certificate), then loiters at its terminal node under the tube controller
u = v + K(x - z). Only (3) counts as a fallback.
"""
from __future__ import annotations

import time

import numpy as np
import clarabel
import osqp
import scipy.sparse as sp

VBUF, UBUF = 0.05, 0.05   # [model] solver buffers on speed (m/s) and input (m/s^2) rows
EPS_FAST, EPS_SLOW = 1e-3, 1e-5   # [model] OSQP tolerances (plans are verified exactly anyway)
OSQP_BUDGET = 0.04   # [model] s, first-stage ADMM budget
TIME_LIMIT = 0.25   # [model] s, solver budget (half the filter period); overrun -> fallback
from constants import DT, TS, SUB, NP, D_SEP, BUF, MU_REG, KP, KD, ETA_INT
from plant import di_matrices

A1, B1 = di_matrices(TS)
Ad, Bd = di_matrices(DT)


class SafetyFilter:
    def __init__(self, geo, tcfg, continuation=True):
        self.geo, self.t = geo, tcfg
        self.continuation = continuation
        self.N = N = geo.N
        self.nh = geo.H.shape[0]
        self.l1h = np.abs(geo.H).sum(1)
        self.pairs = [(i, j) for i in range(N) for j in range(i + 1, N)]
        self.nz = 4 * (NP + 1)
        self.nvar_i = self.nz + 2 * NP
        self.nvar = N * self.nvar_i
        self.I = np.array([p[0] for p in self.pairs], int); self.J = np.array([p[1] for p in self.pairs], int)
        self._build()
        self.v_idx = np.array([self.iv(i, k, c) for i in range(N) for k in range(NP) for c in range(2)])
        self.v0_idx = np.array([[self.iv(i, 0, 0), self.iv(i, 0, 1)] for i in range(N)])
        self.latched = None          # dict(Zf, Vf, created_tick)
        self.Ptriu = sp.triu(self.P).tocsc()
        self.n_osqp = 0; self.n_ipm = 0
        self.log = []

    # ------------------------------------------------------------ indices
    def iz(self, i, k, c):          # state component c of node k
        return i * self.nvar_i + 4 * k + c

    def iv(self, i, k, c):
        return i * self.nvar_i + self.nz + 2 * k + c

    def _build(self):
        N, nh = self.N, self.nh
        rows, cols, vals = [], [], []
        r = 0
        self.r_init = r
        # equality: init + dynamics (per axis)
        for i in range(N):
            for c in range(4):
                rows.append(r); cols.append(self.iz(i, 0, c)); vals.append(1.0); r += 1
        self.r_dyn = r
        for i in range(N):
            for k in range(NP):
                for ax in range(2):
                    # position: p+ - p - Ts v - Ts^2/2 a = 0
                    rows += [r] * 4
                    cols += [self.iz(i, k + 1, ax), self.iz(i, k, ax), self.iz(i, k, 2 + ax), self.iv(i, k, ax)]
                    vals += [1.0, -1.0, -TS, -0.5 * TS * TS]; r += 1
                    rows += [r] * 3
                    cols += [self.iz(i, k + 1, 2 + ax), self.iz(i, k, 2 + ax), self.iv(i, k, ax)]
                    vals += [1.0, -1.0, -TS]; r += 1
        self.n_eq = r
        # corridor
        self.r_cor = r
        for i in range(N):
            for k in range(NP + 1):
                for h in range(nh):
                    rows += [r, r]; cols += [self.iz(i, k, 0), self.iz(i, k, 1)]
                    vals += [self.geo.H[h, 0], self.geo.H[h, 1]]; r += 1
        # speed (nodes 1..Np) and inputs: identity rows
        self.r_spd = r
        for i in range(N):
            for k in range(1, NP + 1):
                for ax in range(2):
                    rows.append(r); cols.append(self.iz(i, k, 2 + ax)); vals.append(1.0); r += 1
        self.r_inp = r
        for i in range(N):
            for k in range(NP):
                for ax in range(2):
                    rows.append(r); cols.append(self.iv(i, k, ax)); vals.append(1.0); r += 1
        # separation: for each pair, for each interval k: node k and node k+1 with n_k
        self.r_sep = r
        self.sep_meta = []           # (pair_idx, interval k, node m)
        self.sep_val_idx = []        # positions in the COO value list to overwrite
        for p, (i, j) in enumerate(self.pairs):
            for k in range(NP):
                for m in (k, k + 1):
                    base = len(vals)
                    rows += [r] * 4
                    cols += [self.iz(i, m, 0), self.iz(i, m, 1), self.iz(j, m, 0), self.iz(j, m, 1)]
                    vals += [1.0, 0.0, -1.0, 0.0]
                    self.sep_meta.append((p, k, m)); self.sep_val_idx.append(base); r += 1
        self.m = r
        vals = np.asarray(vals, float)
        tag = np.arange(1, len(vals) + 1, dtype=float)
        Acsc = sp.csc_matrix((tag, (rows, cols)), shape=(self.m, self.nvar))
        self.perm = (Acsc.data - 1).astype(np.int64)  # csc position -> coo index
        self.coo_vals = vals
        self.A = sp.csc_matrix((vals[self.perm], Acsc.indices, Acsc.indptr), shape=(self.m, self.nvar))
        self.sep_val_idx = np.asarray(self.sep_val_idx)
        self.sep_meta = np.asarray(self.sep_meta).reshape(-1, 3)
        # cost
        pd = np.full(self.nvar, 0.0)
        for i in range(N):
            for k in range(NP):
                for ax in range(2):
                    pd[self.iv(i, k, ax)] = 1.0 if k == 0 else MU_REG
        self.P = sp.diags(pd).tocsc()
        # constant bounds
        self.l = np.full(self.m, -np.inf); self.u = np.full(self.m, np.inf)
        self.l[self.r_dyn:self.n_eq] = 0.0; self.u[self.r_dyn:self.n_eq] = 0.0
        vl = self.t.vlim()
        for i in range(N):
            for k in range(1, NP + 1):
                for ax in range(2):
                    rr = self.r_spd + (i * NP + (k - 1)) * 2 + ax
                    lim = 0.0 if k == NP else vl[k]
                    self.l[rr], self.u[rr] = -lim, lim
        un = self.t.u_nom - UBUF
        self.l[self.r_inp:self.r_sep] = -un; self.u[self.r_inp:self.r_sep] = un
        self.solver = osqp.OSQP()
        self.solver.setup(P=self.P, q=np.zeros(self.nvar), A=self.A, l=self.l, u=self.u, verbose=False,
                          eps_abs=EPS_FAST, eps_rel=EPS_FAST, max_iter=100000, polish=True, warm_start=True, rho=1.0,
                          time_limit=OSQP_BUDGET)

    # ------------------------------------------------------------ helpers
    @staticmethod
    def rollout(x0, V):
        """x0 (N,4), V (N,Np,2) -> node states (N,Np+1,4)."""
        N = x0.shape[0]
        Z = np.zeros((N, NP + 1, 4)); Z[:, 0] = x0
        for k in range(NP):
            Z[:, k + 1, :2] = Z[:, k, :2] + TS * Z[:, k, 2:] + 0.5 * TS * TS * V[:, k]
            Z[:, k + 1, 2:] = Z[:, k, 2:] + TS * V[:, k]
        return Z

    def _normals_from_ref(self, R):
        """Interval normals (P, Np, 2) from reference node positions R (N, Np+1, 2)."""
        I, J = self.I, self.J
        D = R[I] - R[J]
        nrm = np.linalg.norm(D, axis=2, keepdims=True)
        n = np.where(nrm > 1e-6, D / np.maximum(nrm, 1e-9), np.array([1.0, 0.0]))
        return n[:, :NP]

    def _ref_normals(self, X):
        """Re-anchored problem: linearise around the shifted latched plan (translated to the
        current state) if available, else constant-velocity extrapolation."""
        if self.latched is not None:
            Zf = self.latched["Zf"]; off = self.latched["age_sub"]
            idx = np.minimum(off + np.arange(NP + 1) * SUB, Zf.shape[1] - 1)
            R = Zf[:, idx, :2].copy()
            R += (X[:, None, :2] - R[:, :1])
        else:
            tau = np.arange(NP + 1) * TS
            R = X[:, None, :2] + X[:, None, 2:] * tau[None, :, None]
        return self._normals_from_ref(R)

    def _shifted_normals(self):
        """Continuation problem: reuse the latched plan's own normals, shifted (makes the
        shifted latched plan + loiter an exactly feasible candidate)."""
        L = self.latched; j = L["age_sub"] // SUB
        idx = np.minimum(np.arange(NP) + j, NP - 1)
        return L["normals"][:, idx]

    def constraints_for(self, Z0, rho, normals, age=0):
        """Bounds and separation coefficients for a plan starting at nominal state Z0 (N,4)."""
        beta = self.t.beta(rho, age)                  # (N, Np+1)
        bnode = beta.copy(); bnode[:, 1:] = np.maximum(beta[:, 1:], beta[:, :-1])
        l, u = self.l.copy(), self.u.copy()
        # decision positions are RELATIVE to each aircraft's start position (conditioning)
        X0 = Z0.copy(); X0[:, :2] = 0.0
        l[:4 * self.N] = X0.reshape(-1); u[:4 * self.N] = X0.reshape(-1)
        cu = (self.geo.c[None, None, :] - self.l1h[None, None, :] * bnode[:, :, None] - BUF
              - (Z0[:, :2] @ self.geo.H.T)[:, None, :])
        u[self.r_cor:self.r_spd] = cu.reshape(-1)
        vl = self.t.vlim(age)
        lim = np.concatenate([vl[1:NP] - VBUF, [0.0]])  # nodes 1..Np (solver buffer)
        sv = np.repeat(np.tile(lim, self.N), 2)
        l[self.r_spd:self.r_inp] = -sv; u[self.r_spd:self.r_inp] = sv
        vals = self.coo_vals.copy()
        sep = None
        if self.pairs:
            pidx, kk, mm = self.sep_meta[:, 0], self.sep_meta[:, 1], self.sep_meta[:, 2]
            nn = normals[pidx, kk]                    # (rows, 2)
            I, J = self.I[pidx], self.J[pidx]
            bi = np.maximum(beta[I, kk], beta[I, mm])
            bj = np.maximum(beta[J, kk], beta[J, mm])
            sep_l = D_SEP + np.abs(nn).sum(1) * (bi + bj)
            off = np.einsum("rc,rc->r", nn, Z0[I, :2] - Z0[J, :2])
            l[self.r_sep:] = sep_l + BUF - off
            b = self.sep_val_idx
            vals[b] = nn[:, 0]; vals[b + 1] = nn[:, 1]; vals[b + 2] = -nn[:, 0]; vals[b + 3] = -nn[:, 1]
            sep = (nn, I, J, mm, sep_l)
        return l, u, vals, bnode, vl, sep

    def verify(self, Z0, V, bnode, vl, sep):
        """Independent evaluator (A4): forward-simulate and check every certified row, no buffer."""
        if np.any(np.abs(V) > self.t.u_nom + 1e-9):
            return False, None
        Z = self.rollout(Z0, V)
        cor = self.geo.H @ Z[..., :2].reshape(-1, 2).T          # (nh, N*(Np+1))
        lim = (self.geo.c[:, None] - self.l1h[:, None] * bnode.reshape(-1)[None, :])
        if np.any(cor > lim):
            return False, Z
        if np.any(np.abs(Z[:, 1:NP, 2:]) > vl[None, 1:NP, None] + 1e-9):
            return False, Z
        if np.any(np.abs(Z[:, NP, 2:]) > 1e-9):
            return False, Z
        if sep is not None:
            nn, I, J, mm, sep_l = sep
            g = np.einsum("rc,rc->r", nn, Z[I, mm, :2] - Z[J, mm, :2])
            if np.any(g < sep_l):
                return False, Z
        return True, Z

    def _accept(self, x, Z0, bnode, vl, sep):
        V = x[self.v_idx].reshape(self.N, NP, 2)
        V = np.clip(V, -self.t.u_nom, self.t.u_nom)
        Z0r = self.rollout(Z0, V)            # repair: terminal velocity exactly zero
        V[:, NP - 1] = -Z0r[:, NP - 1, 2:] / TS
        ok, _ = self.verify(Z0, V, bnode, vl, sep)
        return ok, V

    def _clarabel(self, P, q, A, l, u, t_left):
        Ar = A.tocsr()
        ne = self.n_eq
        ineq_u = np.where(np.isfinite(u[ne:]))[0] + ne
        ineq_l = np.where(np.isfinite(l[ne:]))[0] + ne
        AA = sp.vstack([Ar[:ne], Ar[ineq_u], -Ar[ineq_l]]).tocsc()
        bb = np.concatenate([u[:ne], u[ineq_u], -l[ineq_l]])
        cones = [clarabel.ZeroConeT(ne), clarabel.NonnegativeConeT(len(ineq_u) + len(ineq_l))]
        st = clarabel.DefaultSettings(); st.verbose = False; st.time_limit = max(t_left, 0.01)
        sol = clarabel.DefaultSolver(self.Ptriu, q, AA, bb, cones, st).solve()
        return str(sol.status), np.asarray(sol.x)

    def _solve(self, Z0, rho, u_des, normals, age, t_budget, allow_ipm=True):
        """OSQP (warm, loose, short budget) first; if it neither certifies nor proves
        infeasibility, an interior-point solve (Clarabel) within the remaining budget."""
        t0 = time.perf_counter()
        l, u, vals, bnode, vl, sep = self.constraints_for(Z0, rho, normals, age)
        q = np.zeros(self.nvar)
        q[self.v0_idx[:, 0]] = -u_des[:, 0]; q[self.v0_idx[:, 1]] = -u_des[:, 1]
        self.solver.update(q=q, l=l, u=u, Ax=vals[self.perm])
        self.solver.update_settings(time_limit=OSQP_BUDGET)
        res = self.solver.solve()
        st = res.info.status
        self.n_osqp += 1
        if res.x is not None and np.all(np.isfinite(res.x)) and st in ("solved", "solved inaccurate",
                                                                         "maximum iterations reached",
                                                                         "run time limit reached"):
            ok, V = self._accept(res.x, Z0, bnode, vl, sep)
            if ok:
                return True, "certified", V
        if "infeasible" in st and "dual" not in st:
            return False, "infeasible", None
        if not allow_ipm:
            return False, "osqp:" + st, None
        left = t_budget - (time.perf_counter() - t0)
        if left < 0.01:
            return False, "time_budget", None
        A = sp.csc_matrix((vals[self.perm], self.A.indices, self.A.indptr), shape=self.A.shape)
        cst, x = self._clarabel(self.P, q, A, l, u, left)
        self.n_ipm += 1
        if cst in ("Solved", "AlmostSolved") and np.all(np.isfinite(x)):
            ok, V = self._accept(x, Z0, bnode, vl, sep)
            if ok:
                return True, "certified", V
            return False, "verify_fail", None
        if "Infeasible" in cst:
            return False, "infeasible", None
        return False, "solver_fail:" + cst, None

    # ------------------------------------------------------------ main entry
    def filter(self, X, rho, u_des, tick):
        t0 = time.perf_counter()
        normals = self._ref_normals(X) if self.pairs else None
        ok, status, V = self._solve(X, rho, u_des, normals, 0, TIME_LIMIT,
                                    allow_ipm=not (self.continuation and self.latched is not None
                                                   and self.latched["certified"]))
        mode, Z0, age = "reanchor", X, 0
        status_re = status
        if not ok and self.continuation and self.latched is not None and self.latched["certified"]:
            L = self.latched; s = L["age_sub"]
            if s < L["Vf"].shape[1]:
                Z0 = L["Zf"][:, s].copy()
            else:
                Z0 = L["Zf"][:, -1].copy(); Z0[:, 2:] = 0.0
            age = L["anchor_age"] + s
            normals = self._shifted_normals() if self.pairs else None
            ok, status, V = self._solve(Z0, rho, u_des, normals, age, TIME_LIMIT)
            mode = "continuation"
        t_total = time.perf_counter() - t0
        info = dict(tick=tick, status=status, status_reanchor=status_re, ok=ok, mode=mode if ok else "fallback",
                    t_solve=t_total, t_total=t_total)
        if ok:
            Zf, Vf = self._fine(Z0, V)
            self.latched = dict(Zf=Zf, Vf=Vf, age_sub=0, certified=True, anchor_age=age,
                                normals=normals)
            dev = np.abs(V[:, 0] - u_des).max(1)
            info.update(fallback=False, dev=dev, v0=V[:, 0].copy())
        else:
            if self.latched is None:          # no certified plan yet (A5 fails): brake-and-hold, UNCERTIFIED
                Zf = np.repeat(X[:, None, :], NP * SUB + 1, 1); Zf[:, :, 2:] = 0.0
                self.latched = dict(Zf=Zf, Vf=np.zeros((self.N, NP * SUB, 2)), age_sub=0, certified=False,
                                    anchor_age=0, normals=None)
            v = self.current_v()
            info.update(fallback=True, dev=np.abs(v - u_des).max(1), v0=v)
        info["certified"] = self.latched["certified"]
        self.log.append(info)
        return info

    def _fine(self, X, V):
        n = NP * SUB
        Zf = np.zeros((self.N, n + 1, 4)); Zf[:, 0] = X
        Vf = np.repeat(V, SUB, axis=1)
        for s in range(n):
            a = Vf[:, s]
            Zf[:, s + 1, :2] = Zf[:, s, :2] + DT * Zf[:, s, 2:] + 0.5 * DT * DT * a
            Zf[:, s + 1, 2:] = Zf[:, s, 2:] + DT * a
        return Zf, Vf

    def current_v(self):
        L = self.latched; s = L["age_sub"]
        return L["Vf"][:, s] if s < L["Vf"].shape[1] else np.zeros((self.N, 2))

    def control(self, X):
        """Tube controller at DT along the latched nominal; advances the latch by one sub-step."""
        L = self.latched; s = L["age_sub"]; n = L["Vf"].shape[1]
        if s < n:
            z, v = L["Zf"][:, s], L["Vf"][:, s]
        else:                                  # loiter terminal set: hover at the terminal node
            z = L["Zf"][:, -1].copy(); z[:, 2:] = 0.0; v = np.zeros((self.N, 2))
        e = X - z
        u = v - KP * e[:, :2] - KD * e[:, 2:]
        L["age_sub"] = s + 1
        return u
