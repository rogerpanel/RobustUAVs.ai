# RobustUAVs.ai — an end-to-end UAV security benchmark and composed certificate

**One sentence:** UAV network intrusion detection bounds what reaches the
aircraft and certified robustness bounds a navigation model's response to a
perturbation, but nothing connects them — this repository is the corpus, the
schema, and the certificate engine that make the connection representable and
then provable, together with the code that produces every number in the
accompanying paper.

The research artifact for **"From Wire to Flight: Composing Network Intrusion
Detection with Certified UAV Mission Safety"** (`paper/paperD_v3.pdf`).

| | |
|---|---|
| **Language** | Python 3.11+, plus C++17 for the third-party detector replay |
| **Hard dependencies** | `jsonschema` for the schema gate; `numpy` + `scipy` for the statistics |
| **Offline reproduction** | ~10 min on a laptop CPU, no data download, no GPU |
| **Full reproduction** | + one Kaggle dataset (~3.2 GB) |
| **Datasets unified** | 6 (5 ingested on real releases, 1 pending — see below) |
| **Licence** | MIT (`LICENSE`). Third-party data stays under its own licence; none is redistributed here. |

---

## ⚠️ Read this first if you are submitting to a double-blind venue

**This repository is not anonymous.** It carries the author's name, GitHub
handle, commit identities, and a Kaggle DOI that resolves to a named account.
`paper/paperD_v3.tex` compiles with `\anontrue` and says *"the repository is
anonymised for review and will be de-anonymised on acceptance"* — that promise
is not yet kept by this URL.

Before the paper goes out, the reviewer-facing link must be an anonymised mirror
(e.g. `anonymous.4open.science`, or a scrubbed zip on Zenodo with an anonymous
record), **not** `github.com/rogerpanel/RobustUAVs.ai`.

`tools/anonymise.py` produces that mirror and, more importantly, **refuses to
pass if any identifying token survives**:

```bash
python3 tools/anonymise.py --out ../RobustUAVs-anon --init-git --zip
```

It rewrites names, affiliations, the GitHub owner, the Kaggle URL and DOI, the
deployment domain, and contact addresses; forces `\anontrue` in every paper and
drops the named builds; rewrites the LICENSE copyright line; drops `docs/PROJECT_CONTEXT.md`
and the supervisor correspondence; starts a fresh single-commit history rather
than rewriting the original (a rewrite leaks through reflogs, forks, and cached
GitHub views); and then re-scans its own output and exits non-zero on any
survivor. Two things it deliberately leaves alone: `third_party/`, because
DATAMUt's authorship is a citation rather than self-identification, and binary
files, which it lists for you to check by hand — **PDFs carry author metadata in
their Info dictionary, so rebuild them inside the anonymised tree rather than
copying them across.**

---

## What the artifact is for

The paper makes a chain of claims. Each link is a file you can run.

| Paper claim | Where it comes from | How to check it |
|---|---|---|
| A two-layer schema whose unit is the *cross-layer pairing* | `schema/uavsec_schema.json` (JSON Schema 2020-12), rationale in `docs/SCHEMA.md` | `python3 ingest/validate.py <events.jsonl> <windows.jsonl>` |
| Six sources ingest losslessly into one representation | `ingest/ingest_*.py`, one adapter per source | `experiments/run_real_corpus.sh`, then `results/ingest_stats.csv` |
| The detector's operating curve has a knee-and-floor shape | `ingest/sweep_theta.py`, `experiments/sweep_full.py` over the patched DATAMUt replay | `results/theta_operating_curve{,_perseed}.csv` |
| Residual budget saturates: Δ(θ) ≤ H·min(θ, s), ≤ 4.84 s over 15,392 hops | `experiments/sweep_full.py` writes the per-hop ledger | `results/hop_ledger.csv`, `results/missed_windows.csv` |
| δ mapping γ ≈ 1.2–1.4 m/s, an order of magnitude below the kinematic bound | `experiments/whelan_delta_calibration.py` on real PX4 flights | `results/whelan_delta_calibration.csv` |
| Local Lipschitz L = 1.181 (not the global 0.983) | `experiments/local_lipschitz.py` | `results/local_lipschitz.csv` |
| Certified floor vs θ; θ = 0.25 s inside the window under the measured mapping | `experiments/compose_certified.py` + `certificates/engine.py` | `results/certified_floor_vs_theta.csv`, `results/certified_operating_window.csv` |
| Composed dominates autonomy-only and network-only at every θ | same, with Wilcoxon + Holm | `results/composition_perseed.csv`, `results/stats_wilcoxon.csv` |
| Every figure and table is machine-generated, not transcribed | `experiments/make_paper_figures.py` | re-run it; `git diff results/` must be empty |

