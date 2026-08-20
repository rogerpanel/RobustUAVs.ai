# Interface characterisation campaign — results

Run in response to the co-author review, which asked us to test δ ≈ γΔ across
UAVs, speeds, flight modes, GNSS conditions, attack intensities and attack
durations, and predicted that an unstable γ would make the paper more
interesting than a stable one.

Two arms, both reproducible from committed data:

- `experiments/gamma_campaign.py` → the interface, on real flights
- `experiments/mission_distribution.py` → the mission distribution, on the
  simulated anchor

---

## Headline: the paper's γ was 19% optimistic, and the conclusion survives anyway

| | |
|---|---|
| γ used in v6 | 1.365 m/s (per-flight secant to peak) |
| γ measured here | **1.625 m/s** (supremum of the baseline-corrected per-sample rate) |
| Understatement | **1.19×** |
| θ = 0.25 s certified at m = 10 m? | **Yes** (θ* = 0.944 s, was 1.124 s) |
| θ = 0.25 s certified at m = 2 m? | No — as v6 already reported |
| Composed dominance over autonomy-only | **13/13 operating points still significant** after Holm |

The correction moves the certified window edge in but does not close it. The
smallest corridor that certifies θ = 0.25 s rises from about 2.25 m to about
5.9 m, so the paper's headline (θ = 0.25 s is inside the window at a 10 m
corridor, outside at 2 m) is unchanged in substance.

---

## Arm A — γ is a function, and we can now say of what

674 post-onset samples from the two attack flights, each carrying the GNSS
condition and kinematics prevailing at that instant.

### The estimator question, which turned out to decide the answer

Two estimators disagree **qualitatively**, and picking the wrong one would have
produced a spurious headline.

- **γ_cum(t) = e(t)/τ.** Rises steeply as τ → 0, reaching 8.6 m/s below 1 s.
- **γ_delta(t) = (e(t) − e(onset))/τ.** Peaks at 1.625 m/s around τ ∈ [5,10) s.

γ_cum is an **artifact**. Onset is declared when the error crosses a detection
threshold, so e(onset) is already non-zero — 0.64 m for jamming at the receiver,
and 9.27 m for spoofing, where the spoof has walked the fix a long way before
the detector fires. Dividing that pre-existing offset by a small τ manufactures
a large rate that belongs to the threshold, not to the attack. Lemma 1's budget
is responsible only for error accrued *since* onset, so **γ_delta is the
estimator the certificate is entitled to**. Both are in
`results/gamma_campaign_samples.csv` so the contrast is auditable.

Had we reported γ_cum, we would have claimed γ ≈ 8.6 m/s at short staleness,
which exceeds γ_req = 6.14 m/s and would have *destroyed* the paper's result —
on an artifact.

### γ_delta across the factors

| Factor | Range measured | γ_delta median → max |
|---|---|---|
| Attack type | jamming vs spoofing | 0.14 → 1.56 (jam), 1.56 → 3.63 (spoof)¹ |
| Satellites in view | 14 → 4 | rises as satellites fall |
| Staleness | 0.4 → 70 s | 0.91 (τ<1 s) → **1.625** (τ∈[5,10)) → 0.02 (τ>40 s) |
| Airspeed | hover only, p90 < 0.65 m/s | weak positive, poorly covered |

¹ per-flight scalars from `gamma_stability.py`; the campaign's per-sample
medians differ because they weight the whole post-onset interval.

**Descriptive OLS on standardised covariates, R² = 0.791:**

| Term | Coefficient | Physically sensible? |
|---|---|---|
| satellites | −0.218 | ✔ fewer satellites → higher γ |
| staleness | −0.259 | ✔ error saturates, so the average rate falls |
| airspeed | +0.116 | ✔ faster → more error per second of staleness |
| HDOP | −0.129 | ✘ counter-intuitive; almost certainly collinear with satellite count |
| receiver noise | −0.089 | weak |

Three of four signs are physically right, which is a weak check that the fit is
picking up mechanism rather than noise. The HDOP sign should not be
over-interpreted: HDOP and satellite count are strongly dependent, and with two
flights the design cannot separate them.

**Statistical health warning, stated in the script and the paper.** Samples
within a flight are strongly autocorrelated and there are only two attack
flights. These are *descriptive* effects. No p-values are reported, because
under this dependence structure they would be meaningless.

### Coverage — what the campaign could and could not vary

| Factor | Status | Why |
|---|---|---|
| Attack type | ✅ varied | jamming and spoofing |
| GNSS condition | ✅ varied, wide | satellites 14→4, HDOP 0.71→4.16, fix 3→0 |
| Staleness / attack duration | ✅ varied | 0.4 to ~70 s |
| Airspeed | ⚠️ poor | hover; median \|v\| < 0.11 m/s, p90 < 0.65 m/s |
| **Platform** | ❌ **not varied** | one PX4 / Pixhawk 4 / Holybro S500 |
| **Flight mode** | ❌ **not varied** | hover / loiter only |

Two of the six factors the review asked for remain untested, and no amount of
re-analysis of this release will change that. They need new flights.

---

## Arm B — the mission distribution matters, and we can now price it

The review asked us to be explicit that MCR is a probability over a distribution
of missions. UAV-EW-Bench-2026 flies 93,600 simulated missions over a full
factorial of defence × J/S × seed × **mission profile** × **receiver model**, so
the dependence can be measured rather than asserted.

**Marginalised over the whole 0–40 dB attack sweep, the spread is negligible:**
MCR ranges from 0.882 to 0.893 across the nine mission distributions, a spread
of **0.011**.

**Conditional on the attack, it is large:**

| Quantity | Value |
|---|---|
| Max MCR spread from mission profile alone | **0.214** (at J/S = 35 dB) |
| Max MCR spread from receiver model alone | **0.154** (at J/S = 30 dB) |
| J/S at which MCR crosses 0.90 | **18.1 to 27.1 dB** across the nine |

That last row is the operationally meaningful one: **a 9 dB range** — roughly a
factor of eight in jammer power — separates the most and least favourable
mission distribution at the same nominal MCR reference. Quoting a single MCR
without naming its distribution hides that.

The marginal-versus-conditional contrast is itself the useful finding.
Averaging over attack intensity makes the dependence look negligible; an
operator who flies one profile against one adversary is living at a point, not
at the average.

**Provenance:** simulation (physics-informed). This arm sizes a sensitivity; it
certifies nothing.

---

## What changed in the artifact

| File | Change |
|---|---|
| `certificates/engine.py` | new `campaign_sup` mapping, γ = 1.625 |
| `experiments/compose_certified.py` | new `empirical_campaign_sup` mapping, read from the campaign output |
| `results/certified_*.csv`, `composition_perseed.csv`, `stats_wilcoxon.csv` | regenerated at the corrected γ |
| `results/gamma_campaign_*.csv`, `mission_distribution.csv` | new |
| two new figure blocks | `block_paperD_tab_gamma_campaign.tex`, `block_paperD_tab_missiondist.tex` |

`certificates/engine.py` self-check passes; all generators are idempotent.

---

## What is still blocked

Unchanged by this campaign, and now the only remaining item on the interface:

1. **Platform diversity.** One airframe. Needs flights on a second and third.
2. **Flight regime.** Hover only. Needs cruise and transition.

Everything else the review asked for has been measured. These two need
airtime, not analysis — and they are what would turn a calibration into a
characterisation.
