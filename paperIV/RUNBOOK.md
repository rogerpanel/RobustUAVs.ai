# Paper IV — Runbook

**Paper:** *When the Attacker Is Indistinguishable from the Weather: A Cross-Layer Benchmark and a Unified Perturbation Budget for Certified UAV Autonomy* (target: USENIX Security)
**Repository:** `rogerpanel/RobustUAVs.ai`, branch `claude/whelan-uavcas-ingest-u00isn` (the branch Papers I-III are developed on; `paperIV/` was started on `claude/paperIV-crosslayer` and merged here).
**Folder:** `paperIV/` (`experiments/`, `results/`, `manuscript/`)

This runbook tells a coding-agent session how to scale up, harden and extend the experiments behind Paper IV. The drafting sandbox ran a compact CPU pilot (2 cores, 7 GB RAM, no GPU, no flight simulator), and every number in the current manuscript comes from that pilot.

Every experiment writes a CSV to `paperIV/results/`. `make_numbers.py` turns those CSVs into LaTeX macros in `manuscript/numbers.tex`, and `export_figdata.py` writes `manuscript/figdata/*.dat`. **Never type a number into `main.tex`.** Re-run the pipeline instead.

---

## 0. What is already done (do not redo)

| Script | Output | What it establishes | Runtime (2 cores) |
|---|---|---|---|
| `sim.py` | — | Vectorised lateral closed loop: 3-state KF, Dryden lateral turbulence (MIL-F-8785C), IMU bias faults, LoE, GNSS Gauss–Markov drift, outages, jamming noise, re-anchoring (C2′, final interval closed); detectors D1 SIG, D2 CHI2, D3 SAV, D4 INV and the anchor gate; `noise=False` attack-only counterfactual | 0.5 s / 400 missions |
| `depbounds.py` | — | Union (standard) bound, Rearrangement Algorithm (reported as min(RA, union)), independence and comonotone tails | seconds |
| `run_pilot.py` E1 | `e1_*.csv`, `e1_calibration.json` | Thresholds at FPR ∈ {1, 2, 5, 10, 20} %; FPR by wind class and by benign source; ROC against naive offsets | 20 s |
| `run_pilot.py` E2 / E2x | `e2_attackers.csv`, `e2x_cross.csv` | 35 CEM attackers (stack × family × FPR); **every attacker cross-evaluated against every stack**, so optimiser failures do not masquerade as detector strength | ≈ 8 min |
| `e2y_no_anchor_gate.py` | `e2y_no_anchor_gate.csv` | Same cross-evaluation with the anchor fused but its gate removed: what the detectors alone discriminate | ≈ 1 min |
| `run_pilot.py` E2b / E2c | `e2b_anchor_sweep.csv`, `e2c_terminal_window.csv` | Stealth budget against the full stack versus T_a ∈ {5, 10, 20} s, pooled over 30 attackers on common missions; E2c leaves the final interval unchecked | ≈ 9 min |
| `run_pilot.py` E3 | `e3_marginal_summary.csv`, `e3_gap.csv`, `e3_marginals.npz` | Marginals (upper/lower/matched wind); union vs RA vs independence vs per-source sum vs joint (dependence, envelope and temporal gaps); per-mission check of condition C5 | 2 min |
| `run_pilot.py` E4 | `e4_delta_adv.csv`, `e4_soundness.csv`, `e4_saturation_control.csv` | Pooled stealth budget; 15 held-out attackers × 3 wind conditions; Theorem 1 tested on its own event {fail ∧ undetected}, with Holm correction; saturation control | ≈ 7 min |
| `run_pilot.py` E5 | `e5_negative_controls.csv` | Power checks: C2′ broken (attacker re-optimised without anchor), C4 broken (45–60 kt) | ≈ 1.5 min |

Regenerate everything:

```bash
cd paperIV/experiments
python3 run_pilot.py            # full pilot (≈ 27 min on 2 cores); --quick for a 9-min smoke run
python3 e2y_no_anchor_gate.py    # gate-removed ablation (needs E1/E2 outputs)
python3 make_numbers.py         # numbers.tex + figdata/*.dat
cd ../manuscript && latexmk -pdf main.tex
```

**Weak points, in the order a USENIX reviewer would raise them:**

