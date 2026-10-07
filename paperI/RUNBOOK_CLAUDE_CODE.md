# Paper I — Claude Code Runbook

**Paper:** *What Authenticity Costs in Metres: A Certified Budget for Cryptography and Sensing in UAV Navigation*
**Repository:** `rogerpanel/RobustUAVs.ai`, branch `claude/whelan-uavcas-ingest-u00isn`
**Folder:** `paperI/` (experiments, results, manuscript)

This runbook tells a Claude Code session exactly what to run for the experiments that could **not** be run in the drafting sandbox. They need the raw Kaggle corpus, a PX4 simulator, or real hardware. Every experiment here writes a CSV that `paperI/experiments/make_numbers.py` turns into LaTeX macros. The manuscript therefore updates itself when a result changes: never type a number into `main.tex` by hand.

---

## 0. What is already done (do not redo)

`paperI/experiments/run_all.sh` regenerates the following from committed inputs, in about 30 s on a laptop:

| Script | Result files | Inputs | Provenance |
|---|---|---|---|
| `transport.py` | `transport_frames.csv`, `transport_cliff.csv`, `transport_des.csv` | HCRL benign rates (`results/hcrl_type_signatures.csv`), frame models | measured U0 + physics_model |
| `budget.py` | `gamma_ratio.csv`, `dead_reckoning_fit.csv`, `dauth.csv`, `crossover*.csv`, `horizon_*.csv`, `parent_table.csv` | 674 real γ samples (`results/gamma_campaign_samples.csv`), literature cycle counts | measured / derived / literature |
| `clock_freshness.py` | `clock_holdover.csv`, `freshness_binding.csv`, `time_push.csv` | MAVLink + OSNMA specs, oscillator classes | literature + physics_model |
| `induced_verification.py` | `iv_amplification.csv`, `induced_verification.csv` | as above | physics_model (DES) |
| `amortise_select.py` | `amortisation.csv`, `selection.csv` | as above | derived |
| `export_figdata.py` / `make_numbers.py` | `manuscript/figdata/*.dat`, `manuscript/numbers.tex` | all of the above | — |

The weakest inputs, in order of how much they move the headline, are:

0. **The authenticated rate γ_a is a proxy.** It is taken from the Whelan jamming flight. An independent review found that this flight's receiver keeps fix_type = 3 with 12–14 satellites throughout every post-onset sample, so it measures a *degraded but still-fused* estimator, not one that has rejected GNSS. **E1 and E3 are therefore load-bearing, not optional.** They measure dead reckoning after rejection directly. The same observation contradicts the parent paper's sentence that under jamming "the estimator gates the missing fix and dead-reckons"; flag this to the author.
1. **Cycle counts.** Literature values from Cortex-M4/M7 at 24 MHz, scaled to 480 MHz. E4 replaces them.
2. **γ_u at short staleness.** One spoofing flight, with an attacker-chosen walk-off rate. E3 replaces this with a swept SITL spoofer, and also adds **cruise**.
3. **The DroneCAN frame model and bitrate.** HCRL bitrate is assumed 1 Mbit/s. E5 checks it against raw frames.

---

## 1. Ground rules for every experiment

1. **New code** goes in `paperI/experiments/` and **outputs** go in `paperI/results/`. Each output row carries a `provenance` column: `measured | derived | literature | physics_model | sitl | hardware`.
2. **Never overwrite a literature value silently.** Add the measured value next to it, then switch `constants.py` to read the measured CSV when present. Keep the literature value as the fallback and record which one was used in `results/provenance_paperI.csv`.
3. **After any change**, run `bash paperI/experiments/run_all.sh`, then build the paper:
   `cd paperI/manuscript && latexmk -pdf main.tex`
4. **Commit per experiment.** Use a message of the form `paperI: E<n> <short result>` and include the CSV diff summary in the body.
5. **Report "not varied" honestly.** If a factor could not be varied, say "not varied". Do not write "no effect".

---

## 2. Data staging (needed by E1, E5)

```bash
pip install kagglehub numpy scipy pandas pyulog
# credentials: ~/.kaggle/kaggle.json  or  KAGGLE_USERNAME / KAGGLE_KEY
python3 data/fetch_kaggle.py --copy
ls data/raw/uav_attack_whelan/*/   # expect gps.csv, local.csv, maybe more topics
ls data/raw/hcrl_uavcan/           # expect type1..type10 *_label.bin / csv
```

