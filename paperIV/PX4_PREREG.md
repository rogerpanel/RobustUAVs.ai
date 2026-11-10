# Paper IV: pre-registration of the PX4 SITL transfer study

Committed before the first attacked SITL mission. Any later change to this file is
visible in the version history. Results are reported whichever way they fall.

## Question

Do the disguise matrix and the stealth budget of the reduced-order study transfer to a
full autopilot estimator (PX4 v1.14.3 EKF2, multicopter position control, SIH physics)?

## Harness (code: `experiments/px4/`)

- **PX4 v1.14.3 SITL with SIH**, airframe 10040 (sihsim_quadx), lockstep, one fresh PX4 process per
  mission, parameters set at boot from a per-mission file (no parameter changes over MAVLink during a
  mission). Patch: `experiments/px4/px4_paperIV.patch`.
- **Attack.** GNSS position offset d(t) added inside the simulated GPS (`sensor_gps_sim`, 10 Hz),
  cross-track (east; the line runs north), with the five disguise families of the reduced-order model
  (`sim.py`), same parameter boxes, on the mission clock. The reported GNSS velocity is shifted by
  d'(t) (a consistent spoofer), except for the step, which has no Doppler signature. The attacker's
  random stream is seeded (`ATK_SEED`); the applied offset is logged (`debug_vect` "p4atk").
- **Benign envelope**, drawn per mission seed exactly as in `sim.simulate`: lateral Dryden gust
  (W20 uniform in [15, 30] kt, spectral synthesis, acts on the SIH airframe through drag), GNSS white
  noise 0.5 m, Gauss-Markov drift 0.8 m / 60 s, outages (p = 0.3, Exp(5 s)), jamming noise x3 for 10 s
  (p = 0.2), accelerometer bias (initial N(0, 0.02), random walk, step p = 0.3, drift x10 p = 0.2),
  loss of effectiveness (p = 0.2, 10-30 %, all rotors). SIH's own IMU noise is kept (it is part of the
  realistic model). Every stream is reseeded at arming from `BEN_SEED`.
