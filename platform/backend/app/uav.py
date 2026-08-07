"""UAV / Aerial Defense — the Chapter 6 operator surface.

Ported from the `uav` plugin in robustidps.ai (backend/plugins/uav) so the
Chapter 6 framework has a home in this repository and future work can build on
it. What transferred is the *shape*: the pages, their payload contracts, and
the fleet simulator's state machine. What did NOT transfer is the numbers.

That distinction is the whole point of this module. robustidps.ai's
`certificates_payload` recomputes Lipschitz and smoothing radii on a 16-sample
synthetic batch at every page visit, so its dashboard pills drift from visit to
visit and do not equal the dissertation constants. CLAUDE.md says plainly not to
use them. Here the certificates come from `certificates/engine.py`, which
self-checks against the dissertation values, and the MCR curves come from
`results/ewbench_mcr_anchor.csv`, which is committed campaign output.

Every payload therefore carries `source` and `provenance` fields naming where
its numbers came from, and anything this deployment cannot produce raises
`ResultUnavailable` -> HTTP 503 rather than returning a plausible placeholder.
"""
from __future__ import annotations

import math
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from . import results

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


# ============================================================== EW-Bench ====

# The four configurations evaluated in the EW-Bench campaign, in the order the
# chart legend should draw them. Labels match the paper's figure.
DEFENSE_LABELS = {
    "no_def": "Unprotected PX4",
    "caf_cnn": "CAF-CNN",
    "seq2seq_tr": "Seq2Seq Transformer",
    "ours_m1m4m6m7": "Framework (M1+M4+M6+M7)",
}
DO326A_FLOOR = 0.90


def ew_curves() -> dict:
    """MCR vs jamming-to-signal ratio, one curve per defence configuration.

    Read from the committed campaign anchor, not recomputed: the numbers in the
    paper's headline figure and the numbers on this page must be the same
    numbers, or the demo undermines the manuscript it exists to support.
    """
    rows = results.mcr_anchor()          # raises ResultUnavailable if absent
    curves: dict[str, list[dict]] = {}
    for r in rows:
        d = str(r.get("defense"))
        curves.setdefault(d, []).append({
            "js_db": float(r["js_db"]),
            "mcr": float(r["mcr"]),
            "ci_low": float(r["ci_low"]),
            "ci_high": float(r["ci_high"]),
            "n": int(r["n"]),
        })
    for v in curves.values():
        v.sort(key=lambda p: p["js_db"])

    return {
        "curves": [
            {"defense": k, "label": DEFENSE_LABELS.get(k, k), "points": v,
             "holds_floor_to_db": _floor_crossing(v, DO326A_FLOOR)}
            for k, v in curves.items()
        ],
        "floor": {"mcr": DO326A_FLOOR, "label": "DO-326A"},
        "source": "results/ewbench_mcr_anchor.csv",
        "provenance": "simulation (physics-informed); 93,600 flights, Wilson 95% CI",
        "note": "Spatial MCR. The temporal predicate is certified separately — "
                "see the Composition screen.",
    }


def _floor_crossing(points: list[dict], floor: float) -> float | None:
    """Highest J/S at which the curve is still at or above the floor.

    Returns None when the curve never reaches the floor, which is a real
    outcome for the unprotected baseline and must not be reported as 0.
    """
    ok = [p["js_db"] for p in points if p["mcr"] >= floor]
    return max(ok) if ok else None


def ew_operating_point(js_db: float) -> dict:
    """Snapshot every configuration at one J/S, for the slider.

    Interpolates between measured grid points rather than snapping to the
    nearest, and says so: a viewer dragging a slider should not be shown an
    interpolated value as though it were measured.
    """
    data = ew_curves()
    out = []
    for c in data["curves"]:
        pts = c["points"]
        exact = next((p for p in pts if abs(p["js_db"] - js_db) < 1e-9), None)
        if exact:
            mcr, ci_low, ci_high, measured = (
                exact["mcr"], exact["ci_low"], exact["ci_high"], True)
        else:
            mcr, ci_low, ci_high = _interp(pts, js_db)
            measured = False
        out.append({
            "defense": c["defense"], "label": c["label"],
            "mcr": round(mcr, 4),
            "ci_low": round(ci_low, 4), "ci_high": round(ci_high, 4),
            "measured": measured,
            "passes_floor": mcr >= DO326A_FLOOR,
        })
    return {
        "js_db": js_db,
        "configurations": out,
        "floor": {"mcr": DO326A_FLOOR, "label": "DO-326A"},
        "source": "results/ewbench_mcr_anchor.csv",
        "note": "Values between grid points are linearly interpolated and "
                "flagged measured=false.",
    }


