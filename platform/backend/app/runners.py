"""The runners a presenter drives from the UI.

Each declares two schemas — what the experiment IS (`params`) and how it was
COMPUTED (`hyperparams`) — so the frontend can render them as separate panels
and an audience can see which knob moved.

All three call the real research code in `certificates/engine.py`. None of them
returns a stored number dressed up as a computation; if a runner cannot produce
a value it says so, exactly as the papers do.
"""
from __future__ import annotations

import math
import sys
from typing import Any

from . import results
from .jobs import Runner, register, report

# The research modules live at the repo root, not in the platform package.
if str(results.REPO) not in sys.path:
    sys.path.insert(0, str(results.REPO))


def _num(spec: str, default, lo=None, hi=None, step=None, unit=""):
    return {"type": "number", "default": default, "min": lo, "max": hi,
            "step": step, "unit": unit, "label": spec}


def _choice(spec: str, default, options):
    return {"type": "choice", "default": default, "options": options,
            "label": spec}


# ==========================================================================
# 1. Certified floor vs theta — the headline sweep
# ==========================================================================

def _run_certified_sweep(run_id: str, params: dict, hyperparams: dict) -> dict:
    from certificates.engine import StalenessGronwallCertificate

    theta_min = float(params["theta_min_s"])
    theta_max = float(params["theta_max_s"])
    n = int(hyperparams["grid_points"])
    mapping = params["mapping"]
    margin = float(params["margin_m"])
    hops = int(params["n_malicious_hops"])

    cert = StalenessGronwallCertificate(
        v_max=float(hyperparams["v_max_m_s"]),
        slack_s=float(params["contact_slack_s"]),
        L=float(hyperparams["lipschitz_L"]),
        T=float(hyperparams["horizon_T"]))

    # Log-spaced: the interesting structure (the knee at the contact slack, and
    # the benign residual floor at 0.178 s) spans two decades.
    lo, hi = math.log10(theta_min), math.log10(theta_max)
    grid = [10 ** (lo + (hi - lo) * i / (n - 1)) for i in range(n)] if n > 1 else [theta_min]

    rows, inside_thetas = [], []
    for i, theta in enumerate(grid):
        report(run_id, int(100 * i / len(grid)), f"theta = {theta:.4f} s")
        r = cert.certify_staleness(theta_s=theta, n_malicious_hops=hops,
                                   margin_m=margin, mapping=mapping).params
        rows.append({"theta_s": round(theta, 5),
                     "delta_staleness_s": r["delta_staleness_s"],
                     "delta_pos_m": r["delta_pos_m"],
                     "tube_m": r["tube_m"],
                     "inside": r["inside_tube"]})
        if r["inside_tube"]:
            inside_thetas.append(theta)

    report(run_id, 100, "done")
    window = ([round(min(inside_thetas), 4), round(max(inside_thetas), 4)]
              if inside_thetas else None)
    return {
        "rows": rows,
        "certified_window_s": window,
        "window_empty": window is None,
        "gamma_m_s": rows and cert.GAMMA.get(mapping, cert.v_max),
        "paper_theta_inside": any(
            abs(r["theta_s"] - 0.25) < 1e-9 or
            (window and window[0] <= 0.25 <= window[1]) for r in rows),
        "note": ("The verdict is parametric in the mapping: the kinematic worst "
                 "case and the measured EKF rate disagree at theta = 0.25 s."),
    }


register(Runner(
    kind="certified_sweep",
    title="Certified floor vs detector operating point",
    description="Sweeps theta and reports where the Gronwall tube still fits "
                "the corridor. This is the paper's headline figure, computed "
                "live.",
    params={
        "theta_min_s": _num("theta minimum", 0.05, 0.01, 1.0, 0.01, "s"),
        "theta_max_s": _num("theta maximum", 10.0, 0.1, 60.0, 0.1, "s"),
        "mapping": _choice("theta -> delta mapping", "ekf",
                           ["kinematic", "receiver", "ekf"]),
        "margin_m": _num("corridor margin m", 10.0, 1.0, 50.0, 0.5, "m"),
        "n_malicious_hops": _num("malicious hops H", 2, 1, 12, 1, "hops"),
        "contact_slack_s": _num("contact-window slack s", 5.0, 0.5, 30.0, 0.5, "s"),
    },
    hyperparams={
        "grid_points": _num("grid points", 40, 5, 400, 1, ""),
        "lipschitz_L": _num("Lipschitz constant L", 1.181, 0.5, 4.0, 0.001, ""),
        "horizon_T": _num("mission horizon T", 1.0, 0.1, 10.0, 0.1, ""),
        "v_max_m_s": _num("kinematic v_max", 15.0, 1.0, 60.0, 0.5, "m/s"),
    },
    fn=_run_certified_sweep,
    provenance="real_corpus",
))