- **Trusted anchor (C2').** Every 5 s of mission time and at the end of the mission, the true position
  plus N(0, 0.3 m) noise, expressed in EKF2's local frame, is published as a vision-position sample
  with a marker. A small EKF2 patch fuses it as an absolute horizontal position, never gated and
  without EKF2's vision-bias estimator. Stock EKF2 v1.14 cannot do this: with GNSS active it fuses
  vision position only relative to a bias estimate, and it does not start vision fusion from samples
  more than 0.2 s apart.
- **Mission.** Take off to 25 m, then a waypoint 700 m north at 8 m/s (PX4 mission mode). Mission time
  t = time since arming - 15 s; window [0, 60] s. Cross-track error e(t) = east ground-truth position
  relative to the take-off point. Completion iff sup |e| <= m, m in {5, 10, 20} m.
- **Attack-only deviation** = sup over t >= t0 of |e_attack(t) - e_twin(t)|, where the twin is the same
  mission (same seeds) with the attack off. The replay floor (sup |e_a - e_b| for one benign mission
  flown twice) is measured in E0 and reported next to every attack-only deviation.

## Detectors (offline from the ULog, `p4_ulog.py`; offline = online because the attacker does not react)

| | PX4 realisation |
|---|---|
| D1 | largest velocity-compensated horizontal jump between consecutive valid fixes |
| D2 | EKF2's own GNSS horizontal-position test ratio, minimum over 3 consecutive fusions, max over the mission |
| D3 | CUSUM on GNSS minus an observer driven by the commanded acceleration (no wind model; gains as in the reduced-order model) |
| D4 | quadratic-fit curvature of GNSS minus double-integrated specific force (attitude-rotated, gravity added) over 4 s, minimum over 5 fixes |
| anchor gate | largest chi-square (2 dof) innovation of the fused anchors |
| D_sat | longest run with a rotor at its limit (reported) |
| PX4 stock | EKF2 GNSS rejections, position resets to GNSS and fusion time-outs (reported) |

Thresholds are calibrated on E0 only: single detector at the (1 - f) quantile, stack thresholds at
(1 - f/4), anchor gate at the 0.99 quantile, f in {1, 2, 5, 10, 20} %, as in the reduced-order study.

## Experiments and seed blocks

| ID | Design | Seeds | Missions |
|---|---|---|---|
| smoke | benign twice (replay), step 5 m, ramp 0.5 m/s | 1000 | 4 |
| E0 | benign calibration, anchor 5 s; 20 seeds flown twice for the replay floor | 1000-1499 | 520 |
| E1 | step 5 m and ramp 0.5 m/s (cap 40 m) at t0 = 25 s, plus twins | 5000-5599 | 1,200 |
| E2 | the 35 optimised attackers of `results/e2_attackers.csv`, **not re-optimised**; attackers 20-24 (full stack, 5 %) on 100 missions, the other 30 on 50; shared seeds, plus 100 twins; evaluated against D1, D2, D3, D4 and the full stack, with and without the anchor gate | 4000-4099 | 2,100 |
| E3 | CEM against the PX4 full stack (5 %, gate armed): 8 candidates x 10 generations x 16 missions per family, objective = mean deviation after onset on stealthy missions (as in the reduced-order CEM); then the best attacker per family on 50 fresh missions with twins | 20000-24999, 25000-25049 | 6,400 + 500 |
| E4neg | negative control: no anchor (C2' broken), ramp 0.5 m/s, plus twins | 3900-3999 | 200 |

E4 (soundness of Theorem 1 in PX4) is run only if E0-E3 finish with time to spare; its protocol will
be added here before it runs.

## Pre-registered reading of E2

The transfer **holds qualitatively** if both hold:

- **(a)** With the anchor gate armed, each of the five primary attackers (20-24) evades the PX4 full
  stack (5 %) in at least 50 % of missions, and its largest undetected attack-only deviation is at
  most twice the reduced-order value (step 2.108, ramp 1.511, fault mimic 2.255, GNSS mimic 2.406,
  weather mimic 2.880 m).
- **(b)** With the anchor gate removed, EKF2's gate (D2) caps every family, meaning the largest
  undetected attack-only deviation under D2 alone is at most 6.77 m (twice the reduced-order maximum,
  3.383 m), while under D4 alone at least one family exceeds 6.77 m.

The outcome is reported either way. A failure to transfer is reported as a finding about EKF2.

## Reported regardless of outcome

Replay floor; failsafes and early disarms; anchors fused per mission; FPR per benign source;
the E2 matrix with unfiltered maxima; E3's PX4 stealth budget next to the reduced-order 4.37 / 5.46 m;
every mission that failed to fly or to parse (`missions.jsonl`, `fail_logs/`).

## Known differences from the reduced-order model (stated in the paper)

IMU noise is SIH's (larger than the model's); GNSS offsets act in 2-D, and the attack is cross-track only;
loss of effectiveness scales all rotors; the D3 observer uses PX4's kinematic acceleration setpoint
without a drag term; the GNSS rate is 10 Hz in both.

## Deviations (recorded 10 Nov 2026, after E0-E3 were flown and before the corrected E2 attack-only deviations were computed)

1. **Validity rule (missions that were never flown).** In 5-7 % of missions PX4 entered Descend or
   Termination before the mission window and never flew the mission (nav_state never 3 in the window;
   along-track speed 0). It occurs at random, independently of the attack: the same seed flies in
   another run (two E0 replay pairs differ only in this), and the rate is similar for benign (7.0 %),
   attacked (5.3-5.8 %) and twin (4 %) missions. It is a start-up race in the harness. Such missions
   are excluded, and an attacked mission is excluded from attack-only statistics when its twin was not
   flown. Counts per experiment are reported (`px4_validity.csv`). E0 thresholds are recalibrated on
   the 465 valid benign missions. Failsafes that start inside the window are kept. From now on, the
   driver retries a mission that was not flown.
2. **E3 attacker selection.** The CEM objective included missions that were never flown, which steered
   the search. Per family, the best attacker is re-selected among the 80 candidates the CEM evaluated,
   with the objective recomputed on valid missions and the recalibrated thresholds
   (`px4_e3_reselect.csv`), and re-evaluated on the pre-registered fresh seeds 25000-25049 with twins
   (`results/px4/e3eval2`). The original selection and its evaluation are kept and reported.
3. **Robust statistics.** Next to every maximum, the median and 95th percentile of the attack-only
   deviation are reported, because a single mission can dominate a maximum.

## E5: the design rule at a 1 s re-anchoring interval (recorded 10 Nov 2026, before its first flight)

Same harness, validity rule, detectors and seeds as above; only the anchor interval changes to 1 s.
Thresholds (D1-D4 at 1 - f and 1 - f/4, anchor gate at 0.99) are recalibrated on the 1 s benign set.

| Part | Design | Seeds | Missions |
|---|---|---|---|
| calibration | benign, anchor 1 s | 1000-1199 | 200 |
| E2 primary | attackers 20-24, not re-optimised, plus twins | 4000-4099 | 600 |
| worst without the gate | attackers 7, 12, 14, 29 (the largest 5 s deviations with the anchor gate removed) | 4000-4049 | 200 |
| E3 | the re-selected PX4 attackers (step, ramp, fault mimic), plus twins | 25000-25049 | 200 |
| naive | ramp 0.5 m/s, plus twins | 5300-5349 | 100 |

**Predictions.** P1: with the anchor gate armed, the largest undetected attack-only deviation over all
E5 attackers against the stack of the proved bound (D1 + anchor gate) is at most the proved linear-loop
bound at 1 s, 10.24 m (an empirical consistency check, not a proof for PX4). P2: it is smaller than the
5 s value (7.09 m), and the same holds for the full stack with the gate (5 s: 4.75 m).
Reported regardless: every cell of `px4_ta1_cross.csv`, medians and 95th percentiles, the cells
without the gate, and the naive ramp.
