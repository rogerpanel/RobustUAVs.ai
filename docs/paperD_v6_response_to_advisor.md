# Response to the co-author / PhD advisor review of Paper D

Source: review of the Conti-corrected v5 draft. Result: `paper/paperD_v6.tex`,
0 errors, 0 undefined references.

Unlike the previous round, this one is **not** a presentation revision. Five of
the six points are about what the paper is entitled to claim, and they are
right. One of them produced a new empirical result.

---

## The headline: point 1 answered with data, and the answer is negative

> *"Test the most important relationship. The authors should demonstrate
> δ ≈ γΔ across different UAVs, speeds, flight modes, GNSS conditions, attack
> intensities, attack durations. If γ is genuinely stable, that would be a very
> strong result. If it is not, the model should instead become
> γ = γ(x, u, flight mode, attack type). That would actually make the paper even
> more interesting."*

We ran this over the factors the released corpus permits, and **γ is not
stable**. New script `experiments/gamma_stability.py`, new
`results/gamma_stability.csv`, new Table (§VII-C, `sec:gammastability`):

| Attack type | Error signal | γ (m/s) |
|---|---|---|
| GPS jamming | raw receiver fix | 0.48 |
| GPS jamming | EKF-filtered | 0.52 |
| GPS spoofing | raw receiver fix | 1.20 |
| GPS spoofing | EKF-filtered | 1.36 |

- **Spread across attack type: 2.6×.** Spoofing drives position error two and a
  half times faster than jamming.
- **Spread across error signal: only 1.14×.** The filter attenuates injected
  error far less than one might hope, which is itself worth reporting.

The direction is mechanistically right, which is a weak check that the
measurement is real: jamming *removes* information, so the estimator gates the
missing fix and dead-reckons at the inertial drift rate; spoofing *injects*
information the estimator accepts, so error accrues at whatever rate the
attacker chooses. A plausible lie should beat silence, and it does.

**What this changes in the paper.** The honest model is
γ = γ(attack type, …), not γ = const, so the certificate is now explicitly
evaluated at the **supremum over observed conditions** (γ = 1.365 m/s). Using
the jamming rate would widen the certified window 2.6× and would not be
defensible against an adversary free to pick the attack.

**What it does not change.** Four combinations, one airframe, hover only. The
release fixes platform, airspeed, flight mode, attack intensity and attack
duration, so the 2.6× we report is a **lower bound** on real variability. The
paper now says this in those words, and the script prints the five unvaried
factors by name so the claim cannot drift.

---

## Point-by-point

### 2. *"The theorem is a guarantee only under Lipschitz dynamics + re-anchoring + valid interface mapping. It should be described more explicitly as a conditional certificate."*

Adopted. New **§I-B "Scope of the Guarantee"**, placed immediately after the
contributions so the reader meets the conditions *before* the theorem rather
than in the limitations section. The three conditions are labelled (C1)–(C3) and
referenced by label wherever they bind:

- **(C1) Dynamics** — Lipschitz over the operating region; outside it the
  certificate makes no statement at all.
- **(C2) Re-anchoring** — one uncorrupted state update per horizon $T_c$; a
  delay adversary satisfies this, a persistent-denial adversary does not.
- **(C3) Interface transfer** — the measured γ applies to the deployment. Named
  as the weakest of the three, with the 2.6× result cited inline.

### 3. *"A substantial part of the cross-layer relationship was not directly observed on the same UAV platform. The claim of mission-level security should either be weakened or supported by substantially more same-platform experiments."*

Weakened, at the point where the claim is made rather than three sections later.
The introduction's "first guarantee that carries a network-security threshold
through to a navigation-safety floor" now carries an immediate qualification:
only one of six datasets observes both layers on one airframe, its release lacks
machine-readable attack intervals, and therefore **no released pairing is of the
strongest evidence class**. The coupling rests on a stated physical relation
calibrated on real flights, not on same-platform observation of both windows
together. "Navigation-safety floor" is also now "mission-completion floor",
which is what is actually bounded.

### 4. *"The comparison demonstrates the logical advantage of composition, but not superiority over modern alternative approaches to robust autonomous-system assurance."*

Conceded explicitly. New subsection **"What this comparison does and does not
establish"** (§X-E) states that the two baselines are *ablations of our own
construction* — what remains when one layer is removed — and that this shows
composition is doing the work, not that we beat anything.

It then names what we do not benchmark against and why: reachability
verification, secure state estimation, runtime assurance, certified RL. The
reason given is a limitation, not an excuse — none of those methods consumes a
detector operating point, so there is no shared axis. The section ends by naming
the comparison that *would* be fair (lower ours to a fixed perturbation ball and
compare tube tightness against a modern reachability tool at equal input radius)
and stating plainly that we have not done it.

