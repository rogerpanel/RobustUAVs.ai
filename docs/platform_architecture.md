# RobustUAVs.ai platform architecture

How the RobustUAVs.ai web platform is organised, derived by tracing the
structure of **RobustIDPS.ai v5** (`Documentation_v5.tex`) and re-targeting it
from network intrusion detection to end-to-end UAV security.

This document is the design authority for `platform/`. It exists because the two
systems are siblings, not clones: the *shape* of RobustIDPS transfers almost
entirely, while the *contents* — the model registry, the page groups, the
copilot's tool surface — do not.

---

## 1. What was extracted from RobustIDPS.ai

### 1.1 The two-plane split

RobustIDPS v4 separates a **control plane** (Python/FastAPI, RBAC, multi-tenant,
LLM router, persistence) from a **data plane** (Rust agents + eBPF/XDP making
microsecond packet decisions), bridged by gRPC over three primitives:

| Primitive | Direction | Purpose |
|---|---|---|
| `StreamFlows` | data → control | server-streaming finalised flow records |
| `UpdateConfig` | control → data | push block-lists to classifier and XDP trie |
| `ApplyModelUpdate` | control → data | chunked INT8 ONNX push, SHA-256 checked, hot-swap under `RwLock` |

**What transfers.** The control-plane half transfers wholesale: FastAPI,
Postgres + Redis + in-memory result cache, RBAC, WebSocket, an LLM router, and a
model registry exposed uniformly to the frontend.

**What does not.** RobustUAVs has no line-rate packet path to defend. There is
no NIC to attach XDP to and no per-flow drop decision to make in kernel space.
The data plane's *role* — a fast, separately-deployed executor that the control
plane feeds artefacts to and reads results from — maps instead onto a **job
plane**: long-running ingest, sweeps, and certificate computations that must not
block an HTTP worker. The three bridge primitives survive with their semantics
intact and their transport changed from gRPC to a task queue:

| RobustIDPS | RobustUAVs equivalent |
|---|---|
| `StreamFlows` (flow records) | `stream_events` — WebSocket stream of ingest/sweep progress and emitted schema records |
| `UpdateConfig` (block-list push) | `update_config` — push a detector operating point θ and δ-mapping selection to a running job |
| `ApplyModelUpdate` (ONNX hot-swap) | `apply_model_update` — publish a trained checkpoint + its certificate constants to the serving registry |

### 1.2 The registry pattern

RobustIDPS exposes **17 registered detectors** through one uniform envelope:
`model_id`, display name, a `category` the frontend groups by, and per-model
flags (`ablation`, `new`). The frontend never special-cases a model; it renders
whatever the registry declares. That indirection is the single most valuable
thing to copy, because it is why adding MambaGuard/SODE-Guard/SSL-Graph-Full in
v4 required no frontend rewrite — they slotted into existing sidebar groups.

RobustUAVs adopts the same envelope with its own categories
(`navigation`, `network`, `certificate`, `baseline`, `composition`) and its own
rows — see §2.2.

### 1.3 The SOC Copilot

Three properties are worth reproducing exactly:

1. **A symmetric tool registry.** Every tool appears in both the `TOOLS`
   registry and the dispatcher, and CI fails the build on asymmetry
   (`aegis-gate.yml`). v5 carries 61 tools this way.
2. **A result cache over page results.** The copilot answers from
   `get_page_result` rather than recomputing, with a per-page summariser that
   surfaces that page's *certificate* fields (smoothing radius, regret bound,
   coverage bound, …). This is why it can answer "what is this model's
   certificate state?" without a model round-trip.
3. **Four LLM providers with a deterministic fallback.** Anthropic, OpenAI,
   Google Gemini, and DeepSeek, plus a synthetic responder so air-gapped
   deployments still function and CI is reproducible.

All three transfer unchanged. The tool *contents* change: RobustUAVs' copilot
answers about θ-sweeps, certified windows, pairing provenance, and δ
calibration.

### 1.4 What is deliberately not carried over

- **Rust/eBPF data plane.** No line-rate path exists here. Revisit only if a
  live on-board agent is ever built.
- **Agent Studio / AegisAgents Kit.** RobustIDPS v5's agent-building product is
  a separate business surface with no analogue in a research artifact.
- **PQC-IDS, MITRE ATT&CK/ATLAS mappers, Suricata comparison.** Network-IDS
  domain content.
- **51 pages / 10 sidebar groups.** RobustUAVs starts at 6 groups (§3.1); the
  registry pattern makes growth cheap, and inheriting empty pages is not a
  feature.

---

## 2. RobustUAVs.ai architecture

### 2.1 Planes

```
┌──────────────────────────────────────────────────────────────┐
│ Clients                                                      │
│   React Native (Expo) mobile app  ·  static web artifact     │
└───────────────┬──────────────────────────────────────────────┘
                │ REST + WebSocket (JSON)
┌───────────────▼──────────────────────────────────────────────┐
│ Control plane — FastAPI                                      │
│   registry · certificates · datasets · experiments · copilot │
│   LLM router (4 providers + synthetic)                       │
└───────┬───────────────────────────────┬──────────────────────┘
        │ enqueue / stream               │ read
┌───────▼──────────────┐        ┌────────▼─────────────────────┐
│ Job plane            │        │ Persistence                  │
│   ingest adapters    │        │   Postgres · Redis · result  │
│   θ-sweep campaigns  │        │   cache · results/ on disk   │
│   certificate engine │        └──────────────────────────────┘
└──────────────────────┘
```

