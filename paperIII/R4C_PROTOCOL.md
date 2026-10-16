# R4c: pre-registered test of the two-part design rule

Written and committed on 2026-10-16, **before** the R4c run. Nothing in this
file is changed after the run. A change would be a new, dated amendment.

## Purpose

R4b showed two things. Holding ρ at its pre-reacquisition value until the
estimator has fused the fix (the latch) removes every metre-scale violation.
But it still failed its zero-violation criterion by at most 0.22 m, because
the release test and the benign floor use θ = 0.178 s, measured on the
parent's hardware receiver, not on the simulator's. RQ8 therefore states a
two-part rule: staleness from the estimator, **and** a benign floor calibrated
for the receiver in use. R4c tests both parts together, on flights neither
part has seen.

## Calibration (fixed, uses only earlier runs)

`r4_sitl_fleet.py --calibrate` over the R4 and R4b PX4 logs
(`rootfs_before_*` on the server). These are moved aside before the R4c flight,
so R4c's own logs are never used.

- **Benign sample:** a fresh fix (receiver staleness < 1 s), more than 10 s
  after any reacquisition.
- **θ_sitl** = the largest benign residual `err/κ − staleness`, i.e. the
  smallest θ for which every benign sample satisfies `err ≤ κ(θ + staleness)`.
  This is the parent's own definition of θ (the measured benign ceiling),
  applied to the simulator's receiver. No margin is added.
- The reacquisition windows are excluded, so the calibration cannot absorb the
  post-release errors that made R4b fail.

## The certificate under test (fixed)

The R4b latch (`GAP_S = 1.0` s, release after `N_CONV = 3` consecutive fixes
within the floor) and the arming check, with θ = θ_sitl everywhere: in ρ, in
the latch's release threshold, and in the oracle.

## Unchanged

κ, alert limits, sites, 6 vehicles, rates 5 and 2 Hz, 240 s per rate,
PX4 v1.14.3 SIH with default parameters, the oracle.

## Fresh outage schedule (fixed)

`SCHEDULE_C` = GNSS loss (`SIM_GPS_USED = 0`) on
vehicle 3 at 30 s for 18 s, vehicle 5 at 70 s for 22 s, vehicle 0 at 110 s
for 14 s, vehicle 2 at 150 s for 26 s, and vehicle 4 at 195 s for 10 s, in
each rate's run. These differ from R4 (40/90/170 s) and R4b (35/75/120/160/200 s).

## Outcomes

**Primary.** Violations of Assumption 1(a) under the latched certificate with
θ = θ_sitl, over **all** logged samples (`violations_latched`, summed over
logs). The design passes only if this is 0. Any other value is reported as a
failure of the two-part rule, with every violating sample.

**Informativeness.** Violations of the receiver certificate (same θ_sitl)
within 10 s after a reacquisition. If that is 0, no reacquisition transient
occurred, and R4c tests only the floor, not the latch. It is reported that
way.

**Secondary, as measured:**
1. θ_sitl and its source log;
2. executed infeasible assignments;
3. coverage, and the epochs in which the latch raised ρ;
4. vehicles grounded or without GNSS.

## Runs

One run. A technical failure before data collection is repeated under this
same protocol, and the failed attempt is reported.

Command: `bash paperIII/experiments/run_server_paperIII.sh r4c`.
Analysis: `python3 paperIII/experiments/r4b_analysis.py --run r4c`.
