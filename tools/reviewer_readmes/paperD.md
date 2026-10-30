# From Wire to Flight: artifact for review

This repository is the anonymised artifact for the paper *From Wire to Flight: A Conditional
Mission-Completion Guarantee for UAVs*. It contains the schema, the ingestion adapters, the
detector harness, the certificate engine, every result file, and the scripts that turn those
files into the figures and tables of the paper.

It is anonymised for double-blind review. Author names, affiliations and the address of the
public data mirror have been removed and will be restored on acceptance.

| | |
|---|---|
| Language | Python 3.10 or newer; C++17 for the third-party detector replay |
| Dependencies for the offline check | `numpy`, `scipy`, `jsonschema`; a TeX Live 2022+ installation to build the paper |
| Offline check | about a minute on a laptop CPU, no download, no GPU |
| Licence | MIT (`LICENSE`); third-party code and data remain under their own licences |

## 1. Quick check (offline, about a minute)

Every figure and table in the paper is generated from the CSV files in `results/`. The quickest
useful check is to regenerate them and confirm that nothing changes.

```bash
python3 -m pip install numpy scipy jsonschema
python3 experiments/compose_certified.py     # theta -> Delta -> delta -> certified floor
python3 experiments/provenance_ledger.py     # provenance distribution of the corpus
python3 experiments/make_paper_figures.py    # every figure and table block of the paper
git status --short results/                  # expected: no output
```

`make_paper_figures.py` rewrites `results/paper_figures/`, and the paper includes those blocks
directly (copied to `paper/figures/`). If the regenerated files differ from the committed ones,
`git status` will list them; an empty output means the paper and the data agree.

To build the paper:

```bash
cd paper && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

## 2. Where each claim comes from

| Claim in the paper | Script | Result file |
|---|---|---|
| Undetected delay saturates at the contact-window slack: no undetected per-hop residual above 4.84 s over 15,392 hops (Lemma 1) | `experiments/sweep_full.py` | `results/hop_ledger.csv`, `results/missed_windows.csv` |
| Threshold-aware attacker: never flagged (1,248 runs); realises a median 73% of H·min(θ, s) at θ = 0.25 s (0.36 s of 0.50 s) and 99% once saturated; never exceeds the bound | `experiments/tuned_attacker.py` | `results/tuned_attacker_{perseed,summary}.csv` |
| Detector operating curve with a knee and a floor, three topologies, two delay regimes, 8 seeds × 4 policies | `experiments/sweep_full.py` | `results/theta_operating_curve{,_perseed}.csv` |
| Delay-to-position rate γ = 1.625 m/s, the supremum over 674 post-onset samples; 6.1× spread between median and supremum | `experiments/gamma_campaign.py`, `experiments/gamma_stability.py` | `results/gamma_campaign_{samples,bins,model}.csv`, `results/gamma_stability.csv` |
| Per-flight calibration (benign, jamming, spoofing) | `experiments/whelan_delta_calibration.py` | `results/whelan_delta_calibration.csv` |
| Local Lipschitz constant L = 1.181 (global estimate 1.013) | `experiments/local_lipschitz.py` | `results/local_lipschitz.csv` |
| Certified floor against θ; window [0.178, 0.944] s at a 10 m corridor; tube 2.65 m at θ = 0.25 s | `experiments/compose_certified.py` | `results/certified_floor_vs_theta.csv`, `results/certified_operating_window.csv` |
| Rate that would push θ = 0.25 s out of the window: γ_req = 6.14 m/s at 10 m | `experiments/compose_certified.py` | `results/delta_mapping_sensitivity.csv` |
| Composed floor exceeds the autonomy-only floor at all 13 θ (Wilcoxon, Holm, 192 paired runs per point) | `experiments/compose_certified.py` | `results/composition_perseed.csv`, `results/stats_wilcoxon.csv` |
| Navigation anchor: MCR 0.938 at J/S = 20 dB over 93,600 flights | `experiments/ewbench_anchor.py` | `results/ewbench_mcr_anchor.csv`, `results/ewbench_margins.csv` |
| Sensitivity to the mission distribution | `experiments/mission_distribution.py` | `results/mission_distribution.csv` |
| Provenance of the corpus and of the pairings | `experiments/provenance_ledger.py` | `results/provenance_distribution.csv` |
| Ingest volumes per source; HCRL attack classes derived from the frames | `experiments/ingest_stats.py`, `experiments/hcrl_type_signatures.py` | `results/ingest_stats.csv`, `results/hcrl_type_signatures.csv` |
| Certificate constants (Gronwall radius, smoothing radius, MWU regret) | `certificates/engine.py` | printed, and asserted against the paper's values; the unit bridge for the RF classes also needs `torch` and reports itself unavailable without it |

The schema is `schema/uavsec_schema.json` (JSON Schema 2020-12), with its rationale in
`docs/SCHEMA.md`. Each adapter in `ingest/` writes events and windows that
`python3 ingest/validate.py <events.jsonl> <windows.jsonl>` checks against it.

## 3. Re-running the detector harness (under a minute)

The detector is the third-party DATAMUt replay in `third_party/datamut/`, included unmodified.
The threshold sweep needs the threshold to be configurable, which we apply as a patch to a copy:

```bash
mkdir -p build && cp third_party/datamut/* build/ && cd build
patch -p0 < ../patches/datamut_epsilon.patch
g++ -O2 -std=c++17 datamut_paper_exact_demo.cc -o datamut_demo && cd ..
python3 experiments/sweep_full.py            # 3 topologies x 2 regimes x 13 thresholds x 8 seeds
python3 experiments/tuned_attacker.py        # threshold-aware attacker on the same grid
python3 experiments/compose_certified.py
python3 experiments/make_paper_figures.py
```

The replay is deterministic per seed, so the regenerated `results/hop_ledger.csv` and the files
derived from it should match the committed ones.

## 4. Full reproduction from the raw corpus

The scripts that read raw data (`gamma_campaign.py`, `whelan_delta_calibration.py`,
`ewbench_anchor.py`, `hcrl_type_signatures.py`, `local_lipschitz.py`, `mission_distribution.py`
and the adapters in `ingest/`) need the six source datasets staged under `data/raw/`. The layout
each adapter expects is in `docs/data_staging_layout.md`, and `docs/KAGGLE_DATASET_DESCRIPTIONS.md`
describes the sources.

The aggregated mirror that `data/fetch_kaggle.py` downloads is withheld during review, because
its address identifies the authors. The six sources are public under their own licences and are
cited in the paper. Their outputs are committed in `results/`, so the offline check above does
not need them. `experiments/run_real_corpus.sh` runs the full pipeline and reports any stage
whose inputs are absent as skipped.

## 5. Scope and known limitations

These points are stated in the paper; they are repeated here so that the artifact is not read
as claiming more.

- **No `measured_same_platform` pairings are released.** The UAV Attack Dataset observes a
  network or RF event and the resulting flight on one airframe, but its release has no
  machine-readable attack intervals. It is used only to calibrate γ. Every released pairing is
  `physics_model` or `synthetic_alignment`, and each record carries its `pairing_basis` flag.
- **γ is calibrated on hover flights of one airframe.** Platform and flight mode were not
  varied.
- **The linear rate model holds for delays up to about 2 s.** For θ > 1 s (Δ > 2 s), the
  floors and window edges computed with the linear model are upper bounds, not certified values.
  The operating point θ = 0.25 s (Δ = 0.5 s) is inside the domain.
- **Two attackers are evaluated.** The campaign attacker draws per-hop delays from U[1, 7] s
  or U[1, 10] s whatever θ is, so at θ = 0.25 s every malicious delay is flagged and its
  undetected delay is zero. The threshold-aware attacker (`tuned_attacker.py`) adds the largest
  delay that keeps each hop below θ and realises 0.36 s (median) of the 0.50 s budget. The
  certificate uses the worst-case budget Δ(0.25) ≤ 0.50 s, not either measured value.
- **The PAC-Bayes bound is reported in symbolic form.** Its prior-to-posterior KL term is
  pending and is flagged rather than substituted.
- **Certificate constants come from a reference model** trained on a synthetic corpus; they are
  tagged `[fixture]` in the constants table.

## 6. Layout

```
certificates/      certificate engine (Gronwall tube, randomised smoothing, PAC-Bayes, MWU)
experiments/       every script that produces a result file or a paper block
ingest/            one adapter per source, schema validation, threshold sweep helper
schema/            the two-layer JSON schema
results/           committed result files; paper_figures/ holds the generated paper blocks
paper/             main.tex, refs.bib and figures/ (copies of results/paper_figures/)
third_party/       DATAMUt detector replay, unmodified
patches/           the threshold patch applied to a copy of DATAMUt
data/              fetch script for the corpus (address withheld during review)
docs/              schema rationale, data staging layout, dataset descriptions
```
