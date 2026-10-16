# R4b — pre-registered test of the RQ8 design rule

Written and committed on 2026-10-16, **before** the R4b run. Nothing in this
file is changed after the run. A change would be a new, dated amendment.

## Purpose

R4 (2026-10-16) found that the certificate premise (Assumption 1(a)) fails at
GNSS reacquisition. Receiver staleness resets when a fix arrives, but PX4's
estimator fuses it gradually (worst case: 13.9 m error against ρ = 0.96 m).
RQ8 states a rule: measure staleness at the estimator, i.e. hold ρ at its
pre-reacquisition value until the estimator has fused the fix. In R4 the rule
was checked only on the run that revealed the problem. R4b tests it on flights
it has not seen.

## The rule (fixed)

`r4_sitl_fleet.Latch`, used both by the driver and by the soundness oracle,
which recomputes it independently from the PX4 log:

- a fix that arrives after more than `GAP_S = 1.0` s of receiver staleness is
  a reacquisition. ρ is then held at `κ(θ + staleness just before the fix)`;
- the hold is released once the estimator position agrees with the receiver
  fix to within the benign floor `κθ = 0.94 m` on `N_CONV = 3` consecutive
  fixes;
- only on-board signals are used (estimator position, receiver fix), never
  ground truth.

Also fixed: a disarmed aircraft gets ρ = ∞ and cannot hold a task.

## Unchanged from R4

κ, θ, alert limits (2, 5, 10, 20 m), sites, 6 vehicles, rates 5 and 2 Hz,
240 s per rate, PX4 v1.14.3 SIH with default parameters (including
failsafes), and the soundness oracle. θ is **not** recalibrated, even though
R4 showed SIH's receiver noise exceeding the floor by up to 3.6 cm.

## Fresh outage schedule (fixed)

`SCHEDULE_B` = GNSS loss (`SIM_GPS_USED = 0`) on
vehicle 2 at 35 s for 15 s, vehicle 4 at 75 s for 25 s, vehicle 5 at 120 s
for 12 s, vehicle 0 at 160 s for 20 s, and vehicle 1 at 200 s for 8 s, in
each rate's run. R4 used vehicles 1, 3 and 0 at 40, 90 and 170 s. Spoofing
is omitted because SIH rejects it.

## Outcomes

**Primary.** Violations of Assumption 1(a) under the latched certificate
within 10 s after a reacquisition, summed over all logs
(`violations_10s_after_reacq_latched`). The rule passes if this is 0. Any
other value is reported as a failure of the rule, with every violating
sample.

**Informativeness.** The same count under the receiver certificate, on the
same flights. If it is 0, no reacquisition transient occurred, and R4b
**cannot** show that the rule works. It is then reported as uninformative,
not as a success.

**Secondary, reported as measured:**
1. benign-floor exceedances (not addressed by the rule);
2. executed infeasible assignments by the monitor;
3. coverage under the latch, and the number of epochs in which latched ρ
   exceeded receiver ρ (the rule's cost);
4. vehicles grounded by PX4 failsafes.

## Runs

One run. If a technical failure prevents data collection, the run is repeated
under this same protocol, and the failed attempt is reported.

Command: `bash paperIII/experiments/run_server_paperIII.sh r4b`.