If the Whelan folders contain only `gps.csv` and `local.csv`, look for the original `.ulg` files in the Kaggle bundle. Run `ulog2csv <file>.ulg` and keep `sensor_combined`, `vehicle_local_position`, `estimator_status` (or `estimator_states`), and `vehicle_gps_position`.

---

## E1 — Inertial (dead-reckoning) γ from real logs (RQ1)

**Goal.** Measure how fast the PX4 estimate degrades when GNSS is withheld (true rejection), on real IMU data. This replaces the jamming-flight proxy for γ_a, which never lost its fix. The current fit (`dead_reckoning_fit.csv`, v0 ≈ 0.86 m/s) characterises the proxy only.

**Method (synthetic outage on benign flights).**
1. Take the **benign** Whelan flight. Pick N = 200 onset times uniformly in its steady segment, avoiding the first and last 10 s.
2. At each onset t0, freeze position and velocity at the EKF state. Integrate `sensor_combined` accelerometer readings, rotated into NED using the logged attitude, for τ ∈ [0, 20] s. Use the EKF bias estimates at t0 if logged.
3. Use the GNSS-aided EKF position as ground truth. Record e(τ) = ‖p_DR(τ) − p_EKF(τ)‖ and γ_δ(τ) = (e(τ) − e(0))/τ.
4. Report the supremum, p95 and median per τ bin, using the same bins as `gamma_campaign_bins.csv`.

**Script:** `paperI/experiments/e1_inertial_gamma.py`
**Output:** `paperI/results/e1_inertial_gamma.csv` with columns `tau_bin, n, gamma_sup, gamma_p95, gamma_med, provenance=measured`.
**Acceptance:** none on the value; report it as measured.
- If γ_DR(τ ≤ 1 s) differs from the proxy (≈ 0.9 m/s) by more than its bootstrap interval, rerun `run_all.sh` with γ_a = γ_DR.
- Report which conclusions in Sections V-A and V-C change.

**Manuscript hook:** Table "gamma sources" and Fig. `fig:gamma`. Add the `gamma_ins.dat` series in `export_figdata.py`.

---

## E2 — Visual–inertial γ (RQ1, strengthens; not load-bearing)

**Goal.** Measure γ_VIO, the error rate of a visual–inertial source when GNSS is absent.

**Method.**
1. Use EuRoC MAV (all 11 sequences) and, if time allows, UZH-FPV.
2. Preferred: take published estimator trajectories if available in `uzh-rpg/rpg_trajectory_evaluation`. Fallback: run OpenVINS in Docker (`rpng/open_vins`) on each sequence.
3. Compute relative error over sub-trajectories of durations τ ∈ {0.5, 1, 2, 5, 10} s, not lengths. Use `evo_rpe` with `--delta-unit s`, after SE(3) alignment of each segment start. Report γ_VIO(τ) = RPE_trans(τ)/τ.

**Output:** `paperI/results/e2_vio_gamma.csv` with columns `dataset, sequence, tau_s, n, gamma_sup, gamma_p95, gamma_med, provenance=measured`.
**Acceptance:** results reported per sequence, plus the supremum over sequences.

---

## E3 — PX4 SITL: spoofer walk-rate sweep, authenticated rejection, and cruise (RQ1, RQ3; also closes the parent's cruise gap)

**Why it matters most.** The horizon-matched crossover (`horizon_crossover.csv`) shows that at θ = 0.25 s, authentication costs a few centimetres, because the observed spoofer had not yet out-run dead reckoning within 0.5 s. That conclusion belongs to **one** spoofer on **one** hover flight. A faster spoofer, still inside the EKF innovation gate, moves the crossover left. This experiment maps that dependence and adds cruise.

**Setup.**
```bash
git clone --recursive https://github.com/PX4/PX4-Autopilot.git && cd PX4-Autopilot
git checkout v1.14.3         # or the version closest to the Whelan logs (v1.11.3)
make px4_sitl gz_x500        # headless: HEADLESS=1
pip install pymavlink mavsdk
```

**Spoofer.** Add a SITL GPS plugin offset. Simplest is a MAVLink `GPS_INPUT` injector with `EKF2_GPS_CTRL` fed from a fake GPS, or patch `SensorGpsSim` to add an offset ramp. The offset ramp is d(t) = v_s · (t − t0), with walk rate v_s ∈ {0.5, 1, 2, 4, 8, 16} m/s and direction randomised per run.