The control plane is **stateless with respect to research results**: every
number it serves traces to a committed file under `results/` or to a live job's
output, never to a hand-entered constant. This is the platform expression of the
provenance discipline the papers rely on.

### 2.2 Model registry

Rows come from `models/uav_defense/` and `certificates/engine.py`. Categories
are what the frontend groups by.

| `model_id` | Display name | Category | Source |
|---|---|---|---|
| `m1_ct_tgnn` | CT-TGNN (GNSS constellation graph) | navigation | `models/ct_tgnn_gnss.py` |
| `m4_mambashield` | MambaShield | navigation | `models/mambashield.py` |
| `m6_uc_hgp` | UC-HGP (uncertainty-calibrated) | navigation | Phase-A stack |
| `m7_fedgtd` | FedGTD (Stackelberg/MWU defender) | navigation | Phase-A stack |
| `caf_cnn` | CAF-CNN | baseline | `models/baselines.py` |
| `seq2seq_tr` | Seq2Seq-Transformer | baseline | `models/baselines.py` |
| `datamut` | DATAMUt forwarding detector | network | `third_party/datamut` |
| `cert_gronwall` | Lipschitz–Grönwall tube | certificate | `certificates/engine.py` |
| `cert_smoothing` | Randomized smoothing (Cohen) | certificate | `certificates/engine.py` |
| `cert_staleness` | Staleness–Grönwall (state space) | certificate | `certificates/engine.py` |
| `cert_mwu` | MWU regret | certificate | `certificates/engine.py` |
| `cert_pacbayes` | PAC-Bayes (McAllester) | certificate | `certificates/engine.py` |
| `composed` | Composed θ→δ→MCR guarantee | composition | `experiments/compose_certified.py` |

Every row carries a **provenance tag** (`real_corpus`, `simulation`,
`fixture`, `pending`) and, where applicable, a `certificate_status`
(`ok`, `unit_bridge_missing`, `kl_pending`). The frontend renders the tag as a
chip; a row that cannot honestly report a number reports its status instead.
This is the platform-level enforcement of "a clearly-marked TODO beats a
plausible-looking wrong number".

### 2.3 Copilot tool surface

Mirrors the RobustIDPS pattern — symmetric registry, dispatcher, result cache —
with UAV tools:

`list_models`, `get_model`, `get_certificate`, `certify_staleness`,
`get_operating_curve`, `get_certified_window`, `get_pairing`,
`get_provenance_distribution`, `list_datasets`, `get_ingest_stats`,
`run_theta_sweep`, `get_job`, `get_paper_figure`, `explain_finding`.

Symmetry is enforced by a test, not by convention (`test_copilot_symmetry`).

### 2.4 LLM router

Four providers in a declared fallback order, plus a deterministic synthetic
responder used when no key is configured — which keeps CI reproducible and lets
the artifact run air-gapped:

```
ANTHROPIC_API_KEY → OPENAI_API_KEY → GEMINI_API_KEY → DEEPSEEK_API_KEY → synthetic
```

The active provider is surfaced to the client as a chip, exactly as RobustIDPS
surfaces its provider chip, so a viewer always knows whether an answer came from
a model or from the fallback.

---

## 3. Frontend

### 3.1 Navigation groups

Six groups, mirroring the paper's structure rather than RobustIDPS's:

| Group | Screens |
|---|---|
| **Overview** | Dashboard, Provenance ledger |
| **Corpus** | Datasets, Ingest stats, Schema browser |
| **Network layer** | Detector operating curve, θ-sweep runner, Residual budget |
| **Autonomy layer** | Navigation anchor (MCR vs J/S), δ calibration, Models |
| **Composition** | Certified floor vs θ, Certified window, Baselines & dominance |
| **Copilot** | Chat, Tool activity |

### 3.2 Why React Native

The user-facing requirement is a live demonstration surface reachable from a
phone during a talk or a review. Expo gives one codebase for iOS, Android, and
web; the web build deploys to the same Caddy origin as the static artifact, so
`robustuavs.ai` serves the interactive
client, with no second host to operate.

---

## 4. Build order

1. **Backend skeleton + registry + certificates** — read-only endpoints over
   committed `results/`. Demonstrable immediately, no job plane needed.
2. **Copilot + LLM router** — symmetric registry, synthetic fallback first, real
   providers behind env keys.
3. **Job plane** — θ-sweeps and ingest as background jobs with a WebSocket
   progress stream.
4. **React Native client** — Overview and Composition groups first, since those
   carry the headline figures.
5. **Auth + multi-tenant** — deferred; the artifact is public and read-mostly.

Steps 1–2 are implemented in `platform/backend/`; step 4 is scaffolded in
`platform/mobile/`.
