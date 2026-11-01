# Certificates as Constraints: artifact for review

This repository is the anonymised artifact for the paper *Certificates as Constraints: A Certified
Reference Monitor for Learned Task Allocation in UAV Swarms under Navigation Attacks*. It contains
the certified projection layer and its closed-form monitors, the brute-force oracle that checks
them, the fleet simulator, the multi-agent learning study, the PX4 software-in-the-loop flight
driver with its ground-truth soundness oracle, the two pre-registration protocols, every result
file, and the scripts that write those results into the manuscript.

It is anonymised for double-blind review. Author names, affiliations, the address of the data
mirror and the original commit history have been removed and will be restored on acceptance.

| | |
|---|---|
| Language | Python 3.10 or newer (tested with 3.11) |
| Dependencies | `numpy`, `scipy`, `torch` (`python3 -m pip install numpy scipy torch`; the CPU wheel from `https://download.pytorch.org/whl/cpu` is enough and a smaller download); TeX Live 2022+ with `pgfplots` to build the paper. The flight experiments also need Docker, `pyulog` and `mavsdk<4` (Section 4) |
| Quick check | about 5 minutes on a laptop or server CPU, no download, no GPU |
| Aggregation, consensus and vector-certificate studies | about 12 minutes |
| Learning study | headline seeds 0–4: about 1 hour on 2 cores; all extended runs: about 6 hours on 4 cores (Section 3) |
| Hardware | any laptop or server CPU; every script is single-threaded, the learning scripts run several in parallel (`PAR`); a learning run peaks at about 1.2 GB of memory; no GPU is used |
| Licence | MIT (`LICENSE`); third-party data remain under their own licences |

## 1. Quick check (about 5 minutes)

Every result in `manuscript/main.tex` is a macro in
`manuscript/numbers.tex` (456 macros), which `make_numbers.py` writes from the result files,
together with the tables `tab_*.tex` and the plotted points in `manuscript/figdata/`.

```bash
python3 -m pip install numpy scipy torch
cd paperIII/experiments
bash run_all.sh       # oracle check, simulations, references, aggregation, flight analyses, numbers
git status --short    # expected: the six latency files listed below, nothing else
git checkout -- ../results/e3_latency.csv && python3 export_figdata.py && python3 make_numbers.py
git status --short    # expected: no output
cd ../manuscript && latexmk -pdf main.tex
```

`run_all.sh` first prints the brute-force oracle check (`e1_verify.py`): nine rows, 83,872
comparisons in total, each with `'disagreements': 0`. It then regenerates every closed-form,
simulation and reference result, re-runs the analyses of the three flight campaigns from their
committed result files, aggregates the committed learning runs and rewrites `numbers.tex`.

Every stage is seeded, so the regenerated files are identical to the committed ones, with one
intended exception. `e3_latency.py` times the monitor on your machine, so it rewrites
`results/e3_latency.csv`, the four `manuscript/figdata/lat_*.dat` files and the latency macros of
`numbers.tex` (`\nLatCPU`, `\nLatCFThousand`, …). The paper quotes the run on an otherwise idle
4-vCPU AMD EPYC-Genoa server, which is the committed CSV. Restoring that CSV and regenerating, as
the `git checkout` line does, returns the tree to the committed state; an empty `git status` then shows that
the paper, the result files and the code agree.

## 2. Where each result comes from

Scripts are in `paperIII/experiments/` and result files in `paperIII/results/`.

