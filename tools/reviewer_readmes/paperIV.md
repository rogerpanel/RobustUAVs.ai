# When the Attacker Is Indistinguishable from the Weather: artifact for review

This repository is the anonymised artifact for the paper *When the Attacker Is Indistinguishable
from the Weather: Provable Bounds on Undetected GNSS-Spoofing Deviation for UAVs*. It contains the
closed-loop simulator, the four detectors and the anchor gate, the five disguise families and
their optimisers, the dependence-bound library, every result file behind every number in the
paper, and the scripts that write those numbers, tables and figure data into the manuscript.

It is anonymised for double-blind review. Author names, affiliations and repository addresses
have been removed and will be restored on acceptance.

| | |
|---|---|
| Language | Python 3.10 or newer |
| Dependencies | `numpy`, `scipy` (quick check, pilot, analytic and measured-marginal studies); `cma`, `optuna` in addition for the scaled attacker study and the revised instantiation; TeX Live 2022+ to build the paper |
| Run time | quick check about a minute; pilot about 27 min on 2 cores; scaled attacker study about 10 CPU-hours; revised instantiation about 30 min on 4 cores; analytic stealth budget at T_a = 5 s about 40 min on 4 cores (full T_a sweep about 14 h) |
| Hardware | CPU only, no GPU and no flight simulator; the pilot peaks below 1.5 GB of RAM |
| Licence | MIT (`LICENSE`); third-party data remain under their own licences |

## 1. Quick check (about a minute)

```bash
python3 -m pip install numpy scipy
cd paperIV/experiments
python3 r5_measured_gnss.py      # measured-jamming-marginal study, from the committed inputs (~10 s)
python3 r1_diagnose.py           # re-simulates the scaled test's violating missions (~40 s)
python3 make_numbers.py          # writes manuscript/numbers.tex, tab_*_body.tex, figdata/*.dat (~10 s)
cd ../..
git status --short               # expected: no output
cd paperIV/manuscript && latexmk -pdf main.tex
```

Every result in the manuscript is a macro in `manuscript/numbers.tex`
which `make_numbers.py` writes from the files in `paperIV/results/`; the four table
bodies (`tab_*_body.tex`) and the pgfplots data (`figdata/*.dat`) are written by the same script.
`r5_measured_gnss.py` and `r1_diagnose.py` recompute two of the studies from committed inputs and
rewrite their result files. An empty
`git status` therefore shows that the paper, the result files and the code agree.

The rate γ = 1.625 m/s of the network term is the supremum over the 674 post-onset samples that
ship with the artifact; from the repository root:

```bash
python3 -c "import csv; r=list(csv.DictReader(open('results/gamma_campaign_samples.csv'))); print(len(r), max(float(x['gamma_delta_m_s']) for x in r))"
# 674 1.625
```

## 2. Where each result comes from

