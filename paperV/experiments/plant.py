"""Seeded, controllable fleet plant (runbook P1.1).

Each aircraft flies its own straight corridor. Coordinates are corridor-frame
(s along-track, l lateral); the world frame (x, y) is used only for snapshots.

    true dynamics   x+ = A x + B sat(u) + B w,   w = C_DRAG * g        (per axis, ZOH at DT)
    g               Dryden gust velocity, MIL-F-8785C low altitude, W20 ~ U[15, 30] kt per
                    mission, clipped at GUST_CLIP_SIGMA * sigma_v(W20) (declared envelope, A1)
    estimate        p_hat = p + e, |e|_inf <= rho_i(t) + b_adv   (A2 plus the covert budget)

The state integrated by `step` is the estimate x_hat; the true position is p_hat - e,
where e is drawn by Nature at every step. The estimate error therefore offsets the true
position but does not excite the loop (the additive-tightening model of the manuscript).
The autopilot cancels its own-speed drag; the unmodelled part is the gust term C_DRAG * g.

rho_i(t) comes from Paper III's CertificateProcess (imported, never edited). Inside (A2)
the profile has no relay jumps (J_bar = 0) and caps the dead-reckoning clock so that
rho <= rho_bar = L_rho * DELTA_BAR_S. Outside (A2) uses Paper III's default profile.

All randomness comes from SeedSequence(mission_seed) sub-streams, so every cell that
shares a mission seed sees the same wind, rho process and layout (common random numbers).

    python3 plant.py --calibrate-wbar --seeds 11000-11199 --inflate 1.2
    python3 plant.py --check-wbar --seeds 14000-14199
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass

import numpy as np

try:
    from . import constants as C
except ImportError:
    import constants as C

sys.path.insert(0, str(C.REPO / "paperIII" / "experiments"))
from certcmdp.certificate import CertificateProcess, ThreatProfile, KAPPA as KAPPA_III  # noqa: E402

STREAMS = ("wind", "rho", "layout", "nature", "planner", "attack")


def substreams(seed):
    """Named, independent generators for one mission seed (CRN across cells)."""
    ss = np.random.SeedSequence(int(seed))
    return {name: np.random.default_rng(s) for name, s in zip(STREAMS, ss.spawn(len(STREAMS)))}


def di_matrices(h=C.DT):
    """Per-axis double integrator, ZOH with step h. State (p, v)."""
    return np.array([[1.0, h], [0.0, 1.0]]), np.array([0.5 * h * h, h])


# ------------------------------------------------------------------ Dryden gusts
class Dryden:
    """Discretised Dryden lateral shaping filter H(s) = (1 + sqrt3 tau s)/(1 + tau s)^2,
    tau = L_v / V, driven by unit white noise and scaled so the stationary standard
    deviation equals sigma_v(W20) exactly (checked against Paper IV in the tests)."""

    def __init__(self, shape, w20_kt, rng, v_air=C.V_CRUISE, clip_sigma=C.GUST_CLIP_SIGMA):
        from scipy.linalg import expm, solve_discrete_lyapunov
        self.sigma, L = C.dryden_sigma(w20_kt)
        tau = L / v_air
        # controllable canonical form of 1/(1 + tau s)^2 = (1/tau^2) / (s^2 + (2/tau) s + 1/tau^2)
        Ac = np.array([[0.0, 1.0], [-1.0 / tau ** 2, -2.0 / tau]])
        Bc = np.array([[0.0], [1.0 / tau ** 2]])
        M = expm(np.block([[Ac, Bc], [np.zeros((1, 3))]]) * C.DT)
        self.Ad, self.Bd = M[:2, :2], M[:2, 2:]
        Cc = np.array([1.0, np.sqrt(3.0) * tau])          # numerator 1 + sqrt3 tau s
        P = solve_discrete_lyapunov(self.Ad, self.Bd @ self.Bd.T)
        self.Cd = Cc * self.sigma / np.sqrt(Cc @ P @ Cc)
        # start in the stationary distribution
        Lc = np.linalg.cholesky(P + 1e-15 * np.eye(2))
        self.rng = rng
        self.x = rng.standard_normal(shape + (2,)) @ Lc.T
        self.clip = clip_sigma * self.sigma

    def step(self):
        n = self.rng.standard_normal(self.x.shape[:-1])
        self.x = self.x @ self.Ad.T + n[..., None] * self.Bd[:, 0]
        return np.clip(self.x @ self.Cd, -self.clip, self.clip)


# ------------------------------------------------------------------ certificate process
class Certificate:
    """Paper III CertificateProcess for one fleet, rescaled for gamma / L, with the (A2) profile."""

    def __init__(self, n, rng, gamma=C.GAMMA_SUP, L=C.L_LOC, within=True, delta_bar=C.DELTA_BAR_S,
                 jump_m=0.0):
        self.scale = C.l_rho(gamma, L) / KAPPA_III
        if within:
            prof = ThreatProfile(relay_rate=0.0, stale_cap_s=max(delta_bar - C.theta_benign(), 0.0))
        else:
            prof = ThreatProfile()
        self.within = within
        self.jump_m = jump_m          # ablation J_bar > 0: added on each re-anchor-free jump onset
        self.proc = CertificateProcess(1, n, prof, rng)

    def rho(self):
        return self.proc.rho()[0] * self.scale

    def staleness(self):
        p = self.proc
        return (p.benign + p.dr + p.relay)[0]

    def step(self, dt=C.DT):
        self.proc.step(dt)
        return self.rho()


# ------------------------------------------------------------------ mission layout
@dataclass
class Layout:
    n: int
    m: float                       # corridor half-width
    waypoints: np.ndarray          # (W,) along-track task sites; last = goal
    origin: np.ndarray             # (n, 2) world origin of each corridor
    heading: np.ndarray            # (n,) world heading of each corridor, rad

    def world(self, P):
        """Corridor frame (n, 2) [s, l] -> world (n, 2) [x, y]."""
        c, s = np.cos(self.heading), np.sin(self.heading)
        return self.origin + np.stack([c * P[:, 0] - s * P[:, 1], s * P[:, 0] + c * P[:, 1]], 1)

    def slack(self, P):
        """(n, 4) signed slack of the corridor half-planes [m-l, m+l, S_HI-s, s-S_LO] (>= 0 inside)."""
        return np.stack([self.m - P[:, 1], self.m + P[:, 1], C.S_HI - P[:, 0], P[:, 0] - C.S_LO], 1)


def make_layout(n, m, rng=None):
    """Parallel straight corridors; the layout stream is consumed even though the
    headline layout is deterministic, so adding randomness later keeps other streams aligned."""
    if rng is not None:
        rng.random()
    origin = np.stack([np.zeros(n), np.arange(n) * C.LANE_SPACING], 1)
    return Layout(n, float(m), np.asarray(C.WAYPOINTS_S, float), origin, np.zeros(n))


# ------------------------------------------------------------------ nature
class Nature:
    """Disturbance w and estimate offset e.

    w_mode  'dryden'  : C_DRAG * clipped Dryden gust (the physical plant)
            'uniform' : uniform in the box |w| <= w_level
            'vertex'  : w_level * sign(outward) (worst box vertex, adversarial)
            'zero'
    e_mode  'random'  : uniform in the box |e| <= rho + b_adv
            'vertex'  : (rho + b_adv) * sign(outward)
            'zero'
    `outward` points at each aircraft's most binding corridor face.
    """

    def __init__(self, n, streams, w20_kt=None, w_mode="dryden", w_level=0.0, e_mode="random", b_adv=0.0):
        self.n = n
        self.rw, self.re = streams["wind"], streams["nature"]
        if w20_kt is None:
            w20_kt = self.rw.uniform(*C.W20_KT)
        self.w20 = float(w20_kt)
        self.gust = Dryden((n, 2), self.w20, self.rw)
        self.w_mode, self.w_level, self.e_mode, self.b_adv = w_mode, float(w_level), e_mode, float(b_adv)

    @staticmethod
    def outward(lay, P):
        sl = lay.slack(P)
        j = sl.argmin(1)
        d = np.zeros((len(P), 2))
        d[j == 0, 1] = 1.0; d[j == 1, 1] = -1.0; d[j == 2, 0] = 1.0; d[j == 3, 0] = -1.0
        # the other axis: toward its own nearer face
        other_l = np.where(P[:, 1] >= 0, 1.0, -1.0)
        other_s = np.where(C.S_HI - P[:, 0] <= P[:, 0] - C.S_LO, 1.0, -1.0)
        d[:, 1] = np.where(d[:, 1] == 0, other_l, d[:, 1])
        d[:, 0] = np.where(d[:, 0] == 0, other_s, d[:, 0])
        return d

    def disturbance(self, lay, P):
        g = self.gust.step()                       # always advanced: keeps the wind stream aligned
        if self.w_mode == "dryden":
            return C.C_DRAG * g
        if self.w_mode == "uniform":
            return self.rw.uniform(-1, 1, (self.n, 2)) * self.w_level
        if self.w_mode == "vertex":
            return self.w_level * self.outward(lay, P)
        return np.zeros((self.n, 2))

    def offset(self, lay, P_hat, rho):
        u = self.re.uniform(-1, 1, (self.n, 2))   # always drawn (CRN)
        mag = (np.asarray(rho) + self.b_adv)[:, None]
        if self.e_mode == "random":
            return u * mag
        if self.e_mode == "vertex":
            # e such that the TRUE position p_hat - e is pushed outward
            return -mag * self.outward(lay, P_hat)
        return np.zeros((self.n, 2))


# ------------------------------------------------------------------ the plant
class FleetPlant:
    """Integrates the estimate x_hat; reports the true position each step."""

    def __init__(self, n, seed, m, cfg=None):
        cfg = dict(cfg or {})
        self.n, self.seed, self.m = n, int(seed), float(m)
        self.st = substreams(seed)
        self.layout = make_layout(n, m, self.st["layout"])
        self.cert = Certificate(n, self.st["rho"], gamma=cfg.get("gamma", C.GAMMA_SUP),
                                L=cfg.get("L", C.L_LOC), within=cfg.get("within", True),
                                delta_bar=cfg.get("delta_bar", C.DELTA_BAR_S))
        self.nature = Nature(n, self.st, w_mode=cfg.get("w_mode", "dryden"), w_level=cfg.get("w_level", 0.0),
                             e_mode=cfg.get("e_mode", "random"), b_adv=cfg.get("b_adv", 0.0))
        self.X = np.zeros((n, 4))                  # [s, l, vs, vl] estimate
        self.X[:, 0] = 0.0
        self.rho = self.cert.rho()
        self.e = self.nature.offset(self.layout, self.X[:, :2], self.rho)
        self.t = 0.0
        self.A, self.B = di_matrices()
        self.last_w = np.zeros((n, 2))
        self.sat_steps = 0

    def true_pos(self):
        return self.X[:, :2] - self.e

    def step(self, U):
        """Apply per-aircraft accelerations U (n, 2); returns the true position after the step."""
        Us = np.clip(U, -C.U_MAX, C.U_MAX)
        self.sat_steps += int(np.any(np.abs(U) > C.U_MAX + 1e-9))
        w = self.nature.disturbance(self.layout, self.X[:, :2])
        a = Us + w
        self.X[:, :2] = self.X[:, :2] + C.DT * self.X[:, 2:] + 0.5 * C.DT * C.DT * a
        self.X[:, 2:] = self.X[:, 2:] + C.DT * a
        self.rho = self.cert.step(C.DT)
        self.e = self.nature.offset(self.layout, self.X[:, :2], self.rho)
        self.last_w = w
        self.t += C.DT
        return self.true_pos()

    def violations(self, P_true=None):
        """Per aircraft: corridor violated (bool) and signed margin (m)."""
        P = self.true_pos() if P_true is None else P_true
        sl = self.layout.slack(P).min(1)
        return sl < 0.0, sl

    def snapshot(self, nominal=None, mode=None, progress=None, completed=None, t_arr=None, on_time=None):
        """Platform-compatible snapshot (uav.py UAVState field names)."""
        P = self.true_pos()
        W = self.layout.world(P)
        Nw = self.layout.world(self.X[:, :2] if nominal is None else nominal)
        st = self.cert.staleness()
        out = []
        for i in range(self.n):
            out.append(dict(
                x=float(W[i, 0]), y=float(W[i, 1]),
                heading_deg=float(np.degrees(np.arctan2(self.X[i, 3], self.X[i, 2])) if np.any(self.X[i, 2:]) else 0.0),
                nom_x=float(Nw[i, 0]), nom_y=float(Nw[i, 1]),
                deviation_m=float(abs(P[i, 1])),
                mission_progress_pct=float(100 * (progress[i] if progress is not None else 0.0)),
                autopilot_mode=(mode[i] if mode is not None else "nominal"),
                staleness_s=float(st[i]),
                completed=bool(completed[i]) if completed is not None else False,
                t_arr_s=(None if t_arr is None or not np.isfinite(t_arr[i]) else float(t_arr[i])),
                on_time=(None if on_time is None else bool(on_time[i]))))
        return out


# ------------------------------------------------------------------ w_bar calibration (P1.4)
def _parse_seeds(s):
    a, b = s.split("-")
    return range(int(a), int(b) + 1)


def gust_supremum(seeds, n=C.N_UAV, steps=None):
    """Largest |w| per mission over the full simulated horizon (w does not depend on control)."""
    steps = steps or int(round(C.T_HORIZON_SIM / C.DT))
    rows = []
    for sd in seeds:
        st = substreams(sd)
        nat = Nature(n, st)
        mx = 0.0
        for _ in range(steps):
            g = nat.gust.step()
            mx = max(mx, float(np.abs(C.C_DRAG * g).max()))
        rows.append((sd, nat.w20, mx, n * steps * 2))
    return rows


def calibrate(seeds, inflate):
    if abs(inflate - C.W_INFLATE) > 1e-12:
        raise SystemExit(f"--inflate {inflate} differs from constants.W_INFLATE = {C.W_INFLATE}; "
                         "W_INFLATE is fixed before calibration")
    rows = gust_supremum(seeds)
    sup = max(r[2] for r in rows)
    out = C.RESULTS / "wbar_calibration.csv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "value", "unit", "provenance", "note"])
        w.writerow(["seeds", f"{min(seeds)}-{max(seeds)}", "-", "derived", "calibration block 11xxx"])
        w.writerow(["missions", len(rows), "-", "derived", ""])
        w.writerow(["samples", sum(r[3] for r in rows), "-", "derived", "aircraft-steps x 2 axes"])
        w.writerow(["sup_abs_w", f"{sup:.6f}", "m/s^2", "sim", "largest |C_DRAG g| observed"])
        w.writerow(["envelope_bound", f"{C.C_DRAG * C.GUST_CLIP_SIGMA * C.dryden_sigma(C.W20_KT[1])[0]:.6f}",
                    "m/s^2", "derived", "C_DRAG * GUST_CLIP_SIGMA * sigma_v(30 kt)"])
        w.writerow(["w_inflate", C.W_INFLATE, "-", "assumption", "fixed before calibration"])
        w.writerow(["w_bar", f"{C.W_INFLATE * sup:.6f}", "m/s^2", "derived", "sup_abs_w x w_inflate"])
    with (C.RESULTS / "wbar_calibration_missions.csv").open("w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["seed", "w20_kt", "sup_abs_w", "samples", "provenance"])
        for r in rows:
            w.writerow([r[0], f"{r[1]:.4f}", f"{r[2]:.6f}", r[3], "sim"])
    return out, C.W_INFLATE * sup


def check(seeds):
    wbar = C.load_wbar()
    rows = gust_supremum(seeds)
    exc = sum(1 for r in rows if r[2] > wbar)
    out = C.RESULTS / "wbar_heldout.csv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["seed", "w20_kt", "sup_abs_w", "w_bar", "exceeds", "provenance"])
        for r in rows:
            w.writerow([r[0], f"{r[1]:.4f}", f"{r[2]:.6f}", f"{wbar:.6f}", int(r[2] > wbar), "sim"])
    return out, exc, len(rows), max(r[2] for r in rows), wbar


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate-wbar", action="store_true")
    ap.add_argument("--check-wbar", action="store_true")
    ap.add_argument("--seeds", default="11000-11199")
    ap.add_argument("--inflate", type=float, default=C.W_INFLATE)
    a = ap.parse_args()
    if a.calibrate_wbar:
        s = _parse_seeds(a.seeds)
        if not (11000 <= min(s) and max(s) <= 11999):
            raise SystemExit("calibration seeds must come from block 11xxx")
        out, wb = calibrate(s, a.inflate)
        print(f"wrote {out}: w_bar = {wb:.4f} m/s^2")
    if a.check_wbar:
        s = _parse_seeds(a.seeds)
        if not (14000 <= min(s) and max(s) <= 14999):
            raise SystemExit("held-out check seeds must come from block 14xxx")
        out, exc, nm, mx, wb = check(s)
        print(f"wrote {out}: {exc}/{nm} missions exceed w_bar = {wb:.4f} (held-out max {mx:.4f})")
