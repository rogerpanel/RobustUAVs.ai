# What Authenticity Costs in Metres: artifact for review

This repository is the anonymised artifact for the paper *What Authenticity Costs in Metres: A
Certified Budget for Cryptography and Sensing in UAV Navigation*. It contains the models,
simulations and result files behind every number in the paper, and the scripts that write those
numbers into the manuscript.

It is anonymised for double-blind review. Author names, affiliations and data-mirror addresses
have been removed and will be restored on acceptance.

| | |
|---|---|
| Language | Python 3.10 or newer |
| Dependencies | `numpy` (`python3 -m pip install numpy`); TeX Live 2022+ to build the paper |
| Run time | about 30 seconds on a laptop CPU, no download, no GPU |
| Licence | MIT (`LICENSE`); third-party data remain under their own licences |

## 1. Quick check (about 30 seconds)

```bash
bash paperI/experiments/run_all.sh     # rewrites paperI/results/, manuscript/figdata/ and manuscript/numbers.tex
git status --short                     # expected: no output
cd paperI/manuscript && latexmk -pdf main.tex
```

No number in `main.tex` is typed by hand. Each one is a macro in `manuscript/numbers.tex`
(213 macros), which `make_numbers.py` writes from the result files. An empty `git status` after
`run_all.sh` therefore shows that the paper, the result files and the code agree.

## 2. Where each result comes from

| Result in the paper | Script | Result file |
|---|---|---|
| Spoofed estimator drifts up to 1.74× faster than one given degraded but honest fixes (RQ1) | `budget.py` | `gamma_ratio.csv` |
| GNSS-outage experiment: dead reckoning measured at 200 onsets on the benign flight's IMU log | `e1_inertial_gamma.py` | `e1_inertial_gamma.csv`, `dead_reckoning_fit.csv` |
| Authentication delay per scheme, e.g. ML-DSA-44 119.0 ms (RQ2) | `budget.py`, `transport.py` | `dauth.csv`, `transport_frames.csv` |
| Admissible message rate and the occupancy cliff, e.g. 16.4 ML-DSA messages per second; SLH-DSA does not fit | `transport.py` | `transport_cliff.csv` |
| Response-time bound checked against a discrete-event simulation of the bus | `transport.py` | `transport_des.csv` |
| Crossover under a constant rate and under the measured envelopes; θ× ≈ 0.259–0.284 s (RQ3) | `budget.py` | `crossover.csv`, `crossover_curves.csv`, `horizon_crossover.csv`, `horizon_envelopes.csv` |
| Freshness windows of 30–165 s never bind; oscillator holdover; GNSS time push (RQ4) | `clock_freshness.py` | `freshness_binding.csv`, `clock_holdover.csv`, `time_push.csv` |
| Verification amplification and the saturating attack share, e.g. 0.105 of the bus for Ed25519 (RQ5) | `induced_verification.py` | `iv_amplification.csv`, `induced_verification.csv` |
| Batching and the certified selection rule | `amortise_select.py` | `amortisation.csv`, `selection.csv` |
| Delay-certificate constants (Section II-A) | `budget.py` | `certificate_table.csv` |
| Decoding of the HCRL UAVCAN capture (payload mix, U0) | `e5_hcrl_bus.py` | `e5_hcrl_bus.csv` |
| Which input was used where a measured and a literature value both exist | `make_numbers.py` | `provenance_paperI.csv` |

Scripts are in `paperI/experiments/` and result files in `paperI/results/`. Every input is
defined once in `constants.py` with a provenance tag (measured, derived, literature,
physics model or assumption), and every result row carries a `provenance` column.

The γ samples (`results/gamma_campaign_samples.csv`) and the HCRL rate signatures
(`results/hcrl_type_signatures.csv`) at the repository root are measured inputs shared with the
pipeline that produced them; they are committed, so no download is needed.

## 3. Experiments that need raw data

`e1_inertial_gamma.py` and `e5_hcrl_bus.py` read raw flight logs and bus captures. Their
outputs are committed. Without the raw data, `run_all.sh` prints `SKIPPED` for these two steps, writes nothing for them, and uses the committed outputs. To re-run them, stage
the public source datasets under `data/raw/` as `data/fetch_kaggle.py` describes. The address of
the aggregated mirror is withheld during review because it identifies the authors; the sources
themselves are public and cited in the paper.

## 4. What has and has not been measured

Table "Validation Status of the Inputs" in the paper lists, for each modelled input, the
experiment that would replace it. Two have been performed: the GNSS-outage experiment and the
decoding of the HCRL capture. The others have not been run, and no result depends on them:

- visual-inertial odometry on EuRoC (γ without GNSS);
- a PX4 software-in-the-loop sweep with a rejection arm, in hover and at 5–15 m/s cruise;
- STM32H7 cycle counts and the ML-DSA signing tail;
- hardware CAN bus timing and a hardware flood test;
- a GNSS time push against MAVLink 2 signing in simulation;
- an OSNMA time-offset replay.

Because every number is generated from the result files, a measured input that replaces a
modelled one changes the paper without any edit to the text.

Two caveats the paper states are worth repeating here. The authenticated rate γ_a is a proxy
taken from a jamming flight on which the receiver kept its fix. The GNSS-outage measurement
(1.14 m/s, interval 0.68–1.14 m/s) contains the proxy, so the proxy is kept, but the difference
is not resolved. The CAN bit rate (1 Mbit/s) is assumed, because the capture's timestamps are
too coarse to measure it (`e5_hcrl_bus.csv`, column `bitrate_verdict`).

## 5. Layout

```
paperI/experiments/   constants.py, transport.py, budget.py, clock_freshness.py,
                      induced_verification.py, amortise_select.py, e1_inertial_gamma.py,
                      e5_hcrl_bus.py, export_figdata.py, make_numbers.py, run_all.sh
paperI/results/       result files (CSV), one provenance column per row
paperI/manuscript/    main.tex (IEEEtran), fig_*.tex, figdata/, numbers.tex, refs.bib
results/              shared measured inputs (γ samples, HCRL signatures)
data/fetch_kaggle.py  staging script for the raw corpus (address withheld during review)
```