| Result in the paper | Script | Result file |
|---|---|---|
| Certificate constants: γ_sup = 1.625 m/s, L = 1.181, L_ρ = 5.30 m/s, θ_ben = 0.178 s, benign floor 0.94 m, median two-hop jump 41.8 m | `certcmdp/certificate.py` | `constants_paperIII.csv` (inputs: `results/hop_ledger.csv`, `results/gamma_campaign_samples.csv`, `results/local_lipschitz.csv` at the repository root) |
| Verification of the closed forms: 83,872 comparisons over 10,000 instances, 0 disagreements; 4,000 instances per misreporting level, no honest violation | `e1_verify.py`, `e4_dynamics.py` | `e1_verify.csv`, `e4_liars.csv` |
| RQ1: the projection executed zero infeasible assignments over 5.8×10⁷ agent-epochs (10 seeds); PPO-Lagrangian executed 8,193,222 (14.22%), jamming-blind PPO 9,506,180 | `e5_marl.py` (`run_marl.sh`, `run_r_marl.sh`), `e6_aggregate.py` | `e5_marl/*_train.csv`, `e6_main.csv`, `e6_curves.csv` |
| RQ1, stronger learners: MAPPO-Lagrangian 2,897,602 training violations, PID-Lagrangian 8,089,556, QMIX without masks 7,526,523; masked QMIX 0 | `e5_marl.py` (`run_r_marl.sh`, block `r2`) | `e5_marl/{mappo_lag,mappo_lag0,pid_lag,qmix,qmix_mask}_s*`, `e6_main.csv`, `manuscript/tab_r2.tex` |
| RQ3: policy trained with the projection 0.491 [0.477, 0.509] at coverage ratio 1.00; keep-or-nearest with projection 0.435; masking ratio 0.62 | `e5_marl.py`, `e6_aggregate.py` | `e5_marl/*_eval.csv`, `e5_marl/references_eval.csv`, `e6_main.csv`, `manuscript/tab_main.tex` |
| RQ3: CBBA with feasible bundles certifies 0.539 [0.525, 0.561], ahead of every learned allocator | `e5_marl.py --references` | `e5_marl/references_eval.csv`, `e6_main.csv` |
| RQ3, fleet size: learned policy 0.491 (N = 12), 0.386 (N = 48), 0.009 (N = 96); CBBA 0.539, 0.526, 0.535 and 0.473; coverage ratio 1.00 throughout | `e5_marl.py` (`run_r_marl.sh` block `r1`, `run_r1_kbs.sh`, `run_r1_kbs24.sh`) | `e5_marl_N{24,48,96}/`, `e6_main_e5_marl_N*.csv`, `manuscript/tab_scale.tex` |
| RQ2: at φ = 0.3 (b = 4 of 12) the fleet certifies 5.55 tasks against the worst adversary, 6.37 under random collapse, against 3.89 for the generic bound; the graded bound coincides with the brute-force worst case in 100% of instances | `e2_degradation.py` | `e2_collapse.csv`, `e2_graded.csv` |
| RQ4: closed-form monitor 0.058 ms at N = 1000 and 11.0 ms at N = 10⁵; exact projection (Hungarian) 11.4 ms at N = 1000 and 30 ms at N = 2000 | `e3_latency.py` | `e3_latency.csv` |
| RQ5: allocator rate 5.01 Hz; the predictive rule cuts exposure by 8.1× and leaves 0 exposures without a jump; hysteresis bound held for 100% of aircraft | `e4_dynamics.py` | `e4_lookahead.csv`, `e4_hysteresis.csv` |
| RQ6: population lift exact under independence (0.934 predicted, 0.927 simulated); under common-cause jamming it puts the loss of six or more tasks at 6.5% against 24.1%, 3.7× too low; N⋆ = 15 | `e2_degradation.py` | `e2_lift.csv`, `e2_fleet_sizing.csv` |
| Replay of measured traces: 11 PX4 flight logs; with common-cause jammers the independent model puts the loss of six or more tasks at 6.5% against 20.8% simulated (3.2×); CBBA 0.546, our layer 0.505 [0.495, 0.513] with zero training violations | `r3_extract_traces.py`, `e2_degradation.py --process trace`, `e5_marl.py --process trace` | `r3_staleness_traces.csv`, `r3_trace_summary.csv`, `e2_lift_trace.csv`, `e5_marl_trace/`, `e6_main_e5_marl_trace.csv` |
| RQ7: honest aircraft executed 0 violations, liars 4,819; the complete graph agreed in every instance within 6 rounds; the ring-plus-chords meshes agreed with two equivocating liars in only 26%, 51% and 74% of instances | `r5_consensus.py` | `r5_consensus.csv`, `manuscript/tab_r5.tex` |
| Vector certificates: at N = 12 and dispersion 0.5, 74% of exact eligibility graphs nested and the scalar surrogate lost 0.65 of 8 tasks on average | `r6_vector.py` | `r6_vector.csv` |
| RQ8, first flight campaign: 0 infeasible assignments over 9,462 aircraft-epochs; the oracle found 89 violations of the premise, 75 of them in 2 reacquisition episodes, peak 13.9 m against ρ_i = 0.96 m | `r4_sitl_fleet.py`, `r4_analysis.py` | `r4_sitl.csv`, `r4_sitl_summary.csv`, `r4_injections.csv`, `r4_soundness.csv`, `r4_soundness_violations.csv`, `r4_px4_events.csv`, `r4_analysis.csv` |
| RQ8, pre-registered rerun: latch cut the worst excess from 5.2 m to 0.22 m, 70 violations remained (criterion failed); third run with θ_ben = 0.206 s, floor 1.09 m: 0 violations over 374,578 samples and 10 reacquisitions, receiver certificate 53 | `r4_sitl_fleet.py`, `r4b_analysis.py`, `r4b_analysis.py --run r4c` | `r4b_*.csv`, `r4c_*.csv` (incl. `r4c_calibration.csv`, `r4c_calibration_logs.csv`), `r4b_analysis.csv`, `r4c_analysis.csv` |
| Sensitivity of the learning study: our layer executed no infeasible assignment in training under any setting, coverage ratio at least 0.99; every PPO-Lagrangian setting at least 1,866,671 | `e5_marl.py` (`run_r_marl.sh` block `r9`) | `r9/`, `e6_main_r9.csv`, `manuscript/tab_r9.tex` |