That last row is the one worth exercising. The paper `\input`s the generated
blocks directly, so if the generator's output differs from what is committed,
the paper and the data have drifted apart and you will see it in `git diff`.

---

## Quick start — 10 minutes, no data download

Everything below runs from a clean clone with no credentials and no network.

```bash
git clone https://github.com/rogerpanel/RobustUAVs.ai && cd RobustUAVs.ai
python3 -m pip install jsonschema numpy scipy   # no torch needed for this path

# 1. Certificate engine self-check. Prints the four certificate constants and
#    asserts them against the values the paper reports.
python3 certificates/engine.py

# 2. Re-derive every figure and table from the committed result CSVs.
python3 experiments/make_paper_figures.py
python3 experiments/provenance_ledger.py
git diff --stat results/                     # expect: no changes

# 3. Re-run the composition: theta -> Delta -> delta -> certified floor.
python3 experiments/compose_certified.py

# 4. Rebuild the paper (needs a TeX Live with IEEEtran + pgfplots).
cd paper && pdflatex paperD_v3 && bibtex paperD_v3 \
  && pdflatex paperD_v3 && pdflatex paperD_v3
```

Step 1 should print, among others, `Gronwall radius local=0.1535 (L=1.181)`,
`RS radius=0.44`, and a `caf_shift_v2` bridge line. Step 3 should print a
certified floor that falls to `0.00` at θ = 5 s, which is the saturation knee
Lemma 1 predicts.

### Rebuilding the detector from third-party source

`third_party/datamut/` holds Keiwan Soltani's DATAMUt replay **unmodified**. We
never edit it; the ε-configurability the sweep needs is applied as a patch.

```bash
mkdir -p build && cp third_party/datamut/* build/ && cd build
patch -p0 < ../patches/datamut_epsilon.patch
g++ -O2 -std=c++17 datamut_paper_exact_demo.cc -o datamut_demo && cd ..

python3 ingest/sweep_theta.py build/datamut_demo results/theta_operating_curve.csv
python3 experiments/sweep_full.py            # full campaign: 3 topologies x 2 modes x 8 seeds
```

**A caution that cost us a result.** The demo *appends* to its summary CSV. An
earlier sweep harness therefore averaged every previous operating point into the
current one, and the tell was recall *rising* with the threshold, which a
threshold detector cannot do. `experiments/sweep_full.py` uses a fresh working
directory per point. If you write your own sweep, do the same.

---

## Full reproduction — with the corpus

The five ingestible datasets are aggregated in one Kaggle release. The two large
ones (UAV Attack Dataset ~700 MB, UAV-CAS ~2.5 GB) are **not** committed here.

```bash
python3 -m pip install -r requirements.txt
python3 data/fetch_kaggle.py          # needs Kaggle credentials; symlinks into data/raw/
experiments/run_real_corpus.sh        # fetch -> stage -> ingest -> validate -> calibrate -> figures
```

- Dataset: <https://www.kaggle.com/datasets/rogernickanaedevha/uavs-network-and-navigation-end-to-end-security-data> (DOI 10.34740/kaggle/dsv/18346203)
- Expected staging layout: `docs/data_staging_layout.md`
- Per-dataset provenance notes: `docs/KAGGLE_DATASET_DESCRIPTIONS.md`