### 5. *"The central link is not a theorem but an empirical calibration. I would not describe the result as 'end-to-end certified security of UAVs.' A more accurate description would be: a composed conditional guarantee under an empirically calibrated cross-layer interface."*

This was the sharpest point and it reached the title.

**Old:** *From Wire to Flight: An End-to-End Framework for Network-to-Navigation
UAV Security*
**New:** *From Wire to Flight: A Conditional Mission-Completion Guarantee for
UAVs under an Empirically Calibrated Cross-Layer Interface*

The abstract now has a dedicated paragraph beginning "We are deliberate about
what this does and does not establish", which says in as many words that the
chain is not a theorem end to end and that its middle link is an empirical
calibration on three flights. §I-B repeats it: the first and last links are
proved, `Δ ↦ δ` is measured, and "presenting the whole as certified end-to-end
security would misstate where the evidence lies, so we do not."

The Conclusion is rewritten to end on this rather than on the strong claim: the
interface decides the outcome, therefore the result is only as strong as the
calibration behind it.

### 6. *"What exactly is the probability space? MCR_benchmark ≠ MCR_arbitrary. I would ask the authors to discuss this much more explicitly."*

New subsection **§II-C "What the probability in Eq. (3) is over"**
(`sec:probspace`). It states the space formally —
$(\Omega, \mathcal{F}, \mathbb{P}_\mathcal{M})$ where a sample point is one
mission: route, duration, corridor margin, initial state, wind realisation, and
the number of attacker-controlled hops — and observes that once θ is fixed,
δ(θ) and Δ(θ) are deterministic, so *all* randomness comes from the mission.

Three consequences are then stated rather than left to be inferred:

1. **The guarantee is relative to $\mathcal{M}$.** Written explicitly:
   $\mathrm{MCR}(\mathcal{M}_\text{benchmark}, \theta) \neq \mathrm{MCR}(\mathcal{M}_\text{arbitrary}, \theta)$,
   and ours is the former.
2. **The dependence is confined to two parameters**, the corridor margin $m$ and
   the hop count $H$. This is a useful thing to be able to say: it is *why* we
   report over a margin family rather than at one value, and it means an
   operator can instantiate the bound for their own distribution by reading off
   their own $m$ and $H$.
3. **A bound on a proportion is not a bound on a flight.** MCR ≥ 0.9 permits one
   mission in ten to fail and says nothing about which. A per-flight guarantee
   would need a bound conditional on ω, which Grönwall supplies only in the
   degenerate case where $m$ and $H$ are known in advance.

The empirical mission distribution used in §X is now stated explicitly instead
of being reconstructable from the figures.

---

## What did not change

No number, no figure, no experimental result. The γ table is new analysis of
data already committed; everything else is scoping.

---

## Page budget — the one thing that got worse

The scoping additions cost about two and a half pages. To pay for them I moved
the learned-detector generalisation to an appendix (it is a derivation we never
instantiate, so it is reference material) and compressed the four-certificate
walkthrough. Net: **the body now ends on page 16 against NDSS's 13**, so it is
roughly 2.5 pages over.

Three options, in the order I would take them:

1. **Move §IX (four-certificate architecture) to an appendix, keeping one
   paragraph and the table in the body.** ~2 pages. The paper's core claim is
   the composition and the interface; the other three certificates are
   architecture, and the reviewers' critique never touched them.
2. **Move the worked end-to-end example (§X-C) to an appendix.** ~0.75 page,
   but it is the section that most helps a reader follow the chain, so I would
   not cut it before option 1.
3. **Switch to the official `ndss.cls`,** which is slightly more compact than
   the IEEEtran configuration currently emulating it. Perhaps 0.3 page.

I have not applied any of these, because they change what is in the paper rather
than how it reads, and after a review asking for *more* validation I would
rather you choose what leaves the body than have me pick.

---

## An observation on the review as a whole

Points 2, 3, 4 and 5 all say a version of the same thing: the paper claims a
general result and possesses a conditional one. Fixing that is mostly
reframing, and it is done. Point 1 is different in kind — it asks for evidence,
and the evidence we could produce came back negative. That is genuinely good for
the paper in the way the reviewer predicted ("that would actually make the
paper even more interesting"), because γ = γ(attack type) with a measured 2.6×
spread is a more interesting and more useful statement than an unexamined
constant. But it also means the interface is now openly the weakest link, and
the campaign to characterise it across platform, airspeed, flight mode, attack
intensity and duration is not a small piece of work.

Combined with Prof. Conti's assessment, the case for postponing this cycle and
running that campaign looks stronger than the case for submitting. That is not
my call, but the paper we would have after the campaign is a materially
different and better paper than the one we have now.
