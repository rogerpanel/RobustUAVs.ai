"""Paper V pilot: every constant, with a provenance tag.

Tags
  [parent]  measured/proved in the parent manuscript, as carried by Paper III/IV code
  [P3]      Paper III (paperIII/experiments/certcmdp/certificate.py)
  [P4]      Paper IV (paperIV/experiments/constants.py, paperIV/results/*)
  [platform] platform/backend/app/uav.py
  [model]   modelling choice of this pilot (stated, sweepable)
  [derived] arithmetic on the above

The repository clone is used READ-ONLY: we read hop_ledger.csv (parent) and the
Paper IV marginals; nothing in the clone is modified.
"""
from __future__ import annotations

import csv
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]                  # repository root (paperV/experiments/ -> repo)
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                                          # paperV/
RESULTS = ROOT / "results"
FIGDATA = ROOT / "figdata"
RESULTS.mkdir(parents=True, exist_ok=True)
FIGDATA.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------ parent chain
GAMMA_SUP = 1.625          # [parent] m/s, campaign supremum over 674 samples
GAMMA_LEVELS = (1.365, 1.625, 15.0)   # [platform]/[parent]/[model] fleet-table gamma, supremum, kinematic
L_LOC = 1.1814             # [parent] local Lipschitz estimate (NOT the engine default 1.01)
T_C = 1.0                  # [parent] certification horizon, s
AMP = math.exp(L_LOC * T_C)  # [derived] e^{L T_c} = 3.259
SLACK_S = 4.84             # [P4] s, saturation of undetected relay delay
H_HOPS = 2                 # [P4] malicious hops


def kappa_rho(gamma=GAMMA_SUP):
    """L_rho = e^{L T_c} gamma: metres of certified error per second of staleness. [P3]"""
    return AMP * gamma


L_RHO = kappa_rho()        # [derived] 5.296 m/s (Paper III \nKappa)

# ------------------------------------------------------------ Paper IV budget
DELTA_ADV = 4.371          # [P4] m, paperIV/results/e4_delta_adv.csv (pooled supremum, FPR 1-10%)
THETA_NET = 0.25           # [P4] s, operating point of the network term


def net_tube(theta_net=THETA_NET):
    """[P4] run_pilot.net_tube: e^{LT_c} gamma H min(theta, s)."""
    return AMP * GAMMA_SUP * H_HOPS * min(theta_net, SLACK_S)


EPS_RISK = 0.10            # [model] tolerated tail risk for the stochastic part s*(eps)

# ------------------------------------------------------------ platform / mission
MAX_FLEET = 12             # [platform] uav.py MAX_FLEET
T_MISSION = 70.0           # [platform] uav.py NOMINAL_MISSION_S (parent reference profile)
KAPPA_SCHED = 0.10         # [parent] schedule tolerance (headline); 0.25 = uav.py KAPPA (sensitivity)
KAPPA_SCHED_ALT = 0.25     # [platform]
T_SIM = T_MISSION * (1 + KAPPA_SCHED_ALT)   # simulate to the longer deadline (87.5 s)
FLEETS = (4, 12)           # [model] pilot fleet sizes

# ------------------------------------------------------------ plant / control
DT = 0.1                   # [model] s, plant + tube-controller step (10 Hz)
TS = 0.5                   # [model] s, safety-filter period (2 Hz); planner queried each TS
SUB = int(round(TS / DT))  # inner steps per filter tick
NP = 10                    # [model] filter horizon N_p (5 s) -- braking from 12 m/s fits
U_MAX = 4.0                # [P4] m/s^2 per-axis actuator limit (Paper IV PD saturation)
V_MAX = 12.0               # [model] m/s per-axis speed limit (Paper III cruise class 12-15 m/s)
KP, KD = 1.2, 1.8          # [P4] tube feedback gains (Paper IV lateral PD)
W_BAR_NOM = 0.5            # [model] m/s^2 per-axis mismatch bound assumed by the filter
                           #   (~ c_drag * sigma_v of light Dryden turbulence, Paper IV constants:
                           #    0.35 1/s * 1.32 m/s = 0.46 m/s^2)
C_DRAG = 0.35              # [P4] 1/s, used only to motivate W_BAR_NOM
D_SEP = 5.0                # [model] m minimum true separation
DELTA_BAR_S = 0.944        # [model] declared staleness envelope (A2): rho <= L_rho * DELTA_BAR = 5.0 m
R_GOAL = 10.0              # [model] m, goal-reached radius
CRUISE = 10.0              # [model] m/s benign cruise speed (pair partners 8.5 m/s)
CRUISE_SLOW = 8.5
LANE = 40.0                # [model] m lateral lane spacing
GOAL_X = 560.0             # [model] m along-track goal distance
BUF = 0.10                 # [model] m, solver buffer for loose OSQP tolerances; plans are verified WITHOUT it
ETA_INT = 1e-2             # [model] m/s^2, intervention threshold on ||v0 - u_des||_inf
MU_REG = 1e-4              # [model] regulariser on v_1..v_{Np-1}


@lru_cache(maxsize=None)
def residual_pools():
    """[parent] per-hop residual pools from results/hop_ledger.csv (as Paper III)."""
    ben, hid = [], []
    with (REPO / "results" / "hop_ledger.csv").open() as fh:
        for r in csv.DictReader(fh):
            x = float(r["residual_s"])
            if r["malicious_sender"] == "0":
                ben.append(x)
            elif r["suspicious"] == "0":
                hid.append(x)
    return np.asarray(ben), np.asarray(hid)


def rho_floor(gamma=GAMMA_SUP):
    """[derived] benign protection-level ceiling: L_rho * max benign residual (~0.94 m)."""
    ben, _ = residual_pools()
    return kappa_rho(gamma) * float(ben.max())


def rho_bar(gamma=GAMMA_SUP, delta_bar=DELTA_BAR_S):
    return kappa_rho(gamma) * delta_bar


def provenance_rows():
    ben, hid = residual_pools()
    return [
        ("gamma_sup_m_s", GAMMA_SUP, "parent"), ("L_loc", L_LOC, "parent"), ("T_c_s", T_C, "parent"),
        ("amp_eLT", AMP, "derived"), ("L_rho_m_per_s", L_RHO, "derived"),
        ("rho_floor_m", rho_floor(), "derived (hop_ledger benign max %.3f s)" % ben.max()),
        ("rho_bar_m", rho_bar(), "model: L_rho * DELTA_BAR_S"),
        ("delta_adv_m", DELTA_ADV, "P4 e4_delta_adv.csv"), ("net_tube_theta025_m", net_tube(), "P4 net_tube"),
        ("hidden_residual_median_s", float(np.median(hid)), "parent hop_ledger"),
        ("max_fleet", MAX_FLEET, "platform"), ("T_mission_s", T_MISSION, "platform"),
        ("kappa_sched", KAPPA_SCHED, "parent"), ("kappa_sched_alt", KAPPA_SCHED_ALT, "platform"),
        ("dt_s", DT, "model"), ("Ts_filter_s", TS, "model"), ("Np", NP, "model"),
        ("u_max", U_MAX, "P4"), ("v_max", V_MAX, "model"), ("kp", KP, "P4"), ("kd", KD, "P4"),
        ("w_bar_nom", W_BAR_NOM, "model"), ("d_sep_m", D_SEP, "model"), ("delta_bar_s", DELTA_BAR_S, "model"),
    ]