1. **Reduced-order dynamics.** The pilot is a 1-D lateral channel with a linear KF, not PX4 EKF2 on a 6-DoF airframe. R2 and R3 close this, and **R3 is load-bearing**.
2. **δ_adv is an empirical supremum over optimised attackers, not a proof.** It is pooled and monotone, and an independently seeded attacker exceeded it in 1 of 45 cells (1.17×). R1 (stronger optimisers) and R8 (analytic stealthy-reachable-set bound) address it. **R1 is load-bearing.**
6. **The bound is conservative.** No undetected failure was observed wherever the bound is informative, so soundness power comes from the negative controls. Closing the temporal gap (bounding the joint supremum per window) is the route to a bound tight enough to stress directly.
3. **The network term δ_net is not simulated.** It enters as the parent's certified tube. R4 injects real relay staleness into SITL.
4. **Benign marginals are simulated.** R5 replaces them with measured data (Whelan γ campaign, RflyMAD and ALFA fault flights) under `measured`/`physics_model` provenance.
5. **The detector set is compact.** R7 adds an ML IDS, DeLorean/PID-Piper-style recovery, active exposure and a fault/attack dual detector.

---

## 1. Ground rules for every experiment

1. **Placement.** New code goes in `paperIV/experiments/` and outputs in `paperIV/results/`. Every new CSV carries a `provenance` column: `measured | physics_model | synthetic_alignment | sim | sitl | hardware`. This matches the parent's `pairing_basis` enum in `schema/uavsec_schema.json`; `sim`/`sitl`/`hardware` qualify `physics_model`.
2. **Seed discipline.** Seeds are split by role and never reused across roles: 1xxx calibration, 2xxx attacker optimisation, 3xxx held-out attacker, 4xxx held-out evaluation, 5xxx negative controls. A new experiment takes a fresh block (6xxx, 7xxx, …) and records it in `results/run_meta.json`.
3. **Soundness is the claim.**
   - A certified floor below the measured MCR is *not* a result to tune away.
   - A Holm-significant violation (`violation=1` in `e4_soundness.csv`) is a bug in the instantiation. Stop, find which condition (C1, C2′, C3, p-box envelope, δ_adv calibration) failed, and report it.
   - Never widen a constant after looking at held-out data.
4. **Statistics.**
   - Clopper–Pearson 95% intervals on every MCR.
   - Holm–Bonferroni across every operating point that is tested together.
   - IQM with stratified-bootstrap CIs across seeds (`rliable`) when reporting optimiser outcomes.
   - When zero violations are observed, report the exact one-sided upper bound and the number of missions.
5. **Dual-use.**
   - No transmit-capable SDR code is committed, and every spoofing path is a simulator interface.
   - The evasion harness lives under `paperIV/experiments/` and is released only with the mitigations from R10.
6. **Commits.** Use `paperIV: R<n> <short result>` and put a CSV diff summary in the body.

---

