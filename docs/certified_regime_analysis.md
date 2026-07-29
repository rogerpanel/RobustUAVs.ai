# The certified-regime question — analysis and verdict

**Date:** 2026-07-28 (W2). **Status:** resolved; determines Paper A's headline.
**Provenance:** every number below is from local, seeded runs of committed code
(DATAMUt replay, Phase-A synthetic corpus). Nothing here is real-corpus-derived:
Kaggle/IEEE DataPort remain unreachable from this environment (egress 403), so
all constants marked *fixture* must be re-derived once the real corpus is
reachable before they appear unqualified in a paper.

## The question

`caf_shift_v1` certifies only sub-decimetre GNSS perturbations: anything above
~10 cm plateaus at feature-space ℓ2 ≈ 5.1, far outside the Grönwall radius
0.18, so the certified MCR floor looked near-zero across the whole operational
range (real spoof/jam errors are metres-plus). Physically correct, or artifact?

**Verdict in one paragraph.** Both, in layers. (a) is an artifact and is fixed:
v1 charged the carrier-phase nuisance to the adversary, understating the
certifiable spoof magnitude by ~216×; the corrected tracking-loop bridge
(`caf_shift_v2`) certifies to ~0.45 m (Grönwall) / ~1.15 m (RS), and the
residual "metre-scale spoofs are outside the tube" is genuine physics — the CAF
feature space *must* be sensitive to metre-scale code-delay displacement or the
detector could not work. (b) is refuted: the radius is not too tight; the local
Lipschitz constant over the operating region is *larger* than the power-iteration
estimate. (c) is the substantive correction and the one that changes Paper A:
for the time-delay class the perturbation lives in vehicle **state space**
(staleness), not in CAF feature space; routing it through the RF bridge was a
category error. With the state-space certificate and a **measured tightening of
Lemma 1**, the certified floor no longer collapses at the knee — it saturates —
and a nonempty certified operating window exists, but it is **narrow and sits at
tighter thresholds than the paper's θ = 0.25 s operating point**.

---

## Finding 0 (unplanned, blocking): the committed operating curve was wrong

The DATAMUt demo **appends** to `datamut-paper-metrics-summary.csv`;
`ingest/sweep_theta.py` reused one working directory across all operating
points and averaged over *all* rows each time. Every point after the first was
a running average over all previous (scenario, mode, ε) points.

Evidence (scenario 1, low mode):

| ε (s) | committed recall | clean recall (8 seeds, fresh dir) | committed `n_runs` |
|------:|-----------------:|----------------------------------:|-------------------:|
| 0.25  | 0.938 | 0.938 | 32 |
| 4.0   | 0.891 | **0.609** | 224 (= 7 accumulated points) |
| 6.5   | —     | **0.234** | — |

The smoking gun is the committed `n_runs` column: 32, 64, 96, … (cumulative),
and the committed medium-mode curve *rises* with ε — impossible for a
threshold detector. **Consequences:** `results/theta_operating_curve.csv`
(regenerated clean), Paper C Fig. 3 coordinates (replaced), and the CLAUDE.md
"measured operating curve" facts (recall ≈ 0.90 for ε ≤ 2 → holds only at
ε ≤ 3; 0.675@4 → 0.609; 0.275@6.5 → 0.234; scenario-3 medium plateau
≈ 0.71 → 0.625) were all contaminated. `sweep_theta.py` is fixed; the full
clean campaign is `experiments/sweep_full.py` →
`results/theta_operating_curve{,_perseed}.csv`.

## Finding 1 — hypothesis (a) CONFIRMED: the plateau was the carrier-phase nuisance

`experiments/bridge_decomposition.py` (64 seeded windows, same corpus as v1
calibration) separates the two first-order signal effects of a d-metre
position error:

| variant | plateau ℓ2 | d at Grönwall R=0.18 | d at RS R=0.44 |
|---------|-----------:|---------------------:|---------------:|
| full (v1 = delay + carrier) | 6.37 | **2.1 mm** | 5.1 mm |
| carrier rotation only       | 5.09 | 2.1 mm | 5.1 mm |
| code delay only             | 6.48 | **0.45 m** | 1.15 m |
| tracked (delay, phase wiped) | 5.66 | **0.45 m** | 1.15 m |

