"""Mission specifications for the Paper IV PX4 SITL transfer study.

A mission is fully described by a dict of PX4 parameters, written into the
instance's working directory before boot (p4_mission_params.txt, sourced by the
patched px4-rc.params). Every random input is drawn inside PX4 from streams
seeded by BEN_SEED and ATK_SEED and reseeded at arming, so a mission and its
benign twin (same spec with ATK_EN = 0) see the same noise, gust and faults.

The benign envelope and the attacker parameter boxes are those of the
reduced-order model (../constants.py, ../sim.py), drawn here per mission seed.
PX4-side differences are stated in PX4_PREREG.md (IMU noise is SIH's own, GNSS
offsets act in 2-D, the attack is cross-track, LoE scales all rotors).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from constants import (W20_KT, dryden_lateral, V_AIR, SIG_GNSS_WHITE, GM_SIGMA, GM_TAU,  # noqa: E402
                       SIG_BIAS_RW, P_BIAS_STEP, BIAS_STEP_SD, P_BIAS_DRIFT, BIAS_DRIFT_MULT,
                       P_LOE, LOE_RANGE, P_OUTAGE, OUTAGE_MEAN_S, P_JAMNOISE, JAMNOISE_MULT,
                       JAMNOISE_S, SIG_ANCHOR, T_MISSION)
from sim import decode, ATTACK_BOX  # noqa: E402

FAM_ID = {"step": 0, "ramp": 1, "fault_mimic": 2, "gnss_mimic": 3, "weather_mimic": 4}
FAMILIES = tuple(FAM_ID)
T_OFF = 15.0          # s after arming at which the 60 s mission window starts
T_END = T_MISSION     # mission window [0, T_END] in mission time
LINE_N_M = 700.0      # waypoint distance north of home (line = north axis through home)
ALT_M = 25.0
CRUISE = V_AIR        # 8 m/s
SIG_MOD = dryden_lateral(W20_KT["moderate"])[0]
W_LO, W_HI = W20_KT["light"], W20_KT["moderate"]

# fixed PX4 configuration of every mission (stated in PX4_PREREG.md)
PX4_FIXED = {
    "SDLOG_PROFILE": 35,          # default + estimator replay (full-rate GPS, IMU) + debug (offset log)
    "SDLOG_MODE": 0,              # log from arming to disarm
    "MPC_XY_CRUISE": CRUISE,
    "MPC_TKO_SPEED": 3.0,
    "MIS_TAKEOFF_ALT": ALT_M,
    "COM_RC_IN_MODE": 4,          # no stick input in SITL
    "COM_RCL_EXCEPT": 7,
    "NAV_RCL_ACT": 0,
    "NAV_DLL_ACT": 0,
    "EKF2_NOAID_TOUT": 10000000,  # 10 s of dead reckoning before the EKF declares position invalid
    "COM_POS_FS_EPH": 50.0,       # do not abort the mission on estimated-accuracy loss (outages)
    "SENS_EN_GPSSIM": 1,
}


def benign(seed: int, anchor: float | None = 5.0, wl=W_LO, wh=W_HI, sources=("env", "gnss", "fault")):
    """Benign envelope of one mission, drawn from seed exactly as sim.simulate draws per rollout."""
    rng = np.random.default_rng(seed)
    w20 = float(np.random.default_rng(seed + 1_000_000).uniform(wl, wh))   # run_pilot.wind(1, seed)
    sig_w, L_w = dryden_lateral(w20)
    bias_step_on = rng.random() < P_BIAS_STEP
    bias_step_t = rng.uniform(5, 55)
    bias_step_mag = rng.normal(0, BIAS_STEP_SD)
    drift_on = rng.random() < P_BIAS_DRIFT
    loe_on = rng.random() < P_LOE
    loe_t = rng.uniform(5, 55)
    loe_mag = rng.uniform(*LOE_RANGE)
    out_on = rng.random() < P_OUTAGE
    out_t = rng.uniform(5, 50)
    out_d = rng.exponential(OUTAGE_MEAN_S)
    jam_on = rng.random() < P_JAMNOISE
    jam_t = rng.uniform(5, 50)
    b0 = rng.normal(0, 0.02)
    env, gnss, fault = ("env" in sources), ("gnss" in sources), ("fault" in sources)
    p = {
        "BEN_SEED": int(seed), "BEN_TOFF": T_OFF, "BEN_T_END": T_END,
        "BEN_W_SIG": sig_w if env else 0.0, "BEN_W_L": L_w, "BEN_W_V": CRUISE,
        "BEN_B0": b0 if fault else 0.0,
        "BEN_BRW": SIG_BIAS_RW * (BIAS_DRIFT_MULT if drift_on else 1.0) if fault else 0.0,
        "BEN_BS_T": bias_step_t if (fault and bias_step_on) else 1e6,
        "BEN_BS_M": bias_step_mag if (fault and bias_step_on) else 0.0,
        "BEN_LOE_T": loe_t if (fault and loe_on) else 1e6,
        "BEN_LOE_M": loe_mag if (fault and loe_on) else 0.0,
        "BEN_GSIG": SIG_GNSS_WHITE if gnss else 0.2,
        "BEN_GMSIG": GM_SIGMA if gnss else 0.0, "BEN_GMTAU": GM_TAU,
        "BEN_OUT_T": out_t if (gnss and out_on) else 1e6, "BEN_OUT_D": out_d if (gnss and out_on) else 0.0,
        "BEN_JAM_T": jam_t if (gnss and jam_on) else 1e6, "BEN_JAM_D": JAMNOISE_S if (gnss and jam_on) else 0.0,
        "BEN_JAM_K": JAMNOISE_MULT,
        "BEN_ANC_T": float(anchor) if anchor else 0.0, "BEN_ANC_SIG": SIG_ANCHOR,
        "ATK_EN": 0, "ATK_SEED": 10_000_019 + int(seed),
    }
    meta = {"w20_kt": w20, "bias_step": bool(bias_step_on), "drift": bool(drift_on), "loe": bool(loe_on),
            "outage": bool(out_on), "outage_t": out_t, "outage_d": out_d, "jam": bool(jam_on)}
    return p, meta


def attack(family: str, phys: dict, direction=math.pi / 2):
    """PX4 parameters of an attacker with physical parameters phys (sim.decode output)."""
    g = lambda k, d=0.0: float(phys.get(k, d))
    p = {"ATK_EN": 1, "ATK_FAM": FAM_ID[family], "ATK_T0": g("t0", 1e6), "ATK_DIR": float(direction),
         "ATK_VCON": 1, "ATK_WNRM": SIG_MOD}
    if family == "step":
        p.update(ATK_A=g("amp"))
    elif family == "ramp":
        p.update(ATK_R=g("rate"), ATK_CAP=g("cap"))
    elif family == "fault_mimic":
        p.update(ATK_B0=g("beta0"), ATK_BSIG=g("sig_beta"), ATK_CAP=g("cap"))
    elif family == "gnss_mimic":
        p.update(ATK_A=g("amp"), ATK_TAU=g("tau"), ATK_C=g("slope"))
    elif family == "weather_mimic":
        p.update(ATK_A=g("amp"), ATK_LAG=g("lag_s"), ATK_WB=g("bias"))
    return p


def attack_u(family: str, u):
    """Attacker from a point u in [0,1]^k of the reduced-order parameter box."""
    phys = {k: float(v) for k, v in decode(family, np.asarray(u, float)).items()}
    return attack(family, phys), phys


def params_file(params: dict) -> str:
    lines = ["# Paper IV mission parameters (written by p4_fleet.py)"]
    for k, v in {**PX4_FIXED, **params}.items():
        if isinstance(v, (bool, np.bool_)):
            v = int(v)
        if isinstance(v, (int, np.integer)):
            lines.append(f"param set {k} {int(v)}")
        else:
            lines.append(f"param set {k} {float(v):.7g}")
    return "\n".join(lines) + "\n"


def mission(mid: str, exp: str, seed: int, anchor=5.0, family=None, phys=None, u=None,
            attacker_id=None, twin_of=None, sources=("env", "gnss", "fault"), extra=None):
    p, meta = benign(seed, anchor=anchor, sources=sources)
    spec = {"mid": mid, "exp": exp, "seed": int(seed), "anchor_s": anchor, "family": family or "none",
            "attacker_id": attacker_id, "u": None if u is None else [float(x) for x in u],
            "phys": phys, "twin": twin_of, "benign_meta": meta, "sources": list(sources)}
    if family:
        if phys is None:
            ap, phys = attack_u(family, u)
            spec["phys"] = phys
        else:
            ap = attack(family, phys)
        p.update(ap)
    if extra:
        p.update(extra)
    spec["params"] = p
    return spec


def twin(spec: dict) -> dict:
    """Seed-matched benign twin: identical parameters with the attack switched off."""
    t = mission(f"twin_{spec['exp']}_a{spec['anchor_s']}_s{spec['seed']}", spec["exp"] + "_twin", spec["seed"],
                anchor=spec["anchor_s"], sources=tuple(spec["sources"]))
    t["twin"] = None
    return t


if __name__ == "__main__":
    s = mission("demo", "demo", 4000, family="ramp", phys={"rate": 0.5, "t0": 25.0, "cap": 40.0})
    print(params_file(s["params"]))
    print(ATTACK_BOX.keys())
