# What transfers from robustidps.ai, and what does not

`robustidps.ai` carries 13 navigation groups. Most are AI/LLM-security surfaces
with no UAV analogue, and copying them would produce pages with nothing behind
them. This records the decision for each, so the question is settled rather than
re-litigated every time the sidebar is compared.

| robustidps.ai group | Decision | Where it landed here |
|---|---|---|
| UAV / Aerial Defense | **transferred, all 8 pages** | `src/screens/uav/` — Chapter 6's operator surface, the reason this project exists |
| AI Data & Models | **re-targeted** | Evaluation group: Robustness, Ablations, ROC, Statistics, Calibration |
| AI Novel Methods | **partially transferred** | Federated Learning (M7 = FedGTD); the rest are IDS models with no UAV counterpart |
| Agent Studio (Build) | **re-targeted** | Agent Studio — builds *runs* rather than agents, which is the analogous act for a benchmark |
| AI Command Center | folded in | the right rail's deployment strip and the Milestones landing |
| SOC Intelligence | **dropped** | threat hunting, incident reports, CVE mapping: a SOC surface, not a benchmark |
| LLM Attack Surfaces | **dropped** | prompt injection, jailbreak taxonomy, RAG poisoning — a different threat model entirely |
| Agent Security (Defend) | **dropped** | MCP security, multi-agent chain: no UAV analogue |
| MLSecOps Standards | deferred | MITRE ATLAS mapping would be real work with real value; not yet started |
| AI Security & Gov | **dropped** | PQ cryptography, zero-trust, supply chain |
| Industry & Research | deferred | the SORA/DO-326A grounding lives on the pages that use it instead |
| System | folded in | `/api/health`, surfaced in the right rail |

## Why the drops

A page that renders without data behind it is worse than no page: it implies a
capability the artifact does not have, and it is exactly what a reviewer opens
first. Every transferred page above is wired to a committed result or says on
its face that it is illustrative.

## The two pages that say "no"

**Calibration (ECE)** returns `available: false`. Expected Calibration Error
needs per-hop detector *scores*; the DATAMUt replay's `PaperExactDetector` emits
a boolean flag, and every reliability diagram derivable from a boolean is
degenerate. The page gives the method, the missing input, and what would unblock
it. A surrogate fitted to the residual-delay distribution would be calibrated
against itself.

**Federated Learning** carries the model definition and the MWU constant
(|S| = 4) but no trained weights, so federated rounds are not runnable. Stated
rather than simulated.

## Ablations: one is not ablatable

Per-certificate removal has no coherent meaning. The four certificates bound
four different objects — a trajectory, a classifier, a generalisation gap, a
regret — and do not compose additively, so "remove one, re-measure a scalar"
answers nothing. The ablation that does make sense is the interface mapping, and
that one is implemented.

## Going forward

The eternal-vertex-cover work has no page yet, deliberately: the schema does not
yet express a guard-placement problem, and inventing a screen before the model
exists would repeat the mistake this document is about. When it does, it belongs
in a new group beside Evaluation, and the pattern to copy is
`platform/backend/app/evaluation.py` — a module of pure read functions over
committed results, one endpoint each, with `ResultUnavailable` for anything not
yet produced.