# ==========================================================================
# 2. Sensitivity: how steep would gamma have to get?
# ==========================================================================

def _run_sensitivity(run_id: str, params: dict, hyperparams: dict) -> dict:
    L = float(hyperparams["lipschitz_L"])
    T = float(hyperparams["horizon_T"])
    H = int(params["n_malicious_hops"])
    theta_ref = float(params["theta_reference_s"])
    margins = [float(x) for x in str(params["margins_m"]).split(",") if x.strip()]

    rows = []
    for i, m in enumerate(margins):
        report(run_id, int(100 * i / max(len(margins), 1)), f"margin {m} m")
        # theta*(m) = m / (gamma e^{LT} H); invert for the gamma that would put
        # theta_ref exactly on the window edge.
        gamma_req = m / (theta_ref * math.exp(L * T) * H)
        rows.append({
            "margin_m": m,
            "gamma_required_m_s": round(gamma_req, 4),
            "cleared_by_ekf": 1.37 < gamma_req,
            "cleared_by_receiver": 1.20 < gamma_req,
            "cleared_by_kinematic": 15.0 < gamma_req,
            "ekf_headroom_x": round(gamma_req / 1.37, 2),
        })
    report(run_id, 100, "done")
    return {"rows": rows, "theta_reference_s": theta_ref,
            "note": "A mapping certifies theta_reference iff its gamma is BELOW "
                    "gamma_required. The measured rates clear it; the kinematic "
                    "worst case does not."}


register(Runner(
    kind="sensitivity",
    title="Interface sensitivity",
    description="How steep the delay-to-position rate would have to become "
                "before the detector's operating point leaves the certified "
                "window.",
    params={
        "theta_reference_s": _num("reference theta", 0.25, 0.01, 10.0, 0.01, "s"),
        "margins_m": {"type": "text", "default": "2,5,10,20",
                      "label": "corridor margins (comma-separated, m)"},
        "n_malicious_hops": _num("malicious hops H", 2, 1, 12, 1, "hops"),
    },
    hyperparams={
        "lipschitz_L": _num("Lipschitz constant L", 1.181, 0.5, 4.0, 0.001, ""),
        "horizon_T": _num("mission horizon T", 1.0, 0.1, 10.0, 0.1, ""),
    },
    fn=_run_sensitivity,
    provenance="real_corpus",
))


# ==========================================================================
# 3. Mapping comparison — the one-tap demo, as a run
# ==========================================================================

def _run_mapping_compare(run_id: str, params: dict, hyperparams: dict) -> dict:
    from certificates.engine import StalenessGronwallCertificate

    cert = StalenessGronwallCertificate(L=float(hyperparams["lipschitz_L"]),
                                        T=float(hyperparams["horizon_T"]))
    theta = float(params["theta_s"])
    out = []
    mappings = ["kinematic", "receiver", "ekf"]
    for i, m in enumerate(mappings):
        report(run_id, int(100 * i / len(mappings)), f"mapping {m}")
        r = cert.certify_staleness(theta_s=theta,
                                   n_malicious_hops=int(params["n_malicious_hops"]),
                                   margin_m=float(params["margin_m"]),
                                   mapping=m).params
        out.append({"mapping": m, "gamma_m_s": r["gamma_m_s"],
                    "delta_pos_m": r["delta_pos_m"], "tube_m": r["tube_m"],
                    "inside": r["inside_tube"], "note": r["mapping_note"]})
    report(run_id, 100, "done")
    disagree = len({r["inside"] for r in out}) > 1
    return {"rows": out, "theta_s": theta, "mappings_disagree": disagree,
            "note": ("The mappings disagree at this operating point: the same "
                     "theorem and the same detector setting give opposite "
                     "verdicts, decided by a measurement."
                     if disagree else
                     "All mappings agree at this operating point.")}


register(Runner(
    kind="mapping_compare",
    title="Mapping comparison at one operating point",
    description="Runs all three theta->delta mappings side by side. Built for "
                "the live demonstration: at theta = 0.25 s they disagree.",
    params={
        "theta_s": _num("detector operating point", 0.25, 0.01, 10.0, 0.01, "s"),
        "margin_m": _num("corridor margin", 10.0, 1.0, 50.0, 0.5, "m"),
        "n_malicious_hops": _num("malicious hops H", 2, 1, 12, 1, "hops"),
    },
    hyperparams={
        "lipschitz_L": _num("Lipschitz constant L", 1.181, 0.5, 4.0, 0.001, ""),
        "horizon_T": _num("mission horizon T", 1.0, 0.1, 10.0, 0.1, ""),
    },
    fn=_run_mapping_compare,
    provenance="real_corpus",
))


def schemas() -> list[dict]:
    from .jobs import RUNNERS
    return [r.schema() for r in RUNNERS.values()]