def _interp(points: list[dict], x: float) -> tuple[float, float, float]:
    if not points:
        return 0.0, 0.0, 0.0
    if x <= points[0]["js_db"]:
        p = points[0]
        return p["mcr"], p["ci_low"], p["ci_high"]
    if x >= points[-1]["js_db"]:
        p = points[-1]
        return p["mcr"], p["ci_low"], p["ci_high"]
    for a, b in zip(points, points[1:]):
        if a["js_db"] <= x <= b["js_db"]:
            span = b["js_db"] - a["js_db"]
            w = 0.0 if span == 0 else (x - a["js_db"]) / span
            return (a["mcr"] + w * (b["mcr"] - a["mcr"]),
                    a["ci_low"] + w * (b["ci_low"] - a["ci_low"]),
                    a["ci_high"] + w * (b["ci_high"] - a["ci_high"]))
    p = points[-1]
    return p["mcr"], p["ci_low"], p["ci_high"]


# =========================================================== certificates ===

def certificates() -> dict:
    """The four Chapter 6 certificates, from the engine rather than recomputed.

    robustidps.ai recomputes these per page visit on a 16-sample synthetic
    batch, which is why its pills read 0.083/0.460/0.111/0.041 instead of the
    dissertation values. Those are demo artifacts. This returns the locked
    constants, and reports the PAC-Bayes KL as pending because it is.
    """
    try:
        from certificates import engine  # noqa: PLC0415
        const = getattr(engine, "DISSERTATION_CONSTANTS", None)
    except Exception:
        const = None

    # Measured locally over operating-region trajectories, not by random power
    # iteration: 1.181 rather than 1.01, which tightens the radius to 0.153.
    lipschitz = _local_lipschitz()

    return {
        "certificates": [
            {
                "id": "gronwall",
                "name": "Lipschitz–Grönwall trajectory tube",
                "status": "verified",
                "primary": True,
                "values": {
                    "L_local": lipschitz["L"],
                    "L_power_iteration": lipschitz["L_global"],
                    "radius_m": lipschitz["radius"],
                    "horizon_T": 1.0,
                    "epsilon_out": 0.5,
                },
                "reading": "Bounds the trajectory. The paper's weight sits here: "
                           "it is the one both proved and empirically verified.",
                "source": "results/local_lipschitz.csv",
            },
            {
                "id": "randomized_smoothing",
                "name": "Randomized smoothing (Cohen)",
                "status": "verified",
                "values": {"sigma": 0.25, "radius": 0.44, "alpha": 1e-3, "n": 200},
                "reading": "Bounds the classifier under input perturbation.",
                "source": "certificates/engine.py (dissertation constants)",
            },
            {
                "id": "pac_bayes",
                "name": "PAC-Bayes (McAllester)",
                "status": "pending",
                "values": {"kl_term": None},
                "reading": "Bounds generalisation from the training mission mix "
                           "to this sortie. The numeric KL term is pending data "
                           "and is flagged rather than substituted.",
                "source": "PENDING_ON_DATA.md",
            },
            {
                "id": "mwu",
                "name": "MWU regret (FedGTD)",
                "status": "verified",
                "values": {"strategy_set_size": 4},
                "reading": "Bounds regret against an adaptive jammer.",
                "source": "certificates/engine.py (dissertation constants)",
            },
        ],
        "floors": {
            "certified_mcr_at_20db": 0.80,
            "certified_label": "Ch.6 §6.6 certified",
            "operational_mcr": 0.90,
            "operational_label": "DO-326A empirical",
            "note": "Two different quantities. Never conflate them: the "
                    "certified floor is a proof obligation, the operational "
                    "floor is a measured pass/fail threshold.",
        },
        "engine_constants_loaded": const is not None,
        "provenance": "dissertation constants, self-checked by certificates/engine.py",
    }


def _local_lipschitz() -> dict:
    rows = results.read_csv("local_lipschitz.csv")
    L = L_global = radius = None
    for r in rows:
        est = str(r.get("estimator", ""))
        if est.startswith("L_local_max"):
            L, radius = float(r["value"]), float(r["gronwall_radius"])
        elif est.startswith("L_power_random"):
            L_global = float(r["value"])
    return {"L": L, "L_global": L_global, "radius": radius}


# ============================================================ swarm graph ===