Every constant of the certificate is listed with its provenance (measured, derived or assumption)
in `constants_paperIII.csv`, and the measured-trace, flight, consensus and vector-certificate files
carry a `provenance` column. The certificate's measured inputs come from the shared `results/`
directory at the repository root, which ships with this artifact: `certificate.py` reads the
relay-hop residuals and the γ samples from those files and takes L from
`results/local_lipschitz.csv`. `r5_consensus.py` samples its meshes with the platform's mesh
generator in `platform/backend/app/corpus.py`, which is included for that purpose.

The extended aggregations and the two remaining studies are regenerated, from
`paperIII/experiments/`, by:

```bash
for d in e5_marl_N24 e5_marl_N48 e5_marl_N96 r9; do python3 e6_aggregate.py --dir $d; done   # ~30 s
python3 r5_consensus.py                                     # Byzantine agreement, ~6 min
python3 r6_vector.py                                        # vector certificates, ~5 min
python3 export_figdata.py && python3 make_numbers.py
git status --short    # expected: results/r6_vector.csv and manuscript/numbers.tex only
```

The aggregations and `r5_consensus.py` reproduce the committed files exactly. `r6_vector.py`
also times the brute-force worst case against the closed form, so its four timing columns and the
three macros `\nVecBruteEight`, `\nVecBruteTwenty` and `\nVecClosed` reflect your machine; every
coverage and nestedness value is unchanged. The measured-trace references and lift are equally
cheap: `python3 e5_marl.py --references --process trace --outdir e5_marl_trace` (~10 s) and
`python3 e2_degradation.py --process trace` (~3 s) both reproduce their committed files.

## 3. The learning study

All learning runs are CPU-only PPO-style training of a parameter-shared actor (Appendix
"Hyperparameters" of the paper) in the `CertSwarm` environment (`certcmdp/env.py`). Each run
writes `<method>_s<seed>_train.csv` (per-update coverage, violations, cumulative violations and
wall-clock time `wall_s`) and `<method>_s<seed>_eval.csv` (held-out evaluation), both committed.

```bash
cd paperIII/experiments
bash run_marl.sh                 # headline N = 12: 5 methods x seeds 0-4, ~1 h on 2 cores
PAR=4 bash run_r_marl.sh         # stronger baselines, headline seeds 5-9, fleet size, sensitivity: ~6 h on 4 cores
PAR=4 bash run_r1_kbs.sh && bash run_r1_kbs24.sh   # scaled keep prior at N = 24, 48, 96: ~1.5 h on 4 cores
for d in e5_marl_N24 e5_marl_N48 e5_marl_N96 r9; do python3 e6_aggregate.py --dir $d; done
python3 e6_aggregate.py && python3 export_figdata.py && python3 make_numbers.py
```

| Block | Runs | Recorded compute (sum of `wall_s`) |
|---|---|---|
| Headline, seeds 0–4 (`run_marl.sh`) | 25 | 2.0 CPU-hours, about 5 min per run |
| Headline, seeds 5–9 (`run_r_marl.sh`, block `n12`) | 25 | 2.0 CPU-hours |
| Stronger baselines: MAPPO-Lagrangian at two cost limits, PID-Lagrangian, QMIX with and without masks, 10 seeds (block `r2`) | 50 | 4.2 CPU-hours |
| Fleet size N = 24, 48 (5 seeds) and 96 (3 seeds, pointer actor) (block `r1`) | 52 | 11.0 CPU-hours, of which 7.2 at N = 96 |
| Sensitivity, 3 seeds per value (block `r9`) | 42 | 3.3 CPU-hours |
| Scaled keep prior (`run_r1_kbs.sh`, `run_r1_kbs24.sh`) | 26 | 5.5 CPU-hours |
| Replay of measured traces (`run_server_paperIII.sh r3`) | 12 | 0.9 CPU-hours |

