"""The SOC Copilot: a symmetric tool registry over the research results.

Three properties are copied deliberately from RobustIDPS.ai v5:

  1. SYMMETRY. Every tool appears in both TOOLS and DISPATCH, and a test fails
     the build on asymmetry. In v5 this is what keeps 61 tools honest; a tool
     advertised but not dispatchable is a lie told to the model.
  2. RESULT CACHE. Tools read the committed result files, not a live
     recomputation, so an answer is fast and reproducible.
  3. PROVENANCE IN THE ANSWER. Every tool result carries the file it came from,
     so the copilot can cite rather than assert.
"""
from __future__ import annotations

from typing import Any, Callable

from . import registry, results
from .llm import complete, provider_status

SYSTEM = """You are the RobustUAVs.ai copilot. You answer questions about an \
end-to-end UAV security benchmark and a composed network-to-navigation \
certificate.

Rules you must follow:
- Answer ONLY from the retrieved tool results supplied to you. Never invent a \
number, a constant, or a file name.
- Every quantity you state must be attributable to a `source` field in the \
retrieved results. Say which file it came from.
- If a value is marked pending, unit_bridge_missing, or kl_pending, say so \
plainly. A clearly-marked gap is correct; a plausible-looking substitute is not.
- Keep the two floors distinct: MCR >= 0.80 is the CERTIFIED target, \
MCR >= 0.90 is the DO-326A OPERATIONAL floor. Conflating them overstates the \
guarantee.
- Be concise and technical."""


# --------------------------------------------------------------------------
# Tool implementations. Each returns a dict carrying its own provenance.
# --------------------------------------------------------------------------

def _wrap(data: Any, source: str, note: str | None = None) -> dict:
    out = {"data": data, "source": source}
    if note:
        out["note"] = note
    return out


def t_list_models(category: str | None = None) -> dict:
    return _wrap([m.model_dump() for m in registry.list_models(category)],
                 "platform/backend/app/registry.py")


def t_get_model(model_id: str) -> dict:
    m = registry.get_model(model_id)
    if m is None:
        return _wrap(None, "platform/backend/app/registry.py",
                     f"no model '{model_id}'; call list_models for valid ids")
    return _wrap(m.model_dump(), "platform/backend/app/registry.py")


def t_get_operating_curve() -> dict:
    return _wrap(results.operating_curve(), "results/theta_operating_curve.csv",
                 "Clean multi-seed campaign. An earlier curve was contaminated "
                 "by a workdir-accumulation bug and has been replaced.")


def t_get_certified_floor() -> dict:
    return _wrap(results.certified_floor(), "results/certified_floor_vs_theta.csv")


def t_get_certified_window() -> dict:
    return _wrap(results.certified_window(),
                 "results/certified_operating_window.csv",
                 "theta*(m) = m / (gamma e^{LT} H). Parametric in the "
                 "theta->delta mapping; report which mapping was used.")


def t_get_delta_calibration() -> dict:
    return _wrap(results.whelan_calibration(),
                 "results/whelan_delta_calibration.csv",
                 "Three real PX4 flights, hover regime, self-referenced to the "
                 "pre-attack median. A calibration sample, not a distribution; "
                 "cruise-regime confirmation is pending.")


def t_get_mcr_anchor() -> dict:
    return _wrap(results.mcr_anchor(), "results/ewbench_mcr_anchor.csv",
                 "Spatial MCR: the source records geometric completion only.")


def t_get_ingest_stats() -> dict:
    return _wrap(results.ingest_stats(), "results/ingest_stats.csv")


def t_get_provenance_distribution() -> dict:
    return _wrap(results.provenance_distribution(),
                 "results/provenance_distribution.csv",
                 "Acquisition split across the corpus. Note separately that the "
                 "released measured_same_platform PAIRING count is zero, "
                 "because the one both-layer source lacks machine-readable "
                 "attack intervals.")


def t_get_dominance() -> dict:
    return _wrap(results.wilcoxon(), "results/stats_wilcoxon.csv",
                 "Wilcoxon signed-rank, Holm-corrected, per seed.")


def t_get_pairings() -> dict:
    return _wrap(results.pairings(), "results/pairings_poc.jsonl")


def t_certify_staleness(theta_s: float, n_malicious_hops: int = 2,
                        margin_m: float = 10.0,
                        mapping: str = "ekf") -> dict:
    """Run the real certificate engine rather than reciting a stored number."""
    import sys
    from pathlib import Path
    root = str(results.REPO)
    if root not in sys.path:
        sys.path.insert(0, root)
    from certificates.engine import StalenessGronwallCertificate  # noqa: PLC0415

    cert = StalenessGronwallCertificate()
    res = cert.certify_staleness(theta_s=theta_s,
                                 n_malicious_hops=n_malicious_hops,
                                 margin_m=margin_m, mapping=mapping)
    payload = res.to_schema() if hasattr(res, "to_schema") else res
    return _wrap(payload, "certificates/engine.py",
                 "Computed live by the certificate engine.")


def t_list_result_files() -> dict:
    return _wrap(results.available(), "results/")


def t_get_llm_providers() -> dict:
    return _wrap(provider_status(), "platform/backend/app/llm.py")