`run_real_corpus.sh` is idempotent and **skips a stage whose inputs are absent,
saying so** rather than substituting anything. A missing dataset degrades the
run; it never silently fabricates it.

---

## What is measured, what is modelled, what is pending

This is the part a reviewer should read before anything else. The schema carries
a mandatory per-record `pairing_basis` flag precisely so this table can exist,
and `experiments/provenance_ledger.py` regenerates it from the adapter outputs
rather than from prose.

### Corpus acquisition (`results/provenance_distribution.csv`)

| Source | Acquisition | Layer | Events | Status |
|---|---|---|---|---|
| HCRL UAVCAN | real testbed | network · intra-bus | 200,000 | ingested |
| UAVIDS-2025 | simulation (NS-3) | network · mesh | 122,171 | ingested |
| UAV-EW-Bench-2026 | simulation (physics-informed) | autonomy | 93,600 | ingested; the navigation anchor |
| DATAMUt replay | simulation (event) | network · mesh | 15,392 | ingested; the sweepable detector |
| UAV Attack Dataset (Whelan) | **real testbed** | **both** | 610 | ingested; **the only source that observes a network/RF event and the flight it degrades on one airframe** |
| UAV-CAS | simulation (digital twin) | network · mesh | 0 | **adapter ready, release file not reachable** — `PENDING_ON_DATA.md` #1 |

200,610 of 431,773 ingested events (46.5%) were captured on real hardware.

### The stronger question, answered against ourselves

Acquisition provenance is the *weaker* question. The stronger one is how many
**pairings** rest on measurement, and there the honest answer is worse:

> **The number of released `measured_same_platform` pairings is currently zero.**