`run_r_marl.sh` is resumable: it skips any job whose `*_eval.csv` already exists, so on the
committed tree it trains nothing and only re-runs the cheap N = 12 references. To retrain a
block, move its directory aside first, for example `mv ../results/r9 ../results/r9_committed`.
Training is seeded per run and single-threaded: on a different CPU and PyTorch version than ours,
the first updates of a retrained run match the committed `*_train.csv` digit for digit; over a
full run, floating-point differences between CPUs and library versions can accumulate. The
trained actors (`*_actor.pt`) are left out of the artifact for size; every number in the paper
comes from the train and eval CSVs.

A short run checks the pipeline in about 10 seconds; its three rows equal the first three rows
of `results/e5_marl/ours_s0_train.csv` (except `wall_s`):

```bash
python3 e5_marl.py --method ours --seed 0 --updates 3 --outdir _smoke
head -4 ../results/_smoke/ours_s0_train.csv; head -4 ../results/e5_marl/ours_s0_train.csv
rm -r ../results/_smoke
```

## 4. Flight experiments and pre-registration

RQ8 tests the certificate premise in closed loop: six PX4 v1.14.3 quadrotors in software in the
loop (SIH, physics inside PX4, headless), driven in offboard mode by `r4_sitl_fleet.py`, with the
projection allocating at 5 and 2 Hz for 240 s each and scheduled GNSS outages. After each flight,
the same script checks the certificate against PX4's logged ground-truth position at every logged
sample (`--soundness-only`).

| Campaign | Protocol | Outage schedule | Analysis | Result files |
|---|---|---|---|---|
| First flight campaign | — | `SCHEDULE` | `r4_analysis.py` | `r4_*.csv` |
| Pre-registered rerun (latched certificate) | `paperIII/R4B_PROTOCOL.md` | `SCHEDULE_B` | `r4b_analysis.py` | `r4b_*.csv` |
| Pre-registered third run (latch and receiver-calibrated floor) | `paperIII/R4C_PROTOCOL.md` | `SCHEDULE_C` | `r4b_analysis.py --run r4c` | `r4c_*.csv` |

Each protocol fixes the rule, the outage schedule, the primary and informativeness outcomes and
the pass criterion before its flight, and records the date on which it was committed, before the
run; the artifact's history is a single fresh commit, so that date is the one stated in the file.
The analysis applies the criterion mechanically and writes the verdict (`fail` for the rerun, `pass`
for the third run) into `r4b_analysis.csv` and `r4c_analysis.csv`. The third run's calibration was
computed once from the logs of the two earlier campaigns and committed before its flight
(`r4c_calibration.csv`, `r4c_calibration_logs.csv`). Its first attempt aborted before flight when
PX4 denied arming one aircraft; that attempt's driver log and soundness file are in
`results/server_logs/` (`r4c_attempt1_*`), next to the driver and soundness logs of every
campaign.

Everything the paper reports from these flights is regenerated by the Quick check from the
committed CSVs. Flying them again needs a Linux machine with Docker (we used 4 vCPUs), a Python
environment with `numpy scipy pyulog 'mavsdk<4'`, and network access to clone PX4 v1.14.3 and pull
the `px4io/px4-dev-simulation-jammy` image:

```bash
bash paperIII/experiments/run_server_paperIII.sh r4    # first campaign; the first PX4 build takes about an hour
bash paperIII/experiments/run_server_paperIII.sh r4b   # pre-registered rerun
bash paperIII/experiments/run_server_paperIII.sh r4c   # pre-registered third run
```

Each campaign then takes about 10 minutes (two 240 s flights, take-off, landing and the log
check). The script moves earlier PX4 logs aside instead of deleting them, so the calibration of
the third run can be recomputed from the first two (`r4_sitl_fleet.py --calibrate`).

The same script runs the two other server stages. `e3` repeats the latency measurement on an idle
machine and records the load and CPU (`results/server_logs/2026-10-14/`). `r3` extracts the GNSS
staleness traces of the measured-trace replay from the public UAV attack dataset cited in the
paper; stage its flight logs under `data/raw/uav_attack_whelan/` (or pass
`r3_extract_traces.py --root <dir>`). The address of the aggregated mirror that
`data/fetch_kaggle.py` downloads is withheld during review, because it identifies the authors.
The extracted traces (`r3_staleness_traces.csv`) are committed, so the trace-driven lift and
learning runs need no download.