The carrier term alone reproduces v1's crossings exactly: the sub-decimetre
cliff was 2πd/λ wrapping at λ = 19 cm. But absolute carrier phase is a
receiver **nuisance parameter** — tracking loops wipe it before any feature
extraction, and in real IQ it is uniformly random per window. (It looked
informative here only because the synthetic clean corpus fixes the initial
phase — a fixture artifact.) The corrected bridge `caf_shift_v2` (code delay +
phase wipe-off by complex correlation) is now the engine default; v1 is kept
for provenance. **What remains after the fix is physics:** at 0.45 m the code
delay already displaces the CAF features by the certified radius — the same
sensitivity that makes the spoof *detectable*. Certify-small / detect-large is
the correct dichotomy, not a defect.

## Finding 2 — hypothesis (b) REFUTED: the radius is not too tight

`experiments/local_lipschitz.py` on the trained Phase-A checkpoint
(`run_phase_a.sh`, synthetic corpus, seed 0; estimator seed 20260728):

| estimator | value | Grönwall radius R = 0.5·e^(−L) |
|-----------|------:|-------------------------------:|
| power iteration, random (h,x) — dissertation | 0.983–1.013 | 0.182–0.187 |
| **local max, data-driven trajectories** | **1.181** | **0.153** |
| local median | 1.152 | 0.158 |
| end-to-end input→logit slope (small ball) | 1.534 | n/a |

The operating-region constant is *larger* than the global estimate, so honest
local certification would *shrink* the radius (0.153), not grow it. L̂ ≈ 1.01
stands as the reference constant; there is no slack to harvest here.

## Finding 3 — hypothesis (c) CONFIRMED: time-delay δ lives in state space

The 0.18 radius certifies the **CT-TGNN model** against perturbations of its
**CAF-feature input** — the right object for GPS spoofing/jamming, where the
adversary reshapes the receiver input. A time-delay forwarding attack never
touches the RF front-end; its effect is that the stack acts on a correction
that is Δ(θ) seconds **stale**. That perturbation is a position-state offset
(metres), and the composition theorem's trajectory tube is a state-space
object with a corridor margin in metres. Feeding v_max·Δ(θ) through the CAF
bridge conflated the two spaces and guaranteed a near-zero floor at any θ.
`certificates/engine.py` now has `StalenessGronwallCertificate`
(`gronwall_state_space`) as the time-delay-class certificate.

### The measured tightening of Lemma 1 (this is the new result)

The clean campaign (3 topologies × 2 modes × 13 ε × 8 seeds × 4 policies;
15,392 observed hops in `results/hop_ledger.csv`) shows:

* **No undetected malicious per-hop residual ever exceeds 4.84 s — at any ε,
  including ε = 10 s.** A delay that overshoots the 5 s contact-window slack
  forces a missed window; the packet waits a full TWiG period, and the
  resulting ≥ 55 s residual is flagged at every plausible threshold. 100 % of
  missed-window events across the campaign were caused by malicious senders.
* Benign residuals never exceed **0.178 s** (the benign delay cap) — this is
  the measured FPR = 0 feasibility floor for θ.

So Lemma 1's budget Δ(θ) ≤ Hθ + P·1[θ > s] tightens to

    Δ(θ) ≤ H · min(θ, s),        s = 5 s (measured cap 4.84 s)

— the penalty term P is not invisibly exploitable: **the knee cuts both
ways.** It also resolves the open scenario-3 question: the medium-mode plateau
(clean value **0.625**, not the contaminated 0.71) is *not* a path-deviation
trigger — at ε ≥ 6.5, path-mismatch detections are zero and every surviving
detection is a ≥ 50 s missed-window residual. The plateau is the attacker's
self-exposure probability P[delay > slack], which is why medium (U[1,10])
plateaus higher (0.625) than low (U[1,7], 0.312).

### The corrected certified curve and its honest shape

With Δ(θ) = H·min(θ, s), δ_pos = v_max·Δ (kinematic worst case,
`staleness_v0`), tube ρ = δ_pos·e^(L·T) (reference L=1.01, T=1 ⇒ ×2.746), and
the stated margin family M = {2, 5, 10, 20} m (10 m ≈ PX4-default
acceptance-radius class):

