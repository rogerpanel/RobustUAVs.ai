# Research roadmap — three follow-on papers from the composition theorem

**Status:** proposals, not commitments. Written 2026-08-13, after Paper D (NDSS)
was revised. Each is scoped so that it (a) reuses machinery already in this
repository, (b) yields a paper, and (c) lands as a page in the platform.

**Recommendation up front.** Run **P1** and **P2**. P1 converts Paper D's
sharpest limitation into a contribution and needs no new theory. P2 is the only
one of the three whose new data you can generate yourself on a €60 board with no
dataset gatekeeper, which given how much of this project has been blocked on
data access is worth more than it looks. **P3** is a systematisation paper: lower
risk, lower novelty, high policy relevance, and the natural fallback if either
of the others stalls.

---

## The thing that makes all three possible

Paper D's chain is

> θ ⟼ Δ(θ) ⟼ δ(θ) ⟼ MCR ≥ f(δ(θ))

and its central empirical finding is that **the interface, not the theorem,
decides the outcome**: γ (metres of position error per second of degraded input)
is what separates a vacuous certified window from one containing the operating
point.

Two properties of that chain are underexploited, and each opens a paper.

1. **γ is a property of the navigation source, not of the attack.** Change the
   PNT modality and you change γ, which moves the certified window without
   touching a line of the proof. → **P1**
2. **Δ is agnostic about why the input is stale.** The theorem never asks
   whether the delay came from an adversary or from your own cryptography.
   → **P2**

---

# P1 — Certified PNT substitution: the certificate as a sensor-selection rule

**Working title:** *Which Navigation Source Certifies? Alternative PNT Under a
Composed Network-to-Navigation Guarantee*

### The gap

Paper D certifies a GNSS-based navigation stack and, in §XII, admits the
boundary honestly: Theorem 1 relies on Definition 2, that at least one
uncorrupted state update arrives per certification horizon T_c. A delay
adversary satisfies this by construction; **a persistent-denial adversary does
not, and there the certificate degrades as e^{L·T_c} in the denial duration.**

That admission is the whole opening. The GNSS-denied navigation literature has
spent a decade building exactly the thing that restores Definition 2 — and none
of it is expressed as a re-anchoring guarantee.

