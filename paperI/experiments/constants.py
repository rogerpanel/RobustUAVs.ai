"""Paper I constants, each with an explicit provenance tag.

Provenance tags (same discipline as the parent artifact):
  measured        -- computed in this repository from a real capture
  derived         -- arithmetic on measured quantities
  literature      -- copied from a cited, peer-reviewed or standard source
  physics_model   -- a stated physical/engineering model with stated parameters
  assumption      -- a modelling choice we make and state; swept where it matters

Nothing in this file is fitted to make a result come out; every value is
either read from the parent artifact or from the cited source.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PARENT_RES = REPO / "results"
OUT = REPO / "paperI" / "results"
OUT.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Parent certificate (paper D, "From Wire to Flight")
# --------------------------------------------------------------------------
H = 2                 # attacker-controlled hops, grid topology   [measured]
S_SLACK = 5.0         # contact-window slack, s                   [measured]
THETA_OP = 0.25       # paper operating point, s                  [assumption]
THETA_BENIGN = 0.178  # benign residual ceiling (FPR=0 floor), s  [measured]
L_LOC = 1.1814        # local Lipschitz constant                  [measured]
T_C = 1.0             # certification horizon, s                  [assumption]
E = math.exp(L_LOC * T_C)
MARGINS = (2.0, 5.0, 10.0, 20.0)  # corridor half-widths, m        [assumption]

# delay-to-position rates from results/gamma_campaign_samples.csv [measured]
# (supremum of the baseline-corrected estimator gamma_delta per flight/signal)
GAMMA_SPOOF_EKF_SUP = 1.625
GAMMA_SPOOF_RX_SUP = 0.6086
GAMMA_JAM_EKF_SUP = 0.9331
GAMMA_JAM_RX_SUP = 1.2309
# per-flight peak secant rates, results/gamma_stability.csv      [measured]
GAMMA_SPOOF_EKF_SECANT = 1.365
GAMMA_JAM_EKF_SECANT = 0.5185


def delta_theta(theta: float, h: int = H, s: float = S_SLACK) -> float:
    """Lemma 1 of the parent: worst undetected cumulative delay."""
    return h * min(theta, s)


# --------------------------------------------------------------------------
# gamma scenarios for (unauthenticated, authenticated) GNSS
#
# gamma_u is measured on the spoofing flight. gamma_a ("estimator not
# following an adversary") is a MEASURED PROXY taken from the jamming flight.
# CAVEAT (independent review): that flight's receiver keeps fix_type=3 with
# 12-14 satellites throughout the post-onset window, so the proxy is a
# degraded-but-honest fused estimator, NOT dead reckoning after rejection.
# Runbook experiments E1/E3 measure the latter; swap it in here when present.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class GammaScenario:
    name: str
    gamma_u: float
    gamma_a: float
    tag: str
    note: str

    @property
    def ratio(self) -> float:
        return self.gamma_u / self.gamma_a


GAMMA_SCENARIOS = [
    GammaScenario("conservative", GAMMA_SPOOF_EKF_SUP, GAMMA_JAM_RX_SUP,
                  "measured_proxy",
                  "gamma_a = largest jamming rate over either error signal"),
    GammaScenario("headline", GAMMA_SPOOF_EKF_SUP, GAMMA_JAM_EKF_SUP,
                  "measured_proxy",
                  "EKF signal on both sides (the signal the certificate consumes)"),
    GammaScenario("secant", GAMMA_SPOOF_EKF_SECANT, GAMMA_JAM_EKF_SECANT,
                  "measured_proxy",
                  "per-flight peak secant rates (coarser calibration)"),
]

# --------------------------------------------------------------------------
# Authentication schemes.  Cycle counts are for ARM Cortex-M (pqm4 / SLOTHY /
# Fujii-Aranha / cifra); we scale to the 480 MHz STM32H7 of a Pixhawk 6
# assuming equal cycles per operation (flash wait states and cache effects at
# 480 MHz are NOT modelled -- that is exactly what RQ2's board run replaces).
# --------------------------------------------------------------------------
F_CPU = 480e6  # STM32H743 core clock, Hz                       [literature]


@dataclass(frozen=True)
class Scheme:
    key: str
    label: str
    tag_bytes: int          # bytes added to the authenticated message
    sign_cycles: float
    verify_cycles: float
    source_auth: bool       # True if a key-holding relay cannot forge for others
    pq: bool                # post-quantum secure
    sign_tail_factor: float  # p(1-1e-6) / mean for sign time (1 if deterministic)
    cite: str

    @property
    def t_sign(self) -> float:
        return self.sign_cycles / F_CPU

    @property
    def t_verify(self) -> float:
        return self.verify_cycles / F_CPU


def _mldsa_tail(eta: float = 1e-6, mean_iters: float = 4.25) -> float:
    """ML-DSA-44 signing is a rejection-sampling loop; the iteration count is
    geometric with success probability p = 1/mean_iters (FIPS 204 reports an
    expected ~4.25 iterations for ML-DSA-44). Return the (1-eta) quantile of
    the iteration count divided by its mean: the tail factor on sign time."""
    p = 1.0 / mean_iters
    k = math.ceil(math.log(eta) / math.log(1.0 - p))
    return k / mean_iters


SCHEMES = [
    # MAVLink 2 style: SHA-256 over key||packet, truncated to 48 bits; 13-byte
    # block (link id 1 + timestamp 6 + signature 6). Shared key per link.
    Scheme("mav2", "Group MAC (MAVLink~2 style, SHA-256/48)", 13, 27_337, 27_337,
           False, True, 1.0, "mavlink_signing,cifra"),
    Scheme("ed25519", "Ed25519", 64, 496_039, 1_265_078,
           True, False, 1.0, "fujii2019curve25519"),
    Scheme("fndsa512", "FN-DSA-512 (Falcon)", 666, 22_469_685, 396_949,
           True, True, 1.0, "pqm4"),  # Falcon tail not modelled
    Scheme("mldsa44", "ML-DSA-44", 2420, 2_127_982, 813_339,
           True, True, _mldsa_tail(), "abdulrahman2025slothy,fips204"),
    Scheme("slhdsa128f", "SLH-DSA-SHA2-128f", 17_088, 368_575_228, 21_923_628,
           True, True, 1.0, "pqm4,fips205"),
    Scheme("slhdsa128s", "SLH-DSA-SHA2-128s", 7_856, 7_657_558_168, 7_471_794,
           True, True, 1.0, "pqm4,fips205"),
]
SCHEME = {s.key: s for s in SCHEMES}

# TESLA-style delayed disclosure: per-message MAC (truncated SHA-256, 10 B)
# plus a disclosed 16 B key; authentication completes only after the key for
# interval i is disclosed d intervals later. t_proto = d * T_int + sync bound.
TESLA_MAC_BYTES = 10
TESLA_KEY_BYTES = 16


# --------------------------------------------------------------------------
# Measured base load of a real UAVCAN bus (HCRL UAVCAN, Pixhawk 4 testbed)
# results/hcrl_type_signatures.csv: benign-segment frame rate per scenario.
# --------------------------------------------------------------------------
def hcrl_benign_rates() -> list[float]:
    import csv
    p = PARENT_RES / "hcrl_type_signatures.csv"
    with p.open() as fh:
        return [float(r["normal_rate_fps"]) for r in csv.DictReader(fh)]


CAN_BITRATE = 1e6        # DroneCAN default, bit/s             [assumption: HCRL bitrate unconfirmed]
CANFD_ARB_RATE = 1e6     # CAN FD arbitration phase, bit/s     [assumption]
CANFD_DATA_RATE = 5e6    # CAN FD data phase, bit/s            [assumption]

# Verification CPU share the flight controller can give to authentication.
BETA_CPU = 0.20          # [assumption; swept in the paper 0.05..1]

# --------------------------------------------------------------------------
# Freshness windows in deployed protocols
# --------------------------------------------------------------------------
TAU_FRESH_MAVLINK = 60.0   # MAVLink 2 signing accepts up to 1 min behind  [literature]
TAU_FRESH_OSNMA = 30.0     # OSNMA loose-sync T_L for ADKD0/4              [literature]
TAU_FRESH_OSNMA_MAX = 165.0  # receiver-guideline upper value              [literature]
