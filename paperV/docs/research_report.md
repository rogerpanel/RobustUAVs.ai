# Recasting Paper V: prove safety, measure liveness honestly

Paper V's core idea holds up and has a real gap to fill. The idea is a predictive safety filter whose physical-safety guarantee is quantified over *every* sequence of language-model outputs, evaluated against an adaptive attacker. No verified LLM-drone system states a theorem universally quantified over an adversarial planner. No published attack on embodied LLM agents has been evaluated against a dynamics-level filter. The only adaptively evaluated robot guardrail, RoboGuard, is semantic, not physical ([RoboGuard](https://arxiv.org/pdf/2503.07885); [Hafez et al.](https://arxiv.org/html/2503.03911v1); [CHAI](https://arxiv.org/html/2510.00181v2)).

The proposal as written is not yet publishable, for three reasons:
- **"In hand" overstates the codebase.** None of the four "in hand" items exists in the form the proposal describes. The certificate engine returns a scalar tube verdict, not an admissible set. The fleet simulator has no action channel and is seeded from wall-clock time. The LLM router is a single-turn text-completion function. Paper III's "projection layer" is a Hungarian matching, not a QP.
- **Several constants and citations are misattributed.** κ = 0.25, MAX_FLEET = 12, R_i(t) ≥ R_min and "ten attack classes" are attributed to the parent manuscript. They do not come from it.
- **Propositions 2 and 3 do not hold as stated.** Prop. 2 misses the cheapest denial an attacker has: steering the agent to propose safe but useless actions, which the filter never overrides. Prop. 3 claims a monotonicity that Paper IV never proves, over a δ_tot that Paper IV never reduces to a scalar.

The paper becomes rigorous and novel if it does three things:
- **Strengthen Theorem 1.** Restate it as robust, planner-invariant safety of the *true* state. It must carry an explicit model-mismatch margin and Paper III's time-varying protection level ρ_i(t), and handle certificate jumps and solver failure.
- **Reformulate the liveness and composition results.** Recast them as a safety/liveness decomposition with a measured denial decomposition, and as a nestedness theorem plus an empirically tested monotonicity.
- **Evaluate with an extended attacker ladder.** The ladder should end in a non-LLM oracle adversary. That adversary is free to run and upper-bounds every prompt-injection attack, because the theorem covers all action sequences.

Almost all of this can be built and run offline on a 2-core CPU; only real-LLM campaigns cost money. Because the SaTML 2027 deadline (29 Sep 2026) has already passed, the realistic targets are the next SaTML cycle or the USENIX Security fallback. That leaves time for the roughly five-month plan at the end of this report.

## The programme supplies a tube, a protection level and a budget, not an admissible set

### What the parent manuscript provides

**The parent's certificate is a per-mission tube.** "From Wire to Flight" chains a detector threshold to a mission-completion floor through θ ↦ Δ(θ) ↦ δ(θ) = γΔ(θ) ↦ ρ = δe^{LT_c} ≤ m. Here:
- Lemma 1 bounds undetected delay at Δ(θ) ≤ H·min(θ, s).
- Theorem 1 is a Lipschitz–Grönwall tube.
- Proposition 1 asserts soundness.

**The chain is not a theorem end to end.** The paper itself says so: "the first and last links are proved; the middle link, Δ ↦ δ, is an empirical calibration" ([Parent p.2](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=2)).

**The constants Paper V inherits are measured and narrow.**
- γ = 1.625 m/s is the supremum of the baseline-corrected rate over 674 post-onset samples.
- L̂_loc = 1.181, T_c = 1 s and margins m ∈ {2, 5, 10, 20} m.
- γ comes from three PX4 flights of one airframe family, "all in low-speed hover or loiter".

Sources: [Parent p.9](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=9); [Parent p.13](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=13); [Parent p.16](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=16).

**The parent's scope conditions are what Paper V's filter must respect.** The certificate applies only:
- (C1) inside a Lipschitz envelope, outside which it is "silent rather than merely loose";
- (C2) under re-anchoring at least once per T_c, which a persistent-denial adversary breaks;
- (C3) under interface transfer, which the parent calls the weakest condition.

([Parent p.2](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=2); [Parent p.11](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=11))

**The parent asks for Paper V by name of its architecture, not by number.** On sustained denial it says certification "needs either a link-layer bound on outage length or a fallback whose guarantee is independent of L, which is the runtime-assurance direction". It also calls its certified window "a candidate specification for exactly that monitor" ([Parent p.15](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=15); [Parent p.17](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=17)). That is the cleanest motivation Paper V can cite. The parent never mentions LLMs, MPC or safety filters, so Paper V is the realisation of a stated programme direction, not a continuation of an existing result.

### Paper I, Paper II, Paper III and Paper IV

