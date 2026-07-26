# Model & certificate port status — RESOLVED

Source of truth: dissertation **Chapter 6** (`chapter6_v11_Ru.tex`), the
**robustidps.ai platform documentation** (`Documentation_v5.tex`), and the
**`uav_defense` reference package** (github.com/rogerpanel/cv, branch
`claude/latex-report-datasets-DiJWE`), all now in hand. The earlier open items
are closed.

## Method mapping (Ch.6 Table `tab:uav_mapping` — authoritative)

| M | Name | UAV defense mechanism | Certificate |
|---|------|----------------------|-------------|
| M1 | CT-TGNN | multiscale swarm dynamics on A(t); GNSS constellation graph | **Lipschitz–Grönwall (Thm 6.1)** |
| M1b | SDE-TGNN | EW/wind/sensor stochastics | Fokker–Planck |
| M2 | FedLLM-API | dronehub federation @30% Byzantine | (ε,δ)-DP (Thm 6.2) |
| M3 | TripleE | mission/waypoint/component graphs | EWC |
| M4 | MambaShield | long telemetry streams, onboard SoC | **PAC-Bayes (Thm 6.3)** |
| M5 | S-Transformer | Bayesian visual attention | ELBO |
| M6 | UC-HGP | go/no-go gate under OOD sensor modes | **ECE gate (0.078)** |
| M7 | FedGTD | Stackelberg game vs adaptive jammer | **MWU regret (Thm 6.4)** |

**Phase-A headline stack = M1 + M4 + M6 + M7.**

## The three previously-open items, resolved

1. **What is M7?** → **FedGTD**: the Stackelberg/multiplicative-weights defender
   that mixes {aggressive maneuver, conservative loiter, return-to-home,
   INS-only} against an adaptive jammer, with sublinear regret R(T) ≤ √(T·ln|S|),
   |S|=4 (Thm 6.4). In the old demo repo its architecture was the file
   mislabelled `federated_graph.py`; the demo README's M-numbers were stale.
2. **Where is the navigation-defense code?** → the **`uav_defense` package**, now
   at `models/uav_defense/`. Real CT-TGNN on the GNSS graph
   (`models/ct_tgnn_gnss.py`), MambaShield, CAF-CNN + Seq2Seq baselines, attack
   suite, `train.py` / `evaluate.py`, and `scripts/run_phase_a.sh` (synthetic
   TEXBAT smoke test, no external data; ~5 min CPU / ~1 min GPU → `metrics.json`).
3. **Where are the certificate constants?** → **Ch.6 §6.6 + `defenses/`**, wired
   into `certificates/engine.py` and self-checked. Dissertation Phase-A values:
   L_g=1.01, T=1, ε_out=0.5 ⇒ **Grönwall radius 0.18**; RS σ=0.25 ⇒ **radius
   0.44** (Cohen, α=1e-3, n=200); MWU |S|=4. certificates/engine.py reproduces
   the 0.18 radius from the real `gronwall_radius` code.

## Remaining real work (not blockers — genuine research steps)

- **Unit bridge for δ (W3).** The certificate radius lives in normalised
  CAF-feature ℓ2 space; the network side produces δ in physical units (metres,
  seconds). The sensor→feature scaling (from `uav_defense/datasets/texbat.py`
  normalisation) must be ported so `pos_error_m` / `state_staleness_s` convert to
  feature-space ℓ2. Until then `engine.certify()` accepts `kind='sensor_l2'` and
  refuses physical-unit deltas rather than guessing.
- **Two floors, never conflate.** Ch.6 certified text says MCR ≥ **0.80** at
  J/S=20 dB (certified); EW-Bench + the dashboard show the DO-326A **0.90**
  operational floor holding to ~20–25 dB (empirical). Different quantities.
  Reconcile the wording in the paper; keep both, labelled.
- **Trained weights.** `run_phase_a.sh` trains on a synthetic TEXBAT-like corpus
  for pipeline validation. Real TEXBAT needs UT-RNL registration; AU-AIR is open.
  For SaTML the synthetic Phase-A pipeline is a legitimate, transparent path
  (state it as such).
- **PAC-Bayes numeric bound.** The (M4) constant lives in the methods chapter,
  not Ch.6; port when reproducing that certificate numerically.
- **Live vs paper constants.** Dashboard pills (L_g 0.083, Grönwall 0.460, RS
  0.111, PAC-Bayes 0.041 in the screenshot) are per-visit recomputes on a
  16-sample synthetic batch — demo variability, NOT the dissertation constants.
  Use the Ch.6 constants for the paper.
