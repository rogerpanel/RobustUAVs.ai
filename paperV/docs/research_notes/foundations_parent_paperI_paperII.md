# Foundations for Paper V: what the parent manuscript, Paper I and Paper II establish

Scope: this is a local-file extraction only. No web sources were used.

Files read:
- Paper V proposal: `/root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/ac54f2a6-PaperV_safety_filter_llm_agent.tex`
- Parent PDF, 21 pp.: `/root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf`. I extracted it with pdftotext into per-page files at `parent_text/p{1..21}.txt`.
- Paper I package, unzipped to `paperI_package/paperI/`
- Paper II package, unzipped to `paperII_package/paperII/`
- Project docs `PaperI/RUNBOOK_CLAUDE_CODE.md` and `PaperII/RUNBOOK_CLAUDE_CODE.md`, read with the Projects tool. Their content matches the packaged runbooks.

Source shorthand (every link below is a local file):
- PARENT = file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf (page given as #page=N)
- P1 = file://paperI_package/paperI/manuscript/main.tex (line given as #LN)
- P1NUM = file://paperI_package/paperI/manuscript/numbers.tex
- P2 = file://paperII_package/paperII/manuscript/main.tex
- P2NUM = file://paperII_package/paperII/manuscript/numbers.tex
- PV = file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/ac54f2a6-PaperV_safety_filter_llm_agent.tex

---

## Q1. Parent manuscript: title, status, models, certificate engine, theorems, attack classes, datasets, metrics, results, limitations, notation

### Takeaway
The parent is "From Wire to Flight: A Conditional Mission-Completion Guarantee for UAVs", anonymised for double-blind review with no venue named. It proves Lemma 1, Theorem 1 (a Lipschitz–Grönwall tube) and Proposition 1 (soundness). Together they chain a detector threshold θ to a certified mission-completion floor:

θ ↦ Δ(θ) ↦ δ(θ) = γΔ(θ) ↦ ρ = δe^{LT_c} ≤ m ↦ MCR ≥ f.

It uses γ = 1.625 m/s (supremum), L̂_loc = 1.181, T_c = 1 s, and m ∈ {2, 5, 10, 20} m.

Several constants that Paper V attributes to the parent do not appear in it at all: R_i(t) ≥ R_min, MAX_FLEET = 12, κ = 0.25, and "ten attack classes". The parent's own schedule tolerance is κ = 0.10. The certificate is a per-mission tube, not an admissible-action set, and the parent never mentions LLMs, MPC or safety filters. It does point explicitly to Simplex/runtime assurance as the fix for its non-Lipschitz and persistent-denial gaps.

### Cited Findings

**Identity, status and venue**
- Title: "From Wire to Flight: A Conditional Mission-Completion Guarantee for UAVs". Header: "Paper #XXX, Submitted for double-blind review". IEEE-style two-column layout, US letter, 21 pages. The PDF was created 1 Oct 2026 — [PARENT p.1](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=1)
- The PDF names no venue. Both Paper I and Paper II cite it as `parentpaper`: author "Anonymous", year 2026, note "Under submission; anonymised for double-blind review" — [P1 refs.bib l.7–11](file://paperI_package/paperI/manuscript/refs.bib); [P2 refs.bib l.8–11](file://paperII_package/paperII/manuscript/refs.bib)
- Paper I's README calls the parent "paper D". Paper II's README says Paper II "broadens proposal P3 of the parent manuscript" — [Paper I README](file://paperI_package/paperI/README.md); [Paper II README](file://paperII_package/paperII/README.md)
- The parent includes sections "XIV. Ethics Considerations" and "XV. Open Science and Artifact Availability", and says it intends to submit the artifact for evaluation — [PARENT p.17](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=17)

**Headline claims in the abstract**
- Hideable delay "saturates at 4.84 s across 15,392 observed relay hops" — [PARENT p.1](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=1)
- "one second of delayed navigation input costs at most 1.63 m of position error, measured at every one of 674 post-onset samples of real GPS-jamming and GPS-spoofing flights" — [PARENT p.1](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=1)
- The rate "varies by 6.1× across the conditions we can observe … so the certificate is evaluated at the supremum rather than the average" — [PARENT p.1](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=1)

**Scope conditions (verbatim, §I "Scope of the Guarantee")**
- "(C1) Dynamics. The navigation drift is L-Lipschitz over the operating region. Outside that region, for instance in a stall-recovery transient or under actuator saturation, no finite L bounds it and the certificate makes no statement at all." — [PARENT p.2](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=2)
- "(C2) Re-anchoring. The estimator receives at least one uncorrupted state update per certification horizon T_c. A delay adversary satisfies this by construction; a persistent-denial adversary does not." — [PARENT p.2](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=2)
- "(C3) Interface transfer. The measured delay-to-position rate γ applies to the deployment in question." The parent calls this "the weakest of the three" — [PARENT p.2](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=2)
- "the chain θ ↦ Δ ↦ δ ↦ MCR is not a theorem end to end. The first and last links are proved; the middle link, Δ ↦ δ, is an empirical calibration" — [PARENT p.2](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=2)

**System model (§II-A, App. A)**
- There are two layers:
  - The network layer covers the swarm mesh, the C2 link (MAVLink) and the intra-UAV bus (UAVCAN/DroneCAN).
  - The autonomy layer covers the GNSS receiver, sensor fusion, the flight controller and the mission outcome.

  [PARENT p.3](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=3)
- The vehicle is PX4 with an EKF fusing GNSS, IMU and barometer. Under GNSS denial the EKF "coasts" on inertial data. The mesh is a DTN with periodic contact windows — [PARENT p.20](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=20)
- Safe corridor: "a tube of lateral half-width m, the corridor margin, centered on the planned route". The SORA contingency terms "sum up roughly 7 m", hence the margin family m ∈ {2, 5, 10, 20} m — [PARENT p.3](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=3)
- Margin rationale: 2 m is "a deliberately adversarial stress case"; 5 m sits inside the default static budget; 10 m is representative of a small multirotor's full contingency extent; 20 m covers fixed-wing — [PARENT p.13](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=13)
- Navigation dynamics, Eq. (10): ẋ(t) = F(x(t), u(t)), t ∈ [0, T]. Here x(t) ∈ Rⁿ is the navigation state and u(t) the sensor/measurement input. An attack perturbs u ↦ u + δu — [PARENT p.10](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=10)

**Threat and detector model (§II-B)**
- The adversary can "(i) inject, drop, delay, or forge traffic on one or more network sublayers, and (ii) manipulate the RF environment of the GNSS receiver" — [PARENT p.3](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=3)
- The detector D_θ has a tunable θ, "a per-hop deviation tolerance in seconds". An evading attacker "stay[s] just under θ". "We assume the adversary knows θ; this is the strongest reasonable assumption and the one our worst-case analysis requires." — [PARENT p.3](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=3)
- The two adversaries the parent names for the theorem are the delay adversary (covered) and the persistent-denial adversary (not covered) — [PARENT p.2, p.10–11](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=10)

**Metric: MCR (§II-C)**
- Eq. (1): MCR = Pr[ sup_{t∈[0,T]} ‖x(t) − x_nom(t)‖ ≤ m  ∧  t_arr ≤ (1+κ)T ]. The first conjunct is spatial and the second temporal. "Spatial MCR" is the label when only the spatial predicate is used — [PARENT p.3](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=3)
- Reference threshold "MCR ≥ 0.90 … consistent with … DO-326A/ED-202A" — [PARENT p.3](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=3)
- Probability space (Ω, F, P_M). A sample point ω is one mission: route, T, m, initial state, wind/turbulence, and hop count H. δ(θ) and Δ(θ) are deterministic, so all randomness is over missions. "A bound on a proportion is not a bound on a flight" — [PARENT p.4](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=4)
- T conventions: "the missions in our corpus run between 136 and 246 s, and the reference mission profile of §X is 70 s, so a schedule tolerance of κ = 0.10 corresponds to a permissible slip of several seconds". T_c "fixed at 1 s throughout" is distinct from T — [PARENT p.4](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=4)
- Temporal predicate, Eq. (2): Δ(θ) ≤ κT, implied by H·min(θ, s) ≤ κT. At θ = 0.25 s, H = 2 the slip is ≤ 0.5 s. At θ near s = 5 s the slip reaches Hs = 10 s — [PARENT p.4–5](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=4)
- Table I covers 9 mission distributions (3 profiles × 3 receivers), marginalised over 0–40 dB J/S:
  - MCR ranges over 0.882–0.893 (spread 0.011).
  - Conditional on attack strength, the spread reaches 0.214 at 35 dB.
  - The J/S at which MCR falls below 0.90 ranges over 18.1–27.1 dB ("9 dB").
  - The table rests on 93,600 missions.

  [PARENT p.4](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=4)

**Cross-layer pairing and composed guarantee (§II-D)**
- Eq. (3): P = (W_n, W_a, θ, Δ(θ), δ, MCR). Eq. (4): θ ↦ Δ(θ) ↦ δ(θ) ↦ MCR ≥ f(δ(θ)) — [PARENT p.5](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=5)
- "Definition 1 (Composed guarantee). Given a detector D_θ and navigation dynamics Eq. (10), a composed guarantee is a function f such that for every attack a with D_θ(a) = 'clean', the mission completes with rate MCR(a) ≥ f(δ(θ)), where δ(θ) bounds the navigation-input perturbation any such a can induce." — [PARENT p.5](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=5)
- pairing_basis ∈ {measured_same_platform, physics_model, synthetic_alignment}. "a claim can never silently upgrade its own provenance" — [PARENT p.6](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=6)

**Certificate engine: how each constant is derived**
- "Lemma 1 (Residual delay budget). Let D_θ flag any forwarding hop whose injected delay exceeds θ. An attacker that evades D_θ injects at most θ of undetected delay per malicious hop, but only up to the contact-window slack s: a per-hop delay exceeding s misses its forwarding window, incurs a full-period penalty P_c, and is therefore flagged at any operating point. Hence undetected delay is capped at min(θ, s) per hop, and over a route with H attacker-controlled hops the worst-case undetected cumulative delay is Δ(θ) ≤ H min(θ, s). (5)" — [PARENT p.8](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=8)
- Lemma 1 measurements:
  - Over 15,392 hops (3 topologies, 2 attack modes, 8 seeds), no undetected malicious per-hop residual exceeds 4.84 s (s = 5 s).
  - Larger delays are flagged as missed windows (≥ 55 s residual).
  - The benign residual ceiling is 0.178 s, and FPR = 0 throughout.

  [PARENT p.7–8](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=8)
- Eq. (6), kinematic: ‖δu‖ ≤ v_max·Δ(θ) with v_max = 15 m/s. Eq. (7), empirical: ‖δu‖ ≤ γ·Δ(θ) with γ ≪ v_max — [PARENT p.8–9](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=9)
- Eq. (8): γ_cum(t) = e(t)/(t − t_0) and γ_Δ(t) = (e(t) − e(t_0))/(t − t_0). Only γ_Δ is admissible: γ_cum reaches 8.6 m/s below 1 s, which is a detector artifact, since e(t_0) = 0.64 m (jam, receiver) and 9.27 m (spoof) — [PARENT p.9](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=9)
- How γ = 1.625 m/s arises: "γ_Δ peaks at 1.625 m/s for t − t_0 ∈ [5, 10) s and decays to 0.02 m/s beyond 40 s". "The certificate is evaluated at the supremum over the conditions it claims to cover, which on this evidence is γ = 1.625 m/s. This is 1.19× the per-flight secant rate of 1.365 m/s". At the corrected rate the 10 m window edge moves from θ* = 1.12 s to 0.94 s — [PARENT p.9](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=9)
- Table V (per-flight γ, m/s): jamming EKF 0.52, jamming receiver 0.48, spoofing EKF 1.36, spoofing receiver 1.20. Spread 2.6× by attack type and 1.14× by error signal. "Conservative value used" 1.36 — [PARENT p.9](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=9)
- Table VII. Three real PX4 flights from the UAV ATTACK DATASET (Whelan): benign, GPS jamming, GPS spoofing.
  - Jamming EKF: γ_lsq −0.1133, γ_peak 0.5185.
  - Spoofing EKF: γ_lsq 0.7007, γ_peak 1.365.
  - Spoofing receiver: γ_peak 1.195.

  [PARENT p.10](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=10)
- Table VI covers 674 samples. Factor maxima of γ_Δ:
  - Satellites [8, 11): 1.62.
  - Staleness [5, 10) s: 1.62 (n = 110).
  - Spoofing: 1.62 (n = 178). Jamming: 1.23 (n = 496).
  - EKF: 1.62 (n = 610). Receiver: 1.23 (n = 64).

  Least-squares fit: R² = 0.79, with coefficients satellites −0.22, staleness −0.26 and airspeed +0.12. No p-values are given, deliberately — [PARENT p.9–10](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=9)
- Linear-domain limit, Eq. (9): ‖δu‖ ≤ γΔ(θ) + ½ b_IMU (Δ(θ) − τ_lin)₊², with τ_lin ≈ 2 s. Eq. (7) is used only for Δ(θ) ≤ τ_lin — [PARENT p.10](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=10)
- "Definition 2 (Re-anchoring interval). The navigation filter admits at least one measurement update not affected by the attack in every window of length T_c, and each such update resets the accumulated deviation to within the filter's nominal estimation error." T_c = 1 s matches 1 Hz GNSS — [PARENT p.10](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=10)
- Theorem 1, verbatim: "Theorem 1 (Composed network-to-navigation guarantee). Let the navigation drift F of Eq. (10) be L-Lipschitz in its input over the operating region, let T_c be a certification horizon satisfying Definition 2, and let m be the safe-corridor margin. Let D_θ be a network detector with residual budget Δ(θ) (Lemma 1) and interface mapping δ(θ) (Eq. (7) or the kinematic Eq. (6)). Then every attack evading D_θ induces a trajectory-tube radius bounded by ρ(θ) = δ(θ) e^{LT_c}, (11) and the mission completes, in the conjunctive sense of Eq. (1), whenever ρ(θ) ≤ m and Δ(θ) ≤ κT; consequently MCR ≥ f(δ(θ)) = Pr_missions[ δ(θ) e^{LT_c} ≤ m ∧ Δ(θ) ≤ κT ]. (12)" — [PARENT p.11](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=11)
- Proof, App. p.21:
  - ‖ė‖ ≤ L‖e‖ + L‖δu‖.
  - Grönwall gives ‖e(T_c)‖ ≤ δ(θ)(e^{LT_c} − 1) ≤ δ(θ)e^{LT_c}, which is Eq. (18). The paper reports the closed-form right-hand bound.
  - Re-anchoring per Definition 2 extends the bound to sup over [0, T].
  - t_arr ≤ T + Δ(θ).

  [PARENT p.21](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=21)
- "Proposition 1 (Soundness). The certified floor never overstates the achievable completion rate: for every θ, the true MCR of any D_θ-evading attack satisfies MCR ≥ f(δ(θ))." — [PARENT p.11](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=11)
- Lipschitz hypothesis caveats: the hypothesis needs attitudes away from gimbal lock, airspeeds below stall, actuators off saturation and no contact dynamics. "there the certificate is silent rather than merely loose" — [PARENT p.11](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=11)
- How L and R are derived:
  - Reference navigation model: "a continuous-time graph model of the GNSS constellation and receiver".
  - Global power iteration gives L̂ ≈ 1.01 (1.013). Local along visited trajectories gives L̂_loc ≈ 1.18 (1.181).
  - "R = ε_out e^{−L̂_loc T_c} ≈ 0.153 (the global estimate gives 0.182)" with ε_out = 0.5, T_c = 1 s. "Every certified quantity in this section uses the measured local Lipschitz constant" — [PARENT p.12–13](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=13)
- Table IX constants:
  - Lipschitz–Grönwall: L̂_loc = 1.181 ⇒ R = 0.153, and L̂ = 1.013 ⇒ R = 0.182. Provenance "global trained ckpt [fixture]".
  - Randomized smoothing: σ = 0.25, R_ℓ2 = 0.44 (measured 0.446), with α = 10⁻³ and n = 200.
  - PAC-Bayes: McAllester on real R_emp; numeric KL pending.
  - MWU: R(T) ≤ √(T ln 4), so T = 100 ⇒ 11.77, |S| = 4.
  - Unit bridge (RF classes): caf_shift_v2 0.45 m (Grönwall) / 1.15 m (RS), synthetic IQ, "TEXBAT pending".
  - θ ↦ δ (delay class): γ = 1.20–1.37 m/s measured, with a kinematic 15 m/s fallback.

  [PARENT p.13](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=13)
- Four-certificate architecture (Table VIII): Lipschitz–Grönwall (deterministic), randomized smoothing (Eq. (13) R_RS = (σ/2)(Φ⁻¹(p_A) − Φ⁻¹(p_B))), PAC-Bayes (Eq. (14)) and MWU regret. "a deployment reads its floor as the pointwise minimum min{f_G, f_RS, f_PB, f_MWU}". In the evaluated regime "the Grönwall term binds" — [PARENT p.12](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=12)

**Headline numerical results (§X)**
- Worked example at θ = 0.25 s, H = 2, s = 5 s:
  - Δ ≤ 0.50 s.
  - γ = 1.37 gives ‖δu‖ ≤ 0.69 m (kinematic: 7.5 m).
  - With L̂_loc = 1.18 and T_c = 1 s, ρ = 0.69e^{1.18} ≈ 2.25 m (kinematic ρ ≈ 24.5 m).
  - Certified for m ≥ 5 m, not at 2 m ("at m = 2 m the tube is 2.22 m").

  [PARENT p.13](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=13)
- Certified window:
  - Empirical interface: "[0.178, 1.12] s at a 10 m corridor". Fig. 7 caption: "EKF window [0.178, 1.124] s at m = 10 m".
  - Kinematic mapping: [0.178, 0.243] s.
  - Window-edge formula: θ*(m) = m/(γ e^{LT_c} H).
  - γ_req = 6.14 m/s at 10 m, which is 4.5× the EKF rate and 5.1× the receiver rate.

  [PARENT p.14–15](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=14)
- Cruise argument (reasoning, not measurement): crossing γ_req at 15 m/s needs a heading error ψ_err ≳ (6.14 − 1.37)/15 ≈ 0.32 rad, about 18° — [PARENT p.14](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=14)
- Dominance over the baselines:
  - The autonomy-only and network-only baselines certify a zero floor; measured cumulative delay reaches 424 s.
  - The composed floor exceeds the autonomy-only floor "at all 13 operating points … every adjusted p < 10⁻²⁰" (Wilcoxon signed-rank with Holm correction).
  - The parent explicitly does not benchmark against reachability, secure state estimation, RTA or certified RL.

  [PARENT p.14–15](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=15)
- Certified vs empirical floors:
  - The empirical MCR is 0.938 at J/S = 20 dB over 93,600 flights, against a certified target of 0.80. The DO-326A operational floor is 0.90.
  - Fig. 5: the undefended baseline falls below 0.90 by J/S ≈ 8 dB, while the strongest configuration ("Ours (M1+M4+M6+M7)") holds to ≈ 25 dB.
  - Other configurations: No-Def (PX4), CAF-CNN, Seq2Seq Tr.

  [PARENT p.12–13, p.15](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=15)
- Table X (representative pairing):
  - Measured undetected delay over 192 runs: median 0.00 s, max 0.00 s.
  - Staleness ≤ 0.69 m ("Whelan, hover").
  - Paired window: UAV-EW-Bench at J/S = 20 dB.
  - MCR 0.938.

  [PARENT p.15](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=15)

**Datasets (Table II, III, XI)**
- The six datasets:
  - UAVIDS-2025: NS-3.24 mesh, 122k flows; blackhole, flooding, Sybil, wormhole.
  - UAV-CAS: AERPAW-calibrated digital twin, 99k flows, 1024 configs; collaborative multi-attack. Ingest status: "adapter ready; file pending".
  - UAV ATTACK DATASET (Whelan et al., IEEE DataPort 2020): real PX4 GPS spoof, jam and ping-DoS. This is "the measured bridge".
  - HCRL UAVCAN: real bus; flooding, fuzzy, replay.
  - DATAMUt traces: event simulation, time-window-graph forwarding detector with sweepable θ.
  - UAV-EW-Bench-2026 (the author's own benchmark): physics-informed; "the navigation anchor: full 0–40 dB J/S sweep with per-flight MCR outcomes".

  [PARENT p.6–7](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=6)
- Ingested event counts: UAV-EW-Bench 93,600 (468 windows); Whelan 610 (0 windows); UAVIDS shard 0 122,171 (4); HCRL 200,000 (34); DATAMUt 15,392 hops. Totals: 200,610 of 431,773 events (46.5 %) are real hardware — [PARENT p.7, p.15–16](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=16)
- Released measured_same_platform pairings: "currently zero". Every released pairing is physics_model or synthetic_alignment. e_align ≤ 0.53 s (Eq. (17)) — [PARENT p.16, p.21](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=16)
- Table IV: HCRL UAVCAN has ten scenarios, type1–type10, with frame-derived classes flooding, replay, fuzzy, and combinations — [PARENT p.7](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=7)

**Attack classes the parent actually names (there is no list of "ten")**
- Time-delay forwarding is the class the theorem covers. Also named:
  - GPS spoofing, GPS jamming, MAVLink ping-DoS.
  - Blackhole, flooding, Sybil, wormhole.
  - Bus flooding, fuzzy, replay.
  - Collaborative multi-attack compositions.
  - RF-manipulation classes, served by the unit bridge.
  - Persistent denial, which is outside the theorem.

  [PARENT p.5–7, p.13, p.16](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=6)
- The schema uses "a unified attack label" and a "common taxonomy" but does not enumerate it in the PDF — [PARENT p.6](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=6)

**Limitations and future work that motivate Papers I–V (§XII)**
- "The interface is calibrated, not characterised … γ is measured on three flights of one PX4 airframe family, all in low-speed hover or loiter". Platform and flight mode are not varied — [PARENT p.16](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=16)
- "The certificate assumes the filter re-anchors … an adversary denying updates outright does not, and there the certified radius degrades as e^{LT_c} in the achieved denial duration. Certifying against sustained denial needs either a link-layer bound on outage length or a fallback whose guarantee is independent of L, which is the runtime-assurance direction of §XI." — [PARENT p.16–17](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=17)
- Fusing the deterministic, smoothing and PAC-Bayes floors "is open" — [PARENT p.17](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=17)
- The PAC-Bayes KL is pending, and the unit bridge is calibrated on synthetic IQ (TEXBAT pending) — [PARENT p.17](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=17)
- Completion outcomes come from "a physics-informed analytical Monte-Carlo backend". The harness uses one threshold detector, and multi-dimensional operating points remain future work — [PARENT p.17](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=17)
- Extending the interface to jamming-intensity-to-error and to bus-level attacks is "direct future work". A comparison of the Grönwall tube against reachability tools at equal radius has "not done it" — [PARENT p.15–16](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=15)
- Ethics on dual use, the template Paper V says it follows: "our harness quantifies how an attacker can stay under a detector's threshold. We judge disclosure net-positive … our central result bounds what such an attacker achieves and shows that it saturates, and the practical consequence is a defensive configuration procedure" — [PARENT p.17](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=17)

**Notation (Table XII, the parent's single symbol reference)**

Symbols to reuse verbatim [PARENT p.20](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=20):
- W_n, W_a: network / autonomy attack window.
- P: cross-layer pairing tuple.
- x(t) ∈ Rⁿ: navigation state.
- u(t), δu: sensor input and its perturbation.
- F: drift of the navigation dynamics.
- T, κ: mission duration (s); schedule tolerance as a fraction of T.
- T_c: certification horizon (1 s).
- m: corridor margin (m).
- D_θ, θ(ε): detector and its operating point.
- s, P_c: contact-window slack (5 s); contact period (60 s).
- H: malicious hops.
- Δ(θ): residual budget.
- δ(θ): induced perturbation.
- γ: delay-to-position rate.
- v_max: 15 m/s.
- L, L̂, L̂_loc: Lipschitz constants.
- ρ(θ) = δ(θ)e^{LT_c}: tube radius.
- θ*(m): window edge.
- f(·): certified MCR floor.
- R, σ, α, n: certified input radius; smoothing noise, confidence, samples.
- R_emp, KL: PAC-Bayes terms.
- |S| = 4.

### Inferences
- **Constants Paper V attributes to the parent that the parent does not contain.**
  - "R_i(t) ≥ R_min" appears nowhere. The parent's only "R" is the certified input radius R = ε_out e^{−L̂_loc T_c} ≈ 0.153 (or R_ℓ2 = 0.44 for smoothing). It has no per-aircraft index i and no time dependence.
  - "MAX_FLEET = 12" appears nowhere.
  - "κ = 0.25" conflicts: the parent uses κ = 0.10.
  - "ten attack classes" appears nowhere. The only "ten" is the ten HCRL scenarios (type1–type10), which collapse to three frame-derived classes.
  - T = 70 s does appear, as the parent's "reference mission profile".
  - These items most likely come from the RobustUAVs.ai platform code. I also grepped the Paper I–IV packages and none of them contains MAX_FLEET, R_min, κ = 0.25 or "ten attack classes".
  - Paper V should either cite the platform/artifact for them or align them with the parent: κ = 0.10, the corridor margin m, the tube ρ(θ) ≤ m, and the radius R.
- **The parent's certificate is a tube and a corridor test, not an admissible-action set A_adm(x_t).** Paper V's statement "The admissible set A_adm(x_t) is exactly the certified set the parent paper's budget produces" [PV l.110–111](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/ac54f2a6-PaperV_safety_filter_llm_agent.tex) is a new construction, not a reuse. A defensible definition is: A_adm(x_t) = {a : the nominal trajectory under a, inflated by ρ = δe^{LT_c} per T_c window, stays inside the m-corridor over H and ends in a control-invariant terminal set}.
- **The input/state roles differ.** The parent's L is the Lipschitz constant of F "in its input" u, a sensor perturbation, measured on a GNSS/receiver graph model checkpoint. Paper V perturbs a high-level action a (waypoint, task, mode), not u. Reusing "F Lipschitz with constant L" for action-driven dynamics needs either a separate Lipschitz constant in the action (or control) input or an explicit argument. The parent's L̂_loc = 1.181 was measured on sensor-input trajectories, not on action perturbations.
- **The Grönwall tube supports a safety filter only within the linearisable envelope (C1).** The parent itself names a Simplex-style monitor as the response when that envelope is left (p.11). Paper V's fallback (loiter/RTL) must keep the aircraft inside that envelope, or carry a guarantee "independent of L", as the parent says on p.17.
- **Internal inconsistency in the parent.**
  - p.9 says that at γ = 1.625 the "smallest corridor certifying θ = 0.25 s rises from about 2.25 m to about 5.9 m". Recomputing gives 0.5 × 1.625 × e^{1.1814} = 0.5 × 1.625 × 3.259 ≈ 2.65 m, which matches Paper I's ρ_U = 2.65 m [P1NUM](file://paperI_package/paperI/manuscript/numbers.tex) and Paper II's epTubeSup = 2.65 [P2NUM](file://paperII_package/paperII/manuscript/numbers.tex).
  - Paper V should use 2.65 m (γ = 1.625) or 2.22–2.25 m (γ = 1.365/1.37), not 5.9 m.
  - The parent's §X worked example and Fig. 7 use γ = 1.37, not 1.625, even though §VII-C says the supremum is what "a sound certificate must use". Quote whichever is meant explicitly.
- **Paper V's "Dual-use … Following the parent manuscript" aligns well with the parent's ethics paragraph.** The structure is the same: the result bounds the attacker's achievement, and the practical output is a defensive configuration procedure.

### Gaps
- The venue of the parent cannot be determined from local files; the PDF and bib give only "under submission".
- The parent never enumerates its unified attack taxonomy, so I cannot confirm "ten attack classes" from it.
- No local file defines MAX_FLEET = 12, κ = 0.25 or R_i(t) ≥ R_min. These need the RobustUAVs.ai repository, which was not available locally.
- Fig. 7, Fig. 8 and Fig. 5 values were read from captions and text, not data files. The parent's results CSVs are not in these packages.

---

## Q2. Paper I: problem, credit/debit budget, results, notation, experiments, numbers, limitations

### Takeaway
Paper I, "What Authenticity Costs in Metres", targets IEEE S&P main track and is under double-blind review. It turns the parent's tube into a design budget:

ρ(θ, κ) = Δ_eff(θ, κ)·γ_eff(κ)·e^{LT_c} ≤ m.

Authentication is a credit (it lowers γ from γ_u = 1.625 to γ_a = 0.933 m/s) and a debit (it adds delay Δ_auth). This is the "credit/debit" Paper V invokes.

Key results:
- An occupancy cliff r* (16.3 signed msgs/s for ML-DSA-44 on classic CAN).
- A horizon-matched crossover θ_× ≈ 0.259–0.284 s.
- Rescue of the 2 m corridor (ρ = 1.88 m vs 2.65 m).
- Time-push converting delay into denial.
- Induced verification.
- A certified selection rule.

Paper I uses κ for the authentication configuration, which clashes with the parent's schedule tolerance κ.

### Cited Findings
- Title "What Authenticity Costs in Metres: A Certified Budget for Cryptography and Sensing in UAV Navigation". Target "IEEE Symposium on Security and Privacy (main track)", IEEEtran conference class. "Paper #XXX, Submitted for double-blind review" — [P1 l.1–14, 66–70](file://paperI_package/paperI/manuscript/main.tex)
- Repository `rogerpanel/RobustUAVs.ai`, branch `claude/whelan-uavcas-ingest-u00isn`, folder `paperI/` — [Project doc PaperI/RUNBOOK_CLAUDE_CODE.md](file://paperI_package/paperI/RUNBOOK_CLAUDE_CODE.md)
- **Credit/debit, verbatim:** "Authenticating a navigation source lowers γ, because an estimator that rejects a forged fix stops absorbing the forger's offset. Authenticating a message raises Δ, because signing, transmitting and verifying the authenticator take time … Authentication is therefore both a credit and a debit against one certified budget." — [P1 l.146–156](file://paperI_package/paperI/manuscript/main.tex)
- Parent restated, Eq. (1): ρ(θ) = Δ(θ)·γ·e^{LT_c} ≤ m. Inherited constants:
  - s = 5 s (cap 4.84 s over 15,392 hops), benign ceiling 0.178 s, H = 2, θ = 0.25 s.
  - γ = 1.625 m/s supremum over 674 samples.
  - L = 1.1814, T_c = 1 s, so E ≜ e^{LT_c} = 3.259.
  - m ∈ {2, 5, 10, 20} m.

  "We call the set of θ for which ρ(θ) ≤ m the certified window. Its lower edge is the benign floor of 0.178 s." — [P1 l.218–260](file://paperI_package/paperI/manuscript/main.tex); [P1NUM nEmult = 3.259](file://paperI_package/paperI/manuscript/numbers.tex)
- Estimator Eq. (3): γ_δ(τ) = (e(t_0 + τ) − e(t_0))/τ. Paper I writes γ_δ; the parent writes γ_Δ — [P1 l.242–249](file://paperI_package/paperI/manuscript/main.tex)
- **Budget**, Eqs. (4)–(6):
  - ρ(θ, κ) = Δ_eff(θ, κ)·γ_eff(κ)·e^{LT_c} ≤ m.
  - Δ_eff(θ, κ, t) = min(Δ(θ), τ_fresh + ε_clk(t)) + Δ_auth(κ, 𝒯).
  - γ_eff = γ_u for unauthenticated sources and γ_a for authenticated ones.
  - Design problem: min_{κ∈𝒦} cost(κ) s.t. ρ(θ, κ) ≤ m, κ admissible on 𝒯, κ secure against 𝒜.
  - "Let κ be an authentication configuration: a scheme, a batch size k … and a flooding mitigation."

  [P1 l.329–354](file://paperI_package/paperI/manuscript/main.tex)
- Adversaries (Table I): 𝒜_spoof, 𝒜_delay, 𝒜_ins (group-key insider), 𝒜_deny ("selectively withholds unauthenticated sources beyond T_c"), 𝒜_iv (invalid-signature injection) and 𝒜_time (shifts the GNSS-disciplined clock) — [P1 l.262–297](file://paperI_package/paperI/manuscript/main.tex)
- Assumptions: "The adversary knows θ, the scheme and the transport". Authenticated navigation is released at r = 10 Hz unless stated. Injected CAN frames do not out-prioritise the legitimate stream — [P1 l.321–327](file://paperI_package/paperI/manuscript/main.tex)
- RQ1–RQ5:
  - RQ1: γ reduction.
  - RQ2: cost — latency vs occupancy.
  - RQ3: crossover.
  - RQ4: freshness under GNSS-coupled clocks.
  - RQ5: induced verification.

  [P1 l.355–364](file://paperI_package/paperI/manuscript/main.tex)
- Theory, statements verbatim or near-verbatim [P1 l.405–548](file://paperI_package/paperI/manuscript/main.tex):
  - Prop. 1 (Crossover): "Authentication strictly reduces the certified error if and only if Δ_auth < C(θ) ≜ Δ(θ)(γ_u/γ_a − 1). Equivalently, for θ < s, authentication pays if and only if θ > θ_× ≜ Δ_auth/(H(γ_u/γ_a − 1))."
  - Prop. 2 (More affordable, less beneficial): B(θ) = m/(γ_a E) − Δ(θ). For θ < s, B has slope −H and C has slope H(γ_u/γ_a − 1).
  - Definition 1 (Error envelope): δ_x(τ) = sup_{τ' ≤ τ}[e(t_0 + τ') − e(t_0)], for x ∈ {u, a}.
  - Theorem 1 (Horizon-matched crossover): "authentication strictly reduces the certified tube radius if and only if δ_a(Δ(θ) + Δ_auth) < δ_u(Δ(θ))."
  - Corollary 1 (Indistinguishability horizon): if δ_u(τ) ≤ δ_a(τ) for all τ ≤ τ_s, authentication cannot pay at any θ with Δ(θ) ≤ τ_s.
  - Prop. 3 (Cliff): R_tx(r) is finite iff r < r* = (1 − U_0)/(n(σ) C_f), using the Davis et al. busy-period analysis.
  - Prop. 4 (Two regimes): "Under 𝒜_deny … the unauthenticated certificate is vacuous. An authenticated source that is still delivered at least once per T_c is then necessary for any certified floor, and, with the authenticated rate γ_a, sufficient for the tube bound."
  - Prop. 5 (Freshness under a GNSS-coupled clock): (a) freshness helps only if τ_fresh + ε_clk(t) < Δ(θ). (b) Pushing GNSS time at rate ν makes every legitimate packet fail after τ_fresh/ν, "convert[ing] 𝒜_delay into 𝒜_deny".
  - Prop. 6 (Verification amplification): ρ_iv = t_ver/(n C_f). The queue is stable iff a ρ_iv + r t_ver < β. A slot budget k_s bounds the induced delay to (k_s − 1) t_ver/β.
  - Algorithm 1 (Certified selection rule), with Eqs. (12)–(13) for amortisation.
- Numbers, all macros in numbers.tex [P1NUM](file://paperI_package/paperI/manuscript/numbers.tex):
  - Rates: γ_u = 1.625, γ_a = 0.933 m/s, ratio 1.74. The 95th-percentile ratio is 1.95 [1.68, 2.67]. Conservative ratio 1.32; secant 2.63.
  - Benefit threshold C(0.25) = 371 ms (headline), 160 ms (conservative), 816 ms (secant).
  - Supremum-discipline crossovers: θ_× = 0.080 s (ML-DSA-44), 0.006 s (Ed25519), 0.003 s (MAC). Conservative ML-DSA: 0.186 s.
  - Tubes at θ = 0.25 s: ρ_U = 2.65 m. Authenticated: ρ_A = 1.88 m (ML-DSA-44), 1.55 m (Ed25519), 1.53 m (MAC). Conservative ML-DSA: 2.48 m.
  - Horizon-matched: θ_× = 0.259 s (MAC) to 0.284 s (ML-DSA-44). Envelope difference 1 cm. δ_u(0.5) = 0.46 m. At θ = 0.5 s: δ_u = 0.93 m vs δ_a = 0.65 m.
  - Dead-reckoning fit: v_0 = 0.857 m/s, b = −0.014 m/s², RMSE 0.16 m, n = 45.
  - Admissible rate r*: ML-DSA-44 16.3/s (18.1 on an idle bus; CAN FD 120). SLH-DSA-128s 5.0/s. Ed25519 563.1/s.
  - Certified authentication delay Δ_auth: ML-DSA-44 119.0 ms, Ed25519 9.1, MAC 4.4, FN-DSA-512 66.8, TESLA (0.1 s interval) 114.6.
  - Bus base load U_0 ∈ [0.081, 0.099].
  - a_sat (Ed25519, β = 0.2) = 0.105.
  - Freshness time-push: 600 s at 100 ms/s, 6000 s at 10 ms/s, 16.7 h at 1 ms/s.
  - Selection grid: 512 cells; authentication rescues 24 of 128 headline delay cells. Denial regime: 24 of 128 infeasible.
  - ML-DSA batching at k = 8: bus load 65.3 % → 18.1 %, at 820 ms certified latency.
- Inputs and provenance [P1 l.594–621](file://paperI_package/paperI/manuscript/main.tex):
  - γ_u: 178 spoofing samples.
  - γ_a: 496 jamming samples, a "measured proxy".
  - Δ(θ), L: from the parent.
  - T_c, θ = 0.25 s, m: "parent choices", tagged assumption.
  - Datasets used: Whelan UAV Attack Dataset and the HCRL UAVCAN capture (508–619 frames/s benign).
- Experiments E1–E8 (runbook):
  - E1: inertial γ from synthetic outages.
  - E2: VIO γ on EuRoC.
  - E3: PX4 SITL spoofer walk-rate sweep with an authenticated arm, hover plus cruise at 5/10/15 m/s. E3 "matters most".
  - E4: STM32H7 cycles.
  - E5: HCRL bus timing.
  - E6: hardware flood.
  - E7: GNSS time push vs MAVLink 2 signing.
  - E8: OSNMA offsets.

  [P1 l.724–741](file://paperI_package/paperI/manuscript/main.tex); [Paper I runbook](file://paperI_package/paperI/RUNBOOK_CLAUDE_CODE.md)
- The runbook flags a contradiction with the parent: the Whelan jamming flight "keeps fix_type = 3 with 12–14 satellites throughout every post-onset sample … The same observation contradicts the parent paper's sentence that under jamming 'the estimator gates the missing fix and dead-reckons'; flag this to the author." — [Project doc PaperI/RUNBOOK_CLAUDE_CODE.md §0](file://paperI_package/paperI/RUNBOOK_CLAUDE_CODE.md)
- Limitations [P1 l.1094–1125](file://paperI_package/paperI/manuscript/main.tex):
  - γ_a is a proxy.
  - One airframe (PX4 Holybro S500), hover only.
  - Compute costs are scaled literature values.
  - The transport model is worst-case and partly assumed.
  - Additivity of Δ_auth is assumed.
  - Single-onset envelopes.
  - External validity: "We therefore release the calculator, not only the numbers."
- Discussion lesson: "A sound certificate is not a design oracle … A design choice should be read from the bound that is tight for both alternatives, not from the one that is safe for each." — [P1 l.1010–1015](file://paperI_package/paperI/manuscript/main.tex)
- Related-work row: "Certified robustness, tubes and runtime assurance~\cite{cohen2019smoothing,mayne2005tube,lohmiller1998contraction,majumdar2017funnel,sha2001simplex,fawzi2014secure}" — [P1 l.1075–1077](file://paperI_package/paperI/manuscript/main.tex)
- Ethics: attacker capabilities are "presented with its mitigation", and MAVLink maintainers are to be notified — [P1 l.1142–1150](file://paperI_package/paperI/manuscript/main.tex)

### Inferences
- **Paper V's "one certified budget, exactly as Paper I's credit/debit did" is consistent in spirit** [PV l.161–163](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/ac54f2a6-PaperV_safety_filter_llm_agent.tex). In Paper I, two security mechanisms trade inside ρ = Δ_eff·γ_eff·E ≤ m. Paper V's analogue is that the language-channel and sensing-channel attacks share the tube/admissible set.
  - The formal object in Paper I is the product Δ·γ·E against m.
  - Paper V's Prop. 3 uses Paper IV's δ_tot instead. Paper V should state how δ_tot relates to Paper I's Δ_eff·γ_eff, for example δ_tot ⊇ γ_eff·Δ_eff, so that the "same budget" claim is checkable.
- **Paper I's Prop. 4 (two regimes) and Prop. 5(b) are direct precedents for Paper V's "safety attack → liveness attack".**
  - Paper I already shows that a security mechanism (authentication plus freshness) can be turned into a denial adversary: "a persistent-denial adversary manufactured from authentication itself".
  - Paper V can cite this as programme precedent for the honest "safety unconditional, liveness not" framing. Its fallback is the analogue of 𝒜_deny's effect.
- **Symbol hazard.** Paper I uses κ for an authentication configuration and ρ_iv for verification amplification. The parent uses κ for schedule tolerance. Paper V uses κ = 0.25 as a simulator parameter. Paper V should define κ explicitly, preferably as the parent's schedule tolerance, and avoid Paper I's κ.
- **Paper I's E = e^{LT_c} = 3.259 and ρ_U = 2.65 m are the numerically consistent values for γ = 1.625.** Paper V can quote them if it states margins.

### Gaps
- Paper I's results for E1–E8 are not yet available, since the runbook says they need data, SITL or hardware. γ_a remains a proxy.
- No Paper I PDF is in the package. Line numbers refer to main.tex, and the final page numbers are unknown.

---

## Q3. Paper II: problem, taxonomy, the "runtime-assurance lift", results, notation, limitations

### Takeaway
Paper II, "SoK: The Quantifier Gap Between Certified Robustness and Airworthiness Assurance", targets the IEEE S&P SoK track with a regulatory cut-off of 7 Oct 2026. It types every guarantee and objective as ⟨scope, modality⟩ and defines seven typed lifts with obligations.

The "runtime-assurance lift" Paper V invokes is Paper II's **L_mon**:
- Edge: ⟨in, ∀|P⟩ → ⟨op, P⟩.
- Obligations: O_mcov, O_lat, O_rec, O_ind.
- Codebook rule: RTA architectures are ⟨op, ∀⟩ with L_mon.

Paper II's H4 finding is that RTA is "the only direct bridge" to per-operation objectives (T4), but "it relocates the deficit". Prop. 4 says so, and a documented override says Simplex covers natural hazards only, "not for attacks on the monitor's own inputs". The phrase "runtime-assurance lift" itself does not appear verbatim in Paper II.

### Cited Findings
- Title "SoK: The Quantifier Gap Between Certified Robustness and Airworthiness Assurance". Target "IEEE Symposium on Security and Privacy, SoK track", IEEEtran, double-blind. Repository `rogerpanel/RobustUAVs.ai`, branch `paperII/full-study` — [P2 l.1–14, 71–74](file://paperII_package/paperII/manuscript/main.tex); [Project doc PaperII/RUNBOOK_CLAUDE_CODE.md](file://paperII_package/paperII/RUNBOOK_CLAUDE_CODE.md)
- Status: pilot. 86 guarantees (46 tier A, 40 tier B), 17 classes and 22 objectives, of which 14 were checked against primary text. Two LLM coders, 50 adjudicated changes across 37 papers. Regulatory cut-off 7 October 2026 — [P2 l.181–191, 625–635](file://paperII_package/paperII/manuscript/main.tex); [P2NUM](file://paperII_package/paperII/manuscript/numbers.tex)
- The core observation, quoted: "A certified radius speaks about every perturbation of one input. A contingency volume speaks about one operation. A per-flight-hour objective speaks about a population of operations." — [P2 l.86–88](file://paperII_package/paperII/manuscript/main.tex)
- Definition 1 (Quantifier type): τ = ⟨σ, μ⟩.
  - Scope σ ∈ {in, tr, op, pop_d, pop_h}.
  - Modality μ ∈ {∀, ∀_α, P, E, ∃}.
  - ∀_α is "for all with confidence 1 − α over the certifier's own randomness".

  [P2 l.303–314](file://paperII_package/paperII/manuscript/main.tex)
- Definitions 2–4 [P2 l.324–402](file://paperII_package/paperII/manuscript/main.tex):
  - Def. 2 (Dominance ⪰): "g discharges o if τ_g ⪰ τ_o and the perturbation model of g covers the hazard of o".
  - Def. 3 (Lift ℓ: τ → τ′) carries obligations 𝒪(ℓ), each with an evidence kind: proof, model, statistical or architectural.
  - Def. 4 (Transfer path and assurance deficit): verdict D, L_k or ×.
- The lift calculus, Table II [P2 l.366–391](file://paperII_package/paperII/manuscript/main.tex):
  - L_α: ⟨σ, ∀_α⟩ → ⟨σ, ∀⟩. Obligation O_α (proof).
  - L_dyn: ⟨in, ∀⟩ → ⟨tr, ∀⟩. Rule: "‖δu(t)‖ ≤ r for all t, drift L-Lipschitz ⇒ ‖e(t)‖ ≤ r(e^{Lt} − 1) on [0, T_c]". Obligation O_lip (model).
  - L_hor: ⟨tr, ∀⟩ → ⟨op, ∀⟩. Obligation O_hor, re-anchoring (model).
  - L_op: ⟨in, ∀|P⟩ → ⟨pop_d, P⟩. Obligation O_prof (statistical).
  - L_sup: ⟨op, ∀⟩ → ⟨pop_d, P⟩. Obligation O_odd, "deployment stays in the certified set" (statistical).
  - L_rate: ⟨pop_d, P⟩ → ⟨pop_h, P⟩. Obligation O_dep (statistical).
  - **L_mon: ⟨in, ∀|P⟩ → ⟨op, P⟩.** Rule: "monitor flags hazardous inputs, switch within latency, verified recovery ⇒ per-operation safety except on monitor misses". Obligations O_mcov, O_lat, O_rec, O_ind, of kinds s, m, p, a.
  - O_thr is added whenever the perturbation model does not cover the objective's hazard.
- "L_mon is the Simplex argument~\cite{sha2001simplex,mehmood2022bbsimplex}" — [P2 l.364](file://paperII_package/paperII/manuscript/main.tex)
- Theorem 1 (Transfer soundness): confidence 1 − δ_π, with δ_π = δ_0 + Σ_{O∈𝒪(π)} δ_O. Here δ_0 = 0 for ∀ and α for ∀_α, and δ_O = 0 for proofs — [P2 l.404–418](file://paperII_package/paperII/manuscript/main.tex)
- Propositions:
  - Prop. 1: dominance is a partial order; ⟨in, ∀⟩ and ⟨pop_h, P⟩ are incomparable, as are ⟨op, ∀⟩ and ⟨pop_d, P⟩.
  - Prop. 2 (No modality for free): every path from ∀ or ∀_α to P "contains at least one lift with a statistical obligation".
  - Prop. 3: rate lift and confirmation credit.
  - Prop. 4: zero-failure ladder (SORA Annex E is the rule of three).
  - Corollary 1: "From ⟨in, ∀⟩, the least-obligation route to ⟨pop_h, P⟩ is L_op L_rate … Every route that also yields a per-operation guarantee costs at least four obligations: O_lip, O_hor, O_odd and O_dep."

  [P2 l.337–501](file://paperII_package/paperII/manuscript/main.tex)
- **Proposition (Runtime assurance relocates the gap), verbatim:** "In the calculus, ⟨op, ∀⟩ objectives are discharged directly only by a guarantee of type ⟨op, ∀⟩. Such a guarantee from runtime assurance is conditional on {O_mcov, O_lat, O_rec, O_ind}. When the monitor's decision depends on a learned perception output, O_mcov is a statement of type ⟨pop_d, P⟩ about that output, the same type as the gap the architecture was introduced to bridge." — [P2 l.482–489](file://paperII_package/paperII/manuscript/main.tex)
- Proof of that proposition: "The Simplex theorem states safety on every execution in which the monitor flags each state outside the recoverable set within the switching latency, and the recovery controller is verified from every state it can be handed. These are O_mcov, O_lat and O_rec, and the monitor's input must not share the failure modes of the channel it guards, which is O_ind." — [P2 l.1139–1148](file://paperII_package/paperII/manuscript/main.tex)
- Class-level override: "a Simplex guarantee holds for arbitrary behaviour of the monitored component, but not for attacks on the monitor's own inputs, so it covers natural hazards only" — [P2 l.620–623](file://paperII_package/paperII/manuscript/main.tex)
- Codebook rule 5: "Runtime-assurance architectures with a conditional safety theorem are ⟨op, ∀⟩ with L_mon". The CODEBOOK scope "op" includes "a runtime property enforced on every execution (Simplex, shields, runtime verification of a mission spec)" — [P2 l.1187–1188](file://paperII_package/paperII/manuscript/main.tex); [CODEBOOK.md](file://paperII_package/paperII/corpus/CODEBOOK.md)
- Transfer-table RTA row (n = 6, type ⟨op, ∀⟩):
  - T1 L₂{sup, rate}; T2 L₁{sup}; T3 L₁{sup}.
  - **T4 D.**
  - **T5 (security threat condition, ⟨op, ∀⟩ adversarial) L₁{thr}.**
  - T6 ×. Evidenced share 0 %.
  - MON (n = 3, ⟨in, ∀⟩) reaches T4 via L₂{dyn, hor} and T5 via L₃{dyn, hor}.
  - RTA class members include shielding (alshiekh2018shielding) and Black-Box Simplex.

  [tab_transfer_body.tex](file://paperII_package/paperII/manuscript/tab_transfer_body.tex); [P2 l.1218](file://paperII_package/paperII/manuscript/main.tex)
- H4 result: "Of the 17 classes, 11 reach a per-operation objective (T4), and only RTA discharges one directly … RTA carries 4 intrinsic obligations … No pilot RTA paper evidences all four, and the evidenced share for the class is zero … H4 is supported in the form 'RTA is the only direct bridge, and it relocates the deficit'. It is not supported in the stronger form 'RTA closes the gap'. … If the monitor reads the same perception channel it guards, the failures are common-cause and the lift collapses." — [P2 l.893–903](file://paperII_package/paperII/manuscript/main.tex)
- Other results:
  - Transfer table: 102 cells, of which 8 D, 66 L and 28 ×.
  - H1: 64 % of 44 perception guarantees are per input, vs 19 % of 32 control guarantees.
  - H2: only 17 % of 54 lifted guarantees account for their assumption, rising from 7 % to 26 % (2017–21 vs 2022–26).
  - Monitor lift: evidenced in 0 % of 9 papers.
  - L_sup: used explicitly by 0 papers.
  - Reliability: type α = 0.83 [0.74, 0.91]; assumption α = 0.46.

  [P2NUM](file://paperII_package/paperII/manuscript/numbers.tex); [P2 l.806–903](file://paperII_package/paperII/manuscript/main.tex)
- The parent as running example (evidence pack, Table V):
  - Steps: θ ↦ Δ (Lemma, ⟨in, ∀⟩, E); Δ ↦ δ (calibration, P); δ ↦ ρ (L_dyn, O_lip, E); ρ ↦ corridor (L_hor, O_hor, A: "re-anchoring every T_c; delay adversary only"); corridor ↦ MCR (L_sup, O_odd, S); MCR ↦ per FH (L_rate, O_dep, O: "not claimed").
  - Hazard O_thr (S): "denial, insider and monitor-input attacks not covered".
  - Numbers: γ = 1.365 gives δ = 0.68 m and ρ = 2.22 m. γ = 1.625 gives 2.65 m. Kinematic gives 24.4 m.
  - Certified at 5/10/20 m, not at 2 m. 6 obligations, 2 open or assumed.

  [P2 l.918–970](file://paperII_package/paperII/manuscript/main.tex); [evidence_pack.json](file://paperII_package/paperII/results/evidence_pack.json); [lift_chain.csv](file://paperII_package/paperII/results/lift_chain.csv)
- Research agenda item 4: "Monitor coverage with confidence (RTA and MON to T4). ASTM F3269 names coverage as a concern … Independence of the monitor's input must be argued, not assumed." Item 2: "Reachable tubes as contingency volumes … The missing step is O_hor under realistic re-anchoring, including denial." — [P2 l.979–997](file://paperII_package/paperII/manuscript/main.tex)
- Notation clashes in Paper II [P2 l.274–289](file://paperII_package/paperII/manuscript/main.tex):
  - τ = ⟨σ, μ⟩ is a type, with σ the scope.
  - δ_o, ε_o are evidence failure probability and error.
  - f, p, λ are decision rate, per-decision hazard and per-hour rate.
  - k is confirmation length; ρ is error persistence Pr(e_t | e_{t−1}).
  - κ (in protocol text) is Cohen's kappa.
- Limitations [P2 l.1028–1054](file://paperII_package/paperII/manuscript/main.tex):
  - Pilot corpus, both coders LLMs.
  - "The calculus is ours."
  - Class-level types hide spread.
  - Regulatory drift: 8 secondary objectives.
  - Construct validity of "accounted for".

### Inferences
- **How Paper V should phrase its Paper II link.** Paper V's sentence "Paper II would classify Paper V as a runtime-assurance lift — a per-operation guarantee discharged by a monitor rather than an offline certificate — which is exactly the bridge Paper II names for objectives no static certificate can reach" [PV l.297–300](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/ac54f2a6-PaperV_safety_filter_llm_agent.tex) matches H4's weak form. To stay consistent with Paper II it should:
  - (a) name the lift as L_mon, and its type as ⟨op, ∀⟩ under codebook rule 5;
  - (b) list O_mcov, O_lat, O_rec, O_ind and state how each is discharged;
  - (c) address Paper II's override that Simplex covers natural hazards only. Paper V's object is an adversarial hazard (T5), where Paper II's RTA row needs O_thr.
- **How each obligation could be discharged.** Paper V's trust boundary — the filter reads the certified navigation model's state, not the LLM's text, and attacks on the certified model are out of scope — is the argument for O_ind and for O_thr restricted to the planning channel.
  - Prop. 1 of Paper V (recursive feasibility) discharges O_rec (fallback verified from the terminal set) and O_mcov on the model, which is proof-kind because the monitor is not learned.
  - O_lat (solver latency vs T_c) remains open.
  - Model-plant mismatch is exactly Paper II's O_lip / O_cal.
- **Paper V's "safety unconditional, liveness not" headline is a ⟨op, ∀⟩ statement.** Its denial rate is a ⟨pop_d, P⟩ statement, measured empirically. Paper II's Prop. 2 (No modality for free) implies that Paper V cannot turn its zero-violation proof into a per-flight-hour claim without L_sup/L_rate obligations. This supports Paper V's own caution.
- **Paper V's composition with Paper IV's sensing attack is a concurrent adversarial input to the monitor's state estimate.** Paper II flags precisely this ("attacks on the monitor's own inputs") as uncovered by Simplex. Paper V's Prop. 3 is therefore where Paper II's O_thr/O_ind must be explicitly argued.

### Gaps
- The exact phrase "runtime-assurance lift" is not found verbatim in Paper II's main.tex. The concept is L_mon / "the Simplex argument" / RTA class.
- Paper II's main.pdf exists in the package, but I did not map page numbers. Line numbers refer to main.tex.
- Paper II's full-study results (S1–S9) do not exist yet, so all corpus numbers are pilot.

---

## Q4. Bibliography keys, preamble files and compile prerequisites for Paper V

### Takeaway
Paper V's tex calls `\input{proposal_preamble3}` and `\bibliography{proposals3}`. **Neither file exists anywhere on the local filesystem**; I searched all of `/`. Paper V will not compile until they are supplied.

Of the 10 citation keys Paper V uses, only `parentpaper` and `sha2001simplex` exist in the Paper I or II bib files. The other eight need new entries in proposals3.bib: openai2024agents, greshake2023injection, seto1998simplex, wabersich2021psf, hewing2020mpclearning, rawlings2017mpc, carlini2017towards, tramer2020adaptive.

### Cited Findings
- Paper V preamble use:
  - `\documentclass[11pt,a4paper]{article}`, `\input{proposal_preamble3}`, `\usepackage{array}`.
  - Column types Y and P.
  - Macros `\safe` = 𝒮, `\adm` = 𝒜_adm, `\prov`.
  - `\proposalheader{..}{..}{..}`.
  - Environments `definition`, `proposition`, `honestly`, and `description` with `[leftmargin=2.6em, style=nextline]` (enumitem).
  - `tabularx`, `booktabs`, `\code{}`.
  - `\bibliographystyle{plain}`, `\bibliography{proposals3}`.
  - Build: pdfLaTeX + BibTeX.

  `\proposalheader`, `honestly`, `\code`, `definition`, `proposition`, tabularx, booktabs and enumitem must all come from proposal_preamble3 — [PV l.9–20, 98, 165, 204, 354–355](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/ac54f2a6-PaperV_safety_filter_llm_agent.tex)
- Citation keys used by Paper V: parentpaper, openai2024agents, greshake2023injection, seto1998simplex, sha2001simplex, wabersich2021psf, hewing2020mpclearning, rawlings2017mpc, carlini2017towards, tramer2020adaptive — [PV](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/ac54f2a6-PaperV_safety_filter_llm_agent.tex)
- The `parentpaper` entry is identical in Paper I and II: `@misc{parentpaper, author={{Anonymous}}, title={{From Wire to Flight: A Conditional Mission-Completion Guarantee for UAVs}}, year={2026}, note={Under submission; anonymised for double-blind review}}` — [P1 refs.bib l.7–11](file://paperI_package/paperI/manuscript/refs.bib); [P2 refs.bib l.8–11](file://paperII_package/paperII/manuscript/refs.bib)
- Paper II refs.bib also has `@misc{paperI, … title={{What Authenticity Costs in Metres: A Certified Budget for Cryptography and Sensing in UAV Navigation}}, year={2026}, note={Under submission; anonymised …}}`. That is usable if Paper V cites Paper I — [P2 refs.bib l.12–15](file://paperII_package/paperII/manuscript/refs.bib)
- Other reusable entries:
  - `sha2001simplex`: P1 refs.bib l.390; P2 l.223.
  - `gronwall1919`, `whelan2020uav`.
  - `jarus_sora25` (P1) and `jarus_sora25_{mb,A,E}` (P2).
  - `do326a`, `mayne2005tube` (P1 l.262).
  - `mehmood2022bbsimplex`, `alshiekh2018shielding` (P2 l.233), `hobbs2023rta`, `astm_f3269` (P2).

  Both bib files carry "% VERIFY" markers on some entries: 13 in Paper I and 3 author items in Paper II, per the READMEs — [P1 refs.bib](file://paperI_package/paperI/manuscript/refs.bib); [P2 refs.bib](file://paperII_package/paperII/manuscript/refs.bib)
- Paper I and II use IEEEtran + `\input{numbers}` (macro-generated numbers, "never type a number into main.tex by hand"). They do not use proposal_preamble3 — [P1 l.9–35](file://paperI_package/paperI/manuscript/main.tex); [P2 l.9–34](file://paperII_package/paperII/manuscript/main.tex)
- Paper IV defines `\newcommand{\dtot}{\delta_{\mathrm{tot}}}`, which is relevant to Paper V's δ_tot. This is from a grep of the Paper IV zip only and is outside my scope — [Paper IV zip, manuscript/main.tex l.43](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/95f3f9ec-PaperIV_full_package.zip)

### Inferences
- **Minimum compile kit for Paper V:**
  - proposal_preamble3.tex defining `\proposalheader`, the theorem environments (definition, proposition), `honestly` (a boxed "honest limitations" environment) and `\code`. It must load amsmath/amsthm, booktabs, tabularx, enumitem and hyperref.
  - proposals3.bib containing the 10 keys above.
  - Reusing `parentpaper` and `sha2001simplex` verbatim from Paper I/II keeps the programme consistent.
- **Paper V cites "Paper III" and "Paper IV" in prose but has no `\cite` keys for them.** Paper II's `paperI` entry pattern could be copied as `paperIII` and `paperIV` entries.

### Gaps
- proposal_preamble3.tex and proposals3.bib were not found locally, so their exact contents (macro definitions, existing entries) are unknown. They probably live in the user's Overleaf project or repository.

---

## Q5. Explicit forward references to Paper V, LLM agents, MPC filters or safety filters

### Takeaway
None of the parent, Paper I or Paper II mentions Paper V, LLM agents in the control loop, MPC, or predictive safety filters. The closest hooks are:
- The parent's Simplex/runtime-assurance passages: a monitor triggered by leaving the Lipschitz envelope, a fallback independent of L, and the certified window as "a candidate specification for exactly that monitor".
- Paper I's citations of tube MPC (mayne2005tube) and Simplex.
- Paper II's L_mon / RTA / shielding class and its agenda item on monitor coverage.

Paper II's only use of LLMs is as coders in the systematization protocol.

### Cited Findings
- Parent, Simplex link, verbatim: "This is also where the runtime-assurance reading of §XI becomes operational: departure from the linearisable envelope is exactly the trigger a Simplex-style monitor must use to hand control to a verified fallback whose guarantee does not depend on L." — [PARENT p.11](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=11)
- Parent, related work: "Simplex and its descendants [31]–[33] guarantee safety by switching from an unverified controller to a verified baseline when a monitor fires; our certified window is the region in which the high-performance policy may run, and we contribute the quantitative boundary such architectures otherwise hand-tune." The references are [31] Sha 2001, [32] Mehmood et al. Black-Box Simplex (NFM 2022) and [33] Cofer et al. RTA for learning-enabled systems (NFM 2020) — [PARENT p.6, p.18](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=6)
- Parent: "Runtime assurance guarantees safety by switching controllers when a monitor fires, and our certified window is a candidate specification for exactly that monitor rather than a competitor to it." — [PARENT p.15](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=15)
- Parent: "Certifying against sustained denial needs either a link-layer bound on outage length or a fallback whose guarantee is independent of L, which is the runtime-assurance direction of §XI." — [PARENT p.17](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=17)
- The parent text contains no occurrence of "LLM", "language model", "MPC", "predictive" or "safety filter". This was checked by grep over the extracted text; the "filter" hits all refer to the EKF/navigation filter — [PARENT extracted text](file://parent_text/parent.txt)
- Paper I cites tube MPC and Simplex together in related work ("Certified robustness, tubes and runtime assurance … robustness to a given perturbation | where the perturbation comes from, and what removing part of it costs"). It contains no LLM, MPC-filter or Paper V reference — [P1 l.1075–1077](file://paperI_package/paperI/manuscript/main.tex)
- Paper II: "Runtime assurance gives per-execution guarantees by switching from an unverified controller to a verified fallback when a monitor fires … (RTA). Shields enforce a safety specification on a learning agent's actions~\cite{alshiekh2018shielding}." — [P2 l.699–701](file://paperII_package/paperII/manuscript/main.tex)
- Paper II's LLM mentions concern only the coding protocol, for example "a large language model (LLM) used as a logged third coder that may never exclude a paper on its own" — [P2 l.168–169, 588–594](file://paperII_package/paperII/manuscript/main.tex)
- Grep across the Paper I–IV packages for "Paper V", "safety filter", "predictive", "MPC" or "LLM agent" found no forward reference to Paper V — [package grep](file://scratch/)

### Inferences
- **Paper V's motivation can be anchored as the realisation of the parent's stated "runtime-assurance direction".**
  - The certified window or tube becomes the monitor specification.
  - The fallback (loiter/RTL) is the "verified fallback whose guarantee does not depend on L".
  - Paper V adds an untrusted LLM planner and an adaptive attacker.
- **Paper V's Prop. 2 (safety attack → liveness attack) is the sibling of the parent's persistent-denial boundary (C2) and Paper I's Prop. 4/5(b).** In all three, the attacker is pushed from violating safety to denying service. This gives the programme a consistent "denial is the residual" thread.
- **Paper V's related-work section is not covered by the programme's bibs.** It will need new entries for shields (alshiekh2018shielding, already in Paper II's bib), predictive safety filters, control-barrier-function filters and LLM-agent security.

### Gaps
- Paper III's projection layer (which Paper V calls "the same object") and Paper IV's δ_tot were outside this assignment. I did not extract them, beyond confirming that Paper IV defines `\dtot` = δ_tot.
