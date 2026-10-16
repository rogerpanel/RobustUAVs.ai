"""Paper V constants, each with a provenance tag (runbook P0.6).

Tags
  [parent]     measured or proved in the parent manuscript, as carried by Paper III/IV code
  [paperIII]   paperIII/experiments/certcmdp/certificate.py
  [paperIV]    paperIV/experiments/constants.py and paperIV/results/*
  [platform]   platform/backend/app/uav.py
  [model]      modelling choice of Paper V (stated, sweepable)
  [assumption] declared before any result that depends on it, never re-tuned afterwards
  [derived]    arithmetic on the above

Values from Papers III and IV are COPIED here (not imported): Paper I, Paper IV and
Paper V all have a flat `constants.py`, and Paper IV's modules do `from constants import *`
(runbook 0.2 item 3). tests/test_constants.py checks every copied value against its source.

    python3 constants.py --write-csv      -> results/constants_paperV.csv
"""
from __future__ import annotations

import csv
import math
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                                  # paperV/
REPO = ROOT.parent                                  # repository root
RESULTS = ROOT / "results"
RESTRICTED = ROOT / "restricted"

# ------------------------------------------------------------------ parent chain
GAMMA_SUP = 1.625        # [paperIV] m/s, campaign supremum over 674 hover samples
GAMMA_KIN = 15.0         # [parent] m/s, kinematic companion row
GAMMA_FLEET = 1.365      # [platform] fleet-table gamma (ablation level only)
L_LOC = 1.1814           # [paperIV] local Lipschitz estimate (results/local_lipschitz.csv)
L_ENGINE = 1.01          # [parent] engine default (ablation level only; never edit the engine)
T_C = 1.0                # [parent] s, certification horizon
AMP = math.exp(L_LOC * T_C)   # [derived] e^{L T_c}
SLACK_S = 4.84           # [paperIV] s, saturation of the undetected relay delay
H_HOPS = 2               # [paperIV] malicious hops
CORRIDOR_M = (2.0, 5.0, 10.0, 20.0)   # [paperIV] corridor half-width classes m


def l_rho(gamma=GAMMA_SUP, L=L_LOC):
    """L_rho = e^{L T_c} gamma: metres of certified error per second of staleness. [paperIII KAPPA]"""
    return math.exp(L * T_C) * gamma


L_RHO = l_rho()          # [derived] 5.2958 m/s (Paper III KAPPA)

# ------------------------------------------------------------------ Paper IV budget
DELTA_ADV_R1 = {0.01: 5.463, 0.05: 5.463, 0.10: 5.038}   # [paperIV] r1_delta_adv.csv delta_pooled_m (headline)
DELTA_ADV_PILOT = 4.371  # [paperIV] e4_delta_adv.csv (sensitivity row only)
FPR_HEADLINE = 0.05      # [paperIV] operating point of the stealth budget
THETA_NET = 0.1          # [model] s, network-delay operating point of level b2
EPS_B3 = 0.05            # [model] tail risk of level b3: s*(0.05)

# ------------------------------------------------------------------ platform / mission
N_UAV = 12               # [platform] uav.py MAX_FLEET
T_MISSION = 70.0         # [platform] uav.py NOMINAL_MISSION_S (= parent reference profile)
KAPPA_SCHED = 0.10       # [parent] schedule tolerance, headline. Never call it KAPPA
KAPPA_SCHED_ALT = 0.25   # [platform] uav.py KAPPA, sensitivity
T_HORIZON_SIM = (1 + KAPPA_SCHED_ALT) * T_MISSION   # [model] 87.5 s: both deadlines from one run
NUM_ATTACK_CLASSES = 9   # [platform] uav.py ATTACKS: nine attack classes plus nominal

# ------------------------------------------------------------------ control and filter
DT = 0.1                 # [model] s, 10 Hz control and filter; Paper III Thm 3 needs DT <= 0.200 s at alpha = 2 m
PLAN_PERIOD = 5.0        # [model] s between planner calls (14 per 70 s mission)
N_P = 20                 # [model] filter horizon (ablation 10, 20, 40). Use N_P, never H
V_MAX = 15.0             # [platform] m/s per-axis speed bound
V_CRUISE = 12.0          # [platform] m/s benign cruise speed
U_MAX = 4.0              # [paperIV] m/s^2 per-axis acceleration limit
KP, KD = 1.2, 1.8        # [paperIV] PD gains: pi_nom position loop and the tube controller
K_V = 1.0                # [model] 1/s velocity-tracking gain of pi_nom
LAMBDA_C = None          # [model] Koehler contraction rate; derived from the tube controller (admissible.py)
ETA_INTERVENE = 1e-3     # [model] m/s^2, ||v0 - pi_nom||_inf above which a step counts as an intervention
TERMINAL_V_LAT = 3.0     # [model] m/s lateral speed cap inside the loiter terminal set X_f

