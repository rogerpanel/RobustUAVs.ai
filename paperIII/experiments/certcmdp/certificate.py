"""Certified protection-level process rho_i(t) for Paper III.

Every constant is read from, or derived from, the parent artifact
(paper D, "From Wire to Flight") and carries a provenance tag:

  measured      computed in this repository from a real capture
  derived       arithmetic on measured quantities
  assumption    a modelling choice we state and sweep where it matters

The parent certificate bounds the position error of an aircraft whose
navigation input is Delta seconds stale by the Gronwall tube

    rho = exp(L*T) * gamma_sup * Delta                               (P-D, Thm 1)

We call rho_i(t) the agent's *certified protection level* (by analogy with the
GNSS integrity protection level) and a task's corridor half-width its *alert
limit* alpha(tau). Agent i may hold task tau only while rho_i(t) <= alpha(tau).
Paper III never looks inside this map: it consumes rho_i(t) as an arbitrary
bounded cadlag process. The generator below only has to be *representative*;
the guarantees do not depend on it.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
PARENT_RES = REPO / "results"
OUT = REPO / "paperIII" / "results"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- constants
L_LOC = 1.1814          # local Lipschitz constant, results/local_lipschitz.csv  [measured]
T_C = 1.0               # certification horizon, s                             [assumption, parent]
GAMMA_SUP = 1.625       # campaign supremum, results/gamma_campaign_samples.csv [measured]
S_SLACK = 5.0           # contact-window slack, s                              [measured, parent]
THETA_BENIGN = 0.178    # benign residual ceiling, s, results/hop_ledger.csv   [measured]
ALERT_LIMITS = (2.0, 5.0, 10.0, 20.0)   # corridor half-widths, m             [assumption, parent]
KAPPA = math.exp(L_LOC * T_C) * GAMMA_SUP  # m of certified error per s of staleness [derived]


def rho_of_staleness(delta_s):
    """Parent tube: certified position-error bound for staleness delta (s)."""
    return KAPPA * np.asarray(delta_s, dtype=float)


@lru_cache(maxsize=None)
def residual_pools():
    """Empirical per-hop residual pools from the parent's 15,392-hop ledger.

    benign:  residuals on hops whose sender is honest           [measured]
    hidden:  residuals on malicious hops the detector did NOT flag [measured]
    """
    ben, hid = [], []
    with (PARENT_RES / "hop_ledger.csv").open() as fh:
        for r in csv.DictReader(fh):
            x = float(r["residual_s"])
            if r["malicious_sender"] == "0":
                ben.append(x)
            elif r["suspicious"] == "0":
                hid.append(x)
    return np.asarray(ben), np.asarray(hid)


@lru_cache(maxsize=None)
def gamma_samples():
    g = []
    with (PARENT_RES / "gamma_campaign_samples.csv").open() as fh:
        for r in csv.DictReader(fh):
            g.append(float(r["gamma_delta_m_s"]))
    return np.asarray(g)


@dataclass
class ThreatProfile:
    """Rates of the three degradation mechanisms (per agent, per second).

    All are [assumption] and are swept in the experiments. Magnitudes of the
    relay-delay jumps are drawn from the measured hidden-residual pool.
    """
    jam_rate: float = 0.010        # onset rate of fix loss (dead reckoning)
    jam_mean_s: float = 6.0        # mean jamming episode length, s
    relay_rate: float = 0.010      # onset rate of an undetected relay-delay attack
    relay_mean_s: float = 10.0     # mean duration of the stale-correction episode
    relay_hops: int = 2            # attacker-controlled hops H (parent, grid)
    fault_rate: float = 0.002      # sensor-fault onset rate
    fault_mean_s: float = 4.0
    reanchor_s: float = 2.0        # re-anchoring time after an episode ends [assumption, parent]
    stale_cap_s: float = 2 * S_SLACK  # staleness saturates (parent Lemma 1 slack x H)


class CertificateProcess:
    """Vectorised generator of rho_i(t) for B fleets of N agents.

    State per agent: benign staleness floor (resampled on each re-anchor),
    a dead-reckoning clock (grows 1 s/s while jammed or faulted), and a
    relay-delay offset (a JUMP: the adversary's hidden delay arrives at once).
    rho = KAPPA * (benign + dr + relay). Upward jumps make the process cadlag
    but not Lipschitz; between jumps it rises at most at rate KAPPA.
    """

    def __init__(self, B: int, N: int, prof: ThreatProfile, rng: np.random.Generator,
                 spatial_jam: np.ndarray | None = None):
        self.B, self.N, self.p, self.rng = B, N, prof, rng
        ben, hid = residual_pools()
        self.ben_pool, self.hid_pool = ben, hid
        self.benign = rng.choice(ben, size=(B, N))
        self.dr = np.zeros((B, N))
        self.relay = np.zeros((B, N))
        self.jam_left = np.zeros((B, N))
        self.relay_left = np.zeros((B, N))
        self.fault_left = np.zeros((B, N))
        self.reanchor_left = np.zeros((B, N))
        self.n_up_jumps = np.zeros((B, N), dtype=int)

    def rho(self):
        return KAPPA * (self.benign + self.dr + self.relay)

    def step(self, dt: float, jam_mask: np.ndarray | None = None):
        """Advance by dt. jam_mask (B,N) bool forces jamming (spatial jammers)."""
        p, rng = self.p, self.rng
        shp = (self.B, self.N)
        # onsets
        jam_on = rng.random(shp) < p.jam_rate * dt
        self.jam_left = np.where(jam_on & (self.jam_left <= 0),
                                 rng.exponential(p.jam_mean_s, shp), self.jam_left)
        f_on = rng.random(shp) < p.fault_rate * dt
        self.fault_left = np.where(f_on & (self.fault_left <= 0),
                                   rng.exponential(p.fault_mean_s, shp), self.fault_left)
        r_on = (rng.random(shp) < p.relay_rate * dt) & (self.relay_left <= 0)
        if r_on.any():
            k = int(r_on.sum())
            hops = rng.choice(self.hid_pool, size=(k, p.relay_hops)).sum(1)
            self.relay[r_on] = hops
            self.relay_left[r_on] = rng.exponential(p.relay_mean_s, k)
            self.n_up_jumps[r_on] += 1
        degraded = (self.jam_left > 0) | (self.fault_left > 0)
        if jam_mask is not None:
            degraded = degraded | jam_mask
        # dead-reckoning clock: grows while degraded, re-anchors after
        was = self.dr > 0
        self.dr = np.where(degraded, np.minimum(self.dr + dt, p.stale_cap_s), self.dr)
        ended = was & ~degraded & (self.reanchor_left <= 0)
        self.reanchor_left = np.where(ended, p.reanchor_s, self.reanchor_left)
        self.reanchor_left = np.where(degraded, 0.0, self.reanchor_left)
        rel = (self.reanchor_left > 0) & ~degraded
        self.reanchor_left = np.where(rel, self.reanchor_left - dt, self.reanchor_left)
        done = rel & (self.reanchor_left <= 0)
        self.dr = np.where(done, 0.0, self.dr)
        if done.any():
            self.benign[done] = rng.choice(self.ben_pool, size=int(done.sum()))
        # relay episodes end (downward jump)
        self.relay_left = np.maximum(self.relay_left - dt, 0.0)
        self.relay = np.where(self.relay_left > 0, self.relay, 0.0)
        self.jam_left = np.maximum(self.jam_left - dt, 0.0)
        self.fault_left = np.maximum(self.fault_left - dt, 0.0)
        return self.rho()


def write_constants_csv():
    ben, hid = residual_pools()
    g = gamma_samples()
    rows = [
        ("L_loc", L_LOC, "measured", "results/local_lipschitz.csv"),
        ("T_c_s", T_C, "assumption", "parent certificate horizon"),
        ("gamma_sup_m_s", GAMMA_SUP, "measured", f"max over {len(g)} post-onset samples"),
        ("gamma_sup_check", float(g.max()), "measured", "recomputed here"),
        ("kappa_m_per_s", KAPPA, "derived", "exp(L*T)*gamma_sup"),
        ("n_benign_hops", len(ben), "measured", "hop_ledger.csv"),
        ("benign_residual_max_s", float(ben.max()), "measured", "hop_ledger.csv"),
        ("n_hidden_hops", len(hid), "measured", "hop_ledger.csv, malicious & unflagged"),
        ("hidden_residual_max_s", float(hid.max()), "measured", "hop_ledger.csv"),
        ("hidden_residual_median_s", float(np.median(hid)), "measured", "hop_ledger.csv"),
        ("rho_benign_max_m", float(KAPPA * ben.max()), "derived", "kappa * benign max"),
        ("rho_jump_max_H2_m", float(KAPPA * 2 * hid.max()), "derived", "kappa * 2 * hidden max"),
    ]
    with (OUT / "constants_paperIII.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "value", "provenance", "source"])
        for r in rows:
            w.writerow([r[0], f"{r[1]:.6g}", r[2], r[3]])
    return rows


if __name__ == "__main__":
    for r in write_constants_csv():
        print(r)