* The certified floor **saturates instead of collapsing** for θ > s.
* The certified operating window [benign ceiling, θ*(m)] is **nonempty but
  narrow** (H = 2 malicious hops, all three topologies):
  θ* = m/(v_max·e^(LT)·H) = **0.243 s** for m = 20 m (window [0.178, 0.243] s);
  un-amplified kinematic tube: θ* = 0.33 s (m = 10) / 0.67 s (m = 20).
* **The paper's θ = 0.25 s operating point sits just outside the 20 m
  Grönwall-amplified window** (0.25 > 0.243). Under the loose kinematic
  mapping nothing is certifiable at θ ≥ 0.25 for m ≤ 20 m.

Full curves: `results/certified_floor_vs_theta.csv`,
`results/certified_operating_window.csv`, per-seed budgets in
`results/composition_perseed.csv`.

### Dominance (per-seed, Wilcoxon signed-rank + Holm; `results/stats_wilcoxon.csv`)

* composed vs autonomy-only floor: composed wins at **13/13** ε points
  (median paired difference 1.0 — with a detector at work the *measured*
  undetected budget is usually 0 s, certifying the whole margin family, while
  autonomy-only must absorb the full delay including 60 s window penalties →
  floor 0); all Holm-adjusted p < 1e-20.
* network-only certifies nothing for evading attacks by definition (floor 0).
* medium vs low recall differs significantly at 10/13 ε; and at ε ≥ 6 the
  medium attacker slips *less* delay past the detector than the low one
  (median −3.17 s, Holm p ≈ 2e-13) — the knee corollary, measured.

## What this means for the papers (contradictions stated plainly)

1. **Paper C Fig. 3 is wrong** (contamination bug) and its medium-mode curve
   is visibly impossible (recall increasing in ε). Replace with the clean
   per-scenario curves; the qualitative story (recall ceiling → knee → floor)
   survives, and the new plateau mechanism is a better story: the detector's
   loose-threshold recall floor *is* the attacker's missed-window penalty.
2. **Paper A's headline figure as drafted is not defensible**: its "certified
   floor" coordinates were placeholders tracing the EW-Bench J/S curve on a θ
   axis. The corrected headline is the state-space certified floor vs θ with
   the knee saturation, the narrow certified window annotation, and the
   dominance baselines. The claim "holds the DO-326A floor across a jamming
   range where neither layer alone does" must be re-scoped: for the
   time-delay class the composition holds its floor **only inside
   [0.178 s, θ*]**, θ* ≤ 0.67 s under worst-case kinematics. The honest
   headline: *the composition is the only configuration with a nonzero
   certified floor at all, and a nonempty FPR-0 certified window exists* —
   dominance survives; blanket-range coverage does not, pending the
   Whelan-grounded δ tightening.
3. **Lemma 1 improves**: add the min(θ, s) tightening with its measured
   justification. Theorem 1's monotone-in-θ statement gains a saturation
   clause.
4. **The two-floors discipline stands**: 0.80 is the certified target inside
   the tube; 0.90 DO-326A remains the empirical operational floor (EW-Bench,
   real-corpus side, unverifiable from this environment).

## ADDENDUM (2026-07-29): the empirical δ mapping — and it WIDENS the window

The real Whelan sample (3 live flights, `experiments/whelan_delta_calibration.py`,
`results/whelan_delta_calibration.csv`) replaces the kinematic v_max·Δ with a
**measured error-growth rate γ [m per second of degradation]**. This is the
number the prior prompt flagged as deciding Paper A's framing, and it lands
clearly on the window-widened side.

**Measured γ (self-referenced, pre-attack median; hover regime):**

| flight | source | onset | peak (m) | γ_lsq (m/s) | γ_peak (m/s) |
|--------|--------|------:|---------:|------------:|-------------:|
| jamming  | receiver | fix-loss @175 s | 6.73 | −0.08 | 0.48 |
| jamming  | ekf      | 3×noise @177 s  | 7.00 | −0.11 | 0.52 |
| spoofing | receiver | 3×noise @119 s  | 14.34 | 0.24 | **1.20** |
| spoofing | ekf      | 3×noise @120 s  | 15.57 | 0.70 | **1.37** |

