"""The model registry.

One uniform envelope for every model, certificate, and detector the platform
exposes, so the frontend never special-cases a row: it renders whatever the
registry declares. This indirection is lifted from RobustIDPS.ai, where it is
the reason three new detectors could ship in v4 without a frontend change
(docs/platform_architecture.md §1.2).

Two fields carry the project's honesty discipline into the product surface:

  provenance          where this row's numbers come from
  certificate_status  whether it can report a certified number AT ALL

A row that cannot honestly produce a number reports its status instead of a
plausible-looking wrong one. The frontend renders both as chips.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Category(str, Enum):
    navigation = "navigation"
    network = "network"
    certificate = "certificate"
    baseline = "baseline"
    composition = "composition"


class Provenance(str, Enum):
    real_corpus = "real_corpus"
    simulation = "simulation"
    fixture = "fixture"
    pending = "pending"


class CertificateStatus(str, Enum):
    ok = "ok"
    unit_bridge_missing = "unit_bridge_missing"
    kl_pending = "kl_pending"
    not_applicable = "not_applicable"


class ModelCard(BaseModel):
    model_id: str
    display_name: str
    category: Category
    provenance: Provenance
    certificate_status: CertificateStatus = CertificateStatus.not_applicable
    source: str = Field(description="Path in the research repo this row is backed by")
    summary: str
    constants: dict = Field(default_factory=dict)
    caveat: Optional[str] = None


# --------------------------------------------------------------------------
# The registry. Every `source` must exist in the repo; test_registry_sources
# enforces that, so a row cannot outlive the code it claims to expose.
# --------------------------------------------------------------------------
REGISTRY: list[ModelCard] = [
    ModelCard(
        model_id="m1_ct_tgnn",
        display_name="CT-TGNN (GNSS constellation graph)",
        category=Category.navigation,
        provenance=Provenance.fixture,
        source="models/uav_defense/models/ct_tgnn_gnss.py",
        summary="Continuous-time temporal graph network over the GNSS "
                "constellation-plus-receiver graph; the navigation model whose "
                "Lipschitz constant the Gronwall tube is measured on.",
        constants={"L_g_global": 1.01, "L_g_local": 1.181},
        caveat="Trained on a synthetic Phase-A corpus; real-TEXBAT "
               "re-calibration is pending.",
    ),
    ModelCard(
        model_id="m4_mambashield",
        display_name="MambaShield",
        category=Category.navigation,
        provenance=Provenance.fixture,
        source="models/uav_defense/models/mambashield.py",
        summary="State-space sequence defence over the receiver feature stream; "
                "M4 of the Phase-A stack.",
    ),
    ModelCard(
        model_id="m6_uc_hgp",
        display_name="UC-HGP (uncertainty-calibrated)",
        category=Category.navigation,
        provenance=Provenance.fixture,
        source="models/PORT_STATUS.md",
        summary="Uncertainty-calibrated hierarchical Gaussian process head; M6 "
                "of the Phase-A stack.",
    ),
    ModelCard(
        model_id="m7_fedgtd",
        display_name="FedGTD (Stackelberg / MWU defender)",
        category=Category.navigation,
        provenance=Provenance.fixture,
        source="models/PORT_STATUS.md",
        summary="Federated graph-temporal-dynamics defender playing a "
                "Stackelberg game against the jammer; supplies the MWU policy "
                "set the regret certificate bounds.",
        constants={"num_policies": 4},
    ),
    ModelCard(
        model_id="caf_cnn",
        display_name="CAF-CNN",
        category=Category.baseline,
        provenance=Provenance.simulation,
        source="models/uav_defense/models/baselines.py",
        summary="Cross-ambiguity-function CNN spoofing detector; published "
                "baseline in the EW-Bench defence sweep.",
    ),
    ModelCard(
        model_id="seq2seq_tr",
        display_name="Seq2Seq-Transformer",
        category=Category.baseline,
        provenance=Provenance.simulation,
        source="models/uav_defense/models/baselines.py",
        summary="Sequence-to-sequence transformer baseline over the telemetry "
                "stream.",
    ),
    ModelCard(
        model_id="datamut",
        display_name="DATAMUt forwarding detector",
        category=Category.network,
        provenance=Provenance.simulation,
        source="third_party/datamut",
        summary="Time-window-graph forwarding detector. Its operating point is "
                "a single sweepable threshold, which is what makes the "
                "cross-layer sweep unambiguous.",
        constants={"epsilon_paper_s": 0.25, "contact_slack_s": 5.0,
                   "contact_period_s": 60.0},
    ),
    ModelCard(
        model_id="cert_gronwall",
        display_name="Lipschitz-Gronwall tube",
        category=Category.certificate,
        provenance=Provenance.fixture,
        certificate_status=CertificateStatus.ok,
        source="certificates/engine.py",
        summary="Deterministic trajectory tube; the active certificate for the "
                "time-delay class and the one that sets the certified window.",
        constants={"radius_local": 0.153, "radius_global": 0.182},
    ),
    ModelCard(
        model_id="cert_smoothing",
        display_name="Randomized smoothing (Cohen)",
        category=Category.certificate,
        provenance=Provenance.fixture,
        certificate_status=CertificateStatus.ok,
        source="certificates/engine.py",
        summary="Probabilistic l2 radius for budgets known only statistically.",
        constants={"sigma": 0.25, "radius": 0.44, "alpha": 1e-3, "n": 200},
    ),
    ModelCard(
        model_id="cert_staleness",
        display_name="Staleness-Gronwall (state space)",
        category=Category.certificate,
        provenance=Provenance.real_corpus,
        certificate_status=CertificateStatus.ok,
        source="certificates/engine.py",
        summary="The correct certificate for the time-delay class: the "
                "perturbation lives in vehicle STATE space, not CAF feature "
                "space. Routing a delay through the feature-space bridge is a "
                "category error and returns unit_bridge_missing by design.",
        constants={"gamma_receiver_m_s": 1.20, "gamma_ekf_m_s": 1.37,
                   "v_max_m_s": 15.0},
    ),
    ModelCard(
        model_id="cert_mwu",
        display_name="MWU regret",
        category=Category.certificate,
        provenance=Provenance.fixture,
        certificate_status=CertificateStatus.ok,
        source="certificates/engine.py",
        summary="Online bound against an adaptive jammer over the time axis; "
                "the only certificate expressing adaptation.",
        constants={"policy_set_size": 4},
    ),
    ModelCard(
        model_id="cert_pacbayes",
        display_name="PAC-Bayes (McAllester)",
        category=Category.certificate,
        provenance=Provenance.pending,
        certificate_status=CertificateStatus.kl_pending,
        source="certificates/engine.py",
        summary="Transfers a floor from the training mission mix to deployment.",
        caveat="Wired to the trained model's measured empirical risk, but the "
               "numeric prior-to-posterior KL is not yet available. Reported as "
               "a form, never as a number.",
    ),
    ModelCard(
        model_id="composed",
        display_name="Composed theta -> delta -> MCR guarantee",
        category=Category.composition,
        provenance=Provenance.real_corpus,
        certificate_status=CertificateStatus.ok,
        source="experiments/compose_certified.py",
        summary="The headline result: the only configuration with a nonzero "
                "certified floor against an evading attacker, dominating both "
                "single-layer baselines at every operating point.",
        constants={"H_hops": 2, "theta_paper_s": 0.25,
                   "window_ekf_s": [0.178, 1.334], "corridor_m": 10.0},
    ),
]

BY_ID = {m.model_id: m for m in REGISTRY}


def list_models(category: Optional[str] = None) -> list[ModelCard]:
    if category is None:
        return list(REGISTRY)
    return [m for m in REGISTRY if m.category.value == category]


def get_model(model_id: str) -> Optional[ModelCard]:
    return BY_ID.get(model_id)


def categories() -> list[str]:
    # Preserve declaration order rather than sorting; it is the order the
    # frontend groups by and it follows the argument of the paper.
    seen, out = set(), []
    for m in REGISTRY:
        if m.category.value not in seen:
            seen.add(m.category.value)
            out.append(m.category.value)
    return out