| Result in the paper | Script | Result file |
|---|---|---|
| Wind and faults alone trip no detector (FPR 0.0%), GNSS error alone up to 5.3%; severe turbulence raises D3 to 8.2% | `run_pilot.py` (calibration) | `e1_fpr_by_source.csv`, `e1_fpr_by_wind.csv`, `e1_thresholds.csv`, `e1_calibration.json` |
| Operating curves against naive offsets: a 5 m step is caught by the χ² gate in 100% of missions and by the signature monitor in 7% (Fig. 2) | `run_pilot.py` (calibration) | `e1_roc.csv` |
| 35 optimised attackers in five disguise families evade every detector, and the full stack, in at least 87% of missions; benign missions raise no alarm in about 94%; in 8 of 25 cells the optimiser aimed at that stack found no evading attacker (RQ1) | `run_pilot.py` (attackers, cross-evaluation) | `e2_attackers.csv`, `e2x_cross.csv` |
| Anchor gate armed: largest undetected contribution 2.1–2.9 m whichever detector is deployed; median KS distance 0.07 for evading against 0.99 for detected attacks (Table I, top) | `run_pilot.py` (cross-evaluation) | `e2x_cross.csv` |
| Anchor gate removed: 9.9 m (D2) to 73.9 m (D1, D3, D4 against the fault mimic) (Table I, bottom) | `e2y_no_anchor_gate.py` | `e2y_no_anchor_gate.csv` |
| Re-anchoring interval: 4.4 m at T_a = 5 s to 20.6 m at 20 s (4.7×); 137.8 m with the final interval unchecked (Fig. 3) | `run_pilot.py` (anchor sweep, terminal window) | `e2b_anchor_sweep.csv`, `e2c_terminal_window.csv` |
| Looseness of the bound at s = 4 m: the RA tightens the union bound by 20% (0.6390 to 0.5133); dependence gap 4×, envelope gap 2.2×, temporal gap 16.6×; (C5) held in 99.63% of joint missions (Fig. 4; RQ3) | `run_pilot.py` (marginals and gaps), `depbounds.py` | `e3_gap.csv`, `e3_marginal_summary.csv`, `e3_marginals.npz` |
| Pilot soundness: δ_adv = 4.37 m; 0 of 270 points with a Holm-significant violation over 30,541 undetected-attack missions; one held-out attacker exceeded δ_adv in 1 of 45 cells (5.13 m, 1.17×); certified 0.9 floor at m = 10.0 m against 8.5 m under independence (Table II, Fig. 5; RQ2, RQ4) | `run_pilot.py` (soundness), `make_numbers.py` (floor curve) | `e4_delta_adv.csv`, `e4_soundness.csv`, `e4_saturation_control.csv` |
| Negative controls: without re-anchoring, undetected deviation reaches 308.5 m and 4 of 6 points are flagged; severe turbulence lets the fault mimic reach 96.7 m (Table III) | `run_pilot.py` (negative controls) | `e5_negative_controls.csv` |
| Scaled attacker study: 126 further attackers (CMA-ES, TPE, tail-objective TPE, mixed family); stealth budget 4.37 to 5.46 m (1.25×); a held-out attacker exceeded it in 12 of 270 cells, up to 7.04 m (RQ5) | `r1_attackers.py` | `r1_attackers.csv`, `r1_attackers_tail.csv`, `r1_delta_adv.csv`, `r1_heldout.csv` |
| Scaled soundness test: 5 of 1,620 tests Holm-significant, all at m = 20 m | `r1_attackers.py` | `r1_e4_soundness.csv` |
| The violations come from 3 missions that fail under their benign inputs alone (19.2–34.5 m); the attack adds at most 2.3 m, and all three saturate the actuator | `r1_diagnose.py` | `r1_violation_diagnosis.csv` |
| Analytic stealth budget at T_a = 5 s (large-sample margins): the anchor gate alone yields no finite bound; with D1, 303 m at 5% FPR and 320 m at 1%; with the saturation alarm, 31.9 m, 5.8× the calibrated δ_adv | `r8_analytic_bound.py` | `r8_analytic_bound.csv` |
| Proved budget against the re-anchoring interval (Table of the attacker-class subsection): 0.5–10 s, with large-sample margins and with the finite-sample confidence correction (order statistic, δ = 0.05) | `r8_bound_vs_anchor.py`, `r10_confidence_bound.py` | `r8_bound_vs_anchor.csv`, `r10_bound_conf.csv` |
| The CUSUM detector as second-order-cone constraints barely tightens the bound (35.9 to 35.2 m at the same evaluation point) | `r9_d3_point.py` (uses `r9_convex_bound.py`) | `r9_d3_point.csv` |
| PX4 SITL: naive offsets, transferred and PX4-optimised attackers, stealth budget, no-anchor control (5 s re-anchoring; Table of the PX4 section) | `px4/p4_fleet.py`, `px4/p4_analyze.py` | `px4/px4_e1_detection.csv`, `px4/px4_e2_cross.csv`, `px4/px4_e2_reading.json`, `px4/px4_e3_cem_eval.csv`, `px4/px4_e3_delta_adv.csv`, `px4/px4_e4neg.csv`, `px4/px4_validity.csv` |
| PX4 SITL at 1 s re-anchoring, with the two pre-registered predictions | `px4/p4_plan.py ta1`, `px4/p4_analyze.py ta1` | `px4/px4_ta1_cross.csv`, `px4/px4_ta1_summary.json` |
| Revised instantiation on fresh seeds: the saturation alarm costs 1.1% benign false alarms (stack 4.8% to 5.6%); 72 held-out attackers; 0 violations in 1,296 tests under each budget; empirical budget exceeded in 6 of 216 cells, up to 6.25 m; floor 0.541 at m = 10 m and 0.992 at m = 20 m | `e4_revised.py` | `e4r_fpr.csv`, `e4r_heldout.csv`, `e4r_soundness.csv` |
| Measured jamming marginal (RQ6): 496 samples, envelope 6.2 m at 10 s and 7.0 m at 15 s; floor at m = 10 m falls from 0.69 (simulated) to 0.34 (measured envelope) and 0.32 (45 s episodes); with the finite-sample band 0.54, 0.21 and 0.19 | `r5_measured_gnss.py` | `r5_gnss_envelope.csv`, `r5_floor_sensitivity.csv` |
| Network term: γ = 1.625 m/s, slack s = 4.84 s, L = 1.181, tube 2.65 m at θ = 0.25 s and H = 2 | `constants.py`, `make_numbers.py` | γ from `results/gamma_campaign_samples.csv`; s and L are inputs recorded in `constants.py` |