# ------------------------------------------------------------------ corridor geometry
S_LO, S_HI = -30.0, 870.0      # [model] along-track geofence, m (a 900 m corridor)
WAYPOINTS_S = (240.0, 480.0, 720.0)   # [model] task sites along the corridor; the last is the goal
R_REACH = 10.0           # [model] m, waypoint reached radius
LANE_SPACING = 60.0      # [model] m between parallel corridors (world snapshot only; separation off)

# ------------------------------------------------------------------ disturbance (A1)
C_DRAG = 0.35            # [paperIV] 1/s drag; the autopilot cancels own-speed drag, gusts act as C_DRAG * g
W20_KT = (15.0, 30.0)    # [paperIV] envelope C4: W20 drawn per mission, uniform in this range
H_FT = 100.0             # [paperIV] Dryden altitude
GUST_CLIP_SIGMA = 2.0    # [assumption] gust velocity clipped at 2 sigma_v(W20): the declared envelope
W_INFLATE = 1.2          # [assumption] fixed BEFORE calibration: W_BAR = W_INFLATE * calibration supremum
W_BAR = None             # [derived] set from results/wbar_calibration.csv by load_wbar()

# ------------------------------------------------------------------ certificate (A2)
DELTA_BAR_S = 0.944      # [assumption] declared staleness envelope: rho <= rho_bar = L_rho * DELTA_BAR_S
J_BAR = 0.0              # [assumption] no upward jumps (delay-adversary, re-anchoring regime); ablation > 0


@lru_cache(maxsize=None)
def residual_pools():
    """[parent] per-hop residual pools of results/hop_ledger.csv (benign, hidden), as Paper III."""
    ben, hid = [], []
    with (REPO / "results" / "hop_ledger.csv").open() as fh:
        for r in csv.DictReader(fh):
            x = float(r["residual_s"])
            if r["malicious_sender"] == "0":
                ben.append(x)
            elif r["suspicious"] == "0":
                hid.append(x)
    return np.asarray(ben), np.asarray(hid)


def theta_benign():
    """[parent] benign residual ceiling, s (Paper III THETA_BENIGN = 0.178)."""
    return float(residual_pools()[0].max())


def rho_floor(gamma=GAMMA_SUP, L=L_LOC):
    """[derived] largest rho right after a re-anchor: L_rho * benign residual ceiling."""
    return l_rho(gamma, L) * theta_benign()


def rho_bar(gamma=GAMMA_SUP, L=L_LOC, delta_bar=DELTA_BAR_S):
    """[derived] declared protection-level envelope (A2)."""
    return l_rho(gamma, L) * delta_bar


def dryden_sigma(w20_kt, h_ft=H_FT):
    """[paperIV] MIL-F-8785C low-altitude Dryden lateral sigma_v (m/s) and L_v (m), re-implemented."""
    kt = 0.514444
    sigma_w = 0.1 * w20_kt * kt
    k = 0.177 + 0.000823 * h_ft
    return sigma_w / k ** 0.4, (h_ft / k ** 1.2) * 0.3048


@lru_cache(maxsize=None)
def load_wbar():
    """W_BAR from the committed calibration (P1.4). Raises if the calibration is missing."""
    p = RESULTS / "wbar_calibration.csv"
    if not p.exists():
        raise FileNotFoundError(f"{p} missing: run plant.py --calibrate-wbar first")
    with p.open() as fh:
        rows = {r["name"]: r for r in csv.DictReader(fh)}
    return float(rows["w_bar"]["value"])