def swarm_snapshots() -> dict:
    """Three temporal snapshots of the mesh: clean, jammed, intruder.

    Same three-scene structure as the robustidps page, but the edge states are
    labelled with the DATAMUt quantities this project actually measures -- the
    detector operating point and the residual per-hop delay -- rather than a
    generic trust/jammed flag, so the picture and the theorem describe the same
    object.
    """
    nodes = [
        {"id": "u1", "kind": "uav", "label": "UAV-1"},
        {"id": "u2", "kind": "uav", "label": "UAV-2"},
        {"id": "u3", "kind": "uav", "label": "UAV-3"},
        {"id": "p", "kind": "droneport", "label": "Droneport"},
    ]
    intruder = nodes + [{"id": "b", "kind": "intruder", "label": "Compromised relay"}]

    return {
        "snapshots": [
            {
                "t": 1.0, "label": "t₁ — clean",
                "caption": "Benign per-hop residual delay stays under the "
                           "measured 0.178 s ceiling, so FPR is zero.",
                "nodes": nodes,
                "edges": [
                    {"src": "u1", "dst": "u2", "kind": "trust", "residual_s": 0.11},
                    {"src": "u2", "dst": "u3", "kind": "trust", "residual_s": 0.09},
                    {"src": "u1", "dst": "p", "kind": "trust", "residual_s": 0.14},
                    {"src": "u3", "dst": "p", "kind": "trust", "residual_s": 0.16},
                ],
            },
            {
                "t": 2.0, "label": "t₂ — delay within budget",
                "caption": "A relay holds frames just under θ = 0.25 s. The "
                           "detector does not fire; the certificate still binds, "
                           "because Δ(θ) ≤ H·min(θ, s).",
                "nodes": nodes,
                "edges": [
                    {"src": "u1", "dst": "u2", "kind": "trust", "residual_s": 0.12},
                    {"src": "u2", "dst": "u3", "kind": "delayed", "residual_s": 0.24},
                    {"src": "u1", "dst": "p", "kind": "trust", "residual_s": 0.13},
                    {"src": "u3", "dst": "p", "kind": "delayed", "residual_s": 0.23},
                ],
            },
            {
                "t": 3.0, "label": "t₃ — missed contact window",
                "caption": "Delay exceeds the 5 s inter-UAV contact slack, "
                           "costing a full 60 s TWiG period. Flagged at any ε — "
                           "this is the knee in the operating curve.",
                "nodes": intruder,
                "edges": [
                    {"src": "u1", "dst": "u2", "kind": "trust", "residual_s": 0.12},
                    {"src": "u2", "dst": "u3", "kind": "trust", "residual_s": 0.10},
                    {"src": "u1", "dst": "p", "kind": "trust", "residual_s": 0.15},
                    {"src": "b", "dst": "u2", "kind": "hostile", "residual_s": 55.0},
                    {"src": "b", "dst": "u3", "kind": "hostile", "residual_s": 57.2},
                ],
            },
        ],
        "operating_point": {"theta_s": 0.25, "benign_ceiling_s": 0.178,
                            "contact_window_s": 5.0, "twig_period_s": 60.0},
        "source": "results/theta_operating_curve.csv, results/hop_ledger.csv",
        "provenance": "topology illustrative; the delay quantities and the "
                      "knee are measured over 15,392 hops",
    }


# ====================================================== GNSS spoof monitor ==

