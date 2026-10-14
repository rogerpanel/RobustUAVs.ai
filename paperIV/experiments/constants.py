"""Every constant used by the Paper IV pilot, with a provenance tag.

Tags
  [parent]   measured or proved in the parent manuscript (paper D) and read
             from ../../results where possible
  [std]      taken from a published standard or datasheet class
  [model]    a modelling choice stated in the manuscript (sweepable)
  [px4]      PX4 EKF2 default class (confirm against the firmware you run)
"""
import math

# ---------------------------------------------------------------- parent chain
GAMMA_SUP = 1.625        # [parent] m/s, campaign supremum over 674 samples
SLACK_S = 4.84           # [parent] s, saturation of the undetected relay delay
H_HOPS = 2               # [parent] malicious hops in the paper operating point
L_LOC = 1.1814           # [parent] local Lipschitz estimate (results/local_lipschitz.csv)
T_C = 1.0                # [parent] certification horizon (s)
AMP = math.exp(L_LOC * T_C)  # Gronwall amplification e^{LT}

# ---------------------------------------------------------------- simulation
DT = 0.05                # [model] s, IMU / control step (20 Hz)
GNSS_EVERY = 2           # [model] GNSS at 10 Hz
T_MISSION = 60.0         # [model] s
N_STEPS = int(round(T_MISSION / DT))

# lateral closed loop
KP, KD = 1.2, 1.8        # [model] PD position gains (omega ~1.1 rad/s, zeta ~0.8)
U_MAX = 4.0              # [model] m/s^2 lateral acceleration limit
C_DRAG = 0.35            # [model] 1/s lateral drag coefficient of a small multirotor

# Dryden lateral turbulence, MIL-F-8785C low-altitude form  [std]
H_FT = 100.0             # altitude 100 ft (~30 m)
V_AIR = 8.0              # m/s cruise airspeed
KT = 0.514444
W20_KT = {"light": 15.0, "moderate": 30.0, "severe": 45.0}


def dryden_lateral(w20_kt, h_ft=H_FT):
    """sigma_v (m/s) and L_v (m) for the low-altitude Dryden model."""
    sigma_w = 0.1 * w20_kt * KT
    k = 0.177 + 0.000823 * h_ft
    sigma_v = sigma_w / k ** 0.4
    L_v = (h_ft / k ** 1.2) * 0.3048
    return sigma_v, L_v


# sensors
SIG_GNSS_WHITE = 0.5     # [model] m, per-axis white GNSS noise
GM_SIGMA, GM_TAU = 0.8, 60.0   # [model] GNSS Gauss-Markov drift (iono/multipath class)
SIG_ACC = 0.05           # [model] m/s^2 accelerometer white noise (per sample)
SIG_BIAS_RW = 0.002      # [model] m/s^2/sqrt(s) accelerometer bias random walk
SIG_ANCHOR = 0.3         # [model] m, trusted re-anchoring fix (condition C2')
T_ANCHOR = 5.0           # [model] s, re-anchoring interval (swept 5/10/20 s)

# benign faults (stochastic) [model, RflyMAD/ALFA categories]
P_BIAS_STEP, BIAS_STEP_SD = 0.30, 0.10   # IMU bias step, m/s^2
P_BIAS_DRIFT, BIAS_DRIFT_MULT = 0.20, 10.0
P_LOE, LOE_RANGE = 0.20, (0.10, 0.30)    # actuator loss of effectiveness
P_OUTAGE, OUTAGE_MEAN_S = 0.30, 5.0      # GNSS outage (jamming-induced fix loss)
P_JAMNOISE, JAMNOISE_MULT, JAMNOISE_S = 0.20, 3.0, 10.0

# KF tuning (the defender's assumed model) [px4-class]
KF_R = 1.0 ** 2          # GNSS measurement variance assumed by the filter
KF_QV = (0.3) ** 2       # velocity process noise (absorbs unmodelled accel)
KF_QB = (0.01) ** 2      # bias process noise (defender's bias-instability prior)

# detectors
CONSEC_CHI2 = 3          # consecutive GNSS epochs above gate
CONSEC_INV = 5
INV_WINDOW_S = 4.0
CUSUM_KAPPA = 1.0
ANCHOR_GATE = 10.83      # chi2(1) 0.999 quantile
FPR_TARGET = 0.05        # per-mission false-alarm budget for the operating point

CORRIDOR_M = (2.0, 5.0, 10.0, 20.0)   # [parent] corridor-margin classes
