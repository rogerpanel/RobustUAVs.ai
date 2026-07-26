#!/usr/bin/env python3
"""Certificate engine for the composed network->navigation guarantee.

Wires the FOUR dissertation Ch.6 certificates (§6.6) to the pairing schema.
The math delegates to the reference implementation ported into
`models/uav_defense/defenses/` (lipschitz.py, smoothing.py) — the same code
behind the robustidps.ai /uav/certification dashboard.

Phase-A constants (dissertation Ch.6, Table + §6.6 text; M1 CT-TGNN config:
8 satellites, 8-dim CAF features, hidden H=32):
    L_g_hat   = 1.01     (power-iteration estimate of drift Lipschitz const)
    T         = 1.0      (integration horizon)
    eps_out   = 0.5      (required output deviation bound)
    => Gronwall certified input radius R = eps_out * exp(-L_g*T) = 0.18
    RS sigma  = 0.25 => certified l2 radius 0.44 (Cohen, alpha=1e-3, n=200)
    MWU regret R(T) <= sqrt(T * ln|S|), defender policy set |S| = 4
      (aggressive maneuver / conservative loiter / return-to-home / INS-only)
Operational anchor (Ch.6 §6.6): with these certificates the navigation stack
sustains reliable operation at J/S <= 20 dB with target MCR >= 0.80.
NOTE the wording gap to reconcile before the paper: Ch.6 text says
"MCR >= 0.80" at J/S=20 dB for the *certified* regime, while the dashboard
banner and EW-Bench empirics state the DO-326A 0.90 floor holds to ~20-25 dB.
Certified floor and empirical floor are different quantities — keep both,
label them clearly, never conflate.

The live dashboard values (screenshot: L_g 0.083, Gronwall radius 0.460,
RS 0.111, PAC-Bayes 0.041) are recomputed per-visit on a 16-sample synthetic
batch — demo variability, NOT the dissertation constants. Use the dissertation
constants for the paper; use `measure_live()` semantics only for demos.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# make the ported package importable when running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "models"))

try:
    from uav_defense.defenses.lipschitz import gronwall_radius, gronwall_output_bound
except Exception:                                    # torch not installed etc.
    def gronwall_radius(L_g, T, eps_out):
        return float(eps_out * math.exp(-L_g * T)) if L_g > 0 else float("inf")
    def gronwall_output_bound(L_g, T, eps_in):
        return float(eps_in * math.exp(L_g * T))

# ------------------------- dissertation constants -------------------------

PHASE_A = {
    "L_g": 1.01,
    "T": 1.0,
    "eps_out": 0.5,
    "rs_sigma": 0.25,
    "rs_radius": 0.44,          # Cohen radius at sigma=0.25, alpha=1e-3, n=200
    "rs_alpha": 1e-3,
    "rs_n": 200,
    "mwu_num_policies": 4,      # {aggressive, loiter, RTH, INS-only}
    "js_anchor_db": 20.0,       # J/S at which the certified regime is anchored
    "mcr_certified_target": 0.80,   # Ch.6 wording (certified)
    "mcr_do326a_floor": 0.90,       # DO-326A operational floor (empirical)
}


@dataclass
class Perturbation:
    """The delta handed over from the network side (schema `delta` block)."""
    kind: str          # 'state_staleness_s' | 'pos_error_m' | 'sensor_linf' | 'sensor_l2'
    value: float
    mapping: str


@dataclass
class CertificateResult:
    name: str
    certified_mcr: Optional[float]
    params: dict = field(default_factory=dict)

    def to_schema(self) -> dict:
        return {"name": self.name, "certified_mcr": self.certified_mcr,
                "params": self.params}


class LipschitzGronwallCertificate:
    """Theorem 6.1 glue: bounded input => bounded trajectory tube.

    certify() answers: does the network-residual perturbation delta fit inside
    the certified input radius R = eps_out * exp(-L_g * T)?  If yes, the
    output deviation is bounded by eps_out and the certified operating regime
    (J/S <= 20 dB, MCR >= mcr_certified_target) applies.

    OPEN ITEM (W3): delta arrives in physical units (metres of position error,
    seconds of staleness); the certificate radius lives in normalised CAF-
    feature l2 space. The unit bridge — the sensor-to-feature scaling that
    converts pos_error_m into feature-space l2 — must come from the
    uav_defense feature pipeline (datasets/texbat.py normalisation constants).
    Until it is ported, pass deltas already expressed in feature space
    (kind='sensor_l2'); certify() refuses other kinds rather than guess.
    """

    name = "lipschitz_gronwall"

    def __init__(self, L_g: float = PHASE_A["L_g"], T: float = PHASE_A["T"],
                 eps_out: float = PHASE_A["eps_out"]):
        self.L_g, self.T, self.eps_out = L_g, T, eps_out
        self.radius = gronwall_radius(L_g, T, eps_out)

    def certify(self, delta: Perturbation) -> CertificateResult:
        if delta.kind != "sensor_l2":
            return CertificateResult(self.name, None, {
                "status": "unit_bridge_missing",
                "detail": f"delta kind '{delta.kind}' not yet mappable to "
                          f"feature-space l2; port the normalisation constants "
                          f"(see class docstring).",
                "certified_input_radius": round(self.radius, 4)})
        inside = delta.value <= self.radius
        return CertificateResult(
            self.name,
            PHASE_A["mcr_certified_target"] if inside else None,
            {"L_g": self.L_g, "T": self.T, "eps_out": self.eps_out,
             "certified_input_radius": round(self.radius, 4),
             "delta_l2": delta.value, "inside_radius": inside,
             "output_bound": round(gronwall_output_bound(self.L_g, self.T,
                                                         delta.value), 4),
             "regime": f"J/S<={PHASE_A['js_anchor_db']:.0f} dB" if inside
                       else "outside certified regime"})


class RandomizedSmoothingCertificate:
    """Cohen l2 certificate; complements Gronwall when the jamming budget is
    only statistically known. Constant-level answer from Ch.6: R=0.44 at
    sigma=0.25 (covers 96% of the TEXBAT-like corpus). Per-sample recompute
    goes through models/uav_defense/defenses/smoothing.certify_l2."""

    name = "randomized_smoothing"

    def certify(self, delta: Perturbation) -> CertificateResult:
        if delta.kind != "sensor_l2":
            return CertificateResult(self.name, None,
                                     {"status": "unit_bridge_missing"})
        inside = delta.value <= PHASE_A["rs_radius"]
        return CertificateResult(
            self.name, PHASE_A["mcr_certified_target"] if inside else None,
            {"sigma": PHASE_A["rs_sigma"], "radius": PHASE_A["rs_radius"],
             "alpha": PHASE_A["rs_alpha"], "n": PHASE_A["rs_n"],
             "delta_l2": delta.value, "inside_radius": inside})


class MWURegretCertificate:
    """Theorem 6.4: defender's MWU policy mixing has regret
    R(T) <= sqrt(T * ln|S|) against an adaptive jammer (Stackelberg,
    M7 FedGTD). Not a per-perturbation certificate; reported per-horizon."""

    name = "mwu_regret"

    def bound(self, horizon_T: int) -> CertificateResult:
        r = math.sqrt(horizon_T * math.log(PHASE_A["mwu_num_policies"]))
        return CertificateResult(self.name, None,
                                 {"horizon_T": horizon_T,
                                  "num_policies": PHASE_A["mwu_num_policies"],
                                  "regret_bound": round(r, 4)})


class PACBayesCertificate:
    """Theorem 6.3: transfers the certificate from the training corpus to the
    test-mission distribution. Constants live in the dissertation's methods
    chapter; recorded here as a named component so pairing records can cite
    it. Numeric bound port: TODO (needs the methods-chapter constants)."""

    name = "pac_bayes"

    def certify(self, delta: Perturbation) -> CertificateResult:
        return CertificateResult(self.name, None,
                                 {"status": "constants_in_methods_chapter"})


REGISTRY = {
    "lipschitz_gronwall": LipschitzGronwallCertificate(),
    "randomized_smoothing": RandomizedSmoothingCertificate(),
    "mwu_regret": MWURegretCertificate(),
    "pac_bayes": PACBayesCertificate(),
}


if __name__ == "__main__":
    # self-check against the dissertation table
    lg = LipschitzGronwallCertificate()
    assert abs(lg.radius - 0.18) < 0.005, lg.radius
    r = lg.certify(Perturbation("sensor_l2", 0.10, "test"))
    assert r.certified_mcr == 0.80 and r.params["inside_radius"]
    r2 = lg.certify(Perturbation("pos_error_m", 30.0, "staleness_v0"))
    assert r2.certified_mcr is None and r2.params["status"] == "unit_bridge_missing"
    print(f"OK  Gronwall radius={lg.radius:.4f} (dissertation: 0.18); "
          f"RS radius={PHASE_A['rs_radius']}; "
          f"MWU bound(T=100)={MWURegretCertificate().bound(100).params['regret_bound']}")