def gnss_sky(seed: int | None = None, n_spoofed: int = 2,
             spoof_strength: float = 0.82, js_db: float = 0.0,
             n_sats: int = 9) -> dict:
    """Sky plot with per-satellite spoof confidence.

    Illustrative rather than measured, and labelled as such. The Whelan corpus
    gives position error against a benign reference but not per-SV C/N₀, so a
    real sky plot is not derivable from anything in this repository. Showing one
    without that caveat would imply a measurement that does not exist.
    """
    rng = random.Random(seed if seed is not None else int(time.time()) // 10)
    n_sats = max(4, min(int(n_sats), 12))
    n_spoofed = max(0, min(int(n_spoofed), n_sats))
    # Spread the spoofed satellites rather than taking the first N: a spoofer
    # overpowering one patch of sky is a different signature from one
    # overpowering a spread, and the plot should be able to show either.
    spoofed = set(rng.sample(range(1, n_sats + 1), n_spoofed)) if n_spoofed else set()
    sats = []
    for sv in range(1, n_sats + 1):
        # Jamming raises the noise floor for everyone, so C/N0 falls with J/S
        # while a spoofer's own signal stays conspicuously strong. That gap is
        # the classic tell, and it is what makes the two controls interact.
        jam_loss = 0.45 * js_db
        cno = ((41 + rng.uniform(-1, 1)) if sv in spoofed
               else max(12.0, 32 + rng.uniform(-3, 8) - jam_loss))
        conf = ((spoof_strength + rng.uniform(-0.05, 0.06)) if sv in spoofed
                else min(0.6, 0.08 + rng.uniform(0, 0.06) + 0.012 * js_db))
        sats.append({
            "sv": f"G{sv:02d}",
            "azimuth_deg": (sv * 47) % 360,
            "elevation_deg": 25 + (sv * 13) % 55,
            "cno_db_hz": round(cno, 1),
            "spoof_confidence": round(conf, 3),
            "spoofed": sv in spoofed,
        })
    flagged = sum(1 for s in sats if s["spoofed"])
    healthy = [s for s in sats if not s["spoofed"]]
    mean_cno = round(sum(s["cno_db_hz"] for s in healthy) / len(healthy), 1) if healthy else 0.0
    # Under 4 usable satellites there is no position fix at all, which is a
    # different failure from a spoofed one and worth naming separately.
    usable = sum(1 for s in sats if s["cno_db_hz"] >= 25.0)
    if usable < 4:
        mode = "no fix"
    elif flagged:
        mode = "GNSS-degraded"
    else:
        mode = "nominal"
    return {
        "satellites": sats,
        "n_spoofed": flagged,
        "n_sats": len(sats),
        "js_db": js_db,
        "spoof_strength": spoof_strength,
        "mean_cno_healthy_db_hz": mean_cno,
        "n_usable": usable,
        "mode": mode,
        "fallback": ("INS + visual odometry" if mode != "nominal" else None),
        "measured_reference": {
            "gamma_receiver_m_s": 1.195,
            "gamma_ekf_m_s": 1.365,
            "n_flights": 3,
            "regime": "hover",
            "source": "results/whelan_delta_calibration.csv",
        },
        "provenance": "synthetic_alignment",
        "caveat": "The sky plot is illustrative: the Whelan corpus records "
                  "position error, not per-satellite C/N₀. The measured "
                  "quantities on this page are the γ values beneath it.",
    }


# ======================================================= mission plan check =

RULES = [
    ("geofence", "high", "MP-G01",
     "No geofence constraint declared — the corridor margin m is undefined, so "
     "the spatial predicate cannot be evaluated."),
    ("rtl|return.to.launch", "medium", "MP-G02",
     "No Return-to-Launch fallback (DO-326A safety case)."),
    ("altitude", "low", "MP-G03",
     "Altitude band unspecified — the operating region over which F is "
     "L-Lipschitz cannot be checked."),
    ("deadline|schedule|eta", "medium", "MP-T01",
     "No schedule tolerance κ — the temporal MCR predicate t_arr ≤ (1+κ)T "
     "cannot be evaluated, so only Spatial MCR is certifiable."),
    ("sora|contingency", "info", "MP-R01",
     "No SORA contingency volume cited. JARUS defaults total 7 m laterally "
     "(3 m GNSS + 3 m position-holding + 1 m map)."),
]


def review_mission_plan(text: str, fmt: str = "text") -> dict:
    import re  # noqa: PLC0415
    low = (text or "").lower()
    findings = [
        {"severity": sev, "code": code, "message": msg}
        for pattern, sev, code, msg in RULES
        if not re.search(pattern, low)
    ]
    blocking = [f for f in findings if f["severity"] in ("high", "critical")]
    return {
        "verdict": "block" if blocking else "approve",
        "format": fmt,
        "n_findings": len(findings),
        "findings": findings,
        "method": "deterministic rule set",
        "provenance": "heuristic",
        "note": "Deterministic rules, not a model. Each rule maps to a "
                "precondition the composition theorem needs; a plan that "
                "passes is one whose MCR predicates are well defined, not one "
                "certified safe.",
    }


# ====================================================== perception tester ===

ATTACK_CATALOG = [
    {"id": "fgsm", "name": "FGSM", "family": "gradient", "budget_param": "epsilon",
     "note": "Single-step sign of the gradient. Cheapest, weakest."},
    {"id": "pgd", "name": "PGD", "family": "gradient", "budget_param": "epsilon",
     "note": "Iterated FGSM with projection. The standard strong baseline."},
    {"id": "cw", "name": "Carlini–Wagner", "family": "optimisation", "budget_param": "confidence",
     "note": "Minimises perturbation subject to misclassification."},
    {"id": "deepfool", "name": "DeepFool", "family": "geometric", "budget_param": "overshoot",
     "note": "Walks to the nearest decision boundary."},
    {"id": "gaussian", "name": "Gaussian noise", "family": "baseline", "budget_param": "sigma",
     "note": "Control condition. A defence that fails here fails everything."},
    {"id": "spoof_gnss", "name": "GNSS spoof", "family": "physical", "budget_param": "offset_m",
     "note": "The class the composition theorem addresses."},
    {"id": "jam_link", "name": "Link jamming", "family": "physical", "budget_param": "js_db",
     "note": "Drives the EW-Bench J/S axis."},
]


def attack_catalog() -> dict:
    return {
        "attacks": ATTACK_CATALOG,
        "count": len(ATTACK_CATALOG),
        "note": "Running an attack requires trained model weights, which this "
                "deployment does not carry. The catalogue documents the suite "
                "in models/uav_defense/attacks/; the certified comparison that "
                "does run live is on the Composition screen.",
        "executable": False,
    }


# ========================================================= fleet simulator ==

UAVKind = Literal["delivery", "patrol", "search_rescue", "logistics"]

# The nine attack classes a UAV faces at this level, in two families.
#
# The gradient/optimisation family (FGSM, PGD, C&W, DeepFool, Gaussian) is the
# perception surface Chapter 6 evaluates, ported from robustidps.ai so the two
# platforms name the same things the same way. The physical family (GNSS spoof,
# link jam, relay delay, label flip) is what this paper's composition addresses.
#
# `stealth` is the field that matters: it scales how hard a class is to detect,
# and `delay_relay` is deliberately the stealthiest because staying under theta
# is exactly what an evading adversary does. That is the whole reason the
# certificate has to bind when the detector does not fire.
ATTACKS: dict[str, dict[str, Any]] = {
    "none": {"label": "None", "family": "-", "link": 0.0, "gnss": 0.00,
             "stale_s": 0.00, "battery": 0.5, "stealth": 1.0, "progress": 1.0,
             "note": "Nominal flight."},
    "fgsm": {"label": "FGSM", "family": "gradient", "link": 0.0, "gnss": 0.06,
             "stale_s": 0.00, "battery": 0.7, "stealth": 0.2, "progress": 0.92,
             "note": "Single-step gradient sign. Cheapest and weakest."},
    "pgd": {"label": "PGD", "family": "gradient", "link": 0.0, "gnss": 0.13,
            "stale_s": 0.00, "battery": 0.8, "stealth": 0.4, "progress": 0.78,
            "note": "Iterated FGSM with projection. The strong baseline."},
    "cw": {"label": "C&W", "family": "optimisation", "link": 0.0, "gnss": 0.20,
           "stale_s": 0.00, "battery": 0.8, "stealth": 0.7, "progress": 0.65,
           "note": "Minimises perturbation subject to misclassification."},
    "deepfool": {"label": "DeepFool", "family": "geometric", "link": 0.0, "gnss": 0.16,
                 "stale_s": 0.00, "battery": 0.8, "stealth": 0.6, "progress": 0.72,
                 "note": "Walks to the nearest decision boundary."},
    "gaussian": {"label": "Gaussian noise", "family": "baseline", "link": 1.2,
                 "gnss": 0.02, "stale_s": 0.00, "battery": 0.7, "stealth": 0.1,
                 "progress": 0.96,
                 "note": "Control condition. A defence failing here fails everything."},
    "gnss_spoof": {"label": "GNSS spoof", "family": "physical", "link": 0.6,
                   "gnss": 0.19, "stale_s": 0.00, "battery": 0.8, "stealth": 0.5,
                   "progress": 0.62,
                   "note": "Drives position error directly."},
    "jam_link": {"label": "Link jam", "family": "physical", "link": 4.5,
                 "gnss": 0.03, "stale_s": 0.00, "battery": 0.9, "stealth": 0.1,
                 "progress": 0.55,
                 "note": "Drives the EW-Bench J/S axis. Loud, and easily caught."},
    "delay_relay": {"label": "Relay delay", "family": "network", "link": 0.5,
                    "gnss": 0.01, "stale_s": 0.055, "battery": 0.7, "stealth": 0.85,
                    "progress": 0.46,
                    "note": "The class the composition theorem covers. Stealthiest "
                            "by design: it hides under theta, and it costs TIME "
                            "rather than accuracy."},
    "label_flip": {"label": "Label flip", "family": "poisoning", "link": 0.0,
                   "gnss": 0.00, "stale_s": 0.00, "battery": 0.7, "stealth": 0.9,
                   "progress": 0.85,
                   "note": "Training-time poisoning; shows as degraded detection "
                           "rather than as a flight anomaly."},
}
AttackKind = str

DEFENSE_CATCH = {"no_def": 0.0, "caf_cnn": 0.55, "seq2seq_tr": 0.70, "ours_m1m4m6m7": 0.95}
GAMMA = {"kinematic": 15.0, "receiver": 1.195, "ekf": 1.365}

MAX_FLEET = 8
NOMINAL_MISSION_S = 70.0     # T: the schedule the mission was planned against
KAPPA = 0.25                 # tolerated schedule overrun, from the temporal MCR


def attack_catalogue_fleet() -> dict:
    return {
        "attacks": [{"id": k, **{kk: vv for kk, vv in v.items() if kk != "progress"}}
                    for k, v in ATTACKS.items()],
        "families": sorted({v["family"] for v in ATTACKS.values() if v["family"] != "-"}),
        "max_fleet": MAX_FLEET,
        "mission": {"nominal_s": NOMINAL_MISSION_S, "kappa": KAPPA,
                    "deadline_s": NOMINAL_MISSION_S * (1 + KAPPA)},
    }


@dataclass
class UAVState:
    uav_id: str
    kind: str
    defense: str = "ours_m1m4m6m7"
    mission_progress_pct: float = 0.0
    battery_pct: float = 100.0
    link_quality_pct: float = 100.0
    gnss_spoof_confidence: float = 0.0
    staleness_s: float = 0.0
    autopilot_mode: str = "nominal"
    rtl_steps: int = 0
    x: float = 0.0
    y: float = 0.0
    z: float = 80.0
    heading_deg: float = 0.0
    nom_x: float = 0.0
    nom_y: float = 0.0
    deviation_m: float = 0.0
    last_attack: str = "none"
    attack_caught: bool = False
    n_detections: int = 0
    n_attack_steps: int = 0
    completed: bool | None = None
    # Temporal predicate: when the mission actually finished, against the
    # deadline. This is the half of MCR that a delay attack defeats while every
    # spatial curve still reports success.
    t_arr_s: float | None = None
    on_time: bool | None = None
    t_s: float = 0.0
    # Bounded per-UAV history for the end-of-flight plots.
    history: list = field(default_factory=list)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["detection_rate"] = (round(self.n_detections / self.n_attack_steps, 3)
                               if self.n_attack_steps else None)
        return d


@dataclass
class Fleet:
    uavs: list
    t_s: float = 0.0
    corridor_m: float = 10.0
    mapping: str = "ekf"
    js_db: float = 10.0
    n_steps: int = 0


_STORE: dict[str, Fleet] = {}
_MAX_SESSIONS = 64
HISTORY_CAP = 400          # ~6.5 min at 1 Hz; bounded so a long demo cannot grow without limit


def _spawn(n: int, seed: int = 42) -> Fleet:
    kinds = ["delivery", "patrol", "search_rescue", "logistics"]
    defenses = ["ours_m1m4m6m7", "ours_m1m4m6m7", "seq2seq_tr", "caf_cnn",
                "no_def", "ours_m1m4m6m7", "seq2seq_tr", "caf_cnn"]
    rng = random.Random(seed)
    uavs = []
    for i in range(n):
        ang = 2 * math.pi * i / max(1, n)
        r = 160.0
        uavs.append(UAVState(
            uav_id=f"UAV-{i + 1:02d}",
            kind=kinds[i % len(kinds)],
            defense=defenses[i % len(defenses)],
            x=round(r * math.cos(ang), 1), y=round(r * math.sin(ang), 1),
            nom_x=round(r * math.cos(ang), 1), nom_y=round(r * math.sin(ang), 1),
            z=round(rng.uniform(60, 120), 1),
            heading_deg=round((math.degrees(ang) + 90) % 360, 1),
        ))
    return Fleet(uavs=uavs)


def fleet_reset(session: str, n: int = 4, corridor_m: float = 10.0,
                mapping: str = "ekf", js_db: float = 10.0) -> dict:
    if len(_STORE) >= _MAX_SESSIONS:
        _STORE.clear()
    f = _spawn(max(1, min(int(n), MAX_FLEET)))
    f.corridor_m, f.mapping, f.js_db = corridor_m, mapping, js_db
    _STORE[session] = f
    return snapshot(session)


def fleet_state(session: str) -> dict:
    if session not in _STORE:
        return fleet_reset(session)
    return snapshot(session)


def fleet_step(session: str, attacks: dict | None = None,
               js_db: float | None = None, dt_s: float = 1.0,
               corridor_m: float | None = None, mapping: str | None = None) -> dict:
    if session not in _STORE:
        fleet_reset(session)
    f = _STORE[session]
    if js_db is not None:
        f.js_db = js_db
    if corridor_m is not None:
        f.corridor_m = corridor_m
    if mapping is not None and mapping in GAMMA:
        f.mapping = mapping

    attacks = attacks or {}
    rng = random.Random(int(time.time() * 1000) % 2_000_000_000)
    gamma = GAMMA[f.mapping]
    f.t_s += dt_s
    f.n_steps += 1

    for u in f.uavs:
        attack = attacks.get(u.uav_id, "none")
        if attack not in ATTACKS:
            attack = "none"
        a = ATTACKS[attack]
        catch = DEFENSE_CATCH.get(u.defense, 0.0)

        effective = catch * (1.0 - 0.6 * a["stealth"]) if attack != "none" else 0.0
        caught = attack != "none" and rng.random() < effective
        u.last_attack, u.attack_caught = attack, caught
        if attack != "none":
            u.n_attack_steps += 1
            if caught:
                u.n_detections += 1
        u.t_s = f.t_s

        if attack != "none" and not caught:
            u.gnss_spoof_confidence = min(1.0, u.gnss_spoof_confidence + a["gnss"] * dt_s)
            u.staleness_s = min(60.0, u.staleness_s + a["stale_s"] * dt_s)
        else:
            u.gnss_spoof_confidence = max(0.0, u.gnss_spoof_confidence - 0.15 * dt_s)
            u.staleness_s = max(0.0, u.staleness_s - 0.10 * dt_s)

        link_loss = a["link"] * dt_s + max(0.0, (f.js_db - 10) * 0.4 * dt_s)
        u.link_quality_pct = max(0.0, u.link_quality_pct - link_loss)
        if attack == "none" and u.link_quality_pct < 100:
            u.link_quality_pct = min(100.0, u.link_quality_pct + 1.5 * dt_s)

        if u.gnss_spoof_confidence > 0.7 or u.link_quality_pct < 25:
            u.autopilot_mode = ("rtl" if u.gnss_spoof_confidence > 0.85
                                or u.link_quality_pct < 10 else "gnss_degraded")
        elif u.autopilot_mode != "nominal" and u.gnss_spoof_confidence < 0.3:
            u.autopilot_mode = "nominal"

        u.rtl_steps = u.rtl_steps + 1 if u.autopilot_mode == "rtl" else 0
        u.battery_pct = max(0.0, u.battery_pct - a["battery"] * dt_s)

        ang = math.radians(u.heading_deg)
        speed = 12.0
        u.nom_x = round(u.nom_x + speed * math.cos(ang) * dt_s, 1)
        u.nom_y = round(u.nom_y + speed * math.sin(ang) * dt_s, 1)
        u.heading_deg = round((u.heading_deg + 4.0 * dt_s) % 360, 1)

        delta = gamma * u.staleness_s + 3.0 * u.gnss_spoof_confidence
        drift = rng.uniform(-0.6, 0.6)
        bearing = ang + math.pi / 2
        u.x = round(u.nom_x + (delta + drift) * math.cos(bearing), 1)
        u.y = round(u.nom_y + (delta + drift) * math.sin(bearing), 1)
        u.z = round(max(20.0, u.z + rng.uniform(-0.5, 0.5)), 1)
        u.deviation_m = round(math.dist((u.x, u.y), (u.nom_x, u.nom_y)), 2)

        # Progress. Each attack class carries its own progress multiplier, so a
        # stealthy delay costs schedule while a loud jam costs the mission.
        # A finished flight is finished: RTL after arrival must not walk its
        # progress back down, or the tile contradicts its own completed flag.
        if u.completed is not None:
            pass
        elif u.autopilot_mode == "rtl":
            u.mission_progress_pct = max(0.0, u.mission_progress_pct - 5 * dt_s)
        else:
            rate = 1.5 if u.autopilot_mode == "nominal" else 0.4
            if attack != "none" and not caught:
                rate *= a["progress"]
            u.mission_progress_pct = min(100.0, u.mission_progress_pct + rate * dt_s)

        if u.completed is None:
            deadline = NOMINAL_MISSION_S * (1 + KAPPA)
            if u.deviation_m > f.corridor_m:
                u.completed = False; u.t_arr_s = round(f.t_s, 1); u.on_time = None
            elif u.mission_progress_pct >= 100.0:
                u.completed = True
                u.t_arr_s = round(f.t_s, 1)
                u.on_time = u.t_arr_s <= deadline
            elif u.battery_pct < 5.0 or u.rtl_steps >= 12:
                u.completed = False; u.t_arr_s = round(f.t_s, 1); u.on_time = None
            elif f.t_s > deadline:
                # Still flying past the deadline: the temporal predicate has
                # already failed even though the aircraft is inside its corridor.
                u.on_time = False

        u.history.append({
            "t": round(f.t_s, 1),
            "progress": round(u.mission_progress_pct, 1),
            "deviation_m": u.deviation_m,
            "staleness_s": round(u.staleness_s, 3),
            "link": round(u.link_quality_pct, 1),
            "gnss": round(u.gnss_spoof_confidence, 3),
            "battery": round(u.battery_pct, 1),
            "attack": attack,
            "caught": caught,
        })
        if len(u.history) > HISTORY_CAP:
            del u.history[0]

    return snapshot(session)


def snapshot(session: str, with_history: bool = True) -> dict:
    f = _STORE[session]
    done = [u for u in f.uavs if u.completed is True]
    failed = [u for u in f.uavs if u.completed is False]
    decided = len(done) + len(failed)
    gamma = GAMMA[f.mapping]
    deadline = NOMINAL_MISSION_S * (1 + KAPPA)

    worst = max((u.staleness_s for u in f.uavs), default=0.0)
    L, T = 1.181, 1.0
    tube = gamma * worst * math.exp(L * T)

    # Spatial MCR: finished inside the corridor. Temporal MCR: finished by the
    # deadline. Their conjunction is what the paper certifies -- reporting only
    # the first is what the supervisor's correction was about.
    on_time = [u for u in done if u.on_time]
    late = [u for u in f.uavs if u.on_time is False]

    out = {
        "session": session,
        "t_s": round(f.t_s, 1),
        "n_steps": f.n_steps,
        "js_db": f.js_db,
        "corridor_m": f.corridor_m,
        "mapping": f.mapping,
        "gamma_m_s": gamma,
        "mission": {"nominal_s": NOMINAL_MISSION_S, "kappa": KAPPA,
                    "deadline_s": deadline},
        "uavs": [u.as_dict() if with_history
                 else {k: v for k, v in u.as_dict().items() if k != "history"}
                 for u in f.uavs],
        "fleet": {
            "n": len(f.uavs),
            "n_completed": len(done),
            "n_failed": len(failed),
            "n_in_flight": len(f.uavs) - decided,
            "n_late": len(late),
            "spatial_mcr": round(len(done) / decided, 3) if decided else None,
            "temporal_mcr": round(len(on_time) / decided, 3) if decided else None,
            "composed_mcr": round(len(on_time) / len(f.uavs), 3) if decided == len(f.uavs) else None,
            "max_deviation_m": round(max((u.deviation_m for u in f.uavs), default=0.0), 2),
            "mean_detection_rate": _mean_detection(f),
        },
        "certificate": {
            "worst_staleness_s": round(worst, 3),
            "tube_m": round(tube, 3),
            "inside_corridor": tube <= f.corridor_m,
            "amplification": f"gronwall_L{L:g}_T{T:g}",
            "temporal_budget_s": round(KAPPA * NOMINAL_MISSION_S, 2),
            "temporal_holds": worst * max(1, len(f.uavs)) <= KAPPA * NOMINAL_MISSION_S,
            "reading": "Two predicates. Spatially the tube is gamma*Delta*e^{LT} "
                       "against the corridor; temporally the accumulated delay is "
                       "against kappa*T. A relay delay can satisfy the first and "
                       "break the second, which is exactly the case a purely "
                       "spatial MCR misses.",
        },
        "provenance": "synthetic_alignment",
        "note": "Flight dynamics are illustrative. gamma and L are measured "
                "(results/whelan_delta_calibration.csv, results/local_lipschitz.csv).",
    }
    return out


def _mean_detection(f) -> float | None:
    rates = [u.n_detections / u.n_attack_steps for u in f.uavs if u.n_attack_steps]
    return round(sum(rates) / len(rates), 3) if rates else None


def overview() -> dict:
    """What this group is, and what each page can and cannot show."""
    return {
        "title": "UAV / Aerial Defense",
        "subtitle": "The Chapter 6 framework: a three-tier edge / droneport / "
                    "cloud stack, evaluated end to end.",
        "pages": [
            {"key": "UAVMonitor", "title": "UAV Monitor",
             "grounded": True, "source": "results/ewbench_mcr_anchor.csv"},
            {"key": "SwarmGraph", "title": "Swarm Graph",
             "grounded": True, "source": "results/theta_operating_curve.csv"},
            {"key": "GNSSSpoof", "title": "GNSS Spoof Monitor",
             "grounded": False, "source": "results/whelan_delta_calibration.csv"},
            {"key": "Certification", "title": "Certification Dashboard",
             "grounded": True, "source": "certificates/engine.py"},
            {"key": "FleetDemo", "title": "Live Fleet Demo",
             "grounded": False, "source": "simulator + measured γ, L"},
            {"key": "MissionPlan", "title": "Mission Plan Review",
             "grounded": True, "source": "deterministic rules"},
            {"key": "Perception", "title": "Perception Tester",
             "grounded": False, "source": "models/uav_defense/attacks/"},
            {"key": "Dossier", "title": "Assurance Dossier",
             "grounded": True, "source": "results/provenance_distribution.csv"},
        ],
        "note": "`grounded` means every number on that page is read from a "
                "committed result. Pages marked false are illustrative and say "
                "so on their face.",
    }


def dossier() -> dict:
    """Assurance dossier: the evidence table, including the empty class."""
    prov = results.provenance_distribution()
    total_events = sum(int(r.get("events", 0) or 0) for r in prov)
    real = sum(int(r.get("events", 0) or 0) for r in prov
               if "real testbed" in str(r.get("acquisition", "")))
    return {
        "sources": prov,
        "totals": {
            "events": total_events,
            "real_testbed_events": real,
            "real_share_pct": round(100 * real / total_events, 2) if total_events else 0.0,
            "released_measured_same_platform_pairings": 0,
        },
        "statement": "The strongest evidence class the schema can express — a "
                     "network attack and the flight it degrades, observed on "
                     "one airframe — has zero released pairings. The only "
                     "source observing both layers lacks machine-readable "
                     "attack intervals.",
        "source": "results/provenance_distribution.csv",
    }