Conservative empirical γ = **1.37 m/s** (max rate). Compare the kinematic worst
case γ = v_max = 15 m/s — **~11× looser**.

**δ source is an explicit switch, not silently chosen** (per the prompt's
constraint 2). Two mappings are carried through every downstream artifact:
`empirical_receiver` (γ=1.20 m/s — the false fix the attack injects at the
estimator *input*) and `empirical_ekf` (γ=1.37 m/s — the filtered error the
controller *acts on*, from local.csv). They differ by <15% here because in the
hover regime PX4's EKF barely rejects the slow spoof/jam ramp; under a fast
spoof they would diverge. The certificate should consume the **ekf** error
(that is what closes the loop), with the receiver error reported as the
attack-injected upper input — both are in the CSVs and both are plotted.

**Does θ = 0.25 s come inside the certified window? YES, at every margin.**
(`results/certified_operating_window.csv`, `results/delta_mapping_sensitivity.csv`;
scenario 1, Grönwall-amplified tube, H=2.)

| mapping | γ (m/s) | θ*(m=2 m) | θ*(m=10 m) | θ*(m=20 m) | θ=0.25 inside? |
|---------|--------:|----------:|-----------:|-----------:|:--------------:|
| kinematic worst case | 15.0 | 0.024 s | 0.121 s | 0.243 s | **no** (all margins) |
| empirical_receiver | 1.20 | 0.305 s | 1.52 s | 3.05 s | **yes** (all margins) |
| empirical_ekf | 1.37 | 0.267 s | 1.33 s | 2.67 s | **yes** (all margins) |

**How gentle must the mapping be to admit θ = 0.25 s?** The threshold is
γ_req = m/(θ·e^{LT}·H). At m = 10 m, γ_req = **7.28 m/s**; the measured γ ≈
1.2–1.4 m/s clears it by ~5×. Even at the tightest 2 m corridor, γ_req = 1.46
m/s and the receiver mapping (1.20) still fits. So θ = 0.25 s is inside the
certified window under the empirical mapping across the entire stated margin
family — the conclusion is not margin-knife-edge.

**Is that physically plausible?** Yes, and for a concrete reason: the kinematic
bound assumes the vehicle flies blind at v_max for the whole staleness
interval, but a real PX4 EKF rejects bad GNSS and coasts on IMU/baro, so
position error grows at ~1 m/s, not ~15 m/s. γ_emp ≪ v_max is the expected
ordering, not a fluke. The bound would only approach kinematic if the estimator
fully trusted the corrupted GNSS — which the DO-326A "no loss of stabilisation"
labelling already excludes.

**Three caveats keep this honest (prompt constraint 3):** (i) n = 3 flights,
**hover regime** (|v| ≈ 0.05 m/s) — at cruise the staleness error per second is
larger, and γ could rise toward the kinematic bound; even so it would need to
exceed 7.28 m/s (m=10 m) to push θ=0.25 back out, a >5× rise. (ii)
Self-referenced to the first 25 % because the true attack intervals are not in
the CSVs (`whelan_manifest.json` intervals are TODO). (iii) These are three
flights, a calibration sample, not a distribution; TEXBAT re-calibration and a
larger flight set stay on the pending list. **Verdict for Paper A: frame the
window as widened by the empirical mapping (θ = 0.25 s certified), with the
kinematic worst case shown as the conservative fallback and the cruise-regime
caveat stated. Draft both abstracts (paper/abstract_A_*.tex); this result
selects the "widened" one, pending confirmation on more flights/cruise data.**

## Calibration-pending register (do not quote unqualified)

| quantity | current value | status |
|----------|---------------|--------|
| caf_shift_v2 crossings (0.45 m / 1.15 m) | synthetic clean corpus | re-calibrate on real TEXBAT |
| v_max·Δ staleness mapping | worst case (15 m/s) | replace with Whelan-measured pos_error vs delay (real corpus, blocked this session) |
| closed-loop L for the vehicle tube | reference L=1.01 (CT-TGNN drift) | needs EW-Bench closed-loop calibration; curves also reported un-amplified (A=1) |
| margin family {2,5,10,20} m | stated model parameter | replace with per-mission corridor margins from EW-Bench design |
| empirical MCR vs θ validation | not measurable here | requires real corpus / EW-Bench backend |