**Authenticated arm.** Same runs, but at t0 the GPS stream is **rejected**, emulating a failed signature check. Do this by stopping `GPS_INPUT`, or by setting `EKF2_GPS_CTRL=0` with a parameter set at t0. This is the "authenticated GNSS under spoofing = dead reckoning" mechanism the paper relies on.

**Flight regimes.** Hover, and straight cruise at {5, 10, 15} m/s (mission mode, waypoints 1 km apart).

**Measure.** e(τ) of the EKF position against SITL ground truth (`vehicle_local_position_groundtruth`), τ ∈ [0, 20] s. Use 20 runs per cell.

**Script:** `paperI/experiments/e3_sitl_spoof_sweep.py` (MAVSDK driver + `pyulog` parsing).
**Output:** `paperI/results/e3_sitl_envelopes.csv` with columns `regime, speed, walk_rate, arm{unauth,auth}, tau, e_sup, e_p95, n, provenance=sitl`.
**Then:**
- Extend `budget.py::horizon_matched` to read SITL envelopes when present.
- Write `horizon_crossover_sitl.csv` with θ_cross per (walk_rate, regime, scheme).

**Acceptance.**
- The authenticated arm's envelope must not depend on walk_rate. If it does, the rejection emulation is wrong.
- Report the walk rate at which the spoofer is caught by the EKF innovation gate. Above that rate, unauthenticated GNSS also falls back to dead reckoning.

**Manuscript hook:** Section "Horizon-matched crossover", plus a new figure of θ_cross versus walk rate.

---

## E4 — Authentication compute on flight-controller hardware (RQ2)

**Targets.**
- Primary: NUCLEO-H743ZI2 (STM32H743, 480 MHz, the same core as Pixhawk 6X/6C).
- Secondary: Raspberry Pi 4/5 or CM4, as the companion computer.

**Firmware harness.** Use the `pqm4` / `mupq` benchmarking pattern, with the DWT cycle counter (`DWT->CYCCNT`):
```bash
git clone --recursive https://github.com/mupq/pqm4.git
# add an stm32h7 platform (libopencm3 supports STM32H7) or use the STM32CubeH7 HAL:
#  - SystemClock 480 MHz, flash latency 4 WS, I-cache + D-cache ON (then repeat with caches OFF)
# schemes: ml-dsa-44 (m4f), falcon-512 / fn-dsa-512 (m4-fpr), sphincs-sha2-128s/128f (clean),
#          ed25519 (e.g. Monocypher or the Fujii–Aranha code), SHA-256 short-message MAC
```
Take 1000 runs per operation. Record the minimum, median, p99, p99.9 and maximum cycles, plus stack high-water and flash size.

**ML-DSA tail.** Log the rejection-loop iteration count per signature, then fit a geometric distribution. This checks the 12.2× (1 − 10⁻⁶) tail factor used in `constants.py`.

**Output:** `paperI/results/e4_h7_cycles.csv` with columns `scheme, op, cache, n, min, med, p99, p999, max, stack_B, provenance=hardware`.
**Integration:** in `constants.py`, if `e4_h7_cycles.csv` exists, use the median cycles for `sign_cycles` / `verify_cycles` and p99.9/median as `sign_tail_factor`.

**No-board fallback.** Run Renode with the `stm32h743` platform for functional checks only. Renode is not cycle-accurate, so tag the result `physics_model` and keep the literature values as headline.

---

## E5 — Bus validation: base load, frame sizes, multi-frame timing (RQ2)

**From the raw HCRL capture** (no hardware needed once Kaggle is staged):
1. Decode the benign segments. Report the frame rate, the DLC histogram, and the fraction of multi-frame transfers (from DroneCAN tail-byte SOT/EOT bits).
2. Infer the bitrate from the minimum inter-frame spacing. At 1 Mbit/s, back-to-back 8-byte extended frames are at least about 131 µs apart.
3. Recompute U0 using the DLC histogram rather than the 8-byte worst case.

**Output:** `paperI/results/e5_hcrl_bus.csv`. Update `constants.CAN_BITRATE` and `transport.u0_from_hcrl` to use the measured DLC mix.