TOOLS: dict[str, dict] = {
    "list_models": {
        "description": "List registered models, certificates, and detectors. "
                       "Optional category filter.",
        "params": {"category": "optional: navigation|network|certificate|"
                               "baseline|composition"}},
    "get_model": {
        "description": "Full card for one model, including constants, "
                       "provenance, and certificate status.",
        "params": {"model_id": "required"}},
    "get_operating_curve": {
        "description": "Detector recall and FPR versus the operating point "
                       "epsilon, from the clean multi-seed campaign.",
        "params": {}},
    "get_certified_floor": {
        "description": "Certified MCR floor versus theta.", "params": {}},
    "get_certified_window": {
        "description": "The certified operating window theta*(m) per corridor "
                       "margin and per theta->delta mapping.", "params": {}},
    "get_delta_calibration": {
        "description": "The measured delay-to-position rate gamma from real "
                       "PX4 flights, receiver and EKF error signals.",
        "params": {}},
    "get_mcr_anchor": {
        "description": "Spatial MCR versus J/S for each defence configuration.",
        "params": {}},
    "get_ingest_stats": {
        "description": "Per-source event and window counts from the "
                       "schema-validated adapter outputs.", "params": {}},
    "get_provenance_distribution": {
        "description": "How much of the corpus is real-hardware capture versus "
                       "simulation, and the pairing-basis position.",
        "params": {}},
    "get_dominance": {
        "description": "Wilcoxon signed-rank, Holm-corrected comparison of the "
                       "composed guarantee against single-layer baselines.",
        "params": {}},
    "get_pairings": {
        "description": "Released cross-layer pairing records.", "params": {}},
    "certify_staleness": {
        "description": "Run the staleness-Gronwall certificate live for a given "
                       "detector operating point.",
        "params": {"theta_s": "required, seconds",
                   "n_malicious_hops": "optional, default 2",
                   "margin_m": "optional, default 10.0",
                   "mapping": "optional: kinematic|receiver|ekf, default ekf. "
                              "Decides whether theta is certifiable, so it is "
                              "always reported back."}},
    "list_result_files": {
        "description": "Every result file available in this deployment.",
        "params": {}},
    "get_llm_providers": {
        "description": "Which LLM providers are configured and which is active.",
        "params": {}},
}

DISPATCH: dict[str, Callable[..., dict]] = {
    "list_models": t_list_models,
    "get_model": t_get_model,
    "get_operating_curve": t_get_operating_curve,
    "get_certified_floor": t_get_certified_floor,
    "get_certified_window": t_get_certified_window,
    "get_delta_calibration": t_get_delta_calibration,
    "get_mcr_anchor": t_get_mcr_anchor,
    "get_ingest_stats": t_get_ingest_stats,
    "get_provenance_distribution": t_get_provenance_distribution,
    "get_dominance": t_get_dominance,
    "get_pairings": t_get_pairings,
    "certify_staleness": t_certify_staleness,
    "list_result_files": t_list_result_files,
    "get_llm_providers": t_get_llm_providers,
}


def call(name: str, **kwargs) -> dict:
    fn = DISPATCH.get(name)
    if fn is None:
        return {"error": f"unknown tool '{name}'", "available": sorted(TOOLS)}
    try:
        return fn(**kwargs)
    except results.ResultUnavailable as exc:
        return {"error": str(exc), "unavailable": exc.name}
    except TypeError as exc:
        return {"error": f"bad arguments for '{name}': {exc}",
                "params": TOOLS[name]["params"]}


# --------------------------------------------------------------------------
# Retrieval. Keyword routing rather than model-driven tool choice: the corpus
# of tools is small and fixed, and this keeps the synthetic fallback useful.
# --------------------------------------------------------------------------
_ROUTES: list[tuple[tuple[str, ...], str]] = [
    (("gamma", "calibration", "delay-to-position", "delta mapping"), "get_delta_calibration"),
    (("window", "operating point", "certifiable", "theta*"), "get_certified_window"),
    (("floor", "certified mcr", "certify"), "get_certified_floor"),
    (("recall", "fpr", "false positive", "operating curve", "epsilon"), "get_operating_curve"),
    (("dominance", "baseline", "wilcoxon", "holm"), "get_dominance"),
    (("provenance", "measured", "synthetic alignment", "how much"), "get_provenance_distribution"),
    (("dataset", "corpus", "ingest", "how many events"), "get_ingest_stats"),
    (("mcr", "j/s", "jamming", "anchor"), "get_mcr_anchor"),
    (("pairing",), "get_pairings"),
    (("model", "certificate", "registry"), "list_models"),
]


def retrieve(question: str) -> list[dict]:
    q = question.lower()
    hits = [name for keys, name in _ROUTES if any(k in q for k in keys)]
    if not hits:
        hits = ["list_models", "get_certified_window"]
    # dict.fromkeys preserves route order while de-duplicating; cap at three so
    # the prompt stays small enough for the synthetic fallback to stay readable.
    return [{"tool": name, "result": call(name)}
            for name in list(dict.fromkeys(hits))[:3]]


async def answer(question: str) -> dict:
    retrieved = retrieve(question)
    context = "\n\n".join(
        f"### tool: {r['tool']}\n{r['result']}" for r in retrieved)
    c = await complete(SYSTEM, f"Question: {question}\n\nRetrieved:\n{context}")
    return {
        "question": question,
        "answer": c.text,
        "tools_used": [r["tool"] for r in retrieved],
        "sources": sorted({r["result"].get("source") for r in retrieved
                           if isinstance(r["result"], dict) and r["result"].get("source")}),
        "provider": c.provider,
        "model": c.model,
        "synthetic": c.synthetic,
    }