## 2. Environment

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install numpy scipy pandas cma optuna pyulog rliable
# R2: pip install gym-pybullet-drones   (or the in-repo 6-DoF model)
# R3: PX4-Autopilot v1.14+ with Gazebo (gz-sim); see R3 for the Docker image
```

The pilot peaks below 1.5 GB. SITL (R3) needs about 2 GB per headless instance, so run `nproc/2` instances in parallel.


## Status of the follow-up runs (2026-10-15)

| Item | Script → output | Result | Departure from the plan |
|---|---|---|---|
| R1 | `r1_attackers.py` → `r1_attackers*.csv`, `r1_delta_adv.csv`, `r1_heldout.csv`, `r1_e4_soundness.csv` | 126 attackers (CMA-ES, TPE, tail-objective TPE; K = 128, CRN; mixed family). δ_adv 4.371 → 5.463 m (1.25×, at the acceptance limit), attained only by the tail objective. Scaled E4 (n = 5,000, 5 held-out seeds): **5 of 1,620 Holm-significant violations**; held-out attackers exceeded δ_adv in 12/270 cells (max 7.04 m, mixed family) | Step 3 (white-box JAX gradient attacker) **not run** |
| diagnosis | `r1_diagnose.py` → `r1_violation_diagnosis.csv` | All violations come from 3 benign-tail missions (benign-only 19–35 m, attack ≤ 2.3 m), all saturating. Failed conditions: C3 (empirical marginal has finite support, p̄ = 0) and C1 (saturation never checked at run time) | — |
| R8 | `r8_analytic_bound.py` → `r8_analytic_bound.csv` | LP over attack offsets with the convex, silence-implied constraints. T_a = 5 s: anchor gate alone unbounded; + D1 295–320 m; + saturation alarm 31.8–31.9 m (5.8× δ_adv) | LP over D1/anchor/D_sat instead of the ellipsoidal SDP: D2–D4 alarm on runs of exceedances and do not give convex constraints. Criterion "< 2× empirical" **not met**, so the certificate keeps the empirical term |
| R5 | `r5_measured_gnss.py` → `r5_gnss_envelope.csv`, `r5_floor_sensitivity.csv` | Measured gps_jamming envelope (496 samples, ≤ 7.0 m). Floor at m = 10 m, 5 % FPR: 0.689 (sim) → 0.343 (measured) → 0.315 (45 s episodes); CP-band 0.54 → 0.21 → 0.19 | Only the GNSS marginal; RflyMAD/ALFA fault marginals **not run** (adapters not written) |
| revision | `e4_revised.py` → `e4r_fpr.csv`, `e4r_heldout.csv`, `e4r_soundness.csv` | Saturation alarm D_sat in the stack (benign cost 1.07 %); simultaneous Clopper–Pearson p-box; δ = R1 calibration value (not widened) and δ = R8 LP, separate Holm families; 72 new held-out attackers, fresh seed block 92xxx | **0 / 1,296 Holm-significant violations under each budget** (510,848 undetected-attack missions); superposition exact on every undetected mission; empirical δ exceeded in 6/216 cells (max 6.25 m, weather mimic, CEM), LP δ never; floor (R1 δ, 5 % FPR) 0.541 at m = 10 m, 0.992 at m = 20 m; LP δ certifies nothing at m ≤ 20 m. No undetected failure at any of the 648 informative points: not refuted, not stressed |

Ground rule kept: the R1 held-out maximum (7.04 m) was **not** used to widen δ_adv; the revision is judged only on seeds never used before.

---

## R1 — Stronger attackers; stabilise δ_adv (RQ1, RQ2) **[load-bearing]**

**Goal.** Show that the pooled supremum δ_adv does not grow materially when the attacker gets a much larger search budget. If it does, the certificate must use the larger value.

1. Replace or supplement CEM with **CMA-ES** (`cma` package, IPOP restarts, popsize 16, 200 generations) and **Bayesian optimisation** (`optuna`, TPE, 400 trials) per (stack × family × operating point).
   - Use K = 128 rollouts per candidate with common random numbers: the same seed block for every candidate in a generation.
2. Add a **mixed-family attacker**: a categorical variable over the five families plus a switch time, so one mission can begin as `gnss_mimic` and finish as `fault_mimic`.
3. Add a **white-box gradient attacker** through a differentiable JAX port of `sim.py`.
   - Use straight-through estimators for the detector thresholds.
   - Use REQUIEM's budget loss ReLU(T − |L_a|) as the stealth penalty (`kim2024predictable`).
4. Recompute `e4_delta_adv.csv` by pooling *all* attackers. **Acceptance:** the new δ_adv is at most 1.25× the pilot value, or the manuscript's floors are regenerated with the new value and the change is reported in §Evaluation.
5. Scale the E4 grid to n = 5,000 missions per operating point, with five held-out attacker seeds.

Expected cost: about 6–10 CPU-hours (embarrassingly parallel; `PAR=$(nproc)`).

## R2 — 6-DoF dynamics and an EKF2-class estimator (C1, C3)

1. Port `sim.py` to a 6-DoF multirotor model, either gym-pybullet-drones (`Quadrotor` with a PID position controller) or the in-repo model under `models/uav_defense`.
2. Implement a 15/24-state error-state EKF with GNSS, IMU, barometer and magnetometer.
   - Use PX4 EKF2 innovation gates (`EKF2_GPS_P_GATE`, `EKF2_GPS_V_GATE`; read the defaults from the firmware version you pin).
   - Use the EKF2 bias process-noise parameters.
3. Re-run E1–E5 unchanged on the new model. Report the per-axis Lipschitz estimate with `experiments/local_lipschitz.py` on the new trajectories. Report whether the closed-loop superposition fraction (`superposition_frac`) stays ≥ 0.99.
   - If it drops, the sub-additivity lemma applies only through the Grönwall factor. Switch the budget to the Grönwall-amplified form (manuscript §4.3, Remark 2).
4. **Offline EKF2 replay fallback**, if SITL is unavailable. Use `pyulog` to extract the sensor topics from real ULog files: the Whelan flights, and the RflyMAD real-flight subset. Replay them through PX4's `ecl` EKF library compiled as a Python extension (or the `EKF/` folder of PX4-ECL), injecting the attack offset at the GNSS input.

## R3 — PX4 SITL transfer validation (C3) **[load-bearing]**

**Goal.** About 1,000 missions per condition in PX4 SITL with Gazebo. Confirm that (a) the detector ranking by disguise and (b) floor soundness transfer from the pilot.

1. Image: `px4io/px4-dev-simulation-jammy` (pin the digest). Build `make px4_sitl gz_x500`. Run headless with `HEADLESS=1`.
2. **Wind.**
   - Use the gz-sim `WindEffects` system, with the mean and Dryden-shaped gusts generated offline by `sim.py::_dryden_ss` and streamed via a small gz plugin. Commit it as `paperIV/sitl/wind_stream.cc`.
   - Classes: light / moderate / severe (W20 = 15 / 30 / 45 kt).
3. **Faults.** Use PX4 failure injection with `SYS_FAILURE_EN=1`: `failure gps off` for outages, and `failure accel|gyro <type>` for IMU faults. Actuator loss of effectiveness goes through the `gz` motor-model parameter at runtime.
4. **Attack (simulation interface only).** Inject the attacker's offset d(t) in the SITL GNSS plugin, by patching the `GpsSim` measurement before publication. Put the patch in `patches/px4_gps_offset.patch`. Read d(t) from a per-mission CSV produced by the optimised parameters in `e2_evasion.csv`.
5. **Detectors.**
   - D2 = EKF2's own innovation test ratios (`estimator_innovation_test_ratios`).
   - D3 = a SAVIOR-style CUSUM on the EKF2 output against a no-wind model.
   - D4 = an IMU–GNSS invariant computed from `sensor_combined` and `vehicle_gps_position`.
   - D1 = a jump rule.
   - Log everything with `ulog`.
6. **Mission.** A 60 s straight segment at 8 m/s; the corridor-margin classes come from `results/ewbench_margins.csv`. Use 1,000 missions per (wind × family × operating point) on the reduced grid: 3 × 5 × 2.
7. **Acceptance.**
   - The disguise ranking per detector must agree with the pilot (Kendall τ ≥ 0.6), or the manuscript reports the SITL ranking instead.
   - Zero Holm-significant floor violations.
   - Write `results/r3_sitl_*.csv` with `provenance=sitl`.

Expected cost: about 1 day on a 16-core workstation (≈ 30,000 missions × 70 s wall-clock, 16 parallel instances).

## R4 — Network-layer coupling in SITL (δ_net, cross-layer pairing)

1. Run two SITL vehicles plus a relay node. Peer position reports travel over MAVLink through `mavlink-router`, and `tc netem` on the relay's veth adds the delay.
2. Drive the delay schedule from the DATAMUt replay hop ledger (`results/hop_ledger.csv`). Use the parent's undetected-delay supremum (≤ 4.84 s) and the detector operating curve (`results/theta_operating_curve.csv`).
3. Emit `CrossLayerPairing` records with `pairing_basis=synthetic_alignment` (SITL); see `schema/uavsec_schema.json`. Each pairing joins the network delay window to the navigation-degradation window it induces.
4. Measure γ in SITL and compare it with the parent's γ_sup = 1.625 m/s. Replace "network term added as its certified worst case" in §Evaluation with the measured coupling.

## R5 — Measured marginals (C3, provenance)

1. **δ_gnss (measured).** Use `results/gamma_campaign_samples.csv`, the 674 post-onset samples. Fit the marginal of position error per unit staleness, keep the 6.1× condition spread as a p-box envelope (`gamma_campaign_bins.csv`), and tag `provenance=measured`.
2. **δ_fault (measured).**
   - Write `ingest/ingest_rflymad.py` and `ingest/ingest_alfa.py` against the unified schema. They must be lossless, with a hash round-trip test in `ingest/validate.py`.
   - From the 497 real RflyMAD flights and the 47 ALFA flights, extract the position deviation in the window after fault onset.
3. Re-run E3 and E4 with the measured marginals. Report both variants (simulated and measured) side by side in `e3_gap_measured.csv`.

## R6 — Benchmark packaging and artifact evaluation

1. Extend `ingest/pair_poc.py` so that fault and environment windows produce pairings with `pairing_basis=physics_model`. Add a `perturbation_source ∈ {net, gnss, fault, env, adv}` field to the schema (bump it to v0.2).
2. Write a datasheet for each corpus (Gebru et al.) in `docs/datasheets/`, and a checklist mapping each Arp et al. pitfall to its mitigation in `docs/arp_checklist.md`.
3. Write a `Dockerfile` with a CPU-only path that reproduces every figure in less than 1 h. Mint a Zenodo DOI for the anonymised snapshot: `python3 tools/anonymise.py --out ../RobustUAVs-anon --init-git --zip`.
4. Target badges: Available, Functional, Reproduced. Write `ARTIFACT_APPENDIX.md` in the USENIX AE format.

## R7 — Additional defences and baselines

| Baseline | Implementation pointer | Role |
|---|---|---|
| ML IDS (one-class SVM, isolation forest, autoencoder) on innovation windows | `models/uav_defense/defenses/` | signature-free learned detector |
| DeLorean-style diagnosis + recovery | re-implement from `dash2024delorean` | recovery baseline; compare time-to-detect against the anchor interval |
| PID-Piper feed-forward recovery | `dash2021pidpiper` | recovery baseline |
| Active exposure (zonotope) | `tian2026` | defence designed to break equivalence |
| Dual fault/attack detector | `xue2025dual` | tests the separability counter-claim (`li2026unified`) |
| GNSS power-distortion monitor | `wesson2018pdm` (signal level; needs IQ, so R9) | signal-layer comparison |

For each, report the false-positive rate (FPR) at the 5% operating point, the evasion rate of the R1 attacker, and the change in δ_adv.

## R8 — Analytic stealth budget (replace the empirical supremum where possible)

For the linear KF + χ² + anchor configuration, compute the stealthy reachable set with the ellipsoidal method of `mo2016` / `murguia2020`. Do this per anchor interval, via an SDP (`cvxpy`). Report it next to the empirical δ_adv. If the analytic bound is finite and below 2× the empirical supremum, use it as the certificate's adversarial term. The adversarial term then becomes a proved quantity, which strengthens RQ2 considerably.

## R9 — Signal-level GNSS (optional)

Register for TEXBAT and OAKBAT. Run GNSS-SDR with the power-distortion monitor, and replay the `gnss_mimic` offsets as code-phase and carrier drag-off profiles with GPS-SDR-SIM. **Never transmit**: use file-based IQ only.

## R10 — Ethics and disclosure

1. Before submission, email the PX4 and ArduPilot security contacts if R3 shows that EKF2 gating can be evaded by a disguise family the pilot already identified. Include the mitigation from §Discussion and allow a 90-day window.
2. Release the evasion harness for simulation interfaces only, together with the mitigation code (anchor-interval sizing rule, IMU–GNSS invariant, source-agnostic floor).
3. Keep the manuscript's "Ethics considerations" and "Open science" sections synchronised with what is actually released.

---

## Data gates (inherited from `PENDING_ON_DATA.md`)

| Gate | Unblocks |
|---|---|
| UAV-CAS `UAV-CAS_stat.csv` (DataPort 10.21227/zgrg-z865) | the sixth real ingest; mesh-layer row of the provenance table |
| Whelan attack-on/off timestamps | `measured_same_platform` pairings (currently zero) |
| TEXBAT/OAKBAT IQ | R9; signal-level `gnss_mimic` |
| RflyMAD / ALFA downloads | R5 measured fault marginals |

## Acceptance checklist before submission

- [x] R1 run; δ_adv within 1.25× (exactly 1.25×) and the floors regenerated with it
- [ ] R3 SITL: zero Holm-significant violations; disguise ranking reported
- [x] R5 measured-marginal variant in the paper (GNSS only; fault marginals still simulated)
- [ ] Every `% VERIFY`/[PRE] entry in `manuscript/refs.bib` re-checked
- [ ] Anonymised artifact URL inserted; `tools/anonymise.py` passes
- [ ] Ethics considerations and Open science sections immediately before the references
