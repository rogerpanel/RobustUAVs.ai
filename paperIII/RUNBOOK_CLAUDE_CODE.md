# Paper III — Claude Code Runbook

**Paper:** *Certificates as Constraints: Feasibility-Preserving Multi-Agent Reinforcement Learning for UAV Swarms Whose Guarantees Degrade* (target: NeurIPS, main track)
**Repository:** `rogerpanel/RobustUAVs.ai`, branch `claude/whelan-uavcas-ingest-u00isn`
**Folder:** `paperIII/` (`experiments/`, `results/`, `manuscript/`)

This runbook tells a Claude Code session exactly how to scale up, extend and harden the experiments that the drafting sandbox (2 CPU cores, 7 GB RAM, no GPU, no simulator) could only run in compact form. Every experiment writes a CSV to `paperIII/results/`. `make_numbers.py` turns those CSVs into LaTeX macros in `manuscript/numbers.tex` and into `manuscript/tab_main.tex`, and `export_figdata.py` writes `manuscript/figdata/*.dat`. **Never type a number into `main.tex`.** Re-run the pipeline instead.

---

## 0. What is already done (do not redo)

| Script | Output | What it establishes | Runtime (2 cores) |
|---|---|---|---|
| `certcmdp/certificate.py` | `constants_paperIII.csv` | κ = L_ρ = e^{LT}·γ_sup = 5.30 m/s; benign floor 0.94 m; hidden-residual pools from the 15,392-hop ledger | 1 s |
| `e1_verify.py` | `e1_verify.csv` | Every closed form against a brute-force oracle: 0 disagreements over ~76k checks | 80 s |
| `e2_degradation.py` | `e2_collapse.csv`, `e2_graded.csv`, `e2_lift.csv`, `e2_fleet_sizing.csv` | Coverage vs φ; exact worst case (graded bound tight in 100% of instances); i.i.d. lift fails under spatial jammers (P(d≥4) underestimated ≈4.6×) | 60 s |
| `e3_latency.py` | `e3_latency.csv` | Monitor 6 ms and greedy projection 40 ms at N = 10⁵; exact Hungarian 53 ms at N = 2000 | 55 s (**run on an idle machine**) |
| `e4_dynamics.py` | `e4_hysteresis.csv`, `e4_lookahead.csv`, `e4_liars.csv` | Predictive rule: exposure without jumps = 0; at 5 Hz it costs no coverage | 40 s |
| `e5_marl.py` (+ `run_marl.sh`) | `results/e5_marl/*` | 5 methods × 5 seeds × 200 PPO updates on N = 12, M = 8, plus non-learned references | ≈ 65 min |
| `e6_aggregate.py` | `e6_main.csv`, `e6_curves.csv` | IQM + stratified-bootstrap CIs, Clopper–Pearson bounds | 5 s |

Regenerate all of it with:

```bash
cd paperIII/experiments
bash run_all.sh                         # E1–E4, references, aggregation, numbers (≈ 5 min)
SEEDS="0 1 2 3 4" UPDATES=200 PAR=2 bash run_marl.sh   # E5 (≈ 1 h on 2 cores)
cd ../manuscript && latexmk -pdf main.tex
```

**Known weak points, in the order they would worry a NeurIPS reviewer:**

1. The MARL study is small: 12 aircraft, 5 seeds, CPU only, 4.8 × 10⁵ fleet-epochs per run. The guarantees do not depend on it, but the comparative return claims do. **R1 is load-bearing.**
2. Baselines are re-implemented in a compact form: PPO-Lagrangian with plain dual ascent and no PID; no MACPO, QMIX or shielded MADDPG. **R2 is load-bearing.**
3. Threat *rates* are modelling assumptions; only magnitudes are measured. R3 replays measured traces instead.
4. No flight-dynamics simulator. R4 (PX4 SITL) closes this.

---

## 1. Ground rules for every experiment

