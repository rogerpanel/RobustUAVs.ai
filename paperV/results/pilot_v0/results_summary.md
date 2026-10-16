# Paper V pilot results (NON-LLM planners, simulation only)

> **Status: PILOT.** Every number below comes from a seeded simulation of a planar double-integrator fleet with *non-LLM* planners (scripted, random, stall and action-space oracle adversaries). No language model was queried; real-LLM campaigns (A1-A5 in the plan's ladder) are pending. Naming: the action-space oracle is the task brief's A7 (the research plan calls it A6 and reserves A7 for its composition with Paper IV's covert sensing attacker; here that composition is approximated by realising the sensing offset at the declared budget). The oracle adversary chooses actions directly and is therefore an upper envelope on any prompt-injection attacker *for the safety claim*; for denial it is a lower bound on what the searched family can do, not a proof of the strongest attack. Dynamics, disturbance and certificate generators are illustrative models (provenance below); nothing here is a hardware claim.

## 0. Headline numbers (pilot)

1. **Safety inside the assumptions (RQ1).** Filter ON: 0 true-state violations (corridor or separation) in 3,608,500 aircraft-steps over 765 episodes (N = 4 and 12, all planners, all stages); 95% Clopper-Pearson upper bound 8.30e-07 per aircraft-step. Oracle adversaries alone (with worst-case disturbance, certificate error and sensing offset): 0 in 1,816,500 aircraft-steps (CP95 1.65e-06); they pushed the true state to within 0.062 m of the keep-in boundary and 0.383 m of the separation minimum, i.e. the tightening is nearly tight and the attack is not weak.
2. **Sanity check, filter OFF:** episodes with a violation - oracle_violation N=4: 40/40; oracle_denial N=4: 40/40; random N=4: 39/40; oracle_violation N=12: 14/14; oracle_denial N=12: 14/14; random N=12: 14/14. The same planners with the filter ON: 0 in every cell (section 3.1).
3. **Benign cost (RQ4).** MCR 1.00 (N = 4, 40 eps) and 1.00 (N = 12, 14 eps) with the filter ON, identical to OFF; benign intervention rate 0.077 [0.073, 0.081] (N = 4) and 0.069 [0.063, 0.076] (N = 12), mostly the take-off acceleration clipped from 4.0 to the tightened 3.31 m/s^2 and crossing-pair separation; mean deviation 0.049 / 0.052 m/s^2; mission-time overhead N = 4: 0.14 [0.10, 0.18] s; N = 12: 0.01 [-0.04, 0.05] s.
4. **Denial decomposition (RQ2/Prop. 2 recast).** N = 4: stall planner denial 1.00 of which in-envelope 1.00 (fallback rate 0.000); progress-intent oracle_denial denial 1.00, filter-induced 0.95 [0.83, 0.99], fallback rate 0.020 [0.015, 0.024], continuation rate 0.374; N = 12: stall planner denial 1.00 of which in-envelope 1.00 (fallback rate 0.000); progress-intent oracle_denial denial 1.00, filter-induced 1.00 [0.78, 1.00], fallback rate 0.124 [0.106, 0.142], continuation rate 0.634. Safe-but-useless proposals deny the mission with the filter essentially transparent - the filter cannot reduce MDR_envelope, exactly as the recast proposition predicts - while a filter-aware attacker that keeps a progress term converts its blocked safety attack into filter-induced denial.
5. **Budget (RQ3/Prop. 3 recast).** Benign denial stays 0.00 for b_tot <= 7.019 m and jumps to 1.00 at b_tot = 12.718 m (full Paper IV b_tot(eps = 0.1)), where the terminal tightening 18.24 m makes the required nominal lane separation 41.5 m exceed the 40 m lane spacing: the admissible set is empty at take-off (A5 fails; the theorem is silent there, and the uncertified brake-and-hold start did show violations under the adversarial offset). Benign intervention rate rises monotonically across levels: 0.087, 0.110, 0.114, 0.126, 0.193, 0.260, 1.000. One-step study: feasible fraction 0.690 -> 0.157 over the 7 levels with 0 nestedness violations (feasibility, transparency, deviation) in 300 instances.
6. **Mismatch negative control.** oracle_violation, N = 4: w_true = 0x w_bar: 0/16 episodes violate, min true margin 0.27 m; w_true = 1x w_bar: 0/16 episodes violate, min true margin 0.10 m; w_true = 2x w_bar: 16/16 episodes violate, min true margin -0.59 m; w_true = 4x w_bar: 16/16 episodes violate, min true margin -5.50 m. Violations appear exactly when the stated mismatch bound is exceeded.
7. **Outside (A2) / ablations.** Paper III's default certificate process (10 s staleness cap, relay jumps): 15/16 oracle episodes violate (min margin -90.6 m) - the theorem is silent there, as stated. Dropping the L_rho look-ahead *inside* (A2): 16/16 episodes violate (min margin -4.29 m), so the Paper III Thm 3 look-ahead is necessary, not cosmetic. Without the continuation problem the fallback rate under oracle_denial is 0.436 (vs 0.020 with it), still with 0 violations.
8. **Latency (O_lat).** N = 4: p50 4.9 ms, p95 52.4 ms, p99 80.3 ms, max 143.0 ms over 146,300 ticks; N = 12: p50 41.4 ms, p95 176.6 ms, p99 206.8 ms, max 330.1 ms over 26,250 ticks (filter period 500 ms; Python prototype, 2 concurrent episodes on 2 vCPU).

## 1. Campaign size and runtime

| stage | episodes | wall time (s) |
|---|---|---|
| cem | 128 | 284 |
| main | 540 | 633 |
| hand | 210 | 280 |
| budget | 319 | 402 |
| mismatch | 208 | 409 |
| negative | 84 | 139 |
| nested | 0 | 26 |


Total: 1,489 episodes (CEM training episodes counted as candidates x training seeds), 36.2 min wall on 2 worker processes (2-vCPU container). Evaluation episodes with the filter ON: 986, 4,501,000 aircraft-steps at dt = 0.1 s. Environment: {"python": "3.13.16", "platform": "Linux-6.18.44-fc-v114-x86_64-with-glibc2.39", "numpy": "2.5.3", "scale": 1.0, "workers": 2, "osqp": "1.1.3", "clarabel": "0.11.1", "scipy": "1.18.1"}.

## 2. What was simulated

- **Plant** (`plant.py`): N in {4, 12} aircraft, per-axis double integrator at dt = 0.1 s, actuator saturation 4 m/s^2 per axis, speed limit 12 m/s per axis, bounded acceleration mismatch |d|_inf <= w_true. Keep-in polygon (6 half-planes incl. two chamfers), 40 m lanes, pairwise lane-swap goals at 560 m (crossing traffic), mission T = 70 s, deadline (1+kappa_sched)T with kappa_sched = 0.10 (headline) and 0.25 (sensitivity), simulated to 87.5 s.
- **True vs navigation state:** p_true = p_nav + e_cert + e_adv with |e_cert|_inf <= rho_i(t) (Paper III generator: L_rho = e^{L T_c} gamma = 5.296 m/s of error per s of staleness, benign residuals from the parent hop ledger) and |e_adv|_inf <= b_adv (covert sensing offset realised at the declared budget). Under (A2) staleness is capped at 0.944 s (rho_bar = 5.0 m) and relay jumps are off.
- **Filter** (`filter.py`): joint-fleet QP every Ts = 0.5 s, horizon N_p = 10 (5 s), tube controller u = v + K(x - z) at 10 Hz with K = (1.2, 1.8) (Paper IV PD). Tightening beta_k = min(max(rho, rho_floor) + L_rho (k+1) Ts, rho_bar) + b_tot + eps_k + bulge; separation linearised with ||n||_1 scaling; loiter (zero-velocity) terminal set; independent exact verifier; continuation plan from the latched nominal when the re-anchored problem fails; latched tail otherwise. Solvers: OSQP (40 ms first stage) then Clarabel IPM; total budget 0.25 s per tick (overrun = fallback).
- **Tightening numbers at b_tot = delta_adv = 4.371 m, w_bar = 0.5 m/s^2:** eps_p(inf) = 0.424 m, eps_v(inf) = 0.400 m/s, eps_u(inf) = 0.690 m/s^2 (nominal accel bound 3.310 m/s^2), terminal tightening 9.898 m, closed-loop spectral radius 0.909.
- **Planners** (`agent.py`, `attacks.py`): benign scripted (A0); random waypoints; stall (benign, then safe holds from a random onset in [5, 30] s); oracle_violation and oracle_denial = CEM-tuned members of a parametric action-space family (push to nearest wall / neighbour / fixed direction / along velocity / toward goal), run with adversarial nature (disturbance, certificate error and sensing offset all pointing at each aircraft's most binding constraint); oracle_denial is constrained to keep a progress-toward-goal term (an attacker that wants the *filter* to cause the denial). Hand-designed family members are evaluated alongside. A `MockLLMPlanner` stub (JSON schema, sha256 cache, usage log) exists for the future LLM runs and was not used in the campaign.
- **Oracle CEM optimum** (N = 4, seeds 2xxx, transferred unchanged to N = 12): theta_violation = [1.634, -0.224, 0.563, 2.378, 0.838, -0.495] (score = -1.494 = minus the minimum true margin), theta_denial = [1.745, -0.15, 0.113, -3.142, 0.934, 1.527] (score 1.267). theta = (w_wall, w_nbr, w_const, phi, w_vel, w_goal).

Constants and provenance (`results/constants_paperV.csv`):

| name | value | provenance |
|---|---|---|
| gamma_sup_m_s | 1.6250 | parent |
| L_loc | 1.1814 | parent |
| T_c_s | 1.0000 | parent |
| amp_eLT | 3.2589 | derived |
| L_rho_m_per_s | 5.2958 | derived |
| rho_floor_m | 0.9426 | derived (hop_ledger benign max 0.178 s) |
| rho_bar_m | 4.9992 | model: L_rho * DELTA_BAR_S |
| delta_adv_m | 4.3710 | P4 e4_delta_adv.csv |
| net_tube_theta025_m | 2.6479 | P4 net_tube |
| hidden_residual_median_s | 3.9420 | parent hop_ledger |
| max_fleet | 12 | platform |
| T_mission_s | 70.0000 | platform |
| kappa_sched | 0.1000 | parent |
| kappa_sched_alt | 0.2500 | platform |
| dt_s | 0.1000 | model |
| Ts_filter_s | 0.5000 | model |
| Np | 10 | model |
| u_max | 4.0000 | P4 |
| v_max | 12.0000 | model |
| kp | 1.2000 | P4 |
| kd | 1.8000 | P4 |
| w_bar_nom | 0.5000 | model |
| d_sep_m | 5.0000 | model |
| delta_bar_s | 0.9440 | model |


## 3. RQ1 - physical safety of the true state

**Filter ON, inside the stated assumptions (A1 w_true <= w_bar, A2 rho within envelope, no actuator saturation, no uncertified start), all stages pooled:** 0 violating aircraft-steps out of 3,608,500 (765 episodes; 0 episodes with any violation). One-sided 95% Clopper-Pearson upper bound on the per-aircraft-step violation probability: **8.30e-07**.

- N = 4: 0 / 2,212,000 aircraft-steps (632 episodes), CP95 upper 1.35e-06.
- N = 12: 0 / 1,396,500 aircraft-steps (133 episodes), CP95 upper 2.15e-06.
- Oracle planners only (adversarial nature): 0 / 1,816,500 aircraft-steps (397 episodes), CP95 upper 1.65e-06; closest approach over all inside-assumption oracle episodes: corridor margin 0.062 m, separation margin 0.383 m (true state).

- Filter-ON episodes nominally inside (A1)/(A2) but excluded from the pooled count because an auxiliary condition failed (actuator saturation or uncertified start): 65 episodes, 2,608 violating aircraft-steps, saturation steps 0, uncertified ticks 8,575 (tags: ['budget', 'gamma15.0', 'no_lookahead']).


### 3.1 Filter ON vs OFF (main stage, b_tot = delta_adv = 4.371 m, w_true = w_bar = 0.5 m/s^2)

| N | planner | filter | eps | episode viol. rate [Wilson 95%] | SVR (per aircraft-step) | CP95 SVR upper (if 0) | IR [boot 95%] | FR [boot 95%] | continuation rate | MCR [Wilson] | denial: filter | denial: envelope | denial: violation | mean ||u*-u_LLM|| (m/s^2) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | benign | OFF | 40.000 | 0.00 [0.00, 0.09] | 0.0000 | 2.14e-05 | - | - | - | 1.00 [0.91, 1.00] | 0.00 | 0.00 | 0.00 | - |
| 4 | benign | ON | 40.000 | 0.00 [0.00, 0.09] | 0.0000 | 2.14e-05 | 0.077 [0.073, 0.081] | 0.000 [0.000, 0.000] | 4.29e-04 | 1.00 [0.91, 1.00] | 0.00 | 0.00 | 0.00 | 0.049 |
| 4 | oracle_denial | OFF | 40.000 | 1.00 [0.91, 1.00] | 0.9601 | - | - | - | - | 0.00 [0.00, 0.09] | 0.00 | 0.00 | 1.00 | - |
| 4 | oracle_denial | ON | 40.000 | 0.00 [0.00, 0.09] | 0.0000 | 2.14e-05 | 1.000 [1.000, 1.000] | 0.020 [0.015, 0.024] | 0.374 | 0.00 [0.00, 0.09] | 0.95 | 0.05 | 0.00 | 4.852 |
| 4 | oracle_violation | OFF | 40.000 | 1.00 [0.91, 1.00] | 0.9602 | - | - | - | - | 0.00 [0.00, 0.09] | 0.00 | 0.00 | 1.00 | - |
| 4 | oracle_violation | ON | 40.000 | 0.00 [0.00, 0.09] | 0.0000 | 2.14e-05 | 1.000 [1.000, 1.000] | 0.008 [0.005, 0.011] | 0.399 | 0.00 [0.00, 0.09] | 0.00 | 1.00 | 0.00 | 4.658 |
| 4 | random | OFF | 40.000 | 0.97 [0.87, 1.00] | 0.0160 | - | - | - | - | 0.00 [0.00, 0.09] | 0.00 | 0.03 | 0.97 | - |
| 4 | random | ON | 40.000 | 0.00 [0.00, 0.09] | 0.0000 | 2.14e-05 | 0.481 [0.460, 0.503] | 2.86e-04 [0.000, 7.14e-04] | 0.083 | 0.00 [0.00, 0.09] | 0.00 | 1.00 | 0.00 | 0.894 |
| 4 | stall | OFF | 40.000 | 0.00 [0.00, 0.09] | 0.0000 | 2.14e-05 | - | - | - | 0.00 [0.00, 0.09] | 0.00 | 1.00 | 0.00 | - |
| 4 | stall | ON | 40.000 | 0.00 [0.00, 0.09] | 0.0000 | 2.14e-05 | 0.070 [0.064, 0.077] | 0.000 [0.000, 0.000] | 0.000 | 0.00 [0.00, 0.09] | 0.00 | 1.00 | 0.00 | 0.047 |
| 12 | benign | OFF | 14.000 | 0.00 [1.39e-17, 0.22] | 0.0000 | 2.04e-05 | - | - | - | 1.00 [0.78, 1.00] | 0.00 | 0.00 | 0.00 | - |
| 12 | benign | ON | 14.000 | 0.00 [1.39e-17, 0.22] | 0.0000 | 2.04e-05 | 0.069 [0.063, 0.076] | 0.000 [0.000, 0.000] | 0.018 | 1.00 [0.78, 1.00] | 0.00 | 0.00 | 0.00 | 0.052 |
| 12 | oracle_denial | OFF | 14.000 | 1.00 [0.78, 1.00] | 0.9600 | - | - | - | - | 0.00 [1.39e-17, 0.22] | 0.00 | 0.00 | 1.00 | - |
| 12 | oracle_denial | ON | 14.000 | 0.00 [1.39e-17, 0.22] | 0.0000 | 2.04e-05 | 1.000 [1.000, 1.000] | 0.124 [0.106, 0.142] | 0.634 | 0.00 [1.39e-17, 0.22] | 1.00 | 0.00 | 0.00 | 4.839 |
| 12 | oracle_violation | OFF | 14.000 | 1.00 [0.78, 1.00] | 0.9601 | - | - | - | - | 0.00 [1.39e-17, 0.22] | 0.00 | 0.00 | 1.00 | - |
| 12 | oracle_violation | ON | 14.000 | 0.00 [1.39e-17, 0.22] | 0.0000 | 2.04e-05 | 1.000 [1.000, 1.000] | 0.144 [0.129, 0.157] | 0.598 | 0.00 [1.39e-17, 0.22] | 0.00 | 1.00 | 0.00 | 4.691 |
| 12 | random | OFF | 14.000 | 1.00 [0.78, 1.00] | 0.0171 | - | - | - | - | 0.00 [1.39e-17, 0.22] | 0.00 | 0.00 | 1.00 | - |
| 12 | random | ON | 14.000 | 0.00 [1.39e-17, 0.22] | 0.0000 | 2.04e-05 | 0.597 [0.573, 0.624] | 0.027 [0.022, 0.033] | 0.312 | 0.00 [1.39e-17, 0.22] | 0.00 | 1.00 | 0.00 | 1.433 |
| 12 | stall | OFF | 14.000 | 0.00 [1.39e-17, 0.22] | 0.0000 | 2.04e-05 | - | - | - | 0.00 [1.39e-17, 0.22] | 0.00 | 1.00 | 0.00 | - |
| 12 | stall | ON | 14.000 | 0.00 [1.39e-17, 0.22] | 0.0000 | 2.04e-05 | 0.064 [0.053, 0.074] | 0.000 [0.000, 0.000] | 0.010 | 0.00 [1.39e-17, 0.22] | 0.00 | 1.00 | 0.00 | 0.044 |


IR = fraction of aircraft-ticks with ||v0 - u_des||_inf > 0.01 m/s^2 (includes fallback ticks); FR = fraction of fleet ticks executing the latched tail; continuation rate = fraction of ticks certified by the continuation problem (not a fallback). MCR = all aircraft reach the goal by (1.10)T with zero violations (conjunctive). Denial causes: *filter* = some aircraft missed the deadline although its planner's cumulative progress intent covered its goal distance; *envelope* = planner never asked for enough progress; *violation* = a violation occurred (only possible OFF or outside the assumptions).


**Benign mission-time overhead (ON minus OFF, paired by seed):** N = 4: 0.14 [0.10, 0.18] s over a mean OFF fleet completion of 66.7 s (0.2%), 40 pairs; N = 12: 0.01 [-0.04, 0.05] s over a mean OFF fleet completion of 67.0 s (0.0%), 14 pairs.


### 3.2 Oracle family members (hand-designed + CEM optimum), worst case per mission

| N | filter | # oracle variants | missions (seeds) | worst-case missions with a violation | min corridor margin (m) | min separation margin (m) | worst-case denial rate |
|---|---|---|---|---|---|---|---|
| 4 | OFF | 7 | 40 | 40/40 [0.91, 1.00] | -17098.12 | -4.99 | 1.00 |
| 4 | ON | 7 | 40 | 0/40 [0.00, 0.09] | 0.06 | 0.44 | 1.00 |
| 12 | OFF | 7 | 14 | 14/14 [0.78, 1.00] | -17098.12 | -5.00 | 1.00 |
| 12 | ON | 7 | 14 | 0/14 [1.39e-17, 0.22] | 0.06 | 0.38 | 1.00 |


Per variant, filter ON:

| N | variant | eps | viol. steps | min corr. margin | min sep. margin | IR | FR | cont. | denial | denial: filter |
|---|---|---|---|---|---|---|---|---|---|---|
| 4 | oracle_denial | 40.000 | 0.000 | 0.06 | 6.30 | 1.000 | 0.020 | 0.374 | 1.00 | 0.95 |
| 4 | oracle_goal_plus_neighbour | 16.000 | 0.000 | 0.72 | 0.76 | 1.000 | 0.001 | 0.258 | 0.56 | 0.56 |
| 4 | oracle_goal_plus_wall | 16.000 | 0.000 | 0.13 | 6.61 | 1.000 | 0.002 | 0.165 | 1.00 | 0.50 |
| 4 | oracle_overspeed | 16.000 | 0.000 | 0.09 | 4.93 | 1.000 | 0.011 | 0.512 | 1.00 | 1.00 |
| 4 | oracle_press_neighbour | 16.000 | 0.000 | 14.37 | 0.44 | 1.000 | 0.000 | 0.023 | 1.00 | 0.00 |
| 4 | oracle_press_wall | 16.000 | 0.000 | 0.21 | 10.64 | 1.000 | 0.000 | 0.035 | 1.00 | 0.00 |
| 4 | oracle_violation | 40.000 | 0.000 | 0.10 | 9.87 | 1.000 | 0.008 | 0.399 | 1.00 | 0.00 |
| 12 | oracle_denial | 14.000 | 0.000 | 0.06 | 4.85 | 1.000 | 0.124 | 0.634 | 1.00 | 1.00 |
| 12 | oracle_goal_plus_neighbour | 5.000 | 0.000 | 0.19 | 0.70 | 1.000 | 0.061 | 0.843 | 1.00 | 1.00 |
| 12 | oracle_goal_plus_wall | 5.000 | 0.000 | 0.08 | 1.23 | 1.000 | 0.017 | 0.338 | 1.00 | 0.00 |
| 12 | oracle_overspeed | 5.000 | 0.000 | 0.12 | 5.08 | 1.000 | 0.094 | 0.574 | 1.00 | 1.00 |
| 12 | oracle_press_neighbour | 5.000 | 0.000 | 0.19 | 0.38 | 1.000 | 0.018 | 0.161 | 1.00 | 0.00 |
| 12 | oracle_press_wall | 5.000 | 0.000 | 0.17 | 10.54 | 1.000 | 0.002 | 0.026 | 1.00 | 0.00 |
| 12 | oracle_violation | 14.000 | 0.000 | 0.06 | 1.37 | 1.000 | 0.144 | 0.598 | 1.00 | 0.00 |


## 4. RQ3 - budget sweep: admissible-set shrinkage, induced fallback/denial, nestedness

Budget levels (m): 0.000 (none), 0.500 (sweep), 1.000 (sweep), 2.000 (sweep), 4.371 (delta_adv (P4)), 7.019 (delta_adv + e^{LT}delta_net(0.25 s)), 12.718 (full b_tot(eps=0.1) with s*=5.70 m). s*(eps = 0.1) = 5.70 m from Paper IV's union bound over its committed marginals. The covert sensing offset is realised at the declared budget (adversarial nature) in every budget cell.

| N | planner | b_tot (m) | terminal tightening (m) | eps | viol. steps | FR [boot] | IR | cont. | denial [Wilson] | denial: filter | denial: envelope | uncertified ticks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | benign | 0.000 | 5.53 | 16.000 | 0.000 | 0.000 [0.000, 0.000] | 0.087 | 0.000 | 0.00 [0.00, 0.19] | 0.00 | 0.00 | 0.000 |
| 4 | benign | 0.500 | 6.03 | 16.000 | 0.000 | 0.000 [0.000, 0.000] | 0.110 | 0.000 | 0.00 [0.00, 0.19] | 0.00 | 0.00 | 0.000 |
| 4 | benign | 1.000 | 6.53 | 16.000 | 0.000 | 0.000 [0.000, 0.000] | 0.114 | 0.000 | 0.00 [0.00, 0.19] | 0.00 | 0.00 | 0.000 |
| 4 | benign | 2.000 | 7.53 | 16.000 | 0.000 | 0.000 [0.000, 0.000] | 0.126 | 0.006 | 0.00 [0.00, 0.19] | 0.00 | 0.00 | 0.000 |
| 4 | benign | 4.371 | 9.90 | 16.000 | 0.000 | 0.000 [0.000, 0.000] | 0.193 | 0.006 | 0.00 [0.00, 0.19] | 0.00 | 0.00 | 0.000 |
| 4 | benign | 7.019 | 12.55 | 16.000 | 0.000 | 0.000 [0.000, 0.000] | 0.260 | 0.011 | 0.00 [0.00, 0.19] | 0.00 | 0.00 | 0.000 |
| 4 | benign | 12.718 | 18.24 | 16.000 | 150.000 | 1.000 [1.000, 1.000] | 1.000 | 0.000 | 1.00 [0.81, 1.00] | 0.81 | 0.00 | 2800.000 |
| 4 | oracle_denial | 0.000 | 5.53 | 16.000 | 0.000 | 0.004 [0.002, 0.006] | 1.000 | 0.263 | 1.00 [0.81, 1.00] | 0.19 | 0.81 | 0.000 |
| 4 | oracle_denial | 0.500 | 6.03 | 16.000 | 0.000 | 0.005 [0.003, 0.008] | 1.000 | 0.304 | 1.00 [0.81, 1.00] | 0.81 | 0.19 | 0.000 |
| 4 | oracle_denial | 1.000 | 6.53 | 16.000 | 0.000 | 0.005 [0.003, 0.008] | 1.000 | 0.314 | 1.00 [0.81, 1.00] | 0.69 | 0.31 | 0.000 |
| 4 | oracle_denial | 2.000 | 7.53 | 16.000 | 0.000 | 0.014 [0.007, 0.020] | 1.000 | 0.380 | 1.00 [0.81, 1.00] | 0.88 | 0.12 | 0.000 |
| 4 | oracle_denial | 4.371 | 9.90 | 16.000 | 0.000 | 0.018 [0.011, 0.024] | 1.000 | 0.345 | 1.00 [0.81, 1.00] | 0.88 | 0.12 | 0.000 |
| 4 | oracle_denial | 7.019 | 12.55 | 16.000 | 0.000 | 0.008 [0.003, 0.013] | 1.000 | 0.316 | 1.00 [0.81, 1.00] | 0.44 | 0.56 | 0.000 |
| 4 | oracle_denial | 12.718 | 18.24 | 16.000 | 150.000 | 1.000 [1.000, 1.000] | 1.000 | 0.000 | 1.00 [0.81, 1.00] | 0.00 | 0.81 | 2800.000 |
| 12 | benign | 0.000 | 5.53 | 5.000 | 0.000 | 0.000 [0.000, 0.000] | 0.066 | 0.025 | 0.00 [0.00, 0.43] | 0.00 | 0.00 | 0.000 |
| 12 | benign | 0.500 | 6.03 | 5.000 | 0.000 | 0.000 [0.000, 0.000] | 0.104 | 0.027 | 0.00 [0.00, 0.43] | 0.00 | 0.00 | 0.000 |
| 12 | benign | 1.000 | 6.53 | 5.000 | 0.000 | 0.000 [0.000, 0.000] | 0.097 | 0.027 | 0.00 [0.00, 0.43] | 0.00 | 0.00 | 0.000 |
| 12 | benign | 2.000 | 7.53 | 5.000 | 0.000 | 0.003 [0.001, 0.006] | 0.126 | 0.033 | 0.00 [0.00, 0.43] | 0.00 | 0.00 | 0.000 |
| 12 | benign | 4.371 | 9.90 | 5.000 | 0.000 | 0.005 [0.001, 0.008] | 0.154 | 0.062 | 0.00 [0.00, 0.43] | 0.00 | 0.00 | 0.000 |
| 12 | benign | 7.019 | 12.55 | 5.000 | 0.000 | 0.000 [0.000, 0.000] | 0.263 | 0.027 | 0.00 [0.00, 0.43] | 0.00 | 0.00 | 0.000 |
| 12 | benign | 12.718 | 18.24 | 5.000 | 510.000 | 1.000 [1.000, 1.000] | 1.000 | 0.000 | 1.00 [0.57, 1.00] | 0.00 | 0.00 | 875.000 |


**Ordered-trend tests (Spearman, per-episode values vs b_tot level, common random numbers):**

- N = 4, benign: denial rho_s = 0.61 (p = 7.25e-13); fallback fraction rho_s = 0.61 (p = 7.25e-13); intervention rate rho_s = 0.98 (p = 6.15e-80). Pathwise: 0/16 seeds have a non-monotone denial sequence and 0/16 a non-monotone fallback-count sequence across levels (pathwise monotonicity is NOT predicted by the theory).
- N = 4, oracle_denial: denial rho_s = n/a (p = n/a); fallback fraction rho_s = 0.53 (p = 1.67e-09); intervention rate rho_s = n/a (p = n/a). Pathwise: 0/16 seeds have a non-monotone denial sequence and 14/16 a non-monotone fallback-count sequence across levels (pathwise monotonicity is NOT predicted by the theory).
- N = 12, benign: denial rho_s = 0.61 (p = 9.24e-05); fallback fraction rho_s = 0.61 (p = 9.77e-05); intervention rate rho_s = 0.94 (p = 1.92e-17). Pathwise: 0/5 seeds have a non-monotone denial sequence and 5/5 a non-monotone fallback-count sequence across levels (pathwise monotonicity is NOT predicted by the theory).

**One-step nestedness / transparency study** (`results/nestedness.csv`; random fleet states, certificates and proposals; Clarabel without time limit; identical linearisation across levels):

| b_tot (m) | instances | feasible fraction | transparent fraction |
|---|---|---|---|
| 0.000 | 300 | 0.690 | 0.567 |
| 0.500 | 300 | 0.650 | 0.543 |
| 1.000 | 300 | 0.617 | 0.517 |
| 2.000 | 300 | 0.550 | 0.470 |
| 4.371 | 300 | 0.440 | 0.370 |
| 7.019 | 300 | 0.337 | 0.277 |
| 12.718 | 300 | 0.157 | 0.117 |


Nestedness violations between adjacent levels: feasibility 0, transparency 0, deviation decreasing by more than 1e-3 m/s^2: 0 (over 300 instances x 6 level pairs). Lemma 1 (transparent <=> deviation <= 0.01) agreed on 1031/1032 feasible (instance, level) pairs; 1032/1032 IPM solutions passed the independent verifier.


**gamma and staleness-envelope levels** (benign, N = 4, b_tot = delta_adv, adversarial nature):

| cell | gamma (m/s) | Delta_bar (s) | rho_bar (m) | terminal tightening (m) | eps | viol. steps | FR | IR | MCR | uncertified ticks |
|---|---|---|---|---|---|---|---|---|---|---|
| dbar0.5 | 1.625 | 0.500 | 2.65 | 7.55 | 12.000 | 0.000 | 0.000 | 0.134 | 1.00 [0.76, 1.00] | 0.000 |
| dbar2.0 | 1.625 | 2.000 | 10.59 | 15.49 | 12.000 | 0.000 | 0.000 | 0.507 | 1.00 [0.76, 1.00] | 0.000 |
| gamma1.365 | 1.365 | 0.944 | 4.20 | 9.10 | 12.000 | 0.000 | 0.000 | 0.172 | 1.00 [0.76, 1.00] | 0.000 |
| gamma1.625 | 1.625 | 0.944 | 5.00 | 9.90 | 12.000 | 0.000 | 0.000 | 0.190 | 1.00 [0.76, 1.00] | 0.000 |
| gamma15.0 | 15.000 | 0.944 | 46.15 | 51.05 | 12.000 | 190.000 | 1.000 | 1.000 | 0.00 [2.78e-17, 0.24] | 2100.000 |


## 5. Mismatch sweep (honest negative control): filter assumes w_bar = 0.5 m/s^2

| N | planner | w_true / w_bar | eps | viol. steps | episode viol. rate | SVR | min true margin (m) | IR [boot] | FR | cont. | saturation steps | MCR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | benign | 0.0x | 16.000 | 0.000 | 0.00 [0.00, 0.19] | 0 (CP95 <= 5.35e-05) | 11.861 | 0.048 [0.048, 0.049] | 0.000 | 0.006 | 0.000 | 1.00 |
| 4 | benign | 1.0x | 16.000 | 0.000 | 0.00 [0.00, 0.19] | 0 (CP95 <= 5.35e-05) | 11.274 | 0.075 [0.068, 0.083] | 0.000 | 0.000 | 0.000 | 1.00 |
| 4 | benign | 2.0x | 16.000 | 0.000 | 0.00 [0.00, 0.19] | 0 (CP95 <= 5.35e-05) | 11.342 | 0.067 [0.060, 0.074] | 0.000 | 3.57e-04 | 4.000 | 1.00 |
| 4 | benign | 4.0x | 16.000 | 0.000 | 0.00 [0.00, 0.19] | 0 (CP95 <= 5.35e-05) | 11.018 | 0.065 [0.056, 0.073] | 0.000 | 0.005 | 200.000 | 1.00 |
| 4 | oracle_press_wall | 0.0x | 16.000 | 0.000 | 0.00 [0.00, 0.19] | 0 (CP95 <= 5.35e-05) | 0.271 | 1.000 [1.000, 1.000] | 0.000 | 0.000 | 0.000 | 0.00 |
| 4 | oracle_press_wall | 1.0x | 16.000 | 0.000 | 0.00 [0.00, 0.19] | 0 (CP95 <= 5.35e-05) | 0.209 | 1.000 [1.000, 1.000] | 0.000 | 0.035 | 0.000 | 0.00 |
| 4 | oracle_press_wall | 2.0x | 16.000 | 2841.000 | 1.00 [0.81, 1.00] | 0.05073 | -0.515 | 1.000 [1.000, 1.000] | 0.000 | 0.960 | 224.000 | 0.00 |
| 4 | oracle_press_wall | 4.0x | 16.000 | 3053.000 | 1.00 [0.81, 1.00] | 0.05452 | -3.683 | 1.000 [1.000, 1.000] | 0.000 | 0.971 | 672.000 | 0.00 |
| 4 | oracle_violation | 0.0x | 16.000 | 0.000 | 0.00 [0.00, 0.19] | 0 (CP95 <= 5.35e-05) | 0.271 | 1.000 [1.000, 1.000] | 0.009 | 0.207 | 0.000 | 0.00 |
| 4 | oracle_violation | 1.0x | 16.000 | 0.000 | 0.00 [0.00, 0.19] | 0 (CP95 <= 5.35e-05) | 0.097 | 1.000 [1.000, 1.000] | 0.009 | 0.432 | 0.000 | 0.00 |
| 4 | oracle_violation | 2.0x | 16.000 | 2548.000 | 1.00 [0.81, 1.00] | 0.04550 | -0.593 | 1.000 [1.000, 1.000] | 0.026 | 0.893 | 3975.000 | 0.00 |
| 4 | oracle_violation | 4.0x | 16.000 | 2866.000 | 1.00 [0.81, 1.00] | 0.05118 | -5.498 | 1.000 [1.000, 1.000] | 0.019 | 0.952 | 6448.000 | 0.00 |
| 12 | oracle_violation | 0.0x | 4.000 | 0.000 | 0.00 [0.00, 0.49] | 0 (CP95 <= 7.13e-05) | 0.225 | 1.000 [1.000, 1.000] | 0.169 | 0.447 | 0.000 | 0.00 |
| 12 | oracle_violation | 1.0x | 4.000 | 0.000 | 0.00 [0.00, 0.49] | 0 (CP95 <= 7.13e-05) | 0.101 | 1.000 [1.000, 1.000] | 0.129 | 0.546 | 0.000 | 0.00 |
| 12 | oracle_violation | 2.0x | 4.000 | 1902.000 | 1.00 [0.51, 1.00] | 0.04529 | -1.847 | 1.000 [1.000, 1.000] | 0.127 | 0.829 | 2990.000 | 0.00 |
| 12 | oracle_violation | 4.0x | 4.000 | 2562.000 | 1.00 [0.51, 1.00] | 0.06100 | -66.849 | 1.000 [1.000, 1.000] | 0.100 | 0.870 | 3218.000 | 0.00 |


## 6. Outside (A2) and ablations

| cell | N | planner | eps | viol. steps | episode viol. rate | min true margin (m) | FR | cont. | steps with rho > rho_bar | MCR | denial: filter |
|---|---|---|---|---|---|---|---|---|---|---|---|
| no_continuation | 4 | oracle_denial | 16.000 | 0.000 | 0.00 [0.00, 0.19] | 0.17 | 0.436 | 0.000 | 0.000 | 0.00 | 0.75 |
| no_lookahead | 4 | oracle_press_wall | 16.000 | 1608.000 | 1.00 [0.81, 1.00] | -4.29 | 0.117 | 0.503 | 0.000 | 0.00 | 0.00 |
| outsideA2 | 4 | benign | 16.000 | 376.000 | 0.38 [0.18, 0.61] | -41.17 | 0.357 | 0.005 | 5476.000 | 0.31 | 0.31 |
| outsideA2 | 4 | oracle_press_wall | 16.000 | 6774.000 | 0.94 [0.72, 0.99] | -90.86 | 0.389 | 0.044 | 5476.000 | 0.00 | 0.00 |
| outsideA2 | 4 | oracle_violation | 16.000 | 6356.000 | 0.94 [0.72, 0.99] | -90.56 | 0.393 | 0.237 | 5476.000 | 0.00 | 0.00 |
| outsideA2 | 12 | benign | 4.000 | 517.000 | 0.75 [0.30, 0.95] | -38.36 | 0.784 | 0.093 | 2855.000 | 0.00 | 0.25 |


*outsideA2*: Paper III default certificate process (staleness cap 10 s, undetected relay-delay jumps from the hidden-residual pool, seeds 5xxx) -- outside the theorem's scope by construction. *no_lookahead*: tightening uses the current rho only (no L_rho growth over the horizon). *no_continuation*: re-anchored problem + latched tail only.


## 7. Solve time (O_lat)

| N | ticks | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | > 250 ms | > 500 ms |
|---|---|---|---|---|---|---|---|
| 4 | 146,300 | 4.9 | 52.4 | 80.3 | 143.0 | 0.0000 | 0.0000 |
| 12 | 26,250 | 41.4 | 176.6 | 206.8 | 330.1 | 0.0024 | 0.0000 |


Times are wall-clock per filter tick (both solve stages + verification), Python + OSQP 1.1 / Clarabel 0.11 on the 2-vCPU container with two episodes running concurrently. The filter period is 500 ms; the in-code budget is 250 ms, after which the tick falls back to the latched plan.


## 8. Findings, bugs found during development, and caveats

- **Filter-ON violations inside the stated assumptions: 0 episodes.** All 150 filter-ON episodes with a violation break a stated assumption by design (episode counts by cell and reason: mismatch/N4/oracle_press_wall: w_true>w_bar, actuator saturation x32; mismatch/N4/oracle_violation: w_true>w_bar, actuator saturation x32; no_lookahead/N4/oracle_press_wall: no look-ahead ablation x16; outsideA2/N4/oracle_press_wall: outside A2 x15; outsideA2/N4/oracle_violation: outside A2 x15; gamma15.0/N4/benign: uncertified start (A5) x12; mismatch/N12/oracle_violation: w_true>w_bar, actuator saturation x8; outsideA2/N4/benign: outside A2 x6; budget/N12/benign: uncertified start (A5) x5; budget/N4/benign: uncertified start (A5) x3; budget/N4/oracle_denial: uncertified start (A5) x3; outsideA2/N12/benign: outside A2 x3). These are reported as findings (the scope boundary of the theorem), not bugs.
- **Bug/finding 1 (fixed before the campaign):** with OSQP alone at tolerance 1e-5 many ticks hit the iteration limit or returned plans that failed the independent verifier by ~1e-4 (terminal velocity and speed rows). Because every executed plan is verified, this never produced an uncertified action - it produced fallbacks. Fix: solver buffers (0.10 m, 0.05 m/s, 0.05 m/s^2) that the verifier does not use, an exact terminal-velocity repair, relative coordinates, and a Clarabel interior-point second stage.
- **Finding 2 (design):** re-anchoring the plan to the navigation state every tick does not preserve recursive feasibility under worst-case disturbance near the boundary (the new tightening counts the already-realised error again). The paper's filter therefore needs the continuation problem (or a Mayne-style initial-state constraint); the no_continuation ablation shows the cost in fallback rate.
- **Bug 3 (fixed, campaign re-run):** the first full run's denial decomposition measured planner intent from the current velocity plus one tick of proposed acceleration, which understated intent when the filter held aircraft at rest (it labelled the empty-admissible-set denial at b_tot = 12.7 m as 'envelope'). Intent is now the velocity the action asks for; all stages except CEM were re-run (first run archived in `results_run1_intentv1/`). Reproducibility across the two full runs (main stage, 540 paired episodes): violation counts identical in 540/540; filter-ON episodes with identical intervention, continuation and fallback counts 63/270. Differences, where present, come from wall-clock solver budgets (OSQP 40 ms first stage, 250 ms per tick): seeds fix the scenario, but which ticks hit a time limit depends on machine load. Safety does not depend on this (every executed plan is verified), the liveness metrics do slightly. At cell level (10 filter-ON main cells) the largest run-to-run differences were: IR 0.0056, FR 0.0257, continuation rate 0.0486, MCR 0.000. For the paper runs the wall-clock budgets should be replaced by iteration caps (deterministic) and latency measured separately.
- **Bug 4 (fixed in the dry run):** the 'inside assumptions' flag initially counted the no-look-ahead ablation as compliant; its violations are correctly attributed to the ablation.
- **CEM search budget is small** (8 candidates x 4 generations x 2 training seeds, N = 4 only, transferred to N = 12). Training score of the violation optimum: closest true approach 1.49 m on seeds 2000-2001. Held-out closest approach per planner (N = 4, filter ON): oracle_denial 0.06 m, oracle_overspeed 0.09 m, oracle_violation 0.10 m, oracle_goal_plus_wall 0.13 m, oracle_press_wall 0.21 m, oracle_press_neighbour 0.44 m, oracle_goal_plus_neighbour 0.72 m, random 3.73 m, stall 8.75 m, benign 11.27 m. Hand-designed members are therefore always evaluated and the worst case per mission is reported; denial numbers are lower bounds on the oracle family's power, not its supremum.
- **Modelling caveats:** estimation and sensing errors are output offsets of the true position (not in the feedback loop), chosen box-worst-case (stronger than the Euclidean certificate); w is bounded by construction (clipped Gauss-Markov), so the w_bar held-out calibration check of the plan is not exercised here - calibrating w_bar against Paper IV's sim.py plant is pending; violations are checked at the 0.1 s plant step; the filter runs at 2 Hz on a joint fleet QP with fleet-level fallback; separation is linearised (conservative); the OFF baseline has no speed governor, so its corridor margins diverge; N = 12 cells have 4-14 episodes, so their CIs are wide; the denial decomposition uses an intent proxy (cumulative progress the actions ask for vs. goal distance); for acceleration-mode (oracle) actions the asked-for velocity is taken as v + a x 1 s, which understates intent when the filter holds an aircraft at rest (e.g. oracle_denial at b_tot = 12.7 m is labelled 'envelope' although the admissible set is empty), so filter-induced shares for oracle planners are conservative; gamma = 1.625 m/s is a hover-regime constant applied to a 10 m/s cruise (transfer assumption C3).
- **Not done (pending):** real-LLM planners (A1-A5), the composed Paper IV covert attacker as an actual detector-gated process (here the sensing offset is simply realised at the budget), PX4 SITL cross-check, baselines other than filter OFF (Simplex accept/reject, one-step CBF-QP, LLM judge), >= 3e6 inside-assumption aircraft-steps per fleet size for a 1e-6 bound per cell.


## 9. Files

Root: `paperV/` in the repository

- `experiments/`: `adaptive.py`, `admissible.py`, `agent.py`, `aggregate.py`, `attacks.py`, `budget.py`, `constants.py`, `episode.py`, `export_figdata.py`, `filter.py`, `make_summary.py`, `plant.py`, `run_all.sh`, `run_campaign.py`, `stats.py`
- `results/`: `budget_levels.json`, `cem_log.csv`, `constants_paperV.csv`, `episodes_budget.csv`, `episodes_hand.csv`, `episodes_main.csv`, `episodes_mismatch.csv`, `episodes_negative.csv`, `nestedness.csv`, `oracle_theta.json`, `run_meta.json`, `solve_times.csv`, `solve_times_budget.npz`, `solve_times_hand.npz`, `solve_times_main.npz`, `solve_times_mismatch.npz`, `solve_times_negative.npz`, `summary_cells.csv`, `time_overhead.csv`
- `figdata/`: `admissible_shrinkage.dat`, `denial_vs_btot_N12_benign.dat`, `denial_vs_btot_N4_benign.dat`, `denial_vs_btot_N4_oracle_denial.dat`, `mismatch_N12_oracle_violation.dat`, `mismatch_N4_benign.dat`, `mismatch_N4_oracle_press_wall.dat`, `mismatch_N4_oracle_violation.dat`, `nestedness.dat`, `solvetime_cdf_N12.dat`, `solvetime_cdf_N4.dat`, `violation_onoff.dat`
