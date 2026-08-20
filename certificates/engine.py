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

# ---- W3 unit bridge: pos_error_m -> CAF-feature l2 (certificates/unit_bridge.py)
# caf_shift_v2 (tracking-loop-aligned) is the default since the P1 certified-
# regime analysis: v1 charged the carrier-phase nuisance to the adversary and
# under-certified by ~216x. v1 remains available for provenance.
try:
    try:
        from certificates.unit_bridge import (
            to_feature_l2, bridge_info, to_feature_l2_v2, bridge_info_v2)
    except ImportError:                              # run as a script from certificates/
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from unit_bridge import (
            to_feature_l2, bridge_info, to_feature_l2_v2, bridge_info_v2)
    HAVE_BRIDGE = True
except Exception:                                    # numpy/torch missing
    HAVE_BRIDGE = False


def _to_feature_l2(delta: "Perturbation"):
    """Map a schema delta to feature-space l2. Returns (l2, meta) or
    (None, meta) when the kind is not yet mappable — the caller reports
    unit_bridge_missing honestly instead of guessing.

    NOTE (P1, docs/certified_regime_analysis.md): this bridge is the
    interface for RF-manipulation classes (gps_spoofing / gps_jamming),
    where the adversary reshapes the receiver input. Time-delay attacks
    perturb the vehicle in STATE space (staleness); route those through
    StalenessGronwallCertificate, not this bridge.
    """
    if delta.kind == "sensor_l2":
        return delta.value, {"unit_bridge": "identity"}
    if delta.kind == "pos_error_m" and HAVE_BRIDGE:
        info = bridge_info_v2()
        return to_feature_l2_v2(delta.value), {
            "unit_bridge": info["version"],
            "unit_bridge_basis": info["basis"],
            "pos_error_m_input": delta.value}
    return None, {
        "status": "unit_bridge_missing",
        "detail": f"delta kind '{delta.kind}' not yet mappable to feature-space "
                  f"l2" + ("" if HAVE_BRIDGE else
                           " (unit_bridge unavailable: numpy/torch not installed)")}

# ------------------------- dissertation constants -------------------------

