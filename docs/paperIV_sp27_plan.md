# Paper IV for S&P 2027 (Cycle 2): consolidated plan

Registration 10 Nov 2026 (AoE), submission 17 Nov 2026 (AoE). This plan merges three
inputs: the supervisor's three points, the author's analysis (replace the empirical attack
budget with a certified worst-case budget for an explicit attacker class), and the PX4
port plan. Internal document; not part of any reviewer artifact.

## 1. What each input asks for, and how they fit

| Input | Asks for | Where it lands |
|---|---|---|
| Supervisor 1 | What becomes possible that existing methods do not provide | §2 positioning table; one paragraph in the introduction |
| Supervisor 2 | Strict justification of the bound against an adaptive attacker | §3 certified budget (formal track) |
| Supervisor 3 | Attacker model and experiments too weak for a security certification | §3 attacker class + §4 PX4 transfer (realism track) |
| Author's analysis | Certified worst-case budget for a defined class; start linear; show how it degrades on a realistic model; the class must be bounded or no finite bound exists | §3, which already has a starting point in the paper (the LP "analytic stealth budget") |
| PX4 port plan | SITL transfer study, title change, page fixes, positioning | §4 and §5; requires the PX4 machine used for Paper III |

## 2. What becomes possible (supervisor 1)

| Existing line of work | What it gives | What it does not give | What Paper IV adds |
|---|---|---|---|
| GNSS spoofing detection (signal-, estimator- and invariant-based) | an alarm | any statement about the mission once the alarm stays silent | a bound on undetected mission failure that holds whether or not any detector fires |
| Stealthy-attack reachability (Mo & Sinopoli; Urbina et al.) | worst-case estimation error under one residual detector | a stack of heterogeneous detectors, benign disturbances of unknown dependence, a mission-level failure probability | all three, for a stack (jump rule, CUSUM, anchor gate, saturation alarm) |
| Control-invariant detection (Choi et al.; SAVIOR) | detection and, for SAVIOR, an empirical deviation an attacker can induce undetected | a proof for an adaptive attacker class; disguise as an attacker choice | an attacker who optimises the disguise against the stack, and a certified worst-case deviation for the class |
| Certified robustness | input-to-output radius of a model | the origin and size of real perturbations; closed-loop missions | closed-loop, mission-level bound with measured benign marginals |
| Runtime assurance (Simplex) | safe switching once a monitor fires | a guarantee when the monitor is fooled | the re-anchoring interval as a monitor design rule with a certified consequence |

One-sentence claim (to be checked against the final results): *for a GNSS-offset attacker who
knows the system and chooses the disguise adaptively, we bound the probability that a UAV
mission fails without any detector firing, for every coupling of the benign disturbances, and we
show that the bound is finite only when the estimator is re-anchored by a trusted fix.*

## 3. Formal track: a certified budget for an explicit attacker class (supervisor 2, author)

**Attacker class A_GNSS.** Any causal, adaptive sequence of GNSS position offsets d_j, one per
GNSS epoch, chosen with full knowledge of the model, the noise realisation and every detector
threshold. The attacker cannot alter the IMU, the actuators or the trusted anchor fix.

**Why the class must be bounded (author's point).** The paper's own analytic rows already show
it: with the anchor gate alone, or without the anchor, the worst case is infinite. Only the trusted
re-anchoring (C2'), the jump rule and the saturation alarm make it finite. This becomes a stated
result: finite worst case if and only if re-anchoring is present (necessity by construction of an
unbounded attack; sufficiency by the convex programme).

**Certified budget.** On the linear loop, the attack-only deviation is linear in d, and each
detector's "no alarm" set implies convex constraints on d (plus benign margins at empirical
quantiles, so the bound holds with probability >= 1 - eps over benign noise, jointly for every
attack in the class, hence for every adaptive policy). The worst-case undetected deviation is then a
convex programme, solved exactly:
- D1 jump rule, anchor gate, D_sat: linear constraints (already in the paper: 31.9 m at T_a = 5 s).
- D3 CUSUM: convex. The CUSUM stays below threshold if and only if every window sum of squared
  residuals stays below a linear function of the window length; with the triangle inequality this
  gives second-order-cone constraints. Implemented in `paperIV/experiments/r9_convex_bound.py`.
- D2 (3 consecutive exceedances) and D4 (5 consecutive): disjunctive, so exact treatment needs a
  mixed-integer programme; dropping them keeps the bound valid (a superset of the feasible set).

**First results (9 Nov).**
- Adding the CUSUM detector (D3) as cone constraints barely tightens the bound (35.2 vs 35.9 m at
  the same evaluation point, T_a = 5 s): its threshold (about 2,479) must admit benign wind,
  jamming noise and outages, so it leaves the attacker almost unconstrained. Formal confirmation of
  the thesis: the benign envelope is the attacker's budget.
- The proved worst case falls almost linearly with the re-anchoring interval
  (LP: jump rule + anchor gate + saturation alarm, 1% FPR, eps = 0.01, stride 20, LoE 1.0/0.7):
  T_a = 0.5 s: 7.5 m; 1 s: 10.2 m; 2 s: 14.8 m; 3 s: 19.7 m; 5 s: 31.9 m.
  This is the design rule with a proof: re-anchoring at 1 s certifies a 20 m corridor against every
  attacker in A_GNSS on the linear loop; 0.5 s certifies 10 m (before subtracting the network tube
  and the benign floor in Theorem 1).
- Full grid (all operating points, all LoE values, stride 10) running:
  results/r8_analytic_bound_short_anchor.csv.
- Still to do: a confidence correction on the empirical benign quantiles (order-statistic bound),
  so the "probability >= 1 - eps" statement holds with stated confidence rather than in the
  large-sample limit.

**Then:** Theorem 1 uses the certified budget instead of the empirical one, so the floor is
certified for A_GNSS on the linear loop, and the empirical optimisers become a lower bound that
brackets the truth (empirical <= true worst case <= certified).

**Degradation to a realistic model (author's point).** Two steps: (i) a model-mismatch term,
the largest attack-only deviation difference between the linear loop and PX4 EKF2 measured in
SITL, added to the certified budget; (ii) the PX4 transfer study (§4) as the empirical check.

## 4. Realism track: PX4 transfer (supervisor 3, PX4 plan)

Follows the PX4 port plan (GNSS-offset hook in the simulated GPS, trusted vision-position anchor,
offline detectors from ULog, seed-matched benign twins, pre-registered E0–E2, E3–E4 if time).
It needs the PX4 v1.14.3 SITL machine used for Paper III; it cannot run in the drafting sandbox.
Code that can be written without the machine: the SITL patch, the MAVLink driver, the offline
detector scripts, the pre-registration file, and the analysis that turns ULogs into the tables.

## 5. Paper changes

- Title: decided after the certified-budget result (see the decision note in the chat).
- Abstract: neutral on PX4 until results exist.
- Theorem 1: the network term's additivity in the statement; the certified budget as the input.
- New subsection: the attacker class, the convex programme, the finiteness result, a small table
  (certified vs empirical budget per T_a), and the held-out exceedance counts (1/45, 12/270, 6/216).
- Page budget: Section V to one paragraph; Ethics and Artifact after the references; §VII-H into
  the Discussion.
- Overlap field: declare Paper III and the delay-certificate paper (shared Section II-B).