## 5. Extensions

The code is set up for the following extensions. Each writes its results next to the committed
ones, and where a run replaces a committed result file, `make_numbers.py` carries the new values
into the paper without any edit to the text.

- **Larger learning budgets.** The fleet-size study refers to budgets of 400 updates for
  N ≤ 24 and 600 for N ≥ 48. `run_r_marl.sh` reads its budget from the environment (`UPDATES`
  for N ≤ 48, `UPDATES_N96` for N = 96) and trains every size whose results are absent, so these
  budgets run with the committed code (from `paperIII/experiments/`):

  ```bash
  mv ../results/e5_marl_N24 ../results/e5_marl_N24_u200
  UPDATES=400 BLOCKS=r1 PAR=4 bash run_r_marl.sh
  mv ../results/e5_marl_N48 ../results/e5_marl_N48_u200 && mv ../results/e5_marl_N96 ../results/e5_marl_N96_u150
  UPDATES=600 UPDATES_N96=600 BLOCKS=r1 PAR=4 bash run_r_marl.sh
  ```

  At the recorded run times this is about 40 CPU-hours, most of it at N = 96. The scaled-prior
  scripts carry their budget in their command lines (`--updates`).
- **A keep term in the projection.** `certcmdp.combinatorics.lexicographic_projection` already
  takes the previous assignment and a weight `eps_prev`, added to the agreement level of the
  weights W without disturbing the lexicographic order; the environment calls it with
  `eps_prev=0.0` (`certcmdp/env.py`), the setting of every reported run. A positive value is the
  keep term the paper names as the remedy for reassignment churn at large N.
- **Embedded latency.** `python3 e3_latency.py --board pi5` (or `orin_nano`) runs the latency
  study unchanged on a companion computer and writes `results/e3_latency_<board>.csv`.
- **Further learners.** New learners plug into the `METHODS` table of `e5_marl.py` and share the
  environment, the step budget, the evaluation and the aggregation; MACPO's second-order update is
  the natural next one.
- **Adversarial outage timing.** The outage schedules of the flights are plain tables of vehicle,
  onset and duration in `r4_sitl_fleet.py` (`SCHEDULE`, `SCHEDULE_B`, `SCHEDULE_C`). A jammer
  that chooses when the fix returns, and so when the reacquisition window of RQ8 opens, is written
  as such a table, and the soundness oracle checks it unchanged.
- **Other receivers and simulators.** The benign floor is recalibrated for any receiver from its
  own logs with `r4_sitl_fleet.py --calibrate <log dirs>`, by the definition the paper uses. The
  driver already issues PX4's falsified-fix failure injection (the `wrong` entries of `SCHEDULE`)
  and logs whether the simulator accepts it, so a simulator that accepts it adds the spoofing case
  to the same oracle.

## 6. Layout

```
paperIII/experiments/      certcmdp/ (certificate.py, combinatorics.py, env.py, trace_process.py),
                           e1_verify.py, e2_degradation.py, e3_latency.py, e4_dynamics.py,
                           e5_marl.py, e6_aggregate.py, r3_extract_traces.py, r4_sitl_fleet.py,
                           r4_analysis.py, r4b_analysis.py, r5_consensus.py, r6_vector.py,
                           export_figdata.py, make_numbers.py, run_all.sh, run_marl.sh,
                           run_r_marl.sh, run_r1_kbs.sh, run_r1_kbs24.sh, run_server_paperIII.sh
paperIII/results/          result files (CSV); e5_marl*/ and r9/ hold the learning runs;
                           server_logs/ holds the driver, soundness and server logs
paperIII/manuscript/       main.tex (IEEEtran), sec_results_marl.tex, fig_framework.tex, refs.bib;
                           numbers.tex, tab_*.tex and figdata/ are generated
paperIII/R4B_PROTOCOL.md   pre-registration of the rerun of the flight experiment
paperIII/R4C_PROTOCOL.md   pre-registration of the third flight run
results/                   shared measured inputs of the certificate (hop ledger, γ samples,
                           local Lipschitz estimate)
platform/backend/app/      mesh generator used by the consensus study
data/fetch_kaggle.py       staging script for the public corpus (address withheld during review)
```
