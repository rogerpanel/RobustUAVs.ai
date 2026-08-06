"""Evaluation surface: robustness, ablations, ROC, statistics, calibration.

The analysis pages robustidps.ai carries under "AI Data & Models" and
"AI Novel Methods", re-targeted at the quantities this project measures.

One page here deliberately returns nothing. Expected Calibration Error needs
per-hop detector *scores*, and the DATAMUt replay emits a boolean flag rather
than a score, so no reliability diagram is derivable from anything committed.
Rather than drop the page or fill it with a surrogate, `calibration()` returns
the method, the exact missing input, and `available: false`. A reviewer asking
"is your detector calibrated?" gets a straight answer about why the question
cannot be answered yet, which is worth more than a plausible curve.
"""
from __future__ import annotations

import math
from collections import defaultdict

from . import results

MAPPINGS = ("kinematic_v15", "empirical_receiver", "empirical_ekf")
MAPPING_LABEL = {
    "kinematic_v15": "Kinematic (v_max = 15 m/s)",
    "empirical_receiver": "Receiver (γ = 1.195 m/s)",
    "empirical_ekf": "EKF (γ = 1.365 m/s)",
}


# ============================================================= robustness ===

def robustness() -> dict:
    """Certified floor against the detector operating point, per mapping.

    This is the paper's Figure 3 as data: it is the curve that shows the
    guarantee degrading as the detector is loosened, and where it stops holding
    at all.
    """
    rows = results.certified_floor()
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[str(r["mapping"])].append({
            "theta_s": float(r["theta_s"]),
            "delta_pos_m": float(r["delta_pos_m"]),
            "tube_m": float(r["tube_m"]),
            "certified_floor": float(r["certified_floor"]),
        })
    for v in by.values():
        v.sort(key=lambda p: p["theta_s"])

    series = [{
        "mapping": k, "label": MAPPING_LABEL.get(k, k), "points": v,
        # Largest theta at which the floor is still 1.0 -- i.e. the certificate
        # still binds everywhere. None means it never does.
        "binds_to_theta_s": max([p["theta_s"] for p in v if p["certified_floor"] >= 1.0],
                                default=None),
    } for k, v in by.items()]

    return {
        "series": series,
        "paper_theta_s": 0.25,
        "benign_ceiling_s": 0.178,
        "source": "results/certified_floor_vs_theta.csv",
        "reading": "The floor is a step, not a slope: below θ* the tube fits "
                   "inside the corridor and the floor is 1.0; above it the "
                   "certificate stops binding. Which side θ = 0.25 s falls on "
                   "is decided by the mapping, not by the theorem.",
    }


# ============================================================== ablations ===

def ablations() -> dict:
    """How much of the guarantee each component is responsible for.

    Two ablations are derivable from committed results and both are here. A
    third -- per-certificate removal -- is not: the four certificates bound
    different objects and are not summable, so "remove one and re-measure" has
    no coherent meaning. Saying that is more useful than inventing a bar for it.
    """
    sens = results.read_csv("delta_mapping_sensitivity.csv")
    grid = []
    for r in sens:
        grid.append({
            "theta_target_s": float(r["theta_target_s"]),
            "margin_m": float(r["margin_m"]),
            "gamma_required_m_s": float(r["gamma_required_m_s"]),
            "ok": {m: bool(int(r[f"ok__{m}"])) for m in MAPPINGS},
        })

    # Amplification ablation: how much of the tube is Grönwall rather than the
    # raw perturbation. e^{LT} at the measured local L, against the global one.
    L_local, L_global, T = 1.1814, 0.9834, 1.0
    amp_local, amp_global = math.exp(L_local * T), math.exp(L_global * T)

    return {
        "mapping_sensitivity": {
            "grid": grid,
            "question": "How tight must γ be for θ = 0.25 s to certify at each "
                        "corridor margin?",
            "source": "results/delta_mapping_sensitivity.csv",
        },
        "amplification": {
            "L_local": L_local, "L_global": L_global, "horizon_T": T,
            "factor_local": round(amp_local, 4),
            "factor_global": round(amp_global, 4),
            "penalty_pct": round(100 * (amp_local / amp_global - 1), 2),
            "reading": "Measuring L over real operating-region trajectories "
                       "rather than by random power iteration costs "
                       f"{round(100 * (amp_local / amp_global - 1), 1)}% of tube "
                       "radius. We pay it: the larger constant is the honest one.",
            "source": "results/local_lipschitz.csv",
        },
        "not_ablatable": {
            "item": "per-certificate removal",
            "reason": "The four certificates bound four different objects — a "
                      "trajectory, a classifier, a generalisation gap, and a "
                      "regret. They do not compose additively, so removing one "
                      "and re-measuring a single scalar has no meaning. The "
                      "ablation that does make sense is the interface mapping, "
                      "which is above.",
        },
    }


# ==================================================================== ROC ===