The Whelan release does not carry machine-readable attack on/off timestamps, so
the adapter cannot emit `AttackWindow` boundaries for it and **refuses to infer
them**. Its three flights still supply the delay-to-position rate γ that the
certificate consumes (self-referenced to each flight's own pre-attack median),
so the headline result does not depend on closing this gap — but a reviewer who
filters the artifact to `measured_same_platform` will correctly retrieve
nothing. §X-H of the paper states this; it is not buried.

### Data-gated items, in full

`PENDING_ON_DATA.md` is the complete list. Nothing else in the project is
blocked on external access. In brief:

1. **UAV-CAS stat CSV** — the sixth real ingest. Adapter is fixture-verified.
2. **Whelan attack intervals** — needed for windowed (not self-referenced) numbers.
3. **TEXBAT IQ** — to re-calibrate the `caf_shift_v2` unit bridge on real signals.
4. **Cruise-regime γ** — three hover/loiter flights are a calibration sample, not a distribution. §X-D argues from the error budget that cruise should not cross the threshold; that is reasoning, not measurement, and the paper says so.
5. **PAC-Bayes numeric KL** — the bound is wired to the model's measured empirical risk and reported as a *form*, flagged pending rather than filled with a plausible number.

---

## Repository map

```
schema/          uavsec_schema.json — Event, AttackWindow, CrossLayerPairing
ingest/          one adapter per source + validate.py (the schema gate)
experiments/     the campaigns: sweep, calibration, composition, statistics, figures
certificates/    engine.py (the four Ch.6 certificates) + unit_bridge.py
models/          uav_defense/ — the reference Phase-A stack (CT-TGNN, MambaShield,
                 UC-HGP, FedGTD) and baselines; PORT_STATUS.md explains provenance
results/         every committed CSV the paper reads, + paper_figures/ (generated)
paper/           paperD_v3.tex (anonymised) · paperD_v3_named.tex · refs.bib
platform/        the live web application: FastAPI backend + Expo/React Native client
third_party/     DATAMUt, unmodified — never edit; extend via patches/
patches/         datamut_epsilon.patch (makes the detector's operating point sweepable)
data/            fetch_kaggle.py; data/raw/ and data/staging/ are gitignored
docs/            schema rationale, certified-regime analysis, deployment, architecture
```

Documents worth opening, in order of usefulness to a reviewer:

- `docs/certified_regime_analysis.md` — the analysis that decided the paper's
  headline framing, including a refuted hypothesis we kept in the record.
- `docs/SCHEMA.md` — why the schema looks the way it does.
- `docs/DATAMUT_CODE_ANALYSIS.md` — what the third-party detector actually does,
  as opposed to what its paper describes.
- `results/paper_figures/README.md` — the generated provenance ledger, per figure.
- `PENDING_ON_DATA.md` — everything blocked on external access.
- `docs/paperD_v3_response_to_supervisor.md` — the 24 review comments and how
  each was addressed, including two numerical inconsistencies we found and fixed
  in our own draft.

---

## Conventions this repository holds itself to

These are enforced by code, not by intent, and they are the reason the tables
above can be trusted.

- **Ingestion is lossless.** Every unmapped source column is preserved in a
  `native` block. Adapters that cannot map a field keep it rather than drop it.
- **Every adapter output is validated before commit.** `ingest/validate.py` is
  the gate; nothing enters `results/` unvalidated.
- **Clocks are relative per scenario.** The sources share no global clock;
  alignment happens at the window level, under a stated affine map with a stated
  error budget (`e_align ≤ 0.53 s`), never by resampling.
- **Missing artifacts are flagged, never substituted.** The PAC-Bayes KL, the
  UAV-CAS ingest, and the Whelan windows are all reported as absent. A clearly
  marked TODO beats a plausible-looking wrong number.
- **`third_party/` is never edited.** Modifications live in `patches/`.
- **The repository is host-agnostic.** No path is tied to one machine.
- **A 503 from the API means "not produced in this deployment", not "failed".**
  The client renders the two differently, because a reviewer must not read a
  pending measurement as a bug.

---

## The live platform

`platform/` is a working web application over the same results, deployed at
<https://robustuavs.ai>. It is a convenience for exploring the artifact, not a
substitute for it: every number it serves traces to a file under `results/` or
to a live call into `certificates/engine.py`.

```bash
cd platform/backend
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000      # interactive docs at /docs
python3 tests_smoke.py

cd ../mobile && npm install && npx expo start --web
```

It offers a live fleet simulation (up to 12 aircraft, ten attack classes,
emergent mesh partitioning), a GNSS spoof process monitor, the evaluation suite
(robustness, ablations, ROC, statistics, calibration, federated), an
upload-and-analyse path for a reviewer's own CSVs, and an SOC copilot. Design
authority is `docs/platform_architecture.md`; deployment is
`docs/deployment_runbook.md` and `deploy/`.

One honest note about the simulation: `docs/simulation_architecture.md` records
which fleet quantities are *measured* (link residuals, sampled from the six
datasets) and which are *modelled* (damage rates, RTL thresholds), and lists the
four steps that would move the modelled ones to measured. The UI badges every
page `measured` or `illustrative` for the same reason.

---

## Branches

- **`main`** — the reviewable state. What you are reading.
- **`dev/*`** — working branches, fast-forwarded into `main` when a milestone
  lands. No divergence: `main` is always an ancestor-or-equal of the active
  working branch.

## Where this is going

`docs/research_roadmap_2027.md` sets out three follow-on directions with the
machinery each would reuse, the measurements each needs, and where each lands in
the platform: certified PNT substitution (alternative navigation sources as a
sensor-selection rule), post-quantum authentication treated as self-inflicted
staleness against the same budget an attacker spends, and the certificate
recast as a SORA/ED-324 compliance artifact.

---

## Citation

```bibtex
@misc{robustuavs2026,
  title  = {{RobustUAVs.ai}: An End-to-End UAV Security Benchmark and
            Evaluation Harness},
  year   = {2026},
  howpublished = {\url{https://github.com/rogerpanel/RobustUAVs.ai}},
  note   = {Dataset DOI 10.34740/kaggle/dsv/18346203}
}
```

Third-party datasets and the DATAMUt detector must be cited to their own
authors; `paper/refs.bib` has the records. We redistribute none of the raw
third-party data — the adapters fetch each source from its origin under its own
licence.