Scripts are in `paperIV/experiments/` and result files in `paperIV/results/` unless a path says
otherwise. `run_meta.json` records the mission counts, the optimiser budgets and the seed blocks
of every run; the 1,909,600 pilot missions are counted in `mission_count.txt` and
`mission_count_e2y.txt`. Every input is defined once in `constants.py` with a provenance tag
(standard, model choice, autopilot default class, or shared measured input).

`results/gamma_campaign_samples.csv` at the repository root holds the measured navigation error
during the real GPS jamming and spoofing flights of the UAV Attack Dataset. It is committed, so no
download is needed; the measured-marginal study uses its jamming samples only.

## 3. Full re-run

```bash
python3 -m pip install numpy scipy cma optuna
cd paperIV/experiments
python3 run_pilot.py                                   # pilot, ~27 min on 2 cores
python3 e2y_no_anchor_gate.py                          # cross-evaluation without the anchor gate, ~1-2 min
python3 r1_attackers.py --par 4 --stage optimise       # scaled attacker study: CMA-ES and TPE
python3 r1_attackers.py --par 4 --stage optimise_tail  # tail-objective TPE
python3 r1_attackers.py --par 4 --stage delta          # pooled stealth budget over all attackers
python3 r1_attackers.py --par 4 --stage e4             # scaled soundness test (n = 5,000 per cell)
python3 r1_diagnose.py                                 # the violating missions, one by one
python3 r8_analytic_bound.py --par 4                   # analytic stealth budget, T_a = 5, 10, 20 s and none
python3 r8_bound_vs_anchor.py                          # proved budget for T_a = 0.5-10 s (~20 min on 4 cores)
python3 r10_confidence_bound.py                        # the same with the finite-sample correction (~1 h on 4 cores)
python3 r9_d3_point.py                                 # D3 as cone constraints at the 5 s maximum (~30 min)
python3 r5_measured_gnss.py                            # measured jamming marginal
python3 e4_revised.py --par 4                          # revised instantiation on fresh seeds
python3 make_numbers.py
cd ../manuscript && latexmk -pdf main.tex
```

Each stage reads the outputs of the stages above it, so the order matters. The paper uses the
analytic budget at T_a = 5 s only; `r8_analytic_bound.py --par 4 --anchors 5 --out r8_ta5.csv`
computes those rows in about 40 minutes and writes them next to the committed table for
comparison; the other intervals add about 13 h. `r8_assemble.py` is the script that assembled the
committed table from a sweep run in parts; running `r8_analytic_bound.py` with its default
intervals writes the table directly.

The simulation scripts write to `paperIV/results/`, or to the directory named by `P4_RESULTS`
(`make_numbers.py` always reads `paperIV/results/`). To re-run the pilot without touching the
committed files:

```bash
mkdir -p /tmp/p4 && P4_RESULTS=/tmp/p4 python3 run_pilot.py && P4_RESULTS=/tmp/p4 python3 e2y_no_anchor_gate.py
```

and compare `/tmp/p4` with `paperIV/results/`. `run_pilot.py` writes `run_meta.json` afresh with
its own block (including its wall-clock time); the scaled study and the revised instantiation add
their blocks when they run. `run_pilot.py`, `r1_attackers.py`, `r8_analytic_bound.py` and
`e4_revised.py` accept `--quick` for a smoke run, which also writes to the results directory, so
point `P4_RESULTS` elsewhere for it.

Seeds are partitioned by role and never reused across roles:

| Block | Role |
|---|---|
| 1xxx | calibration: thresholds, benign marginals, pooled stealth budget (1700 + attacker id), benign margins of the analytic budget |
| 2xxx | attacker optimisation (CEM; anchor sweep 2100+, terminal window 2200+, negative controls 2300+) |
| 3xxx | held-out attacker optimisation (also the tail-objective TPE seeds 3700 + h of the revised instantiation) |
| 4xxx | held-out evaluation: cross-evaluation 4100+, anchor sweep 4200+, terminal window 4300+, soundness 4400+, no-gate cross-evaluation 4500+, negative controls 4900+ |
| 55xx | episode draws of the measured-marginal study |
| 6xxx | scaled attacker study: optimiser job j at 6000 + j, tail objective 6500 + j |
| 7xxx, 8xxx | scaled soundness test: held-out CEM attackers 7000 + h, evaluation missions 8000 + 10h + w |
| 92xx, 97xx, 92000+ | revised instantiation: benign false-alarm check 9201, held-out CEM attackers 9200 + h, tail-objective TPE 9700 + h, evaluation 92000 + 10h + w (+5000 for TPE); its `--quick` smoke test uses a block offset by 500 |

## 4. Cross-layer event schema

The evaluation's records follow a cross-layer event schema with three record kinds: an *Event*
(an atomic observation), an *AttackWindow* (a labelled interval) and a *CrossLayerPairing*,
which joins a network or environmental window to the navigation window it induces and carries the
detector operating point, the residual budget, the induced perturbation and the mission outcome.

This paper extends the schema to version 0.2 so that benign sources share the attack pairings'
representation:

- a `perturbation_source` field with the values `net`, `gnss`, `fault`, `env` and `adv`;
- **fault sources**: accelerometer bias steps, bias drift and actuator loss of effectiveness,
  following the RflyMAD and ALFA fault taxonomies (`sim.py`, rates in `constants.py`);
- **environmental source**: Dryden lateral turbulence (MIL-F-8785C) at 100 ft, with the declared
  envelope W20 = 15–30 kt as a probability box and severe turbulence (45–60 kt) as a negative
  control;
- a **provenance flag** on every pairing: `measured_same_platform` (both windows observed on one
  airframe), `physics_model` (coupled through a stated physical relation) or
  `synthetic_alignment` (aligned in simulation).

The evasion study runs in simulation, so its results belong to the class the schema flags as
`synthetic_alignment`. The schema files are `schema/uavsec_schema.json` (v0.1) and
`schema/uavsec_schema_v0.2.json`, which adds `perturbation_source` as an optional field, so v0.1
records remain valid; the adapters are in `ingest/`. The result files
of the follow-up studies carry a `provenance` column on every row: `sim` for simulation outputs,
`physics_model` for the analytic stealth budget, `measured` for the jamming envelope, and
`measured+sim` where that envelope is combined with simulated marginals. The pilot's result files
(`e1_*` to `e5_*`) are simulation outputs throughout. The number of `measured_same_platform`
pairings is zero, as the paper states.

## 5. Scope and extensions

The paper states the following points; they are collected here so that the artifact is read with
the right scope.

- **Model.** The proof and the soundness test hold for a reduced-order lateral channel of a
  multirotor with a three-state Kalman filter, the four detectors D1–D4 and the anchor gate. The
  PX4 SITL study below transferred the stealth budget but not the full disguise matrix.
- **Measured inputs.** The measured-marginal study replaces the GNSS marginal with the measured
  jamming envelope from one campaign on one airframe. The fault and environmental marginals are
  simulated in every study; calibrating the fault marginal on RflyMAD and ALFA flight logs extends
  the measured-marginal study in the same way, with both variants reported side by side.
- **Adversarial term.** The usable δ_adv is an empirical supremum over optimised attackers, and
  every exceedance by a held-out attacker is reported. The proved budget holds for every causal,
  adaptive GNSS-offset attacker against stacks containing D1, the anchor gate and the saturation
  alarm, with probability at least 1 − ε over the benign noise (ε = 0.01), on missions without a
  GNSS outage, on the linear loop, with confidence at least 1 − δ (δ = 0.05) over the calibration
  sample; it is 33.5 m at a 5 s re-anchoring interval and 10.6 m at 1 s (31.9 m and 10.2 m with
  large-sample margins)
  (`r8_analytic_bound.csv`, `r8_bound_vs_anchor.csv`; adding the CUSUM detector as cone
  constraints: `r9_d3_point.csv`). Each benign margin is a distribution-free order-statistic bound on
  its quantile (`r10_confidence_bound.py`, `r10_bound_conf.csv`).
  Reachable-set bounds for detectors that alarm on runs of exceedances, and a white-box gradient
  attacker through a differentiable simulator, would tighten and extend these.