**Optional hardware.** Use two NUCLEO-H743 boards on a CAN transceiver at 1 Mbit/s, or a Pixhawk 6X and a PCAN-USB:
- Send signed transfers at increasing rate, with a background generator replaying HCRL benign timing.
- Measure end-to-end latency with a logic analyser or the PCAN timestamps.
- Compare against `transport_cliff.csv` with a KS test on latency distributions, and report the empirical r*.

**Output:** `paperI/results/e5_bus_hw.csv` (`provenance=hardware`).

---

## E6 — Induced verification on hardware (RQ5, optional)

On the E5 rig, flood forged Ed25519 and ML-DSA-44 transfers at a lower CAN priority than the legitimate stream. Measure the p99 latency of the legitimate stream with verification on the H7 at CPU shares β ∈ {0.05, 0.2, 1.0}. Use a FreeRTOS task with a time budget.

Test the three mitigations: none, prefilter (outsider), and slot budget (k = 2).

**Output:** `paperI/results/e6_iv_hw.csv`, compared against `induced_verification.csv`.
**Acceptance:** Ed25519 diverges for attacker bus share above `Asat`. ML-DSA-44 on classic CAN does not.

---

## E7 — GNSS time push against MAVLink 2 signing (RQ4)

**Goal.** Validate `time_push.csv`, i.e. confirm that a spoofer which advances GPS time by more than 60 s turns signed MAVLink into a denial.

**Method.**
1. In PX4 SITL (or ArduPilot SITL, whose signing implementation follows the spec more literally), enable MAVLink 2 signing on a second link with `pymavlink` (`mav.setup_signing(key, sign_outgoing=True)`).
2. Have the ground station send signed `COMMAND_LONG` / position-target messages at 10 Hz.
3. Push the vehicle's GPS time forward at ν ∈ {1 ms/s, 10 ms/s, 100 ms/s, step}, using the SITL GPS time offset or a GPS_INPUT injector.
4. Record when signed packets start being rejected. Use the autopilot's MAVLink signing reject counters if they are exposed; otherwise the absence of `COMMAND_ACK`.

**Output:** `paperI/results/e7_time_push.csv`.
**Acceptance:** onset of rejection within ±10 % of τ/ν. Report if the autopilot clamps the GPS-time update rate, since that would be a mitigation worth naming.

---

## E8 — OSNMA freshness with OSNMAlib (RQ4, appendix)

```bash
pip install osnma   # or: git clone https://github.com/Algafix/OSNMA
```
Replay the official test vectors and FGI-JSDR / Jammertest-2023 Galileo E1 data. Apply receiver-time offsets of {0, 10, 25, 29, 31, 60} s, and record which subframes authenticate.

**Output:** `paperI/results/e8_osnma_offsets.csv`. This confirms T_L = 30 s as the effective freshness window used in `freshness_binding.csv`.

---

## 3. Order of work and time estimate

| Order | Experiment | Needs | Effort | Moves headline? |
|---|---|---|---|---|
| 1 | E5 (HCRL part) | Kaggle | 0.5 day | U0, r* (small) |
| 2 | E1 | Kaggle | 1 day | γ_a mechanism check |
| 3 | E3 | PX4 SITL | 3–4 days | **yes — crossover location, cruise** |
| 4 | E4 | NUCLEO-H743 (≈ €30) | 2–3 days | Δ_auth compute terms |
| 5 | E7 | SITL | 1 day | freshness → denial claim |
| 6 | E2, E6, E8 | datasets / rig | 1–2 days each | strengthen only |

## 4. Prompt to paste into Claude Code

> You are working in `rogerpanel/RobustUAVs.ai` on branch `claude/whelan-uavcas-ingest-u00isn`. Read `paperI/RUNBOOK_CLAUDE_CODE.md` and `paperI/experiments/constants.py`. Stage data with `data/fetch_kaggle.py`, then run E5 (HCRL part), then E1, following the runbook's ground rules exactly. Each output carries a provenance column. Then wire the measured values into `constants.py` with literature fallbacks, run `bash paperI/experiments/run_all.sh`, rebuild `paperI/manuscript/main.tex`, and report which macros in `numbers.tex` changed and by how much. Do not edit numbers in `main.tex` by hand. If a result contradicts the manuscript's text (not just a number), stop and summarise the contradiction before changing any prose.