**Paper I** supplies the "credit/debit" template. Authentication lowers γ from 1.625 to 0.933 m/s but adds delay Δ_auth. Both trade inside one inequality, ρ(θ, κ) = Δ_eff·γ_eff·e^{LT_c} ≤ m, with E = e^{LT_c} = 3.259 and an unauthenticated tube of ρ_U = 2.65 m at θ = 0.25 s ([Paper I main.tex](file://paperI_package/paperI/manuscript/main.tex); [Paper I numbers.tex](file://paperI_package/paperI/manuscript/numbers.tex)). Paper I also gives the programme its "denial is the residual" thread:
- Its Prop. 4 shows the unauthenticated certificate is vacuous under a denial adversary.
- Its Prop. 5(b) shows a GNSS time-push "convert[s] 𝒜_delay into 𝒜_deny".

This is a direct precedent for Paper V's "safety attack becomes liveness attack".

**Paper II** supplies the assurance vocabulary. A runtime-assurance guarantee is the lift **L_mon: ⟨in, ∀|P⟩ → ⟨op, P⟩**. It carries four obligations:
- O_mcov: monitor coverage.
- O_lat: switching latency.
- O_rec: a verified recovery controller.
- O_ind: monitor independence.

Codebook rule 5 types RTA architectures as ⟨op, ∀⟩ ([Paper II main.tex](file://paperII_package/paperII/manuscript/main.tex)).

Paper II's H4 finding is double-edged for Paper V. RTA is "the only direct bridge" to per-operation objectives, but it "relocates the deficit". A Simplex guarantee "holds for arbitrary behaviour of the monitored component, but not for attacks on the monitor's own inputs, so it covers natural hazards only". The first clause is exactly Paper V's Prop. 1. The second clause is exactly what Prop. 3's concurrent sensing attack violates.

**Paper III** supplies the per-aircraft protection level Paper V actually needs: ρ_i(t) = e^{LT}γ_sup Δ_i(t).
- The slope is L_ρ = 5.30 m/s per second of staleness, with a benign floor of about 0.94 m.
- It treats ρ_i(·) as an adversarially chosen càdlàg process.
- Its Theorem 3 gives the horizon look-ahead logic Paper V's MPC needs. A holder stays feasible for H unless a jump occurs, provided acquire and keep look-aheads of L_ρH and L_ρΔt are used.
- "Jumps cannot be predicted from a rate bound": the median two-hop jump is about 41.8 m.

([Paper III main.tex](file://paperIII_package/paperIII/manuscript/main.tex); [Paper III numbers.tex](file://paperIII_package/paperIII/manuscript/numbers.tex))

Paper III's evaluation design transfers almost verbatim:
- Violations are counted per agent-epoch, never averaged per episode.
- Zero-violation claims carry a Clopper–Pearson bound (0 over 2.9×10⁷ agent-epochs, CP ≤ 1.0×10⁻⁷).
- A "coverage ratio" separates "safe because idle" from "safe and maximal".
- Adding the projection "at deployment" to any learned policy is a standard ablation.

**Paper IV** supplies the budget δ_tot = δ_net(θ) ⊕ δ_adv(θ) ⊕ δ_gnss ⊕ δ_fault ⊕ δ_env.
- The ⊕ has mixed semantics. Deterministic terms shift the margin. Stochastic and p-box terms enter through a dependence-sharp tail bound p̄.
- The certified statement is Pr[fail ∧ U] ≤ p̄(s_m), with s_m = m − e^{LT_c}δ_net(θ) − δ_adv(θ) ([Paper IV main.tex](file://paperIV_package/paperIV/manuscript/main.tex)).
- Its headline numbers are δ_adv = 4.37 m, and zero Holm-significant violations at 270 operating points over 30,541 undetected-attack missions.
- A held-out attacker exceeded δ_adv once, at 5.13 m (1.17×).
- Paper IV certifies **covert attackers only**: "An attacker indifferent to detection is bounded instead by detection latency and the failsafe, which we do not certify here" ([Paper IV sec_results](file://paperIV_package/paperIV/manuscript/sec_results.tex); [Paper IV sec_discussion](file://paperIV_package/paperIV/manuscript/sec_discussion.tex)).

### The synthesis

Paper V's admissible set must be *constructed* from three pieces: Paper III's ρ_i(t), which tightens for estimation error; Paper IV's s_m-style margin, which tightens for the sensing budget; and a new model-mismatch tube, which tightens for plant error. The construction is new work, and the paper should say so. The proposal's line "The admissible set 𝒜_adm(x_t) is exactly the certified set the parent paper's budget produces" ([Proposal](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/ac54f2a6-PaperV_safety_filter_llm_agent.tex)) should go.

## Twenty-six inconsistencies to fix before any experiment runs

The table below lists every discrepancy between the proposal and its sources, with a recommended fix. Items 1–8 are attribution and constant errors. Items 9–14 are claims about prior papers that the sources contradict. Items 15–20 concern the codebase. Items 21–26 concern build, venue and notation.

| # | Proposal says | Sources say | Fix |
|---|---|---|---|
| 1 | Simulator has "ten attack classes" | `ATTACKS` in `uav.py` has 10 keys including `none`, i.e. 9 classes plus nominal. The module comment says "The nine attack classes". The parent never lists ten; its only "ten" is HCRL's type1–type10, which collapse to 3 frame classes ([uav.py](file://platform/backend/app/uav.py); [Parent p.7](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=7)) | Say "nine attack classes plus nominal", or add `prompt_injection` as a genuine tenth class |
| 2 | κ = 0.25 | `uav.py` `KAPPA = 0.25` is a schedule overrun (deadline 87.5 s). The parent's schedule tolerance is κ = 0.10. κ also means four other things in the programme: Paper I's authentication configuration, Paper III's `\nKappa` = L_ρ = 5.30 m/s, Paper IV's CUSUM κ, and Paper II's Cohen's κ ([Parent p.4](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=4); [Paper III numbers](file://paperIII_package/paperIII/manuscript/numbers.tex)) | Rename to κ_sched. Use the parent's 0.10 as the headline and 0.25 as a sensitivity, or justify 0.25 explicitly |
| 3 | MAX_FLEET = 12, T = 70 s are "in hand" | Both are `uav.py` constants. T = 70 s is also the parent's reference mission profile. Paper III uses N = 12 but 150 s missions; Paper IV uses a 60 s single-aircraft segment | Cite the platform for these constants, not the parent. State that the fleet-level composition with Paper IV is untested |
| 4 | Safe set has "certified radius R_i(t) ≥ R_min" | No R_i(t) or R_min exists anywhere. The parent's R = ε_out e^{−L̂_loc T_c} ≈ 0.153 is a feature-space input radius with no index i and no time dependence. The nearest object is Paper III's ρ_i(t), where *larger is worse*, so a "≥ R_min" constraint points the wrong way ([Parent p.13](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=13)) | Use ρ_i(t) as the protection level that tightens the corridor: m − ρ_i(t) − … |
| 5 | 𝒜_adm is "exactly the certified set the parent paper's budget produces" | The parent provides a tube and a corridor test. `certify_staleness` returns a yes/no for one (θ, H, m). No "admissible" identifier exists in `certificates/` ([engine.py](file://certificates/engine.py)) | Present 𝒜_adm as a new construction built from parent, Paper III and Paper IV quantities |
| 6 | Certificate engine is "in hand" with γ = 1.625 | `StalenessGronwallCertificate` defaults to the global L = 1.01. A live call returned tube 2.231 m where 1.181 gives 2.65 m. Changing the default would break the parent's self-check at engine.py L386 ([engine.py](file://certificates/engine.py)) | Pass `L=1.1814` from Paper V; do not edit the engine |
| 7 | γ = 1.625 m/s governs the simulator | The fleet simulator's `GAMMA` table is {15.0, 1.195, 1.365} and omits 1.625, so the fleet tube uses 1.365. γ is hover-only ("p90 of \|v_xy\| is under 0.65 m/s"), while the simulators cruise at 12–15 m/s ([PENDING_ON_DATA.md](file://PENDING_ON_DATA.md)) | Headline 1.625. Report kinematic 15 m/s as a conservative bound, and flag the cruise regime as a (C3) transfer assumption |
| 8 | "F Lipschitz with constant L … as in the parent" | The parent's L is the Lipschitz constant of F *in its sensor input u*, measured on a GNSS/receiver graph-model checkpoint. It is not a constant in the action a, and not the simulated plant's | Use L̂_loc = 1.181 only inside ρ_i(t). Give the plant its own mismatch bound w̄ and contraction rate |
| 9 | "This is the same object as Paper III's projection layer" | Paper III's Π is lexicographic maximum-weight bipartite matching (Hungarian), not a QP. Closeness to the proposal is only its third objective, so Π is **not transparent** to a feasible but non-maximal proposal. Its closed forms are lost beyond scalar certificates (Remark 1) ([Paper III main.tex](file://paperIII_package/paperIII/manuscript/main.tex)) | Say Paper V reuses Paper III's safeguard-in-environment placement, the "for every policy" quantifier of Thm 1(i), and the Thm 3 look-ahead. The continuous minimal-deviation filter is new |
| 10 | Prop. 3: fallback rate "monotone in δ_tot" | Paper IV never states or proves this. δ_tot is not a scalar, and only pieces exist: p̄ is non-increasing in s_m, the stochastic-dominance monotonicity is in the proof of Thm 1, and δ_adv is monotone in θ "by construction" ([Paper IV main.tex](file://paperIV_package/paperIV/manuscript/main.tex)) | Define a scalar tightening b_tot(ε). Prove nestedness of 𝒜_adm. Test rate monotonicity empirically (see the formal model below) |
| 11 | Composed sensing attacker is "Paper IV's" | Paper IV certifies covert attackers only, on the event U of no alarm and under C2′. δ_adv is empirical and was exceeded 1.17× once | Restrict the composed attacker to Paper IV's covert class, or add a detection/failsafe argument. Inherit the R1/R8 caveat |
| 12 | "exactly as Paper I's credit/debit did" | Paper I's object is the product Δ_eff·γ_eff·E ≤ m, not δ_tot | State the relation explicitly, e.g. e^{LT_c}δ_net = E·γ_eff·Δ_eff when authentication is off |
| 13 | Paper II "would classify Paper V as a runtime-assurance lift" | The phrase does not appear in Paper II. The object is L_mon, with O_mcov, O_lat, O_rec and O_ind, plus O_thr for adversarial hazards. Paper II says Simplex covers natural hazards only, not attacks on the monitor's inputs ([Paper II main.tex](file://paperII_package/paperII/manuscript/main.tex)) | Name L_mon, give a discharge table for each obligation, and say Prop. 3 is where O_ind/O_thr fail |
| 14 | Prop. 2: attacker's "maximal effect is to force the filter to override" | False as stated. An attacker who controls the agent's inputs can make it propose *admissible but non-progressing* actions ("hold", wrong-but-safe waypoints). The filter is then transparent and the mission still stalls. LLM-agent "malfunction amplification" looping attacks are exactly this ([Breaking Agents](https://arxiv.org/abs/2407.20859)) | Reformulate as liveness confinement plus a denial decomposition: filter-induced vs in-envelope denial |
| 15 | Fallback is "loiter, or return-to-launch" | Only an invariant terminal set is certified by recursive feasibility. RTL is a long manoeuvre that must itself be certified | Make loiter the certified fallback. Admit RTL only as a filtered plan |
| 16 | Fleet simulator is in hand for "agent in the loop" | `fleet_step` has no action input; the track is a fixed 12 m/s circle. Its per-step RNG is seeded from `time.time()`. Dynamics are documented as "illustrative", and the payload's provenance is `synthetic_alignment` ([uav.py](file://platform/backend/app/uav.py); [simulation_architecture.md](file://docs/simulation_architecture.md)) | Build a new seeded, controllable plant (see the experimental design below) |
| 17 | "the platform already integrates anthropic / openai / gemini / deepseek" | `llm.complete()` is a single-turn completion: no tools, no structured output, no temperature or seed, no usage or cost capture, no retries. Errors become synthetic text. Model strings "claude-sonnet-5" and "gpt-4o" are unverified ([llm.py](file://platform/backend/app/llm.py)) | New `agent.py` with a JSON-schema action, a sha256 cache and usage logging. Record exact model IDs and dates |
| 18 | Paper IV runbook "Remark 2" | That remark does not exist in the shipped Paper IV manuscript | Cite Paper IV's design rule in sec_discussion instead |
| 19 | Parent: θ = 0.25 s tube "rises … to about 5.9 m" at γ = 1.625 | Recomputing gives 0.5 × 1.625 × 3.259 ≈ 2.65 m, which matches Paper I and Paper II. The parent's worked example also uses γ = 1.37, not the supremum it mandates ([Parent p.9](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=9)) | Quote 2.65 m (γ = 1.625) or 2.22–2.25 m (γ ≈ 1.37), and say which |
| 20 | Jamming makes the estimator dead-reckon | The Whelan jamming flight keeps fix_type 3 with 12–14 satellites throughout; Paper I's runbook flags this as contradicting the parent ([Paper I runbook](file://paperI_package/paperI/RUNBOOK_CLAUDE_CODE.md)) | Treat Paper III's 1 s/s staleness growth under jamming as a modelling assumption |
| 21 | `\input{proposal_preamble3}`, `\bibliography{proposals3}` | Neither file exists anywhere locally. The repository copy uses `proposal_preamble.tex` and `proposals.bib`, which define `\proposalheader`, `honestly`, `\code` and the theorem environments, and contain all 10 cited keys ([proposals.bib](file://paper/proposals/proposals.bib); [proposal_preamble.tex](file://paper/proposals/proposal_preamble.tex)). Only `parentpaper` and `sha2001simplex` exist in the Paper I/II bibs | Revert to the repository names, or copy the files to the "3" names |
| 22 | Prose cites Papers III and IV | There are no `\cite` keys for them | Add `paperIII` and `paperIV` `@misc` entries on Paper II's `paperI` pattern |
| 23 | `hewing2020mpclearning` | Its venue is the *Annual Review of Control, Robotics, and Autonomous Systems* 3:269–296, not *Annual Reviews in Control* ([DOI](https://doi.org/10.1146/annurev-control-090419-075625)) | Check the bib entry |
| 24 | Branch `claude/whelan-uavcas-ingest-u00isn` | PENDING_ON_DATA §0 schedules it for deletion. The Paper IV runbook names `dev/whelan-uavcas-ingest` as the long-lived equivalent. Paper II lives on `paperII/full-study` | Cut `paperV/…` from `dev/whelan-uavcas-ingest` |
| 25 | Target "IEEE SaTML" | The SaTML 2027 deadline was 29 Sep 2026. That date comes from an aggregator, because the official CFP page could not be fetched ([mldeadlines](https://mldeadlines.com/conference/satml/)) | Target the next SaTML cycle or USENIX Security; confirm dates and page limits on satml.org |
| 26 | Symbols H, ρ, α, T, U | H means hops (parent, III, IV), look-ahead (III) and MPC horizon (V). ρ means tube (IV), protection level (III) and contraction rate (Köhler). α means alert limit, FPR and RA level. U means the no-alarm event | Use N_p for the MPC horizon and λ_c for the contraction rate. Keep T_c, m and ρ_i(t) as defined in Papers III and IV |

Two further items are quieter but matter for credibility.

**The proposal cites `openai2024agents` as its only evidence that LLMs sit in autonomy loops.** Peer-reviewed UAV precedents exist and should be added:
- REAL puts GPT-4 into a multirotor's control loop at 0.1–1 Hz, writing an additive LQR term and retuning Q/R ([REAL](https://arxiv.org/abs/2311.01403)).
- TypeFly plans in 1.0–5.7 s per task ([TypeFly](https://arxiv.org/html/2312.14950v1)).

**The "certified navigation model" language must inherit the parent's own caveat.** The Δ ↦ δ link is calibrated, not proved, so Paper V's "unconditional" safety is conditional on (C3) transfer of γ.

## The publishable theory is robust, planner-invariant safety of the true state

### Formal model

The proposal's Definition 1 is the right shape. The literature, however, fixes three details the proposal leaves open.

**The planner's output must enter only the cost, never the constraints.** In every predictive safety filter the desired input appears only in the objective. The feasible set, and hence the recursive-feasibility induction, is therefore independent of it. The induction rests on a terminal set that is control invariant, plus the shift argument: the tail of yesterday's plan plus one admissible terminal input is feasible today ([Wabersich et al., CSM preprint](https://par.nsf.gov/servlets/purl/10473415)).

**Safety must hold for the true state, not the estimate.** This requires tightening by Paper III's protection level ρ_i(t).

**The plant must carry an explicit mismatch disturbance.** There are two standard tightenings:
- Lipschitz-based (Limón et al.): ε_k = w̄ Σ_{j<k} L_d^j, which grows geometrically when L_d > 1.
- Contraction-based (Köhler et al.): ε_k = c·w̄(1 − λ_c^k)/(1 − λ_c), which stays bounded in the horizon.

([Köhler et al., arXiv:1910.12081](https://arxiv.org/pdf/1910.12081); [Limón et al.](https://doi.org/10.1109/CDC.2002.1185106))

For aircraft i the model is as follows. Write x_i = (p_i, v_i) for the state; z for the nominal state with nominal input v; and π_nom(x̂, a) for the tracking law that maps a high-level action a (waypoint, velocity setpoint, mode) to a nominal input.

```
Plant (true):     x_i⁺ = A x_i + B u_i + w_i,   ‖w_i‖∞ ≤ w̄            (calibrated mismatch)
Feedback:         u_i = v_i + K(x̂_i − z_i)                               (tube controller)
Estimate:         ‖p̂_i(t) − p_i(t)‖ ≤ ρ_i(t) = e^{L̂_loc T_c} γ_sup Δ_i(t)  (Paper III As. 1)
Tightening at k:  β_i,k = ρ_i(t) + L_ρ·kΔt + ε_k + b_tot(ε)
Filter:           min_{v_0..v_{Np−1}} ‖v_0 − π_nom(x̂_i, a_t^LLM)‖²
                  s.t. z_{k+1} = A z_k + B v_k,  z_0 = x̂_i(t)
                       p(z_k) ∈ Corridor_m ⊖ 𝔹(β_i,k),  v_k ∈ U ⊖ K·Z,  separation_ij ⊖ (β_i,k + β_j,k)
                       z_{Np} ∈ X_f(β)   (loiter set: brake-to-hover fits inside the tightened margin)
Infeasible or solver failure → execute the tail of the last feasible plan (latched certificate).
```

Discrete actions (task, mode) pass first through a *minimal-deviation* variant of Paper III's eligibility test. That variant is new code, because Paper III's lexicographic projection is not transparent. The continuous filter then acts on the result.

**The loiter terminal set gives an analytic invariant without a reachability toolbox.** An equilibrium is the trivial admissible choice of control-invariant terminal set ([Wabersich et al.](https://par.nsf.gov/servlets/purl/10473415)). For a double integrator, zero-velocity hold is invariant if the braking distance v²/(2u_max) plus the steady-state tube fits inside the tightened margin. The rest of the filter is a small convex QP. It decouples per aircraft unless separation constraints are active.

**The latched-tail fallback borrows Black-box Simplex's key idea.** That architecture keeps the last valid runtime certificate to fall back on, so the backup itself need not be verified ([Mehmood et al.](https://arxiv.org/abs/2102.12981v3); [Hobbs et al.](https://arxiv.org/abs/2110.03506)).

### Theorem 1: planner-invariant robust safety

**Assumptions.**
- (A1) Mismatch is bounded by w̄.
- (A2) Certificate soundness, with ρ_i growing at most L_ρ between jumps and jumps bounded by J̄ (with J̄ = 0 in the delay-adversary, re-anchoring regime).
- (A3) X_f is robust control invariant under the tube controller.
- (A4) The solver either returns a certified-feasible plan or flags failure. Feasibility is checked by an independent constraint evaluator, not trusted from the solver.
- (A5) The problem is feasible at t₀.

**Claim.** For **every** planner sequence {a_t^LLM}, every w with ‖w‖ ≤ w̄, and every sensing perturbation within the declared budget, the true position satisfies p_i(t) ∈ Corridor_m for all t. The planner sequence may be history-dependent and chosen by an adversary who knows the filter, the model and the solver.

**Proof strategy, in five steps.**
1. Universality: the feasible set does not contain a^LLM, so the shift argument quantifies over all sequences for free.
2. Robustness: the tube tightening ε_k absorbs mismatch.
3. Estimate-to-truth: the ρ term transfers safety from x̂ to x.
4. Time-varying constraints: the L_ρ·kΔt look-ahead absorbs predictable growth, which is Paper III's Thm 3 logic. Bounded jumps are absorbed by J̄.
5. Failure: the latched tail is feasible by induction, so solver failure never executes an uncertified action.

**This proof is more than "just MPC recursive feasibility", which answers the proposal's own Risk 1.** The constraint set is exogenous and time-varying, the guarantee is about a state the filter never observes, and the action space is hybrid.

**The paper must also state what happens outside the assumptions.** When a relay jump exceeds the margin, an unbounded J̄ breaks (A2). The theorem then becomes silent, exactly as the parent's certificate is outside (C1)–(C2), and the filter cannot repair it. The median two-hop jump of about 41.8 m alone exceeds every margin in {2, 5, 10, 20} m. The paper should say this in the theorem's scope paragraph, not in a limitations box.

**Lemma 1 (transparency) makes the benign-cost metric exact.** The filter returns a^LLM unchanged *if and only if* the nominal input for a^LLM is the first step of some feasible plan. Benign interventions therefore occur exactly when a benign proposal leaves the viability kernel of the tightened problem. The benign intervention rate then measures two things: the planner's unsafety, and the conservatism gap between the maximal invariant set and the tightened feasible set. That gap shrinks as w̄ → 0 and as N_p grows ([Wabersich et al.](https://par.nsf.gov/servlets/purl/10473415)).

### Proposition 2 should become liveness confinement plus a denial decomposition

Use the Alpern–Schneider decomposition:
- S is the set of constraint-satisfying traces. It is a safety property and closed.
- 𝓛 is the set of traces that eventually complete the mission. It is a liveness property and dense.

Theorem 1 confines every attacker to S. The attacker's best response is therefore a trace in S \ 𝓛 ([Alpern & Schneider](https://doi.org/10.1016/0020-0190(85)90056-0)).

**The decomposition the paper needs** is MDR = MDR_filter + MDR_envelope:
- MDR_filter is denial caused by interventions and fallbacks.
- MDR_envelope is denial from admissible but non-progressing proposals, where the filter never intervenes.

**Stealthy denial is a third dimension, not a third component.** It is any denial trace whose per-step anomaly signals stay below an operator's detection threshold. RL-Hammer shows such stealth is achievable for the language channel: with a stealth reward its injections reach 0% detection across four detectors while keeping 97% attack success ([RL-Hammer](https://arxiv.org/html/2510.04885v1)).

**This reformulation turns the proposal's weakest proposition into its most interesting one.** The filter does not reduce MDR_envelope at all. That component can only be reduced by a language-side defence or by a progress-preserving fallback. One option for the latter is a liveness budget: after k consecutive interventions or non-progress epochs, quarantine the language channel and hand control to a certified scripted mission planner. That would let the paper state a bounded mission-delay result instead of only reporting denial. Bounding the filter-induced component this way is a recommendation, not something any source has done.

**Filter-induced denial has a control-theoretic mechanism the paper should cite.** CBF-QP filters introduce asymptotically stable spurious equilibria on the boundary of the safe set, even for linear systems with one convex obstacle ([Reis et al.](https://arxiv.org/abs/2003.07819v3)). In multi-robot settings they deadlock at equilibria with active constraints ([Grover et al.](https://arxiv.org/pdf/1911.09146)). A boundary-riding attacker exploits exactly this.

### Proposition 3 should become a nestedness theorem plus a tested monotonicity

**Define a scalar tightening:** b_tot(ε) = e^{LT_c}δ_net(θ) + δ_adv(θ) + s*(ε), with p̄(s*) ≤ ε. This mirrors Paper IV's own design rule, "choose T_a such that δ_adv(T_a) ≤ m − e^{LT_c}δ_net − s*" ([Paper IV sec_discussion](file://paperIV_package/paperIV/manuscript/sec_discussion.tex)).

**What can be proved.**
- (a) **Nestedness.** For b' ≥ b, 𝒜_adm(x; b') ⊆ 𝒜_adm(x; b), and the filter's feasible region is nested likewise.
  - Deterministic terms enter as shifts, by Paper IV Prop. 2(e).
  - Stochastic terms are monotone under first-order stochastic dominance, by the proof of Paper IV's Thm 1.
- (b) **Pointwise monotonicity of the one-step intervention indicator.** At any fixed (x̂, a), intervention under b implies intervention under b'.

**What cannot be proved in general.** Pathwise monotonicity of the *rate* fails because closed-loop trajectories diverge as b changes. Monotonicity holds under a per-step evaluation model, where interventions are counted from a fixed state distribution. Otherwise it is an empirical hypothesis. It should be tested with an ordered-alternative trend test across the b_tot grid, with common random numbers.

**The paper must also say which attacker composes.** Only Paper IV's covert class does: attackers that stay silent (event U) and leave C2′ intact. A detection-indifferent spoofer is a different object. The relevant precedent is "stealthy deactivation of safety filters": false-data injection biases the observer estimate deeper into the safe set, so a CBF filter accepts unsafe inputs while the residual stays under the detector threshold ([Arnström & Teixeira](https://arxiv.org/abs/2403.17861)). Under such attacks O_ind fails, and Paper II's caveat applies in full.

### Discharging Paper II's obligations

The table below is the honest discharge of L_mon. It also shows where Paper V relocates, rather than closes, the gap.

| Obligation | Evidence kind | How Paper V discharges it | What remains open |
|---|---|---|---|
| O_mcov (monitor coverage) | proof | Theorem 1: the monitor is model-based, not learned | Depends on certificate soundness (A2), which rests on calibrated γ (C3), a ⟨pop_d, P⟩-type statement: the gap is relocated |
| O_lat (switching latency) | measured | Solver p99.9 latency against the control period; the latched tail covers overruns | Must be benchmarked: no QP latency exists in the repository |
| O_rec (verified recovery) | proof | Robust-invariant loiter terminal set plus the latched tail | RTL is not certified unless filtered |
| O_ind (monitor independence) | architectural | The filter reads the certified navigation state, never the LLM's text | Fails under the composed sensing attack (Prop. 3), so O_thr must restrict the attacker to Paper IV's covert class |

## Related work places Paper V at an empty intersection

**Safety-filter theory is mature and supplies Paper V's proof machinery.**
- Predictive safety filters give recursive feasibility for any desired input under a control-invariant terminal set ([Wabersich et al.](https://par.nsf.gov/servlets/purl/10473415)).
- Predictive CBFs add an always-feasible recovery mechanism ([Wabersich & Zeilinger, PCBF](https://arxiv.org/abs/2105.10241v3)).
- Hsu, Hu and Fisac unify HJ, CBF and PSF filters as "monitor plus intervention" ([Hsu et al.](https://arxiv.org/abs/2309.05837v1)).
- FaSTrack's guarantee holds for *any* planner trajectory via an offline tracking-error bound. It is the closest template when the planner emits references rather than inputs ([FaSTrack](https://doi.org/10.1109/CDC.2017.8263867)).

**Aviation RTA already standardises the architecture.**
- ASTM F3269-21 is the Simplex-based standard for run-time assurance of aircraft systems containing complex functions ([ASTM F3269-21](https://store.astm.org/f3269-21.html)).
- Hobbs et al. distinguish switching Simplex from optimisation-based ASIF filters ([Hobbs et al.](https://arxiv.org/abs/2110.03506)).

Paper V is an ASIF/PSF-type RTA with a Simplex-style latched fallback. It should say so in F3269 terms, because that is how airworthiness reviewers will read it.

**LLM-in-the-loop robotics treats the language model as error-prone, never adversarial.**
- SwarmGPT, the strongest peer-reviewed drone-fleet example, passes LLM trajectories through a minimal-correction filter at about 2.9 ms per drone for 10 drones ([SwarmGPT](https://www.dynsyslab.org/wp-content/papercite-data/pdf/schuck-ral25.pdf)).
- SAGE-LLM claims "provable safety certification for LLM outputs" for UAV decisions via a fuzzy CBF, but reports no adversarial evaluation ([SAGE-LLM](https://arxiv.org/abs/2602.23719)).
- SAFER's CBF constraints are parsed from LLM output, so its guarantee is conditional on the LLM ([SAFER](https://ar5iv.arxiv.org/html/2503.15707)).

**Attacks on embodied LLMs are strong and drone-relevant.**
- CHAI hijacks a simulated drone's emergency landing in up to 72.8% of trials and aerial tracking in up to 95.5% via printed signs. It evaluates no defence and calls for "provably robust defenses" ([CHAI](https://arxiv.org/html/2510.00181v2)).
- An LLM drone-control benchmark finds GPT-3.5 refuses harmful requests only 12.50% of the time. Even 13–34B models refuse only about 42% of unintentional hazards. Alignment cannot be the safety mechanism ([Tang et al.](https://arxiv.org/pdf/2411.02317v2)).

**The defence landscape divides cleanly, and Paper V sits on the system-level side.**
- *Model-level defences* (instruction hierarchy, SecAlign, detectors) keep falling to adaptive attacks. RL-Hammer reaches 98% ASR on GPT-4o and 72% on GPT-5 with instruction hierarchy ([RL-Hammer](https://arxiv.org/html/2510.04885v1)).
- *System-level defences* bound what a compromised model can do. CaMeL solves 77% of AgentDojo tasks with provable security against 84% undefended ([CaMeL](https://arxiv.org/abs/2503.18813)).

Paper V is the physical-layer member of the second family. CaMeL's 7-point utility cost is the right precedent for reporting benign intervention cost.

| Work | Layer | Guarantee independent of LLM | Adaptive evaluation | UAV |
|---|---|---|---|---|
| RoboGuard ([arXiv](https://arxiv.org/pdf/2503.07885)) | LTL plus root-of-trust LLM | Partial (LLM-written specs) | Yes: adaptive RoboPAIR ASR 2.5–5.2% | No |
| Hafez et al. reachability ([arXiv](https://arxiv.org/html/2503.03911v1)) | Physical, receding horizon | Yes | No | No |
| SanDRA ([arXiv](https://www.arxiv.org/abs/2510.06717)) | Reachability plus temporal logic | Yes | No | No (AV) |
| SAFER ([ar5iv](https://ar5iv.arxiv.org/html/2503.15707)) | LLM judge plus LLM-parameterised CBF | No | No | No |
| SAGE-LLM ([arXiv](https://arxiv.org/abs/2602.23719)) | Fuzzy CBF | Claimed | Not reported | Yes |
| Secure safety filter ([arXiv](https://arxiv.org/abs/2505.06845)) | Robust CBF over plausible states under sensor attack | Not LLM-based | Sensor attacks, not adaptive LLM | Yes (PX4, X500) |
| **Paper V** | Predictive filter at control rate | **Yes** | **Yes** | **Yes** |

**The novelty claim must survive the reviewers who wrote the adaptive-evaluation canon.** Nasr, Carlini, Tramèr and colleagues broke 12 recent jailbreak and prompt-injection defences, most at above 90% ASR, many of which had originally reported near-zero ASR. Their recommendations are explicit: assume the attacker knows the defence, use compute-heavy optimisation, and diversify gradient, RL, search and human attacks ([The Attacker Moves Second](https://arxiv.org/abs/2510.09023)). Zhan et al. bypassed all eight indirect-injection defences they tested at above 50% ASR ([Zhan et al.](https://arxiv.org/abs/2503.00061)).

Paper V has a structural advantage these defences lacked: its safety claim is a theorem over all action sequences, so no attack on the language model can break it. The flip side is that any reported *denial* number is only as strong as the attacker that produced it. Hence the oracle level in the protocol below.

**Three claims appear unoccupied, each as an "I found no prior work" statement to recheck before submission:**
- a dynamics-level filter universally quantified over an adversarial LLM planner;
- a physical mission-denial attack induced through a safety mechanism;
- a UAV harness combining dynamics, an LLM planner and adaptive injection.

These are gaps found in the searches, not exhaustively verified absences. A December 2025 survey of LLM-robot security independently lists two related open gaps: symbolic specifications "do not cover continuous dynamics", and CBFs are decoupled from LLM reasoning ([Huang et al. survey](https://arxiv.org/pdf/2601.02377)).

## An eight-level attacker ladder, paired metrics and rule-of-three statistics

### The attacker ladder

The ladder below extends the protocol synthesised from Carlini et al., Tramèr et al. and Nasr et al. ([Carlini et al. 2019](https://arxiv.org/abs/1902.06705); [Tramèr et al. 2020](https://arxiv.org/abs/2002.08347)). Each level is a superset of the previous one. Every level reports violations and denial against four goals:
- a safety violation;
- maximal fallback;
- stealthy denial;
- boundary riding.

| Level | Capability | Construction (reuse) |
|---|---|---|
| A0 | None (benign) | Scripted mission prompts |
| A1 | Static injection corpus | AgentDojo "important message", InjecAgent base and enhanced, HouYi templates, translated to mission text ([AgentDojo](https://arxiv.org/abs/2406.13352); [InjecAgent](https://arxiv.org/html/2403.02691v3)) |
| A2 | Black-box, filter-unaware search | PAIR/TAP-style LLM attacker ([PAIR](https://arxiv.org/abs/2310.08419)) |
| A3 | Black-box, filter-aware: knows the constraint set, observes the intervene bit | CMA-ES/TPE over template parameters, reusing Paper IV's `r1_attackers.py` harness and seed discipline ([r1_attackers.py](file://paperIV/experiments/r1_attackers.py)) |
| A4 | White-box open-weights planner plus full filter knowledge | GCG/universal-injection gradients; RL-Hammer-style trained attacker with a stealth reward ([RL-Hammer](https://arxiv.org/html/2510.04885v1)) |
| A5 | Human red team | Required by Nasr et al. ([arXiv](https://arxiv.org/abs/2510.09023)) |
| A6 | **Oracle action-space adversary** (no LLM): chooses a^LLM directly | Boundary-pressing and denial-maximising action search. Free to run, and an upper envelope on A1–A5 |
| A7 | A6 or A3 composed with Paper IV's covert sensing attacker | Paper IV CEM disguise families (step, ramp, fault/GNSS/weather mimic) under the anchor gate and C2′ |

**A6 is the methodological contribution reviewers will remember.** Theorem 1 covers every action sequence, so A6's zero violations are the strongest possible test of RQ1. A6 does not need an LLM, so it can run 10⁶–10⁷ aircraft-steps cheaply. For comparison, Paper IV's CPU-only pilot ran 1,839,600 missions in 1,637 s ([run_meta.json](file://paperIV/results/run_meta.json)).

**A6 also turns "we cannot prove we found the strongest attack" into a measured quantity.** The gap between A6's denial and the best language-mediated attack (A4/A5) is the **LLM-mediation slack**: how much of the theoretical denial an attacker can actually realise through text.

**Required sanity checks:**
- With the filter off, SVR under A1–A3 must be high. Otherwise the attacks are too weak to say anything.
- An unbounded A6 must reach near-100% denial.
- Attack success must be non-decreasing in budget.
- Results must report the worst case over attackers per mission, never an average over attacks.

### Metrics

The metrics map onto AgentDojo's three-way split of benign utility, utility under attack and targeted ASR ([AgentDojo](https://arxiv.org/abs/2406.13352)). They also carry over Paper III's per-step counting convention.

| Metric | Definition | Role |
|---|---|---|
| SVR | True-state constraint violations (corridor, separation) per aircraft-step, never per episode | RQ1. Report as 0/n with a 95% Clopper–Pearson upper bound |
| MDR, split into MDR_filter and MDR_envelope | Missions not completed within (1+κ_sched)T with no violation, split by cause | RQ2 and RQ3. The decomposition answers Prop. 2 |
| FR | Fraction of steps executing the latched fallback | Filter-induced denial mechanism |
| IR and BIR | Fraction of steps with ‖a* − a^LLM‖ > η, under attack (IR) and without attack (BIR) | RQ4 conservatism |
| BMS, time overhead | Benign mission success; extra mission time | RQ4. CaMeL-style utility cost |
| Coverage-ratio analogue | Progressing holders over feasible holders | Separates "safe because loitering" from "safe and progressing" (Paper III) |
| Stealth | Detection rate of denial by an operator-side monitor | Goal (iii) |
| Latency p50/p99/p99.9 | Filter solve time against the control period | O_lat |
| LLM-mediation slack | MDR(A6) − max MDR(A1–A5) | Attack-completeness proxy |

Temporal MCR should use the parent's conjunctive definition, MCR = Pr[sup‖x − x_nom‖ ≤ m ∧ t_arr ≤ (1+κ)T] ([Parent p.3](file:///root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/fe231096-paperD_v7b.pdf#page=3)). That ties Paper V's liveness metric to the programme's headline quantity.

### Statistical design

The statistical design copies Paper IV's discipline ([Paper IV runbook, project doc](file://paperIV_package/paperIV/RUNBOOK_CLAUDE_CODE.md)).

**Seed blocks by role:**
- 1xxx: calibrate w̄ and detector thresholds.
- 2xxx: attacker optimisation.
- 3xxx: held-out attackers.
- 4xxx: held-out evaluation.
- 5xxx: negative controls.
- New 6xxx/7xxx blocks: LLM sampling seeds and Paper V attacker search, recorded in `run_meta.json`.

**Comparisons and corrections:**
- Common random numbers pair filter-on and filter-off and all b_tot levels.
- Holm correction across operating points.
- "Never widen a constant after looking at held-out data."

**Violation sample size.** By the rule of three, claiming a violation rate ≤ 10⁻⁶ at 95% needs about 3×10⁶ violation-free aircraft-steps. That is affordable only with mock and A6 planners, as Paper III's 2.9×10⁷ agent-epochs show. LLM campaigns support coarser bounds: 10⁴ aircraft-steps give ≤ 3×10⁻⁴. The paper should present both.

**Denial uncertainty.** Use stratified bootstrap CIs over missions and IQM across seeds ([Paper III](file://paperIII_package/paperIII/manuscript/main.tex)). With 200 missions per cell, a binomial MDR has a 95% half-width of at most about ±0.07, enough to separate attacker levels that differ by 0.15.

**LLM nondeterminism.** Use temperature 0 where supported, three repeated samples per mission on a subset, and report within-mission variance.

**Model mismatch.** Calibrate w̄ as the block-1xxx supremum of one-step prediction error of the nominal model against the true plant, inflated by a stated factor. Check exceedances on held-out blocks. Any exceedance is reported and treated as an RQ1 bug, as the proposal already promises.

### Baselines and ablations

**Baselines** should span the defence families:
- no filter;
- prompt-level hardening (spotlighting, sandwich or instruction hierarchy);
- an LLM-judge guard in the SAFER style;
- a rule-based plan review (the platform's existing regex `review_mission_plan`);
- Simplex accept/reject with loiter and no projection;
- a myopic one-step CBF-QP;
- Paper III's fixed design margin, which in Paper III both under-covered (0.163) and still violated (8.03%).

The one-step CBF-QP matters because MPC-CBF achieves safety with shorter horizons than distance-constrained MPC and is less myopic than a one-step QP ([Zeng et al.](https://doi.org/10.23919/ACC50511.2021.9483029)). A stacked semantic-plus-physical configuration should also be run. RoboGuard itself names "LTL may not capture safety tied to system dynamics" as a limitation, so the two layers are complementary rather than competing.

**Ablations** should vary:
- horizon N_p;
- terminal set: loiter, filtered RTL, or none;
- tightening: none, Limón, or Köhler;
- the L_ρ look-ahead (on/off);
- hard versus soft constraints;
- latching;
- L ∈ {1.01, 1.181};
- γ ∈ {1.365, 1.625, 15};
- m ∈ {2, 5, 10, 20};
- planner cadence;
- lexicographic versus minimal-deviation discrete projection;
- separation constraints (on/off).

## A new paperV tree on dev/whelan-uavcas-ingest reuses six components and builds eleven

### Branch and folder layout

Work belongs on a branch cut from `dev/whelan-uavcas-ingest`, not the clone's `claude/whelan-uavcas-ingest-u00isn`. PENDING_ON_DATA §0 asks for the latter's manual deletion, and the Paper IV runbook names the `dev/` branch as its long-lived equivalent ([PENDING_ON_DATA.md](file://PENDING_ON_DATA.md)).

The folder must sit inside the same repository tree. Paper III's `certificate.py` resolves constants from the parent's `results/` directory (`hop_ledger.csv`, `gamma_campaign_samples.csv`, `local_lipschitz.csv`), so the imports break elsewhere ([certificate.py](file://paperIII/experiments/certcmdp/certificate.py)).

The house conventions carry over unchanged:
- `paperV/{experiments, results, manuscript}`;
- provenance-tagged constants;
- CSV results;
- `make_numbers.py` → `numbers.tex`;
- "never type a number into main.tex";
- commits formatted `paperV: R<n> <result>`.

### Reused versus newly built

| Component | Status | Source |
|---|---|---|
| γ, L̂_loc, T_c, slack, margins | **Reuse** | Paper IV `constants.py` (GAMMA_SUP 1.625, L_LOC 1.1814, SLACK_S 4.84, CORRIDOR_M) |
| ρ_i(t) process with measured residual pools | **Reuse** | Paper III `CertificateProcess.rho()/step()`, 65.8 µs per step at N = 12 |
| Discrete eligibility with look-ahead and hysteresis | **Reuse** | Paper III `combinatorics.eligibility()` |
| δ_net, p̄, union and RA bounds, committed marginals and δ_adv | **Reuse** | Paper IV `run_pilot.net_tube/pbar`, `depbounds.py`, `e3_marginals.npz`, `e4_delta_adv.csv` (δ_adv = 4.371 m) |
| Mismatch disturbance source (drag, Dryden wind) | **Reuse** | Paper IV `sim.py` |
| Statistics helpers (CP, Holm, bootstrap, IQM) | **Reuse** | Paper III `e6_aggregate.py`, Paper IV `run_pilot.py` |
| Staleness tube | **Reuse with a fix** | `engine.certify_staleness`, passing L = 1.1814 explicitly |
| Seeded controllable fleet plant | **New** | `plant.py`: double integrator, waypoint/velocity/mode actions, `UAVState`-compatible fields |
| Admissible-set constructor | **New** | `admissible.py`: corridor ⊖ β_i,k, loiter terminal set |
| Predictive safety filter | **New** | `filter.py`: QP via cvxpy+OSQP/Clarabel with a SciPy fallback; latched tail; status log |
| Minimal-deviation discrete projection | **New** | Variant of `lexicographic_projection` that is transparent to feasible proposals |
| b_tot(ε) wrapper | **New** | `budget.py` over Paper IV helpers (there is no `delta_tot()` today) |
| LLM agent | **New** | `agent.py`: delimited channels, JSON-schema actions, sha256 cache, usage logging, retries; wraps but does not reuse `llm.complete()` |
| Mock and oracle planners | **New** | `ScriptedAgent`, `OracleAdversarialPlanner` (A6) |
| Injection attacks and adaptive loop | **New** | `attacks.py`, `adaptive.py` (A1–A4, A7) |
| Campaign runner and logs | **New** | `episode.py`, `run_campaign.py`: per-step JSONL logs feeding RQ CSVs |
| Platform page | **New** | `safety_filter.py` backend; `PaperVScreen.js`; `"V": "paperV"` in `PAPERS`; optional Agent Studio runner |
| Manuscript kit | **New / fix** | IEEEtran two-column; Paper IV's colour-blind palette and `figure*` idiom; repository preamble and bib |

Sources for the table: [codebase: engine.py](file://certificates/engine.py); [Paper IV run_pilot.py](file://paperIV/experiments/run_pilot.py); [Paper IV e4_delta_adv.csv](file://paperIV/results/e4_delta_adv.csv); [papers.py](file://platform/backend/app/papers.py).

**`uav.py` stays where it is, because it cannot host the experiment.** It has no action channel, and its `random.Random(int(time.time()*1000) …)` makes runs irreproducible. Keeping `UAVState` field names and the snapshot schema lets the platform page render Paper V's plant anyway. The page should default to replaying committed results plus a mock agent, with an optional user-supplied API key. The platform's LLM rate limit is 30 calls per hour per session, so live steps would exhaust it quickly ([sessions.py](file://platform/backend/app/sessions.py)). The page should also carry the `illustrative` badge for dynamics. The Safety Filter page is already listed as "planned, not built" in Documentation_v2 ([Documentation_v2.tex](file://docs/Documentation_v2.tex)).

### Mission scenario

The scenario should keep T = 70 s (the parent's reference profile) and N = 12 aircraft, with waypoint and task missions so that liveness is measurable.

**Cruise speed and γ.** The plant cruises at 12–15 m/s while γ was measured in hover. Every headline therefore needs a kinematic-γ (15 m/s) companion row.

**SITL cross-check.** An optional PX4 SITL check reuses the Paper III R4/Paper I E3 toolchain: PX4-Autopilot v1.14.3, MAVSDK and the `GPS_INPUT` offset ramp ([Paper III runbook R4](file://paperIII_package/paperIII/RUNBOOK_CLAUDE_CODE.md)). It turns "simulation cannot claim hardware safety" from a disclaimer into a measured agreement statistic. Paper IV's runbook uses Kendall τ ≥ 0.6 as its acceptance threshold for that statistic.

## Only the language-model campaign costs real money

### The offline pipeline runs in the existing container

The entire offline pipeline fits the existing 2-vCPU, 7 GB, GPU-less container:
- certificate calls cost about 2.3 µs;
- Paper III's projection costs about 46 µs at N = 12;
- Paper IV's pilot ran 1,839,600 missions in 1,637 s.

A per-aircraft QP with N_p of 10–20 is expected in the millisecond range. No repository benchmark confirms this, so it must be measured and reported as O_lat ([codebase map, run_meta.json](file://paperIV/results/run_meta.json)).

**No QP solver is installed.** NumPy and SciPy are available, but cvxpy, OSQP and Clarabel are not. The filter therefore needs a SciPy fallback (SLSQP, or a closed-form box/half-plane projection) so RQ1 can run before network installs are allowed.

### LLM campaign cost

Cost is driven by call volume. The volume follows from a fleet-level planner call every 5 s of a 70 s mission: **14 calls per episode**. One call per aircraft would be 12× that.

A defensible core campaign uses:
- 2 frontier models;
- 4 attacker levels (A0–A3);
- 4 b_tot levels;
- 100 missions per cell.

That is 3,200 filtered episodes. Adding 400 filter-off sanity episodes and 800 benign RQ4 episodes gives about **4,400 episodes, or about 62,000 planner calls**. At an assumed 2,500 input and 300 output tokens per call, that is roughly **155M input and 19M output tokens**, before prompt caching of the fixed system prompt.

Dollar cost is 155M × p_in + 19M × p_out at the providers' current prices. Those prices are not recorded anywhere in the repository and must be looked up when the model IDs are pinned. A2's attacker LLM roughly doubles call volume for its cells.

### Adaptive search must run on a surrogate

The binding constraint is adaptive search. Paper IV's CEM budget (12 candidates × 25 generations × 48 missions = 14,400 missions per attacker cell) would cost about 200,000 planner calls per cell against a frontier model. That is infeasible.

The protocol should therefore:
- search against a mock surrogate or a local open-weights planner, which needs a GPU server the container lacks;
- transfer only the top-k injections (e.g., 20 injections × 50 missions) to frontier models;
- cache every completion by sha256(provider, model, system, prompt) for offline replay.

RL-Hammer-style trained attackers (A4) are GPU-bound and should be scoped as optional, with a fixed GPU-hour budget declared in advance. Without A4/A5 the paper must say its denial numbers are lower bounds on attacker power, and lean on A6 for the upper envelope.

## Conclusion and phased work plan

The useful shift in understanding is that Paper V's contribution is not the safety theorem. It is the *conversion ledger*: what an attacker who can no longer crash the aircraft can still take away, and through which channel.

The filter provably removes envelope violations and leaves two things behind:
- filter-induced denial, which control theory explains as boundary equilibria and deadlock;
- in-envelope denial, which no physical filter can touch.

A paper that measures both, bounds the first with an oracle adversary, and proposes a liveness budget for the second is genuinely new at SaTML. A paper that claims "the attacker's power is bounded by the fallback rate" is wrong and will be caught. The composition result should likewise be sold as what it is: a nestedness theorem plus an empirical trend test, valid for covert sensing attackers only. In Paper II's terms, that is the boundary where runtime assurance relocates rather than closes the assurance gap.

| Phase (weeks) | Work | Exit gate |
|---|---|---|
| 0 (1–2) | Fix items 1–26: preamble and bib, κ_sched, L = 1.1814, attack-class count, notation table. Cut the branch from `dev/whelan-uavcas-ingest`. Confirm the SaTML/USENIX dates | Proposal compiles; every constant has a provenance tag |
| 1 (2–6) | Theory: Theorem 1 with mismatch, ρ_i(t), jumps and the latched tail; transparency lemma; Prop. 2 recast as liveness confinement with the denial decomposition; Prop. 3 recast as nestedness; L_mon obligation table | Proofs written. Scope paragraph states where the theorem goes silent |
| 2 (3–8) | Offline core: constants, plant, admissible set, filter (SciPy, then OSQP), budget, statistics, mock and A6 planners | RQ1: 0 violations over ≥3×10⁶ aircraft-steps (CP ≤ 10⁻⁶); latency p99.9 under the control period; w̄ held-out check passes |
| 3 (7–11) | Agent layer (JSON actions, cache, usage); A1–A3 on a cheap or open model; baselines | Filter-off sanity shows high SVR; denial curves non-decreasing in budget |
| 4 (10–14) | Frontier-model campaign (~62k calls); RQ2–RQ4; A7 composition sweep over b_tot; ablations | Trend test on MDR vs b_tot; all cells with CIs |
| 5 (13–16) | Optional: A4 GPU attacker, A5 human red team, PX4 SITL cross-check, liveness-budget mitigation | Kendall τ ≥ 0.6 SITL agreement, or "not varied" stated honestly |
| 6 (16–20) | Platform page; `numbers.tex` and figures; ethics and disclosure following Paper IV; anonymised artifact | Submission-ready package |

**Decision gate after phase 2.** If A6 forces near-100% denial at trivial budget, invoke the proposal's own fallback framing: safety filtering is "necessary but not sufficient". Promote the liveness-budget mitigation from optional to a core contribution, so the paper still offers a positive defensive result.