The most interesting instance: **Iridium STL is roughly 1000× stronger than
GNSS at the receiver and is cryptographically authenticated**, so a receiver can
reject a spoofed or tampered navigation solution rather than fuse it
([Inside GNSS](https://insidegnss.com/iridium-next-leo-satellites-as-an-alternative-pnt-in-gnss-denied-environments-part-1/),
[Ground Control](https://www.groundcontrol.com/blog/a-pnt-trusted-positioning-bvlos-drone-operations/)).
Multi-constellation LEO signals-of-opportunity work reports 9.5 m 3D RMSE and
4.4 m final 3D error from four Starlink, one OneWeb, two Orbcomm and one Iridium
satellite ([Inside GNSS](https://insidegnss.com/a-look-at-the-stars-navigation-with-multi-constellation-leo-satellite-signals-of-opportunity/)),
and NAL Research and VectorNav are productising STL-aided INS
([The GPS Time](https://www.thegpstime.com/nal-research-vectornav-iridium-stl-ins-gnss-denied-navigation/)).

Nobody has asked the composed question: **does switching PNT source move the
detector's operating point into the certified window, and by how much?**

### The claim

Let a platform carry a set of PNT modalities S = {GNSS, LEO-SoOP, terrain-
referenced, visual-inertial, INS-only}, each with

- a **degradation rate** γ_s (m/s of position error per second of stale input),
- an **authentication state** a_s ∈ {authenticated, unauthenticated}, and
- an **availability process** over the mission.

Then:

- **Claim 1 (γ becomes a vector).** The certified window edge
  θ*(m) = m / (γ_eff · e^{L·T_c} · H) is computed against the γ of the *fused*
  estimate, and fusing a low-γ source strictly widens the window. This is
  arithmetic, not new theory — which is the point. The contribution is the
  *measurement* of γ per modality, exactly as Paper D's contribution was the
  measurement of γ for GNSS.
- **Claim 2 (authentication restores Definition 2).** A cryptographically
  authenticated PNT source supplies an uncorrupted update per T_c *under RF
  denial of the unauthenticated sources*, because the adversary can jam it but
  cannot forge it — and a jammed authenticated source is detected, not fused.
  This converts Paper D's admitted limitation into a *satisfiable hypothesis*
  with a named piece of hardware behind it.
- **Claim 3 (a selection rule).** Given corridor margin m, detector operating
  point θ, and a per-modality cost, the certificate induces a partial order over
  sensor suites: the minimal suite whose fused γ keeps θ inside the window. This
  is a procurement-grade output, and it is what an operator actually wants.

### What is reused, what is new

| Reused unchanged | New |
|---|---|
| Theorem 1, Lemma 1, Definition 2 | γ measurement per modality |
| `certificates/engine.py` | availability/authentication state in the schema |
| `experiments/compose_certified.py` | fusion model for γ_eff |
| the corridor-margin family, SORA-anchored | the selection rule and its proof of optimality |

Schema change is small and additive: `Event.metrics` gains `pnt_source` and
`pnt_authenticated`; a new `PNTModality` enum joins `$defs`. No change to
`CrossLayerPairing`.

### Experiment plan

1. **γ per modality.** GNSS is done (Whelan, γ = 1.20 receiver / 1.37 EKF m/s).
   For the others, in descending order of evidential strength:
   - INS-only: measurable today from the Whelan logs themselves, by holding the
     GNSS fix and integrating IMU — this gives the dead-reckoning γ that Paper
     D's §X-D error-budget argument currently *asserts*. **Do this first; it
     retroactively strengthens Paper D.**
   - Visual-inertial: public VIO datasets with UAV motion profiles.
   - LEO-SoOP: the honest gap. Either a partnership for STL receiver logs, or a
     `physics_model` γ derived from published RMSE and update rate, tagged as
     such. **Do not report a modelled γ as measured** — the whole provenance
     discipline exists to prevent that.
2. **Fusion model.** Start with the conservative γ_eff = min_s γ_s over
   available authenticated sources; then the EKF-weighted version. Report both.
3. **Denial sweep.** Extend `sweep_full.py` with a denial-duration axis: for
   each modality set, the certified floor vs (θ, denial duration).
4. **Selection rule.** Verify the induced order against brute force over suites.

### Platform integration

A **PNT Source Selector** page: toggle modalities and their authentication
state, watch θ*(m) and the certified floor move live, with the fused γ shown.
Reuses `ExportMenu`, the `measured`/`illustrative` badge, and
`/api/certify/staleness`. New endpoint `/api/uav/pnt/window`.

### Risks

- **LEO-SoOP γ may stay unmeasured.** Mitigation: the paper stands on GNSS +
  INS + VIO, with LEO as a clearly-tagged modelled extension. That is still
  three measured modalities against Paper D's one.
- **The fusion model could become the contribution by accident.** Keep it
  conservative and boring; the contribution is the measurement and the rule.

### Venue and timeline

Target **IEEE TIFS** or **ACM TCPS** (journal — the measurement campaign wants
space), or **NDSS/CCS** if the selection rule proves sharp. Roughly 5–6 months,
front-loaded on the INS-only γ, which is a week of work on data already on disk.

---

# P2 — The security tax: post-quantum authentication as a self-inflicted delay attack

**Working title:** *Paying for Authenticity in Milliseconds: A Certified Budget
for Post-Quantum Signing on the UAV Bus and Link*

### The gap

This is the proposal I would run first if forced to pick one, because the
framing is genuinely new and the data is entirely within your reach.

Three facts collide.

1. **MAVLink 2 signs but does not encrypt.** It carries a 13-byte HMAC-SHA256
   signature for authentication and integrity, and provides no payload
   confidentiality ([Trout Software](https://www.trout.software/blog/securing-uav-ground-stations-mavlink-vulnerabilities)).
   The PX4 community discussion of adding encryption is open, not settled
   ([Dronecode forum](https://discuss.px4.io/t/mavlink-encryption-protocols/48172)).
2. **DroneCAN, the bus ArduPilot and PX4 use for peripherals
   ([spec](https://dronecan.github.io/Specification/4.3_MAVLink_bus_transport_layer/)),
   has no authentication at all.** Your HCRL UAVCAN ingest is 200,000 real
   frames of flooding, fuzzing, and replay against exactly this surface.
3. **Post-quantum migration is arriving on constrained UAV platforms**:
   Kyber-based group key agreement for swarms
   ([Electronics 14:3364](https://doi.org/10.3390/electronics14173364)),
   CRYSTALS-Kyber/Dilithium and Falcon integrated into MAVLink-based systems
   ([Authorea preprint](https://www.authorea.com/users/839872/articles/1358782/master/file/data/Post-Quantum%20Cryptography%20for%20Military%20UAV%20Communication%20Systems/Post-Quantum%20Cryptography%20for%20Military%20UAV%20Communication%20Systems.pdf)),
   PQ authentication for drone networks
   ([IEEE TQE](https://www.computer.org/csdl/journal/tq/5555/01/11267242/2bW68AyFFoQ)).

Every one of those PQC papers reports the same metrics: signature size, key
size, cycles, energy. **None of them reports what those milliseconds do to the
aircraft.** And the numbers are brutal on a bus whose payload is 8 bytes (CAN
2.0) or 64 (CAN-FD): a Dilithium2 signature is ~2.4 kB, Falcon-512 ~666 B. On
DroneCAN that is multi-frame fragmentation, which is latency, which is
**staleness of exactly the kind Lemma 1 already bounds.**

### The claim

> **Security hardening and the adversary draw on one budget, and the
> composition theorem is what arbitrates between them.**

Formally: the residual budget Δ(θ) ≤ H·min(θ, s) bounds *adversarial*
staleness. Authentication contributes *self-inflicted* staleness Δ_auth, a
deterministic function of the scheme, the message rate, and the transport MTU.
The certificate consumes their sum:

> ρ(θ) = (Δ(θ) + Δ_auth) · γ · e^{L·T_c} ≤ m

which yields, for a given corridor margin, a **certified authentication
budget**: the maximum per-message signing latency a platform can afford while
remaining airworthy. Corollaries fall out immediately and are all testable:

- Tightening the detector (lowering θ) *buys* authentication headroom. Network
  security and cryptographic security trade against each other through the
  corridor. Nobody has stated this.
- There exists a corridor margin below which **no** post-quantum scheme
  certifies on DroneCAN, and the paper can name it.
- The scheme ranking under this metric need not match the ranking by signature
  size, because fragmentation is a step function of the MTU, not linear in bytes.

### What is reused, what is new

| Reused unchanged | New |
|---|---|
| Theorem 1 and its proof (Δ is Δ, whatever its source) | Δ_auth model: scheme × rate × MTU → seconds |
| Lemma 1 | measured signing/verification latency on flight-controller-class hardware |
| `certificates/engine.py`, corridor family | the budget-allocation result and its corollaries |
| HCRL UAVCAN ingest (200k real frames) | a defence side for `intra_bus` and `c2_link`, which the schema has but the corpus does not |

### Experiment plan

1. **Measure, do not cite.** Bench Ed25519, HMAC-SHA256 (the MAVLink 2
   baseline), Dilithium2, Dilithium3, Falcon-512, and Kyber-768 KEM on a
   flight-controller-class MCU (STM32H7, as on Pixhawk 6) and on a companion-
   computer class board (Raspberry Pi 5 / Jetson Orin Nano). Report sign,
   verify, and *end-to-end frame-to-frame* latency, the last being the one that
   matters and the one nobody reports.
2. **Fragmentation model.** Signature size → DroneCAN frame count → bus
   occupancy at realistic message rates → Δ_auth. Validate against a real bus
   using the HCRL capture's timing as the benign baseline.
3. **Compose.** Push Δ_auth through the existing chain. Produce the certified
   authentication budget vs corridor margin, and the scheme ranking.
4. **Adversarial interaction.** The interesting case: an attacker who *induces*
   authentication work (flooding with invalid signatures) turns your defence
   into the delay attack. This is a genuine new attack, it is directly
   measurable on the HCRL surface, and the theorem bounds it.

### Platform integration

A **Crypto Budget** page: pick a transport (MAVLink 2 / DroneCAN / CAN-FD), a
scheme, a message rate, and a corridor margin; get the certified floor and a
pass/fail against the DO-326A 0.90 reference. This is the single most
operationally useful page the platform could have, and it needs no dataset.

### Risks

- **Hardware access.** An STM32H7 dev board is inexpensive; a Pixhawk is not
  required for the timing measurement, only for the bus validation. If neither
  is reachable, `pqcrypto`/`liboqs` benchmarks on a pinned ARM target are a
  defensible second best — but say so, and tag it.
- **Reviewers may read it as "PQC benchmarking".** The framing must lead with
  the budget theorem, not the numbers. The numbers are the instrument.

### Venue and timeline

Target **ACM AsiaCCS**, **ESORICS**, or **IEEE EuroS&P**; **NDSS** if the
induced-authentication attack lands. 4–5 months, and the bench work is
parallelisable with P1's measurement campaign.

---

# P3 — From certified radius to operational volume: the certificate as a compliance artifact

**Working title:** *Certified Robustness Meets Airworthiness: Mapping ML
Robustness Guarantees onto SORA Operational Volumes and ED-324 Learning
Assurance*

### The gap

Paper D already computes a quantity that regulators independently ask for and
does not say so loudly enough. The corridor margin family {2, 5, 10, 20} m was
chosen to bracket the JARUS SORA contingency volume, whose lateral extent is the
sum of GNSS accuracy, position-holding error, map error, reaction distance, and
contingency-manoeuvre stopping distance. The certified tube radius ρ(θ) is
directly comparable to that sum.

Meanwhile the assurance framework is arriving:

- **ED-324 / ARP6983** is EUROCAE WG-114 and SAE G-34's process standard for
  developing and certifying aeronautical products implementing AI
  ([WG-114 briefing](https://www.icao.int/sites/default/files/EURNAT/MeetingDocs/Safety%20workshops/2025%20Safety%20-%20ICAO%20workshop%20on%20use%20of%20artificial%20intelligence%20for%20safety%20data%20processing%20and%20analysis/3-EUROCAE-WG-114-ICAO_AI-Workshop.pdf)).
- **EASA's learning-assurance framework** turns on a Concept of Operations, an
  Operational Domain, and an ODD for the ML constituent
  ([EASA MLEAP](https://www.easa.europa.eu/en/research-projects/machine-learning-application-approval),
  [AI Concept Paper Issue 2](https://www.easa.europa.eu/en/newsroom-and-events/news/easa-publishes-artificial-intelligence-concept-paper-issue-02-guidance),
  [AI Roadmap 2.0](https://sassofia.com/wp-content/uploads/2026/04/EASA-Artificial-Intelligence-Roadmap-2.0.pdf)).
- **Network Remote ID becomes mandatory for U-space participation**, with the
  Commission's Drone Security Package targeted for approval in Q3 2026
  ([AirHub](https://www.airhub.app/resources/news/remote-id-easa-vs-uk-2026),
  [Elsight](https://www.elsight.com/blog/primer-on-easa-remote-id-regulations/)).

Paper D's "operating region" hypothesis on the Lipschitz constant — smooth
regime, no gimbal lock, no stall, actuators off saturation — **is an ODD**, and
we describe it in exactly those terms without claiming the connection.

### The claim

A three-part systematisation plus tooling:

1. **A mapping.** Certified-robustness vocabulary (radius, tube, operating
   region, certified window, floor) ↔ SORA/ED-324 vocabulary (contingency
   volume, ODD, operational domain, learning assurance objective). Where the
   correspondence is exact, prove it. Where it is not, say what is missing — and
   the honest finding is likely to be that **certified radii are per-input while
   assurance objectives are per-operation**, which is a real gap worth naming.
2. **A gap analysis.** Which ED-324 learning-assurance objectives can a
   Grönwall/smoothing/PAC-Bayes certificate discharge, which can it only
   evidence, and which does it not touch?
3. **An evidence generator.** Emit a SORA Annex A-shaped evidence pack from a
   certified run: the ODD as the measured operating region, the contingency
   extent as the tube radius, the MCR floor as the safety objective, each with
   its provenance tag. This is the artifact that makes the paper more than a
   survey.

### What is reused, what is new

Everything on the compute side is reused; the new work is the mapping, the gap
analysis, and a report generator over `results/`. It is the cheapest of the
three to execute and the only one with no measurement risk.

### Platform integration

A **Compliance Pack** export: one button that produces the evidence bundle for
a chosen operating point. Slots straight into the existing `ExportMenu`.

### Risks

- **It is a systematisation paper, and it must be honest about that.** Its
  contribution is the mapping and the generator, not new theory. Pitch to a
  venue that wants that (SoK tracks, or an aviation-assurance venue) rather than
  overselling it at a top-tier security conference.
- **The standards move.** ED-324 is in preparation; `refs.bib` already carries it
  as such. Any claim keyed to a draft clause number will rot.

### Venue and timeline

**IEEE S&P SoK track**, **ACM CSUR**, or **DASC** (Digital Avionics), which
would put it in front of the audience that actually writes these standards. 3
months, and it can run in the gaps of P1/P2.

---

## What I am not proposing, and why

**Byzantine-robust federated learning for swarm IDS.** It fits the assets —
FedGTD (M7) is ported and the Federated Learning page exists — but the area is
crowded and the marginal contribution would be "we did it on UAVs". If it is
pursued, the only angle I would defend is composing a Byzantine-robustness
guarantee with the mission floor, so that a poisoned participant's effect on MCR
is bounded. That is really P1's structure applied to a different input, and it
is worth revisiting only after P1 shows the pattern generalises.

**A new dataset.** The provenance ledger says the honest thing: the number of
released `measured_same_platform` pairings is zero, because no public release
observes a network event and the flight it degrades with machine-readable
attack intervals. Producing one would be genuinely valuable and is the highest-
value extension of the corpus — but it is a flight-test campaign, not a paper
you can plan around a September deadline.

---

## Sequencing against the current schedule

| When | P1 | P2 | P3 |
|---|---|---|---|
| Now → NDSS submission | INS-only γ from existing Whelan logs (strengthens Paper D §X-D) | order hardware | — |
| Post-submission | VIO γ; denial sweep | bench campaign; Δ_auth model | mapping draft |
| +3 months | fusion model; selection rule | compose; induced-auth attack | evidence generator |
| +5 months | write | write | write |

The one item worth pulling forward before the NDSS deadline is **P1's INS-only
γ**. Paper D currently argues from an error budget that cruise will not push γ
past γ_req = 6.14 m/s. Measuring the dead-reckoning γ directly from the Whelan
IMU replaces an argument with a measurement in the paper's most contested
paragraph, and the data is already on disk.

---

# Coverage against Paper D's stated limitations

Asked directly whether these three proposals close the manuscript's limitations,
the honest answer is **no, not most of them**. They close one fully, one
partially, and leave four untouched. Setting that out plainly is more useful
than claiming coverage, because the four uncovered ones are what a reviewer will
press on and two of them need no new paper at all.

| Paper D §XII limitation | Covered by | How completely |
|---|---|---|
| **The certificate assumes the filter re-anchors** (Definition 2 fails under persistent denial) | **P1** | **Fully.** This is P1's central claim: an authenticated PNT source can be jammed but not forged, so it supplies the uncorrupted update Definition 2 requires. The limitation becomes a satisfiable hypothesis with hardware behind it. |
| **γ is a three-flight hover calibration** | **P1** | **Partially.** P1 measures the dead-reckoning γ from the Whelan IMU, which replaces §X-D's error-budget *argument* with a *measurement*, and adds γ for further modalities. It does **not** deliver the cruise-inclusive flight campaign, which is the actual gap. |
| **Conservatism of the deterministic core** (fusing the four floors into one tighter envelope is open) | — | **Not covered.** See P0-A below. |
| **Evidence-class imbalance** (zero `measured_same_platform` pairings) | — | **Not covered, deliberately.** Closing it means a flight-test campaign producing a capture with machine-readable attack intervals. Valuable, but not schedulable against a conference deadline, and I said so above rather than pretending a paper closes it. |
| **Calibration constants that remain data-gated** (TEXBAT unit bridge, PAC-Bayes KL) | — | **Not covered.** But see P0-B: only half of this is genuinely data-gated. |
| **Analytical anchor and detector scope** (one detector, a single scalar operating point) | partly **P2** | **Weakly.** P2 exercises a second surface (the bus) but still with a scalar operating point. §VI-B generalises to learned detectors on paper and never instantiates it. See P0-C. |

## P0 — limitation-closing work that needs no new paper

Three of the gaps above are self-contained engineering or analysis that would
strengthen Paper D itself, or its camera-ready, without a new venue. Ranked by
value per unit of effort.

**P0-A. Fuse the four certified floors into one envelope.** §IX already argues
the four certificates bound *different objects* and compose by conjunction, so a
deployment reads `min{f_G, f_RS, f_PB, f_MWU}`. That minimum is currently
computed and reported but never *tightened*: where two certificates bound the
same failure mode through different routes, the conjunction can be sharper than
either. A short analysis plus a change to `certificates/engine.py` would turn
"the architecture is a four-certificate cover" from an architectural claim into
a numerical one. Directly addresses the conservatism limitation. Days, not weeks.

**P0-B. Compute the PAC-Bayes KL.** `PENDING_ON_DATA.md` #5 lists this with the
data-gated items, but it is not data-gated: the bound is already wired to the
trained model's measured empirical risk, and the prior/posterior KL is a
computation over the checkpoint in `models/uav_defense/`. Doing it removes the
one *pending* cell from Table `tab:constants` and halves the "calibration
constants" limitation. It should be moved out of `PENDING_ON_DATA.md` and into
a work item, because listing a compute task as data-gated overstates how blocked
the project is.

**P0-C. Instantiate the learned-detector generalisation.** §VI-B derives
θ_eff = g⁻¹(P_th) and argues any scored detector slots in, then instantiates
nothing. Training one classifier on the UAVIDS-2025 flows, measuring its
score-to-magnitude profile g, and running one sweep in θ_eff would convert a
paragraph of "the framework does not depend on that choice" into a figure. It
also produces the stochastic-score case that §IX says is randomized smoothing's
proper regime, which currently has no worked example. This is the single change
that would most blunt a reviewer's "you evaluate one hand-built detector".

## What stays open after everything above

Two things, and both should stay stated as limitations rather than papered over:

1. **No public capture observes both layers on one airframe with published
   attack intervals.** Everything else in the project is downstream of that.
2. **Four of six sources are simulation or calibrated twin,** so absolute
   detector numbers are corpus-specific. What transfers is the structure, which
   §XII already says.

The roadmap does not fix either, and no reasonable amount of desk work does.