def constant_rows():
    """(name, value, unit, provenance, source) for results/constants_paperV.csv."""
    try:
        wbar = load_wbar(); wsrc = "results/wbar_calibration.csv (11xxx supremum x W_INFLATE)"
    except FileNotFoundError:
        wbar = float("nan"); wsrc = "not yet calibrated"
    return [
        ("GAMMA_SUP", GAMMA_SUP, "m/s", "paperIV", "paperIV/experiments/constants.py (674 hover samples)"),
        ("GAMMA_KIN", GAMMA_KIN, "m/s", "parent", "kinematic companion row"),
        ("GAMMA_FLEET", GAMMA_FLEET, "m/s", "platform", "fleet-table gamma (ablation)"),
        ("L_LOC", L_LOC, "1/s", "paperIV", "results/local_lipschitz.csv"),
        ("T_C", T_C, "s", "parent", "certification horizon"),
        ("L_RHO", L_RHO, "m/s", "derived", "e^{L_LOC T_C} GAMMA_SUP (Paper III KAPPA)"),
        ("SLACK_S", SLACK_S, "s", "paperIV", "paperIV/experiments/constants.py"),
        ("H_HOPS", H_HOPS, "-", "paperIV", "paperIV/experiments/constants.py"),
        ("CORRIDOR_M", "2;5;10;20", "m", "paperIV", "paperIV/experiments/constants.py"),
        ("DELTA_ADV_R1_FPR01", DELTA_ADV_R1[0.01], "m", "paperIV", "paperIV/results/r1_delta_adv.csv"),
        ("DELTA_ADV_R1_FPR05", DELTA_ADV_R1[0.05], "m", "paperIV", "paperIV/results/r1_delta_adv.csv (headline)"),
        ("DELTA_ADV_R1_FPR10", DELTA_ADV_R1[0.10], "m", "paperIV", "paperIV/results/r1_delta_adv.csv"),
        ("DELTA_ADV_PILOT", DELTA_ADV_PILOT, "m", "paperIV", "paperIV/results/e4_delta_adv.csv (sensitivity)"),
        ("THETA_NET", THETA_NET, "s", "model", "network-delay operating point of b2"),
        ("EPS_B3", EPS_B3, "-", "model", "tail risk of b3"),
        ("N_UAV", N_UAV, "-", "platform", "uav.py MAX_FLEET"),
        ("T_MISSION", T_MISSION, "s", "platform", "uav.py NOMINAL_MISSION_S"),
        ("KAPPA_SCHED", KAPPA_SCHED, "-", "parent", "schedule tolerance (headline)"),
        ("KAPPA_SCHED_ALT", KAPPA_SCHED_ALT, "-", "platform", "uav.py KAPPA (sensitivity)"),
        ("T_HORIZON_SIM", T_HORIZON_SIM, "s", "model", "(1 + 0.25) T"),
        ("NUM_ATTACK_CLASSES", NUM_ATTACK_CLASSES, "-", "platform", "uav.py ATTACKS: nine plus nominal"),
        ("DT", DT, "s", "model", "10 Hz control; <= (alpha - rho_0)/L_rho = 0.200 s at alpha = 2 m"),
        ("PLAN_PERIOD", PLAN_PERIOD, "s", "model", "planner cadence"),
        ("N_P", N_P, "-", "model", "filter horizon"),
        ("V_MAX", V_MAX, "m/s", "platform", "per-axis speed bound"),
        ("V_CRUISE", V_CRUISE, "m/s", "platform", "benign cruise"),
        ("U_MAX", U_MAX, "m/s^2", "paperIV", "PD saturation"),
        ("KP", KP, "1/s^2", "paperIV", "PD position gain"),
        ("KD", KD, "1/s", "paperIV", "PD velocity gain"),
        ("K_V", K_V, "1/s", "model", "pi_nom velocity gain"),
        ("ETA_INTERVENE", ETA_INTERVENE, "m/s^2", "model", "intervention threshold"),
        ("TERMINAL_V_LAT", TERMINAL_V_LAT, "m/s", "model", "lateral speed cap in X_f"),
        ("S_LO", S_LO, "m", "model", "along-track geofence"),
        ("S_HI", S_HI, "m", "model", "along-track geofence"),
        ("WAYPOINTS_S", ";".join(str(w) for w in WAYPOINTS_S), "m", "model", "task sites; last = goal"),
        ("R_REACH", R_REACH, "m", "model", "waypoint radius"),
        ("C_DRAG", C_DRAG, "1/s", "paperIV", "paperIV/experiments/constants.py"),
        ("W20_KT_LO", W20_KT[0], "kt", "paperIV", "envelope C4"),
        ("W20_KT_HI", W20_KT[1], "kt", "paperIV", "envelope C4"),
        ("H_FT", H_FT, "ft", "paperIV", "Dryden altitude"),
        ("GUST_CLIP_SIGMA", GUST_CLIP_SIGMA, "-", "assumption", "declared gust envelope"),
        ("W_INFLATE", W_INFLATE, "-", "assumption", "fixed before calibration"),
        ("W_BAR", wbar, "m/s^2", "derived", wsrc),
        ("DELTA_BAR_S", DELTA_BAR_S, "s", "assumption", "declared staleness envelope (A2)"),
        ("RHO_FLOOR", rho_floor(), "m", "derived", "L_RHO x benign residual ceiling (hop_ledger.csv)"),
        ("RHO_BAR", rho_bar(), "m", "derived", "L_RHO x DELTA_BAR_S"),
        ("J_BAR", J_BAR, "m", "assumption", "no upward jumps"),
    ]


def write_csv():
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "constants_paperV.csv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "value", "unit", "provenance", "source"])
        for name, val, unit, prov, src in constant_rows():
            if isinstance(val, float):
                val = f"{val:.6g}"
            w.writerow([name, val, unit, prov, src])
    return out


if __name__ == "__main__":
    if "--write-csv" in sys.argv:
        print("wrote", write_csv())