1. **Placement.** New code goes in `paperIII/experiments/` and outputs in `paperIII/results/`. Each new CSV carries a `provenance` column: `measured | derived | assumption | sim | sitl | hardware`.
2. **Do not touch the guarantee code paths without re-verifying.** After any change to `certcmdp/combinatorics.py`, run `python3 e1_verify.py`. It must report **0 disagreements** on every row. If it does not, stop and fix the code: never relax the check.
3. **Report statistics properly.**
   - Report IQM with 95% stratified-bootstrap CIs, using `e6_aggregate.py` or `rliable`.
   - Report per-step violation counts, never episode averages.
   - When zero violations are observed, report the exact Clopper–Pearson upper bound together with the exposure in agent-epochs.
4. **Keep latency clean.** Run `e3_latency.py` and any latency study on an otherwise idle machine. Record the CPU model; the script does this.
5. **Commit per experiment.** Use a message of the form `paperIII: R<n> <short result>` and put the CSV diff summary in the body.
6. **Report honestly.** If a factor could not be varied, write "not varied". If a learned method does not beat the keep-or-nearest + projection heuristic, say so: the paper's claims are the guarantees, and the learning study is supporting evidence.

---

## 2. Environment

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install numpy scipy networkx torch pandas
# for R2: pip install safepo omnisafe   (or clone PKU-Alignment/Safe-Policy-Optimization)
# for R1-GPU: pip install "jax[cuda12]" flax optax   (optional JAX port)
```

Memory: the compact study peaks below 1 GB per process. If the machine is memory-limited, set `PAR=1` in `run_marl.sh`, or reduce `B` (parallel fleets) in `e5_marl.py::train` from 16 to 8 and double `--updates`.

---

## R1 — Scale the MARL study (RQ1, RQ3) **[load-bearing]**

**Goal.** Show that the projection-in-environment result (zero training violations, coverage ratio near 1, competitive certified coverage) holds at larger fleets and with more seeds.

**Grid.**
- N ∈ {12, 24, 48, 96}, with M = ⌈2N/3⌉ and the arena side scaled by √(N/12).
- Spatial jammers: 2 for N = 12, scaled ∝ N/12.
- Seeds: 10 per cell, 20 for the N = 12 headline.
- Updates: 400 (N ≤ 24), 600 (N ≥ 48).

**Changes.**
1. Add `--N --M --updates --arena` CLI flags to `e5_marl.py`, writing to `results/e5_marl_N{N}/`.
2. For N ≥ 48, replace the MLP actor with a permutation-invariant one, so input size does not grow with M. Use attention over the K = 16 nearest tasks (pointer-style head) plus mean-pooled fleet context, as in Wang & Gombolay's graph-attention schedulers.
3. Keep the projection exact (Hungarian) up to N = 96. Its latency is < 2 ms there (see `e3_latency.csv`).
4. GPU option: port `CertSwarm` to JAX (`jax.lax.scan` over epochs). The projection then runs on CPU via `jax.pure_callback`. Alternatively use VMAS for the motion part and keep `certcmdp` for certificate and projection.

**Outputs.** `results/e5_marl_N{N}/<method>_s<seed>_{train,eval}.csv`. Generalise `e6_aggregate.py` with a `--dir` flag, and write `e6_main_N{N}.csv`.

**Acceptance.**
- `ours`, `ours_nodev` and `mask` report **0** training violations at every N.
- `ours` has coverage ratio ≥ 0.95 at every N.
- Report where, or whether, `ours` beats `heuristic+proj` on certified coverage.

**Manuscript hook.** Add a figure "certified coverage and coverage ratio vs N" to §5 (RQ3), and replace "compact study" in §6 Limitations.

---

## R2 — Stronger baselines (RQ1, RQ3) **[load-bearing]**

Implement a PettingZoo `ParallelEnv` wrapper `certcmdp/pz_env.py` around `CertSwarm`: per-agent obs, discrete actions {KEEP, IDLE, k-th nearest task}, info carrying `cost` and `viol`. Then run:

| Baseline | Source | Notes |
|---|---|---|
| MAPPO-Lagrangian, MACPO | `PKU-Alignment/Safe-Policy-Optimization` (SafePO) multi-agent module | cost = `info["cost"]`, cost limit 0.005 / agent-epoch, plus a 0.0 variant |
| PID-Lagrangian PPO | Stooke et al. 2020 (OmniSafe `CPPOPID`) | single-agent over the joint action is infeasible; use the parameter-shared version |
| QMIX (+ action masks) | EPyMARL or JaxMARL | report with and without the projection at deployment |
| Shielded MADDPG | ElSayed-Aly et al. 2021 factored shield = our per-agent mask + conflict resolution | continuous relaxation of the categorical action via Gumbel-softmax |
| CBBA | Choi, Brunet & How 2009 | decentralised, non-learned; score = value − distance cost; feasibility enforced in the bundle |

**Outputs.** `results/e5_marl/<baseline>_s<seed>_{train,eval}.csv`, in the same schema. `e6_aggregate.py` picks them up automatically. Add display names in `make_numbers.py::names`.

**Acceptance.** Every in-expectation method reports a non-zero training violation count, or else its cost limit was 0 and its coverage collapsed. Report both.

---

## R3 — Measured-trace certificate replay (RQ2, RQ6)

**Goal.** Replace the Poisson onset model with measured staleness traces.

1. Stage the corpus: `python3 data/fetch_kaggle.py --copy`. The Whelan UAV Attack Dataset gives PX4 logs of benign, jamming and spoofing flights.
2. From each attacked flight, extract the per-epoch staleness Δ(t): time since the last fix with `fix_type ≥ 3` that the estimator fused, with the receiver timestamps aligned to `vehicle_gps_position`. From the hop ledger (`results/hop_ledger.csv`), take per-packet residual time series ordered by `packet`.
3. Write `certcmdp/trace_process.py` with the same interface as `CertificateProcess` (`rho()`, `step(dt, jam_mask)`). It samples a trace segment per aircraft with random offsets and sets ρ = κ·(benign + Δ_trace + relay_trace).
4. Re-run E2 part (c) and E5 with `--process trace`.

**Output.** `results/e2_lift_trace.csv` and `results/e5_marl_trace/…` (`provenance=measured`).
**Acceptance.** Report how far the trace-driven class law q differs from the synthetic one, using total variation distance. Report whether the O1 failure persists. With traces from separate flights, aircraft are independent by construction, so add spatial jammers on top as in E2.

---

## R4 — PX4 SITL multi-vehicle vignette (RQ5; sim-to-real path)

**Setup** (identical toolchain to Paper I E3):

```bash
git clone --recursive https://github.com/PX4/PX4-Autopilot.git && cd PX4-Autopilot
git checkout v1.14.3
# multi-vehicle Gazebo: Tools/simulation/gz/... or sitl_multiple_run.sh with 6 x500 instances
pip install mavsdk pymavlink
```

**Driver.** Write `paperIII/experiments/r4_sitl_fleet.py`:
1. Spawn 6 vehicles and 4 task sites with alert limits {2, 5, 10, 20} m.
2. Run the allocator (`certcmdp.combinatorics.lexicographic_projection` with `keep_lookahead = κ·Δt`, `lookahead = κ·Δt`) at 5 Hz and 2 Hz. Send offboard position setpoints to the assigned sites.
3. Compute ρ_i(t) online from the vehicle's GPS staleness (time since the last accepted fix in `vehicle_gps_position`) via `certificate.rho_of_staleness`.
4. Inject jamming: drop the GPS stream for one vehicle via the SITL failure injection `failure gps off`. Inject spoofing by reusing Paper I E3's `GPS_INPUT` offset ramp.
5. Log the true position from `vehicle_local_position_groundtruth`.

**Measure.**
- Executed violations (must be 0).
- Inter-epoch exposure, with and without jumps.
- Realised position error versus ρ_i(t). This is a *soundness check of the parent certificate in closed loop*: report any sample with error > ρ_i(t).
- Certified coverage.

**Output.** `results/r4_sitl.csv` (`provenance=sitl`).
**Acceptance.**
- 0 executed violations.
- Exposure without jumps equals 0 at 5 Hz.
- Report the soundness check as-is; do not filter.

**Manuscript hook.** One paragraph and one small table in §5 (RQ5), and remove "simulation only" from Limitations if this passes.

---

## R5 — Decentralised count consensus with misreporting aircraft (Prop. 6)

Implement W-MSR resilient consensus (LeBlanc et al. 2013) on the count profile (n_k) over the mesh graph from `platform/backend/app/corpus.py::sample_mesh`, with f ∈ {0, 1, 2} Byzantine aircraft. Measure:
- the rounds needed to agree;
- the error in d (must be ≤ f);
- the extra violations, which must come only from the liars.

**Output.** `results/r5_consensus.csv`.

---

## R6 — Vector certificates: where the closed forms stop (Remark 1)

Give each aircraft (ρ_h, ρ_v) and each task (α_h, α_v), with eligibility by dominance. Compare:
- Hopcroft–Karp maximum matching (exact) against the scalar surrogate max(ρ_h/α_h, ρ_v/α_v);
- brute-force b-robustness against the scalar margin.

Report the coverage lost by the surrogate and the brute-force time growth.

**Output.** `results/r6_vector.csv`.

---

## R7 — Learned jammer adversary (RQ2)

Train a jammer-placement policy, in the style of Pinto et al. 2017 (RARL), with K jammers and a budget, to maximise fleet deficiency against a frozen `ours` policy. Compare the achieved d with the closed-form worst case of Prop. 2 for the induced degradation.

**Acceptance.** The learned adversary never exceeds the closed-form worst case. If it ever does, there is a bug: check `e1_verify.py`.

**Output.** `results/r7_adversary.csv`.

---

## R8 — Embedded latency

Run `e3_latency.py` unchanged on a Raspberry Pi CM4/5 and a Jetson Orin Nano, as candidate companion computers.

**Output.** `results/e3_latency_<board>.csv`. Add one curve per board to Fig. 3.

---

## R9 — Sensitivity

Sweep the following and report IQM certified coverage and training violations:

| Parameter | Values |
|---|---|
| λ_dev | {0, 0.02, 0.05, 0.1, 0.2} |
| keep-logit prior | {0, 1, 3} |
| Lagrangian cost limit | {0, 0.001, 0.005, 0.02} |
| dual step | {0.1, 1, 5} |
| threat rates | ×{0.5, 1, 2} |

**Output.** `results/r9_sensitivity.csv`, with a table in the appendix.

---

## 3. Building and submitting

```bash
cd paperIII/experiments && bash run_all.sh
cd ../manuscript && latexmk -pdf main.tex
```

1. **Style file.** Download the official NeurIPS style (`neurips_2027.sty` when released) into `paperIII/manuscript/`. `main.tex` picks it up automatically, and falls back to an equivalent article layout otherwise.
2. **Bibliography.** Check every `% CHECK` entry in `refs.bib` against the publisher page.
3. **Anonymity.** Build from the anonymised tree: `python3 tools/anonymise.py --out ../RobustUAVs-anon --init-git --zip`, then rebuild the PDF there. The companion papers are cited as anonymous (`parentpaper`, `paperI`, `paperII`).
4. **Checklist.** Fill in the NeurIPS paper checklist. Answers already supported:
   - **Proofs:** Appendix A.
   - **Code and data:** this folder.
   - **Compute:** Appendix C plus `wall_s` in the train CSVs.
   - **Error bars:** IQM with stratified-bootstrap 95% CIs.
   - **Limitations:** §6.
   - **Broader impact:** §6.