def roc() -> dict:
    """The detector's operating curve, and the ROC generalisation.

    The harness is built around a threshold detector, but the composition does
    not depend on that: for a scoring detector with score function g and cutoff
    P_th, an evading attacker must satisfy g(mu) < P_th, so the residual lemma
    applies with theta replaced by theta_eff = g^-1(P_th).
    """
    rows = results.operating_curve()
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        key = f"scenario {r['scenario']} · {r['mode']}"
        by[key].append({
            "epsilon": float(r["epsilon"]),
            "recall": float(r["recall"]),
            "fpr": float(r["fpr"]),
            "precision": float(r.get("precision") or 0.0),
            "n_runs": int(r.get("n_runs") or 0),
        })
    for v in by.values():
        v.sort(key=lambda p: p["epsilon"])

    all_fpr = {p["fpr"] for v in by.values() for p in v}

    return {
        "curves": [{"label": k, "points": v} for k, v in sorted(by.items())],
        "fpr_is_identically_zero": all_fpr == {0.0},
        "benign_ceiling_s": 0.178,
        "knee": {
            "contact_window_s": 5.0,
            "twig_period_s": 60.0,
            "explanation": "Recall holds to ε = 3 s then collapses, because "
                           "past the 5 s contact window a delayed hop misses "
                           "its slot and costs a full 60 s period — which is "
                           "flagged at any ε. The survivors at high ε are all "
                           "missed-window residuals, not path deviations.",
        },
        "generalisation": {
            "formula": "μ < g⁻¹(P_th) =: θ_eff(P_th)",
            "reading": "Any detector emitting a per-hop score plugs in here: "
                       "the residual-budget lemma applies verbatim with θ "
                       "replaced by the effective operating point. The "
                       "threshold detector is the special case g = id.",
            "requirements": ["monotone g", "measurable inverse on the operating range"],
        },
        "source": "results/theta_operating_curve.csv",
    }


# ============================================================= statistics ===

def statistics() -> dict:
    """Wilcoxon signed-rank with Holm correction, as run for the paper."""
    rows = results.wilcoxon()
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[str(r["comparison"])].append({
            "epsilon": float(r["epsilon"]),
            "n_pairs": int(r["n_pairs"]),
            "median_diff": float(r["median_diff"]),
            "p_raw": float(r["p_raw"]),
            "p_holm": float(r["p_holm"]),
            "significant": bool(int(r["significant_0.05"])),
        })

    families = []
    for k, v in sorted(by.items()):
        v.sort(key=lambda p: p["epsilon"])
        n_sig = sum(1 for p in v if p["significant"])
        families.append({
            "comparison": k,
            "n_points": len(v),
            "n_significant": n_sig,
            "verdict": f"{n_sig}/{len(v)} significant at α = 0.05 after Holm",
            "min_p_holm": min((p["p_holm"] for p in v), default=None),
            "points": v,
        })

    return {
        "families": families,
        "method": "Wilcoxon signed-rank, paired by seed; Holm correction "
                  "within each family",
        "reading": "The dominance of the composed guarantee over autonomy-only "
                   "is 13/13 under every mapping, so it does not depend on the "
                   "interface calibration that decides the certified window.",
        "source": "results/stats_wilcoxon.csv",
    }


# ============================================================ calibration ===

def calibration() -> dict:
    """Expected Calibration Error — not computable from what is committed.

    Returned as a described gap rather than omitted. The page exists so the
    question has a visible answer; `available: false` is the answer.
    """
    return {
        "available": False,
        "metric": "Expected Calibration Error (ECE)",
        "method": "Bin predicted probabilities into M equal-width bins; ECE = "
                  "Σ (|B_m|/n) · |acc(B_m) − conf(B_m)|. Reliability diagram "
                  "plots acc against conf per bin.",
        "missing_input": "per-hop detector scores in [0, 1]",
        "why": "The DATAMUt replay's PaperExactDetector emits a boolean flag — "
               "residual delay > ε, or next-hop mismatch — not a score. A "
               "boolean has two confidence levels, so every reliability "
               "diagram derivable from it is degenerate.",
        "what_would_unblock_it": "Either a scoring detector (SPRITZ's ML "
                                 "classifier would qualify) or a soft "
                                 "surrogate over the residual-delay "
                                 "distribution, which we have not built "
                                 "because it would be calibrated against "
                                 "itself.",
        "related": "The ROC page shows what IS derivable from a threshold "
                   "detector: recall and FPR across the ε grid, plus the "
                   "θ_eff mapping that generalises the composition to any "
                   "scoring detector.",
        "tracked_in": "PENDING_ON_DATA.md",
    }


# ================================================= federated learning (M7) ==

def federated() -> dict:
    """M7 = FedGTD, the Stackelberg/MWU defender, as the registry knows it."""
    from . import registry  # noqa: PLC0415

    cards = [c for c in registry.REGISTRY
             if "fed" in str(getattr(c, "model_id", "")).lower()
             or "M7" in str(getattr(c, "model_id", ""))
             or "fedgtd" in str(getattr(c, "name", "")).lower()]

    return {
        "model": "M7 — FedGTD (federated Stackelberg game-theoretic defender)",
        "role": "The defender in the MWU regret certificate: it plays a "
                "distribution over |S| = 4 strategies against an adaptive "
                "jammer, and the certificate bounds its regret.",
        "registry_entries": [
            {k: v for k, v in vars(c).items() if not k.startswith("_")}
            for c in cards
        ],
        "stack": "Phase-A stack is M1 (CT-TGNN) + M4 (MambaShield) + "
                 "M6 (UC-HGP) + M7 (FedGTD).",
        "trained_weights": False,
        "note": "This deployment carries the model definitions and the "
                "certificate constants, not trained weights. Federated rounds "
                "are therefore not runnable here; the MWU bound that depends "
                "on M7 is reported from the dissertation constants "
                "(|S| = 4) rather than re-derived.",
        "source": "models/PORT_STATUS.md, certificates/engine.py",
    }