PHASE_A = {
    "L_g": 1.01,
    "L_g_local": 1.181,         # measured local (operating-region) Lipschitz
                                # on the trained checkpoint (experiments/
                                # local_lipschitz.py, data-driven trajectories)
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
# Two radii, both honest and both reported (P1(b), docs/certified_regime_analysis.md):
#   0.182 from the global power-iteration L=1.01 (dissertation-reproducing);
#   0.153 from the measured local L=1.181 over the operating region (tighter,
#   the defensible number for the paper). The local radius is NOT loose - it is
#   SMALLER, refuting "the radius is too tight".
PHASE_A["gronwall_radius_global"] = round(
    PHASE_A["eps_out"] * math.exp(-PHASE_A["L_g"] * PHASE_A["T"]), 4)
PHASE_A["gronwall_radius_local"] = round(
    PHASE_A["eps_out"] * math.exp(-PHASE_A["L_g_local"] * PHASE_A["T"]), 4)


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

    Unit bridge (W3, landed): kind='pos_error_m' deltas are converted to
    feature-space l2 through certificates/unit_bridge.py (caf_shift_v1 — the
    measured sensitivity of the ported texbat.py CAF extractor to a
    code-delay + carrier-phase shift of d metres, upper envelope). Note the
    bridge saturates above ~lambda_L1: metre-scale spoofs certify as OUTSIDE
    the radius, which is the physically honest outcome. Deltas already in
    feature space pass through (kind='sensor_l2'); other kinds
    (state_staleness_s, sensor_linf) still return unit_bridge_missing rather
    than guess.
    """

    name = "lipschitz_gronwall"

    def __init__(self, L_g: float = PHASE_A["L_g"], T: float = PHASE_A["T"],
                 eps_out: float = PHASE_A["eps_out"], regime: str = "local"):
        # regime='local' uses the measured operating-region L=1.181 (radius
        # 0.153, the defensible paper number); 'global' uses L=1.01
        # (radius 0.182, dissertation-reproducing). Explicit L_g overrides.
        if L_g == PHASE_A["L_g"] and regime == "local":
            L_g = PHASE_A["L_g_local"]
        self.L_g, self.T, self.eps_out, self.regime = L_g, T, eps_out, regime
        self.radius = gronwall_radius(L_g, T, eps_out)

    def certify(self, delta: Perturbation) -> CertificateResult:
        l2, meta = _to_feature_l2(delta)
        if l2 is None:
            meta["certified_input_radius"] = round(self.radius, 4)
            return CertificateResult(self.name, None, meta)
        inside = l2 <= self.radius
        return CertificateResult(
            self.name,
            PHASE_A["mcr_certified_target"] if inside else None,
            {"L_g": self.L_g, "T": self.T, "eps_out": self.eps_out,
             "certified_input_radius": round(self.radius, 4),
             "delta_l2": round(l2, 4), "inside_radius": inside,
             "output_bound": round(gronwall_output_bound(self.L_g, self.T,
                                                         l2), 4),
             "regime": f"J/S<={PHASE_A['js_anchor_db']:.0f} dB" if inside
                       else "outside certified regime",
             **meta})


class RandomizedSmoothingCertificate:
    """Cohen l2 certificate; complements Gronwall when the jamming budget is
    only statistically known. Constant-level answer from Ch.6: R=0.44 at
    sigma=0.25 (covers 96% of the TEXBAT-like corpus). Per-sample recompute
    goes through models/uav_defense/defenses/smoothing.certify_l2."""

    name = "randomized_smoothing"

    def certify(self, delta: Perturbation) -> CertificateResult:
        l2, meta = _to_feature_l2(delta)
        if l2 is None:
            return CertificateResult(self.name, None, meta)
        inside = l2 <= PHASE_A["rs_radius"]
        return CertificateResult(
            self.name, PHASE_A["mcr_certified_target"] if inside else None,
            {"sigma": PHASE_A["rs_sigma"], "radius": PHASE_A["rs_radius"],
             "alpha": PHASE_A["rs_alpha"], "n": PHASE_A["rs_n"],
             "delta_l2": round(l2, 4), "inside_radius": inside, **meta})


class StalenessGronwallCertificate:
    """State-space Gronwall tube for the TIME-DELAY class (P1(c)).

    The time-delay attack never touches the RF front-end: its effect is that
    the navigation stack acts on a network-delivered correction that is
    Delta(theta) seconds stale. The perturbation therefore lives in vehicle
    STATE space (metres), and the certificate is the trajectory-tube
    argument of the composition theorem — NOT the CT-TGNN feature-space
    radius (using that radius here was the category error that made the
    certified floor look near-zero everywhere; see
    docs/certified_regime_analysis.md).

    Chain: Delta(theta) <= H*min(theta, s)   [tightened Lemma 1 — the
           contact-window slack s caps invisible per-hop delay at any
           epsilon; measured: max undetected malicious residual 4.84 s over
           15,392 hops, slack s = 5 s]
           delta_pos = v_max * Delta(theta)  [kinematic worst case,
           staleness_v0; the Whelan-grounded empirical tightening is
           real-corpus work]
           tube rho = delta_pos * exp(L*T)   [reference L=1.01, T=1;
           closed-loop L for the real vehicle is calibration-pending]
           certified iff rho <= margin m.
    """

    name = "gronwall_state_space"

    def __init__(self, v_max: float = 15.0, slack_s: float = 5.0,
                 L: float = PHASE_A["L_g"], T: float = PHASE_A["T"]):
        self.v_max, self.slack_s, self.L, self.T = v_max, slack_s, L, T

    # Delay-to-position rates, in metres of position error per second of
    # staleness. The kinematic bound is always sound but assumes the aircraft
    # flies at top speed in the wrong direction for the whole interval; the
    # measured rates come from three real PX4 flights (results/
    # whelan_delta_calibration.csv) and are ~11x tighter. Which one is used
    # decides whether theta=0.25 s is certifiable, so it is an explicit
    # parameter and never a silent default.
    GAMMA = {
        "kinematic": 15.0,   # v_max worst case
        "receiver": 1.20,    # raw receiver fix the attack injects
        "ekf": 1.37,         # filtered position the controller acts on
        # Supremum of the baseline-corrected per-sample rate over all 674
        # post-onset samples (experiments/gamma_campaign.py). The per-flight
        # secant rates above are long-horizon averages and understate the rate
        # by ~1.19x; a certificate is entitled to the supremum over the
        # conditions it covers, so this is the defensible mapping.
        "campaign_sup": 1.625,
    }

    def certify_staleness(self, theta_s: float, n_malicious_hops: int,
                          margin_m: float,
                          mapping: str = "kinematic") -> CertificateResult:
        if mapping not in self.GAMMA:
            raise ValueError(
                f"unknown delta mapping {mapping!r}; "
                f"choose one of {sorted(self.GAMMA)}")
        gamma = self.v_max if mapping == "kinematic" else self.GAMMA[mapping]
        delta_stale = n_malicious_hops * min(theta_s, self.slack_s)
        delta_pos = gamma * delta_stale
        rho = delta_pos * math.exp(self.L * self.T)
        inside = rho <= margin_m
        note = ("kinematic worst case (sound but ~11x loose)" if mapping == "kinematic"
                else "measured on 3 real PX4 flights, hover regime; "
                     "cruise-regime confirmation pending")
        return CertificateResult(
            self.name,
            PHASE_A["mcr_certified_target"] if inside else None,
            {"theta_s": theta_s, "n_malicious_hops": n_malicious_hops,
             "slack_s": self.slack_s,
             "delta_staleness_s": round(delta_stale, 4),
             "mapping": mapping,
             "mapping_note": note,
             "gamma_m_s": gamma,
             "delta_pos_m": round(delta_pos, 3),
             "L": self.L, "T": self.T,
             "tube_m": round(rho, 3), "margin_m": margin_m,
             "inside_tube": inside})


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
    """Theorem 6.3: transfers the certificate from the training mission
    distribution to unseen deployment.

    The numeric prior/posterior KL is a methods-chapter constant that is NOT
    in the ported code (see PENDING_ON_DATA.md), so we cannot emit a single
    number. What we CAN do honestly is wire the McAllester bound to the
    trained checkpoint's measured empirical risk and expose the bound as a
    function of KL: given empirical risk R_emp on m samples, with prob 1-delta
        R_true <= R_emp + sqrt( (KL + ln(2 sqrt(m)/delta)) / (2m) ).
    Pass the real R_emp (1 - clean_acc from metrics.json) and a candidate KL;
    the number is real once the methods-chapter KL replaces the placeholder.
    """

    name = "pac_bayes"

    def bound(self, r_emp: float, m: int, kl: Optional[float] = None,
              delta: float = 0.05) -> CertificateResult:
        if kl is None:
            return CertificateResult(self.name, None, {
                "status": "kl_pending",
                "detail": "McAllester bound wired to real R_emp; the numeric "
                          "prior/posterior KL is a methods-chapter constant "
                          "not in the ported code (PENDING_ON_DATA.md). Pass "
                          "kl to evaluate.",
                "r_emp": r_emp, "m": m,
                "form": "R_true <= R_emp + sqrt((KL + ln(2 sqrt(m)/delta))/(2m))"})
        slack = math.sqrt((kl + math.log(2 * math.sqrt(m) / delta)) / (2 * m))
        r_true = min(1.0, r_emp + slack)
        return CertificateResult(self.name, round(1.0 - r_true, 4), {
            "r_emp": r_emp, "m": m, "kl": kl, "delta": delta,
            "slack": round(slack, 4), "r_true_upper": round(r_true, 4),
            "certified_accuracy_floor": round(1.0 - r_true, 4)})


REGISTRY = {
    "lipschitz_gronwall": LipschitzGronwallCertificate(),
    "gronwall_state_space": StalenessGronwallCertificate(),
    "randomized_smoothing": RandomizedSmoothingCertificate(),
    "mwu_regret": MWURegretCertificate(),
    "pac_bayes": PACBayesCertificate(),
}


if __name__ == "__main__":
    # self-check against the dissertation table
    # global regime reproduces the dissertation radius 0.182
    lg_global = LipschitzGronwallCertificate(regime="global")
    assert abs(lg_global.radius - 0.18) < 0.005, lg_global.radius
    # default = local regime, the tighter measured radius 0.153 (P1(b))
    lg = LipschitzGronwallCertificate()
    assert abs(lg.radius - 0.153) < 0.005, lg.radius
    r = lg.certify(Perturbation("sensor_l2", 0.10, "test"))
    assert r.certified_mcr == 0.80 and r.params["inside_radius"]

    # W3 unit bridge: pos_error_m now converts instead of refusing
    r2 = lg.certify(Perturbation("pos_error_m", 30.0, "whelan_measured"))
    if HAVE_BRIDGE:
        # a 30 m spoof shifts the code phase far outside the 0.18 tube
        assert r2.certified_mcr is None and not r2.params["inside_radius"], r2
        assert r2.params["unit_bridge"] == "caf_shift_v2"
        # sub-crossing (~0.45 m) errors stay inside the certified tube under
        # the corrected tracking-loop bridge (v1 capped this at ~2 mm)
        r3 = lg.certify(Perturbation("pos_error_m", 0.3, "whelan_measured"))
        assert r3.certified_mcr == 0.80 and r3.params["inside_radius"], r3
        bridge_note = (f"bridge caf_shift_v2: 0.3 m -> l2="
                       f"{r3.params['delta_l2']}, 30 m -> l2="
                       f"{r2.params['delta_l2']} (plateau)")
    else:
        assert r2.certified_mcr is None and r2.params["status"] == "unit_bridge_missing"
        bridge_note = "bridge unavailable (numpy/torch missing) - honest refusal kept"

    # kinds with no bridge still refuse honestly
    r4 = lg.certify(Perturbation("state_staleness_s", 2.0, "staleness_v0"))
    assert r4.certified_mcr is None and r4.params["status"] == "unit_bridge_missing"

    # state-space staleness certificate (time-delay class, P1(c)):
    ss = StalenessGronwallCertificate()
    # tight detector, H=2, 20 m corridor: inside the certified window
    r5 = ss.certify_staleness(theta_s=0.2, n_malicious_hops=2, margin_m=20.0)
    assert r5.certified_mcr == 0.80 and r5.params["inside_tube"], r5
    # paper operating point 0.25 s is JUST outside the 20 m window (0.243 s)
    r6 = ss.certify_staleness(theta_s=0.25, n_malicious_hops=2, margin_m=20.0)
    assert r6.certified_mcr is None and not r6.params["inside_tube"], r6
    # the slack cap: theta=10 s certifies exactly like theta=5 s (knee)
    r7 = ss.certify_staleness(theta_s=10.0, n_malicious_hops=2, margin_m=20.0)
    assert r7.params["delta_staleness_s"] == 10.0, r7

    # PAC-Bayes: pending without KL, real-valued once KL supplied
    pb = PACBayesCertificate()
    assert pb.bound(r_emp=0.0, m=256).params["status"] == "kl_pending"
    assert pb.bound(r_emp=0.0, m=256, kl=5.0).certified_mcr is not None

    print(f"OK  Gronwall radius local={lg.radius:.4f} (L=1.181), "
          f"global={lg_global.radius:.4f} (dissertation 0.18); "
          f"RS radius={PHASE_A['rs_radius']}; "
          f"MWU bound(T=100)={MWURegretCertificate().bound(100).params['regret_bound']}; "
          f"{bridge_note}")
