"""CertSwarm: a vectorised certificate-constrained task-allocation environment.

B independent fleets of N aircraft and M task sites on an L x L arena.
Each step (dt seconds):
  1. every agent proposes a task (or IDLE);
  2. an *allocation layer* turns proposals into an executed assignment
     (one of: projection, masking, first-claimant, fixed-margin);
  3. agents fly toward their executed task at speed v;
  4. the certificate process advances; spatial jammers move;
  5. task j is *certified-covered* iff its holder is on site (<= r_cap)
     and rho_holder <= alpha_j. A *violation* is an executed pair with
     rho_i > alpha_j at the moment it is executed.

Rewards: `r_cert` (value-weighted certified coverage, what the mission
needs) and `r_nom` (value-weighted on-site coverage ignoring the certificate,
what a jamming-blind planner sees), plus `cost` = violations / N.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .certificate import ALERT_LIMITS, KAPPA, CertificateProcess, ThreatProfile
from . import combinatorics as C

IDLE = C.IDLE
VALUE_OF_ALPHA = {2.0: 4.0, 5.0: 3.0, 10.0: 2.0, 20.0: 1.0}   # [assumption]


@dataclass
class EnvConfig:
    N: int = 12
    M: int = 8
    L: float = 1000.0          # arena side, m
    speed: float = 15.0        # m/s
    r_cap: float = 30.0        # on-site radius, m
    dt: float = 0.5            # decision epoch, s
    horizon: int = 300         # 150 s missions
    n_jammers: int = 2
    jam_radius: float = 200.0
    jam_speed: float = 4.0
    threat: ThreatProfile = field(default_factory=ThreatProfile)


class CertSwarm:
    def __init__(self, B: int, cfg: EnvConfig, seed: int = 0):
        self.B, self.cfg = B, cfg
        self.rng = np.random.default_rng(seed)
        self.reset()

    # ------------------------------------------------------------------
    def reset(self):
        c, B, rng = self.cfg, self.B, self.rng
        self.t = 0
        self.pos = rng.uniform(0, c.L, (B, c.N, 2))
        self.site = rng.uniform(0.1 * c.L, 0.9 * c.L, (B, c.M, 2))
        self.alpha = rng.choice(ALERT_LIMITS, size=(B, c.M))
        self.value = np.vectorize(VALUE_OF_ALPHA.get)(self.alpha).astype(float)
        self.jam = rng.uniform(0, c.L, (B, c.n_jammers, 2))
        self.jam_v = rng.normal(0, 1, (B, c.n_jammers, 2))
        self.cert = CertificateProcess(B, c.N, c.threat, rng)
        self.rho = self.cert.rho()
        self.rho_prev = self.rho.copy()
        self.assign = np.full((B, c.N), IDLE, dtype=int)
        self.dwell = np.zeros((B, c.N))
        return self.obs()

    # ------------------------------------------------------------------
    def jam_mask(self):
        d = np.linalg.norm(self.pos[:, :, None, :] - self.jam[:, None, :, :], axis=-1)
        return (d <= self.cfg.jam_radius).any(-1)

    def obs(self, blind: bool = False):
        """Per-agent egocentric observation (B, N, D)."""
        c = self.cfg
        B, N, M = self.B, c.N, c.M
        rel = (self.site[:, None, :, :] - self.pos[:, :, None, :]) / c.L      # B,N,M,2
        dist = np.linalg.norm(rel, axis=-1, keepdims=True)                     # B,N,M,1
        rho = np.minimum(self.rho, 60.0)
        drho = np.clip(self.rho - self.rho_prev, -20, 20) / 20.0
        elig = (self.rho[:, :, None] <= self.alpha[:, None, :]).astype(float)
        mine = np.zeros((B, N, M))
        bi, ii = np.nonzero(self.assign >= 0)
        mine[bi, ii, self.assign[bi, ii]] = 1.0
        held = mine.sum(1, keepdims=True)                                      # B,1,M
        other = np.clip(held - mine, 0, 1)
        a = np.broadcast_to((self.alpha / 20.0)[:, None, :, None], (B, N, M, 1))
        v = np.broadcast_to((self.value / 4.0)[:, None, :, None], (B, N, M, 1))
        if blind:
            elig = np.zeros_like(elig)
        tf = np.concatenate([rel, dist, a, v, elig[..., None], mine[..., None],
                             other[..., None]], -1)                            # B,N,M,8
        # egocentric, permutation-invariant layout: slot k = k-th nearest task
        self.order = np.argsort(dist[..., 0], axis=-1, kind="stable")          # B,N,M
        tf = np.take_along_axis(tf, self.order[..., None], axis=2)
        task_feats = tf.reshape(B, N, M * 8)
        own = np.stack([self.pos[..., 0] / c.L, self.pos[..., 1] / c.L,
                        rho / 20.0, drho, (self.assign >= 0).astype(float)], -1)
        jrel = ((self.jam[:, None, :, :] - self.pos[:, :, None, :]) / c.L).reshape(B, N, -1)
        lv = np.asarray(ALERT_LIMITS)
        prof = (self.rho[:, :, None] <= lv[None, None, :]).mean(1)              # B,4
        prof = np.broadcast_to(prof[:, None, :], (B, N, lv.size))
        if blind:
            own = own.copy()
            own[..., 2:4] = 0.0
            prof = np.zeros_like(prof)
        return np.concatenate([own, task_feats, jrel, prof], -1).astype(np.float32)

    @property
    def obs_dim(self):
        return 5 + 8 * self.cfg.M + 2 * self.cfg.n_jammers + len(ALERT_LIMITS)

    # ------------------------------------------------------------------
    def allocate(self, proposal, mode: str, h: float = 0.0, lookahead: float = 0.0,
                 design_rho: float | None = None, dwell_s: float = 0.0,
                 eta: float = 0.0, keep_lookahead: float = 0.0):
        """Map proposals (B,N) to executed assignments (B,N)."""
        c = self.cfg
        out = np.full_like(proposal, IDLE)
        for b in range(self.B):
            prop = proposal[b].copy()
            prev = self.assign[b]
            if dwell_s > 0:   # voluntary moves only after the dwell time
                stay = (prev >= 0) & (self.dwell[b] < dwell_s)
                prop[stay] = prev[stay]
            if mode == "project":
                el = C.eligibility(self.rho[b], self.alpha[b], holder_of=prev, h=h,
                                   lookahead=lookahead, eta=eta,
                                   keep_lookahead=keep_lookahead)
                out[b] = C.lexicographic_projection(el, prop, self.value[b], prev=prev,
                                                    eps_prev=0.0)
            elif mode == "mask":
                ok = prop >= 0
                ok[ok] = self.rho[b][ok] <= self.alpha[b][prop[ok]]
                out[b] = C.resolve_conflicts(np.where(ok, prop, IDLE), c.M)
            elif mode == "fixed_margin":
                ok = prop >= 0
                ok[ok] = design_rho <= self.alpha[b][prop[ok]]
                out[b] = C.resolve_conflicts(np.where(ok, prop, IDLE), c.M)
            elif mode == "none":
                out[b] = C.resolve_conflicts(prop, c.M)
            elif mode == "gnp":
                out[b] = C.nested_greedy(self.rho[b], self.alpha[b], value=self.value[b])
            else:
                raise ValueError(mode)
        return out

    # ------------------------------------------------------------------
    def step(self, executed):
        c = self.cfg
        B, N = self.B, c.N
        bidx = np.arange(B)[:, None]
        # violations are judged at execution time, on the current certificate
        held = executed >= 0
        a_exec = np.where(held, self.alpha[bidx, np.maximum(executed, 0)], np.inf)
        viol = held & (self.rho > a_exec)
        d_dec = C.batch_deficiency(self.rho, self.alpha)   # Lemma 1 at the decision epoch
        switched = (executed != self.assign) & (self.assign >= 0)
        self.dwell = np.where(executed == self.assign, self.dwell + c.dt, 0.0)
        self.assign = executed
        # motion
        tgt = np.where(held[..., None], self.site[bidx, np.maximum(executed, 0)], self.pos)
        vec = tgt - self.pos
        dist = np.linalg.norm(vec, axis=-1, keepdims=True)
        stepv = np.minimum(dist, c.speed * c.dt)
        self.pos = self.pos + np.where(dist > 1e-9, vec / np.maximum(dist, 1e-9), 0) * stepv
        on_site = held & (np.linalg.norm(tgt - self.pos, axis=-1) <= c.r_cap)
        # jammers random-walk, reflect at the walls
        self.jam_v = 0.9 * self.jam_v + 0.1 * self.rng.normal(0, 1, self.jam_v.shape)
        sp = np.linalg.norm(self.jam_v, axis=-1, keepdims=True) + 1e-9
        self.jam = np.clip(self.jam + self.jam_v / sp * c.jam_speed * c.dt, 0, c.L)
        # certificate
        self.rho_prev = self.rho
        self.rho = self.cert.step(c.dt, jam_mask=self.jam_mask())
        # coverage after the move, judged against the certificate now in force
        a_now = np.where(held, self.alpha[bidx, np.maximum(executed, 0)], np.inf)
        feas_now = held & (self.rho <= a_now)
        vals = np.where(held, self.value[bidx, np.maximum(executed, 0)], 0.0)
        tot = self.value.sum(1)
        r_cert = (vals * (on_site & feas_now)).sum(1) / tot
        r_nom = (vals * on_site).sum(1) / tot
        info = {
            "viol": viol.sum(1),                       # violating agent-steps
            "cost": viol.mean(1),
            "r_cert": r_cert,
            "r_nom": r_nom,
            "assigned_feasible": (held & ~viol).sum(1),
            "bound": c.M - d_dec,                          # max coverable tasks, Lemma 1
            "switches": switched.sum(1),
            "cov_cert_count": (on_site & feas_now).sum(1),
            "exposure": (held & ~viol & ~feas_now).sum(1),   # feasible at decision, jumped before next
        }
        self.t += 1
        done = self.t >= c.horizon
        return self.obs(), info, done