- **Network term.** δ_net enters as the certified tube (2.65 m at θ = 0.25 s); injecting measured
  relay staleness into software-in-the-loop simulation is a stated extension.
- **Finite calibration.** With 4,000 samples per source, the simultaneous band certifies at most
  0.992.
- **Attacker class.** The bound covers covert attackers whose failure goes undetected; the
  attacker adds an offset to the GNSS position and cannot inject into the IMU.
- **Dual use.** Every attack acts through the simulator interface; the artifact contains no
  transmit-capable code path.

**PX4 software-in-the-loop transfer study** (`paperIV/experiments/px4/`, results in
`paperIV/results/px4/`, protocol and dated deviations in `paperIV/PX4_PREREG.md`).

- *Platform*: PX4 v1.14.3 SITL with SIH physics, quadrotor, mission mode, a 60 s segment at about
  8 m/s; one fresh PX4 process per mission, parameters set at boot.
- *Injection*: `px4_paperIV.patch` adds the GNSS offset families and the benign GNSS envelope to the
  simulated GPS, the gust, IMU faults and loss of effectiveness to SIH, all from seeded streams so
  that each attacked mission has a benign twin; and an EKF2 change that fuses the trusted fix as an
  absolute position (stock v1.14 fuses vision relative to a bias estimate while GNSS is active).
- *Detectors*: computed offline from the ULogs (`p4_ulog.py`); D2 is EKF2's own GNSS innovation test.
- *Running it*: `run_server_paperIV.sh` (stages setup, smoke, e0, e1, e2, e3, e4neg, reanalyze,
  e3fix, ta1, pack) needs Docker and the `px4io/px4-dev-simulation-jammy` image; the tables are
  rebuilt from the committed per-mission rows by `p4_analyze.py`, except those that need the
  time series, which are kept in the full results archive.
- *Exclusions*: missions in which PX4 entered a failsafe before the window (a harness start-up
  race, independent of the attack) are excluded and counted in `px4_validity.csv`.

## 6. Layout

```
paperIV/experiments/   constants.py         every input, with a provenance tag
                       sim.py               lateral closed loop: KF, Dryden wind, faults, GNSS drift,
                                            outages and jamming noise, re-anchoring, detectors D1-D4,
                                            anchor gate, saturation alarm, five disguise families
                       depbounds.py         union bound, Rearrangement Algorithm, independence,
                                            comonotone, finite-sample (Clopper-Pearson) band
                       run_pilot.py         pilot: calibration, attackers and cross-evaluation, anchor
                                            sweep, terminal window, marginals and gaps, soundness,
                                            saturation control, negative controls
                       e2y_no_anchor_gate.py   cross-evaluation with the anchor gate removed
                       r1_attackers.py      scaled attacker study and soundness test
                       r1_diagnose.py       diagnosis of the scaled test's violations
                       r8_bound_vs_anchor.py, r10_confidence_bound.py   proved budget against the
                                            re-anchoring interval, without and with the finite-sample
                                            correction of the benign margins
                       r9_convex_bound.py, r9_d3_point.py   D3 as second-order-cone constraints
                       px4/                 PX4 SITL harness: px4_paperIV.patch, p4_fleet.py (driver),
                                            p4_ulog.py (offline detectors), p4_plan.py, p4_analyze.py,
                                            run_server_paperIV.sh
                       r8_analytic_bound.py analytic (LP) stealth budget; r8_assemble.py assembled
                                            its committed table from a sweep run in parts
                       r5_measured_gnss.py  measured jamming marginal
                       e4_revised.py        revised instantiation on fresh seeds
                       make_numbers.py      numbers.tex, tab_*_body.tex, figdata/*.dat
paperIV/results/       result files (CSV, JSON, NPZ) and run_meta.json; px4/ holds the PX4 tables
                       and the per-mission rows (missions.jsonl.gz)
paperIV/PX4_PREREG.md  pre-registration of the PX4 study, with its dated deviations
paperIV/manuscript/    main.tex (IEEEtran), sec_*.tex, fig_*.tex (TikZ/pgfplots), figdata/,
                       numbers.tex, tab_*_body.tex, refs.bib
results/               gamma_campaign_samples.csv (shared measured input)
```
