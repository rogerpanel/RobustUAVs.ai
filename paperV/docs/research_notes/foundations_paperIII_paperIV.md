# Foundations from Papers III and IV for Paper V (predictive safety filter for LLM UAV agents)

Source conventions used below (all local, extracted read-only; no package code was executed):
- `P3/` = `paperIII_package/paperIII/`
- `P4/` = `paperIV_package/paperIV/`
- `PV` = `/root/.claude/uploads/86d21519-d84c-520e-85e5-f8721a022b2a/ac54f2a6-PaperV_safety_filter_llm_agent.tex`
- Project docs `PaperIII/RUNBOOK_CLAUDE_CODE.md` and `PaperIV/RUNBOOK_CLAUDE_CODE.md` (read via Projects `project_read`) match the copies inside each zip (`P3/RUNBOOK_CLAUDE_CODE.md`, `P4/RUNBOOK_CLAUDE_CODE.md`).
- Line numbers: `file:Lx-Ly`. Numeric values come from the generated macro files (`P3/manuscript/numbers.tex`, `P4/manuscript/numbers.tex`). Each value is given with the macro name that holds it.

---

## Q1. Paper III: what is the projection/feasibility layer exactly? Is it a QP? What does it guarantee? How was it evaluated, and with which numbers?

### Takeaway
Paper III's layer Π is **not a QP**. It is a discrete **maximum-weight bipartite matching**: the Hungarian algorithm via `scipy.optimize.linear_sum_assignment`, plus an O(N log N + M log M) greedy nested variant. It works over a scalar-threshold eligibility graph ρ_i(t) ≤ α_j. Its guarantees are exact (lexicographic optimality, so there is no "optimality gap"): (i) every executed assignment is feasible at every epoch for any policy; (ii) it covers the maximum M−d tasks, then maximises value, then maximises agreement with the proposal; (iii) it is an MDP with unbiased policy gradient, but only under a Markov threat model. Closeness to the proposal is only the **third** lexicographic objective. Paper V's filter, argmin‖a − a^LLM‖, makes closeness the *only* objective, so it is a different object and must say so.

### Cited Findings

**Problem setting and notation (keep verbatim)**
- Certificate: `‖p̂_i(t) − p_i(t)‖ ≤ ρ_i(t) ≔ e^{LT} γ_sup Δ_i(t)` (eq. `eq:rho`). Δ_i(t) is the staleness, "the age of the newest trustworthy fix". It grows at 1 s/s under jamming and jumps by the hidden per-hop residual under relay delay — [P3/manuscript/main.tex:204-216](P3/manuscript/main.tex)
- `L_ρ ≔ e^{LT}γ_sup = \nKappa = 5.30 m/s`; `γ_sup = 1.625 m/s` (674 samples); `L = 1.181`, T = 1 s; `e^{LT} = 3.26` (`\nExpl`); benign floor `ρ_0 = L_ρ·0.178 ≈ 0.94 m`; median two-hop jump ≈ 41.8 m (`\nJumpMed`); hidden residual median/max 3.94/4.84 s over 15,392 hops (1,346 undetected, 10,621 benign) — [P3/manuscript/main.tex:218-228](P3/manuscript/main.tex); [P3/manuscript/numbers.tex:45,51,71,78,80,133,146-148,171,181](P3/manuscript/numbers.tex); [P3/results/constants_paperIII.csv](P3/results/constants_paperIII.csv), where `kappa_m_per_s = 5.29577` (derived) and `rho_jump_max_H2_m = 51.2948`.
- Assumption 1 (Certificate soundness, from parentpaper): "Whenever ρ_i(t) is reported, ‖p̂_i(t)−p_i(t)‖≤ρ_i(t). This work consumes ρ_i(·) and makes no assumption about how it is computed. We model ρ_i(·) as an arbitrary nonnegative, bounded càdlàg process … chosen by an adversary: a jammer is not a distribution. Only Thm. proj(iii) and the learning study additionally assume a Markov threat model." — [P3/manuscript/main.tex:240-247](P3/manuscript/main.tex)
- Fleet CMDP. Notation: fleet 𝒩={1..N}, tasks 𝒯={1..M} with alert limit α_j and value v_j>0, epochs t_k = kΔt. An assignment σ: 𝒩→𝒯∪{∅} is injective on 𝒯. Reward is certified coverage `r_cert(t)=Σ_j v_j 1[holder of j on site and ρ_{σ^{-1}(j)}(t) ≤ α_j]/Σ_j v_j` — [P3/manuscript/main.tex:250-257](P3/manuscript/main.tex)
- Pointwise constraint: `(C) ρ_i(t_k) ≤ α_{σ_{t_k}(i)} for every i with σ_{t_k}(i)≠∅, every epoch k, every episode` (eq. `eq:constraint`). Eligibility graph G(t): i∼j iff ρ_i(t) ≤ α_j. Count profile `n_k(t) ≔ |{i: ρ_i(t) ≤ α_(k)}|` with α sorted ascending. G(t) is a difference (chain) graph — [P3/manuscript/main.tex:259-268](P3/manuscript/main.tex)
- Problem statement P1–P4. P1 requires that "(C) holds at every epoch of training and deployment, for any policy parameters, without collapsing coverage. Leaving every aircraft idle satisfies (C) trivially, so coverage must be part of the guarantee". Research questions RQ1–RQ6 — [P3/manuscript/main.tex:288-313](P3/manuscript/main.tex)

**The projection operator (Algorithm 1, `alg:proj`)**
- Inputs: proposal `a∈(𝒯∪{∅})^N`, ρ, α, v, previous assignment σ^-, band η∈[0,1), h≥0, look-aheads ℓ_acq, ℓ_keep ≥ 0.
- Step 1: `E_ij ← [ρ_i+ℓ_acq ≤ (1−η)α_j − h]` for j≠σ^-(i), and `E_{iσ^-(i)} ← [ρ_i+ℓ_keep ≤ α_{σ^-(i)}]` (acquire/keep).
- Step 2: `W_ij ← B + c_v v_j + 1[a_i=j]` on E, with `c_v=(N+1)/min Δv` and `B > M(c_v max v + 1)`.
- Step 3: `σ ← maximum-weight matching of (E,W)` (Hungarian; greedy nested variant per Lemma ore).
- Step 4: return σ. σ is executed, and the policy is trained on a ("safeguard-in-environment", SE, after markgraf2025).
- Source: [P3/manuscript/main.tex:376-393](P3/manuscript/main.tex)
- Theorem 1 (Certified projection, `thm:proj`), with η=h=ℓ_acq=ℓ_keep=0, "for every policy π_θ, every parameter value θ and every certificate trajectory permitted by As. sound":
  - (i) the executed assignment "satisfies (C) at every epoch of every episode, in training and in deployment";
  - (ii) it "assigns exactly M−d(t_k) tasks, the maximum. Among maximum assignments it maximises assigned value … among those it maximises agreement with the proposal a_{t_k}";
  - (iii) "if, in addition, the threat process is Markov in a state s that includes σ^-, the process seen by the policy is a Markov decision process … with kernel P_Π(s'|s,a)=P(s'|s,Π(a;s)) … The likelihood-ratio policy gradient … is therefore unbiased … Differentiating through Π instead gives zero gradient almost everywhere, because Π is piecewise constant in a";
  - "For the coverage-only objective, the greedy nested variant … achieves (i) and the cardinality part of (ii) in O(N log N+M log M)".
  - Source: [P3/manuscript/main.tex:395-416](P3/manuscript/main.tex)
- The paper's own caveats on Thm 1:
  - Part (i) alone is easy: per-agent masking also achieves it, because the constraint is separable. It is "the familiar shield guarantee, transposed to a certificate-driven set".
  - "under As. sound alone, the projected process is a game against the jammer rather than an MDP, and (i)–(ii) still hold while (iii) does not".
  - A deviation penalty λ_dev is added on the fraction of overridden proposals.
  - Source: [P3/manuscript/main.tex:418-429](P3/manuscript/main.tex)
- Proof of (ii): weight scaling plus transversal-matroid basis exchange — [P3/manuscript/main.tex:970-993](P3/manuscript/main.tex)

**Exact monitors (usable as conservatism metrics)**
- Lemma 1 (Ore on nested graphs): max coverage = M − d with `d = max_{1≤k≤M}(k − n_k)^+` (eq. `eq:deficiency`), computable in O(N log N + M log M) — [P3/manuscript/main.tex:326-336](P3/manuscript/main.tex)
- Lemma 2 (coverage margin, b-extended Hall): full coverage survives the collapse of any b aircraft iff n_k ≥ k+b ∀k; `μ = min_k(n_k − k)` — [P3/manuscript/main.tex:338-343](P3/manuscript/main.tex)
- Prop. 1 (optimal collapse adversary): `d_b = max_k(k−(n_k−b)^+)^+`, attained by collapsing the b smallest-ρ aircraft — [P3/manuscript/main.tex:349-354](P3/manuscript/main.tex)
- Prop. 2 (graded degradation, exact worst case): any b aircraft have ρ raised by s≥0 ("for example by s/L_ρ seconds of dead reckoning"). With `n^{(s)}_k=|{i:ρ_i+s≤α_(k)}|`, coverage is at least `M − max_k(k − max{n_k−b, n^{(s)}_k})^+` (eq. `eq:graded`), and an adversary attains it. **This is the closest existing monotone-degradation result for Paper V Prop. 3**: raising every certificate by s shrinks every eligibility set, and n^{(s)}_k is non-increasing in s — [P3/manuscript/main.tex:356-367](P3/manuscript/main.tex)
- Thm 2 (Hysteresis): forced releases of aircraft i on [0,τ] number at most `1+TV^+_i[0,τ]/(ηα_(1)+h)`. If ℓ_keep ≤ ℓ_acq+h, coverage is at least M−d(ρ̃) with ρ̃_i=(ρ_i+h+ℓ_acq)/(1−η) — [P3/manuscript/main.tex:439-446](P3/manuscript/main.tex)
- Thm 3 (Predictive feasibility and the allocator rate). Assume every ρ_i grows at rate at most L_ρ between upward jumps. If ℓ_keep ≥ L_ρΔt and ℓ_acq ≥ L_ρH with H ≥ Δt, then:
  - (i) a holder can be exposed only if its certificate jumps;
  - (ii) a newly acquired task stays feasible for at least H unless a jump occurs;
  - an aircraft can hold α only if `Δt ≤ (α−ρ)/L_ρ`.
  - With the measured constants: Δt ≤ (2−0.94)/5.30 = 0.200 s, i.e. **5.01 Hz** (`\nRateMin`, `\nDtMax`). "Jumps cannot be predicted from a rate bound".
  - **This is a horizon-H recursive-feasibility-like statement; Paper V's MPC horizon H can cite it.**
  - Source: [P3/manuscript/main.tex:448-470](P3/manuscript/main.tex)
- Prop. 4 (misreported certificates): with f misreporters, the deficiency error is ≤ f, and every violation of (C) under Π is committed by a misreporter — [P3/manuscript/main.tex:472-482](P3/manuscript/main.tex)
- Prop. 5 (population lift, obligations O1 independence and O2 identical law q): `P(d=0)=P(Σ_{ℓ'≤ℓ}C_{ℓ'} ≥ m_ℓ ∀ℓ)`, C~Multinomial(N,q), computed by DP in O(cN²) — [P3/manuscript/main.tex:493-511](P3/manuscript/main.tex)
- Remark 1 (where the closed forms stop): with vector certificates, eligibility becomes a dominance order. Matching stays polynomial, but the closed forms are lost and robust assignment becomes hard to approximate. **Relevant for Paper V**: a continuous MPC admissible set is not scalar-nested, so none of Paper III's closed forms transfer automatically — [P3/manuscript/main.tex:521-529](P3/manuscript/main.tex)

**Experimental setup**
- CertSwarm: B fleets, N=12, M=8, 1×1 km arena, 15 m/s, on-site radius 30 m, 2 spatial jammers (radius 200 m), Δt=0.5 s, 150 s missions, α∈{2,5,10,20} m with values {4,3,2,1} — [P3/manuscript/main.tex:548-560](P3/manuscript/main.tex); [P3/experiments/certcmdp/env.py:28-44](P3/experiments/certcmdp/env.py)
- Threat process rates are assumptions (`ThreatProfile`): jam_rate 0.010/s (mean 6 s), relay_rate 0.010/s (mean 10 s, H=2 hops), fault_rate 0.002/s (mean 4 s), reanchor 2 s, stale_cap = 2·S_SLACK = 10 s — [P3/experiments/certcmdp/certificate.py:80-95](P3/experiments/certcmdp/certificate.py)
- Learning: MAPPO-style PPO with a shared actor and centralised critic. 16 parallel fleets, rollouts of 150 epochs, 200 updates (480k fleet-epochs, 5.8×10⁶ agent-epochs per run), 5 seeds. Hyperparameters: clip 0.2, γ=0.995, GAE 0.95, Adam 3e-4, entropy 0.003, 2×128 tanh, keep logit +3, λ_dev=0.05, Lagrangian dual step 1.0 and limit 0.005. About 5 min per run on 1 CPU core — [P3/manuscript/main.tex:562-567,1057-1065](P3/manuscript/main.tex)
- Methods:
  - Ours (Π in env);
  - masking (first-claimant conflicts);
  - PPO-Lagrangian;
  - jamming-blind;
  - every non-projected policy also evaluated "+ projection at deployment";
  - non-learned references: keep-or-nearest+Π, tightest-fit greedy, fixed design margin ρ_0+L_ρ·1 s, no certificate.
  - Source: [P3/manuscript/main.tex:569-592](P3/manuscript/main.tex)
- Metrics:
  - r_cert;
  - **coverage ratio** = feasible holders / (M−d(t)), which "separates 'safe because idle' from 'safe and maximal'" (**direct analogue for Paper V's liveness/denial metric**);
  - violations per agent-epoch, counted per step and never averaged per episode;
  - inter-epoch exposure;
  - reassignments.
  - Statistics: IQM with 95% stratified-bootstrap CIs (rliable/agarwal2021), and the Clopper–Pearson (CP) one-sided bound when zero violations are observed (≈3/n, "rule of three").
  - Evaluation: 3 held-out seeds × 16 fleets per training seed.
  - Source: [P3/manuscript/main.tex:594-606,513-519](P3/manuscript/main.tex)

**Headline numbers**
- Oracle verification: 83,872 comparisons over 9 checks on 10,000 instances, 0 disagreements — [P3/manuscript/numbers.tex:182-185](P3/manuscript/numbers.tex); [P3/results/e1_verify.csv](P3/results/e1_verify.csv)
- RQ1 (training violations):
  - Π: **0 over 2.9×10⁷ agent-epochs**, CP ≤ 1.0×10⁻⁷;
  - PPO-Lagrangian: 3,903,179 (13.55%);
  - jamming-blind: 4,744,505 (16.47%);
  - masking: 0.
  - Source: [P3/manuscript/sec_results_marl.tex:5-17](P3/manuscript/sec_results_marl.tex); [P3/manuscript/numbers.tex:89-90,13,12,161-162](P3/manuscript/numbers.tex)
- RQ3 (Table `tab:main`), as r_cert IQM [CI] / coverage ratio / eval violations:

  | Method | r_cert IQM [CI] | Cov. ratio | Eval viol. |
  |---|---|---|---|
  | Ours | 0.496 [0.473, 0.525] | 1.00 | 0 (≤3.5×10⁻⁶) |
  | Masking | 0.464 | 0.62 | — |
  | Masking + Π | 0.499 | 1.00 | — |
  | PPO-Lag | 0.036 | 0.04 | — |
  | PPO-Lag + Π | 0.393 | 0.99 | — |
  | Blind | 0.451 | 0.51 | 13.75% |
  | Blind + Π | 0.492 | 1.00 | — |
  | Keep-or-nearest + Π | 0.435 | 1.00 | — |
  | Tightest-fit greedy | 0.169 | 0.98 | — |
  | Fixed margin | 0.163 | 0.31 | 8.03% |
  | No certificate | 0.459 | 0.51 | 13.97% |

  Source: [P3/manuscript/tab_main.tex:6-18](P3/manuscript/tab_main.tex). Key message: "Adding the projection at deployment to any learned policy removed every violation and lifted the coverage ratio to at least 0.99" — [P3/manuscript/sec_results_marl.tex:60-66](P3/manuscript/sec_results_marl.tex)
- RQ4 latency (2-core x86-64):

  | Component | Size | Latency |
  |---|---|---|
  | Closed-form monitor | N=1000 | 0.038 ms |
  | Closed-form monitor | N=10⁵ | 6.2 ms |
  | Greedy projection | N=1000 | 0.21 ms |
  | Greedy projection | N=10⁵ | 40 ms |
  | Hungarian | N=12 | 0.038 ms |
  | Hungarian | N=1000 | 11.0 ms |
  | Hungarian | N=2000 | 53 ms |
  | Hopcroft–Karp | N=10⁴ | 1682 ms |

  Source: [P3/manuscript/main.tex:667-678](P3/manuscript/main.tex); [P3/manuscript/numbers.tex:93-102](P3/manuscript/numbers.tex)
- RQ5 (between epochs):

  | Δt | Rule | r_cert | Exposure | Exposures w/o jump |
  |---|---|---|---|---|
  | 0.5 s | standard | 0.393 | 1.51% | 2930 |
  | 0.5 s | predictive (H=Δt) | 0.263 | 0.19% | 0 |
  | 0.19 s | standard | 0.390 | — | — |
  | 0.19 s | predictive | 0.371 | — | 0 |

  Exposure cut factors: 8.1× (0.5 s) and 6.4× (0.19 s). Hysteresis η=0.5 cut reassignments from 2.38% to 2.01% at a coverage cost of 0.393→0.379 — [P3/manuscript/main.tex:700-744](P3/manuscript/main.tex); [P3/manuscript/numbers.tex:21-44,73-77](P3/manuscript/numbers.tex)
- RQ2 (φ=0.3, b=4 of 12): worst 5.55, random 6.37, generic bound 3.89 tasks. The graded bound was tight in 100% of instances with 0 violations — [P3/manuscript/numbers.tex:16-20,58-59](P3/manuscript/numbers.tex)
- RQ6 (lift):
  - Independent case: P(d=0) predicted 0.934 vs simulated 0.927.
  - Spatial jammers: the independent model is too pessimistic on full coverage by 3.4× (0.074 vs 0.250) and too optimistic on losing six or more tasks by 3.7× (6.5% vs 24.1%).
  - Fleet size needed for 99% full coverage: N*=15 under independence; >30 with spatial jammers.
  - Source: [P3/manuscript/numbers.tex:111-132,172-173](P3/manuscript/numbers.tex)

**Limitations and stated future work (Paper III)**
- "Thm. proj is sure, not statistical, but it is conditional. It holds at decision epochs, given a sound certificate."
- Limitations:
  - dependence on the certificate;
  - inherited caveats (hover-regime calibration of γ, Lipschitz dynamics, re-anchoring);
  - simulation only, with rates assumed;
  - a compact learning study (12 aircraft, 5 seeds, CPU);
  - scalar certificates only.
- Source: [P3/manuscript/main.tex:872-892](P3/manuscript/main.tex)
- Broader impact: "an assurance mechanism that withholds tasks from aircraft that cannot be trusted with them; it does not increase any capability to cause harm" — [P3/manuscript/main.tex:894-898](P3/manuscript/main.tex)
- Related-work positioning: predictive safety filters (wabersich2021psf, hsu2024safetyfilter), reachability and Simplex "protect a fixed safe set … complementary to this work" — [P3/manuscript/main.tex:820-831](P3/manuscript/main.tex). Paper III already cites `wabersich2021psf` and `sha2001simplex`, which Paper V also uses.

### Inferences
- Paper V's line "This is the same object as Paper III's projection layer" (PV:82-86) needs qualification:
  - Paper III projects onto a **discrete** feasible set (matchings of G(t)) with a **lexicographic** objective: cardinality, then value, then agreement.
  - Paper V solves a **continuous** min-distance problem with a horizon-H trajectory constraint and a terminal invariant set.
  - Correct wording: Paper V reuses the *SE placement* (filter in the environment, proposer untouched), the *pointwise-for-any-proposer* quantifier of Thm 1(i), and Thm 3's horizon/look-ahead logic. Thm 1(ii) (maximal coverage) and the closed forms do not lift; Remark 1 says the closed forms are lost beyond scalar certificates.
- Thm 1's quantifier "for every policy π_θ, every parameter value θ" is the direct ancestor of Paper V Prop. 1's "for every sequence {a_t^LLM}". Paper III explicitly treats ρ as adversarial (As. 1), but treats the *proposer* as trusted/learned. Paper V's novelty is making the proposer adversarial, which is consistent with PV:292-294.
- Paper III's "coverage ratio" (safe-and-maximal vs safe-because-idle) and the "+ projection at deployment" evaluation design map naturally onto:
  - Paper V's RQ4 (benign intervention rate);
  - the denial rate (fallback = "idle");
  - a "filter added to any agent" ablation.
- A ready-made benign-cost baseline exists: Paper III's "fixed design margin" (ρ_0+L_ρ·1 s) is a design-time conservative alternative that both under-covers (0.163) and still violates (8.03%).

### Gaps
- No optimality-gap result exists. Π is exactly optimal lexicographically, and the greedy variant is exact for cardinality only. Paper V cannot cite a Paper III "optimality gap".
- Paper III has no continuous-action, MPC, QP or terminal-invariant-set formulation, and no fallback (loiter/RTL) concept. The "idle" action ∅ is the nearest analogue. The lift to continuous MPC is entirely new work for Paper V.
- Paper V's constants "MAX_FLEET=12, T=70 s, κ=0.25" (PV:239-240) do not appear in either package. Paper III's N=12 matches MAX_FLEET, but its missions are 150 s, and its κ (`\nKappa`) means L_ρ = 5.30 m/s, not 0.25. These must come from the parent manuscript, which was not provided.

---

## Q2. Paper IV: how is δ_tot defined and decomposed? How does it map to the certified radius R_i(t) and the admissible set? What are the attack models and results? Are there monotonicity results that Paper V Prop. 3 can cite?

### Takeaway
δ_tot is defined as `δ_net(θ) ⊕ δ_adv(θ) ⊕ δ_gnss ⊕ δ_fault ⊕ δ_env`. The ⊕ is **mixed-semantics composition, not a plain sum**:
- deterministic terms (δ_net, δ_adv) shift the margin;
- stochastic terms (δ_gnss, δ_fault) and the p-box term (δ_env) are aggregated over all couplings via p̄.

Paper IV **never defines a certified radius R_i(t) or an admissible set 𝒜_adm**. Its only "shrinking" object is the effective margin `s_m = m − e^{LT_c}δ_net(θ) − δ_adv(θ)`, which feeds the bound `Pr[fail ∧ U] ≤ p̄(s_m)`.

Monotonicity is available only implicitly:
- p̄ is a tail probability, so it is non-increasing in s_m;
- s_m decreases in the deterministic terms;
- Theorem 1's proof gives monotonicity under first-order stochastic dominance (p-box);
- δ_adv is "monotone in the operating point by construction" (pooled empirical supremum).

No result anywhere states that a *fallback or denial rate* is monotone in δ_tot. Paper V must prove that itself.

### Cited Findings

**Notation and macros (Paper IV main.tex preamble)**
- `\dnet=δ_net`, `\dfault`, `\denv`, `\dgnss`, `\dadv`, `\dtot=δ_tot`, `\TV`, `\KL`, `\MCR`, `\pbar=p̄`, `\Dclass=𝒟`, `\code` — [P4/manuscript/main.tex:37-52](P4/manuscript/main.tex)
- Notation table (Appendix A):
  - m: corridor margin;
  - L, T_c: Lipschitz constant and certification horizon (1 s);
  - θ, θ_D: operating point and per-detector thresholds;
  - Δ(θ), s, H: hidden staleness, contact-window slack, malicious hops;
  - γ: delay-to-position rate;
  - X_i: sup-deviation under source i alone;
  - S_i: survival function;
  - F̲, F̄: p-box CDFs, where "F̲ is stochastically largest";
  - p̄, p_U: worst-case and union tail bounds;
  - f(m)=1−p̄(s_m): certified floor;
  - U: no-alarm event;
  - T_a: re-anchoring interval;
  - O_{0:T}, P_a, P_d, 𝒟_k.
  - Source: [P4/manuscript/sec_appendix.tex:1-28](P4/manuscript/sec_appendix.tex)

**Problem setting**
- Dynamics `ẋ=F(x,u)`, feedback on x̂. Completion iff `sup_{t∈[0,T]}|e(t)| ≤ m` (eq. `eq:complete`). `MCR = Pr_{ω∼ℳ}[…]` is "a population quantity, not a statement about any single flight" — [P4/manuscript/main.tex:224-237](P4/manuscript/main.tex). Paper V reuses `ẋ=F(x,u)`, F Lipschitz with constant L, and corridor margin m (PV:93-95), which is consistent.
- Parent chain, condition (C1): F L-Lipschitz, so Grönwall gives the tube radius `ρ = δ e^{LT_c}`. Residual budget `Δ(θ) ≤ H min(θ,s)`, s = 4.84 s over 15,392 hops, γ = 1.625 m/s. Network contribution `e^{LT_c} δ_net(θ)`, with `δ_net(θ)=γ H min(θ,s)` (eq. `eq:dnet`), L = 1.181, T_c = 1 s. At θ=0.25 s, H=2 it contributes **2.65 m** (`\nNetTubeQuarter`) — [P4/manuscript/main.tex:239-257](P4/manuscript/main.tex); [P4/manuscript/numbers.tex:145,195-198](P4/manuscript/numbers.tex). Code: `net_tube(theta_net) = AMP*GAMMA_SUP*H_HOPS*min(theta_net, SLACK_S)` — [P4/experiments/run_pilot.py:269-270](P4/experiments/run_pilot.py)
- Source/semantics table — [P4/manuscript/main.tex:263-275](P4/manuscript/main.tex):

  | Term | Origin | Semantics |
  |---|---|---|
  | δ_net(θ) | relay delay below θ | deterministic worst case |
  | δ_adv(θ) | disguised GNSS offset below the detector stack at θ | deterministic worst case (stealth budget) |
  | δ_gnss | noise, Gauss–Markov drift, outages, jamming noise | stochastic, known marginal |
  | δ_fault | inertial bias steps and drift, actuator loss of effectiveness | stochastic, known marginal |
  | δ_env | turbulence within a declared intensity range | bounded-unknown (p-box), Dryden MIL-F-8785C light to moderate |

- Budget statement: "The budget δ_tot=δ_net(θ)⊕δ_adv(θ)⊕δ_gnss⊕δ_fault⊕δ_env combines deterministic worst-case terms, stochastic terms and a bounded-unknown term represented as a probability box (p-box)" — [P4/manuscript/main.tex:178-191](P4/manuscript/main.tex); [P4/README.md:5](P4/README.md)
- Problem statement P1–P3 and RQ1–RQ4 — [P4/manuscript/main.tex:288-311](P4/manuscript/main.tex)

**Threat model (Paper IV attack models)**
- Capabilities:
  - (a) delay relayed messages on up to H hops;
  - (b) add an offset d(t) to the GNSS position (simulator interfaces only).
- The attacker cannot corrupt the IMU or the trusted re-anchoring fix, which arrives at least every T_a (condition C2′).
- Kerckhoffs: the attacker knows the detectors and thresholds and observes local wind. Its goal is maximal cross-track deviation with no alarm; "Being detected late counts as being detected."
- Source: [P4/manuscript/main.tex:320-337](P4/manuscript/main.tex)
- Def. 1 (ε-observational equivalence): `inf_{d∈𝒟} TV(P_a,P_d) ≤ ε`. Lemma 1 (Le Cam): `Pr_a[ψ=1] ≤ Pr_d[ψ=1]+TV(P_a,P_d) ≤ Pr_d[ψ=1]+√(KL(P_a‖P_d)/2)` — [P4/manuscript/main.tex:346-371](P4/manuscript/main.tex)
- Def. 2 (Disguise-optimal attacker): `δ*_k(θ)=sup_{φ∈Φ_k} E[Δ_φ·1{ψ_{D,θ_D}(O^φ)=0 ∀D}]`, with k*(θ)=argmax_k — [P4/manuscript/main.tex:373-385](P4/manuscript/main.tex)
- Prop. 1 (Detector-gated certificates): `MCR_a ≤ 1 − q_a(1−α−ε)`. "A floor that is to remain valid against every such attack must therefore bound the deviation the attack itself causes on undetected missions; the detector's silence is no evidence of benignity." — [P4/manuscript/main.tex:387-413](P4/manuscript/main.tex). **This aligns philosophically with Paper V's "independent of the component that cannot be secured".**
- Disguise families (offset d(t) from onset t_0) — [P4/manuscript/main.tex:662-686](P4/manuscript/main.tex):
  - step: d=A;
  - ramp: min{r(t−t_0),A};
  - fault mimic: d̈=β_0+β(t), |d| ≤ A;
  - GNSS mimic: A|g(t)|+c(t−t_0);
  - weather mimic: A·w(t−ℓ)/σ_mod + b·min{(t−t_0)/10,1}.
  - Optimiser: CEM with 12 candidates, 4 elites, 25 generations and 48 missions per candidate, and every attacker is cross-evaluated against every stack.
- Detectors — [P4/manuscript/main.tex:636-660](P4/manuscript/main.tex):
  - D1 signature, max jump;
  - D2 χ² NIS on 3 consecutive fixes;
  - D3 SAVIOR-style CUSUM `g_k=max(0,g_{k−1}+r_k²−(1+κ))`. **This κ is a third, unrelated use of the symbol κ**;
  - D4 IMU–GNSS invariant over a 4 s window on 5 consecutive fixes;
  - an anchor gate (FPR 1%);
  - thresholds set on 4,000 benign missions, with the ALL stack splitting the FPR budget equally.

**Theory: Sub-additivity Lemma 2 (lem:subadd)**
- Statement: "If the closed loop is then linear in its additive inputs … e=e_ben+e_adv, and sup_t|e(t)| ≤ sup_t|e_ben(t)|+sup_t|e_adv(t)|."
- Saturation breaks it, so it holds only inside the (C1) region.
- Per-source decomposition `sup_t|e_ben| ≤ Σ_i X_i` is an assumption, condition (C5).
- Source: [P4/manuscript/main.tex:419-445](P4/manuscript/main.tex)

**Theory: Dependence-sharp aggregation**
- Definitions: `p̄(s)=sup_C Pr_C[Σ_i X_i > s]`, `p_U(s)=min{1, inf_{s_1+…+s_d=s} Σ_i S_i(s_i)}` — [P4/manuscript/main.tex:447-455](P4/manuscript/main.tex)
- Prop. 2 (Tightness of the union bound) — [P4/manuscript/main.tex:457-483](P4/manuscript/main.tex):
  - (a) p̄ ≤ p_U;
  - (b) sharp for d=2 (Makarov);
  - (c) strict possible for d≥3, approximated by RA;
  - (d) ratio ≤ d under comonotonicity, unbounded under independence;
  - (e) "A deterministic term X_j ≡ c … shifts s by c and contributes no dependence gap."
- "Who chooses the coupling?": the adversarial offset is deterministic, so it has no coupling to choose. An attacker controlling a *stochastic* source (jamming timing) chooses its coupling, "provided the induced episodes leave the marginal of X_gnss within its calibration (C3)" — [P4/manuscript/main.tex:486-499](P4/manuscript/main.tex). **This is the mechanism by which a sensing attacker enters the budget, relevant to Paper V Prop. 3.**

**Theory: Theorem 1 (Source-agnostic, dependence-sharp bound, thm:floor)**
- Assumptions:
  - (C1) Lipschitz, unsaturated closed loop;
  - (C2′) a trusted re-anchoring fix at least every T_a s, including at mission end;
  - (C3) transfer of γ, the marginals of X_i, and δ_adv;
  - (C4) environmental marginal inside the declared envelope `F̲_env ≤ F_env ≤ F̄_env`;
  - (C5) sub-additivity across benign sources.
- Statement: "Let U be the event that the stack Ψ_θ raises no alarm. Then, for every coupling of the benign sources and every attack, `Pr[fail ∧ U] ≤ p̄(s_m), s_m = m − e^{LT_c}δ_net(θ) − δ_adv(θ)` (eq. `eq:floor`), with p̄ evaluated at the stochastically largest environmental marginal … Consequently Pr[complete | U] ≥ 1 − p̄(s_m)/Pr[U] … f(m)=1−p̄(s_m)."
- Source: [P4/manuscript/main.tex:502-521](P4/manuscript/main.tex)
- Proof sentence usable for monotonicity: "The tail of a sum is non-decreasing under first-order stochastic dominance of any summand, for every coupling and hence for the supremum, so the stochastically largest member of the p-box is the worst." — [P4/manuscript/main.tex:523-530](P4/manuscript/main.tex); appendix proof "Monotonicity in the p-box" — [P4/manuscript/sec_appendix.tex:78-84](P4/manuscript/sec_appendix.tex)
- Remark: the theorem is "conditional in exactly the sense of the parent guarantee: its first and last links are proved, and its interface quantities are measured". Bounding the joint event {fail ∧ U} avoids conditioning on silence — [P4/manuscript/main.tex:532-540](P4/manuscript/main.tex)
- Computation:
  - marginals estimated on calibration block 1xxx from 4,000 missions per source;
  - RA with N=1,000 quantile levels;
  - report `min(RA, p_U)`, with p_U as the proven bound;
  - independence and comonotone tails "for reference only … Neither is a certificate".
  - Source: [P4/manuscript/main.tex:542-554](P4/manuscript/main.tex)

**Explicit monotonicity statements (candidate citations for Paper V Prop. 3)**
- "Every attacker uses the same missions at every operating point, and an attack that is stealthy against stricter thresholds is also stealthy against looser ones, so the pooled supremum is monotone in the operating point by construction." — [P4/manuscript/main.tex:702-707](P4/manuscript/main.tex). Framework figure box: "δ_adv(θ): pooled supremum, monotone in θ" — [P4/manuscript/fig_framework.tex:63](P4/manuscript/fig_framework.tex). Code comment: "same calibration seed per attacker across FPRs -> monotone" — [P4/experiments/run_pilot.py:284](P4/experiments/run_pilot.py)
- The defender design rule couples budget and margin: "choose T_a such that `δ_adv(T_a) ≤ m − e^{LT_c}δ_net − s*`, where s* is the smallest budget with p̄(s*) below the tolerated risk" — [P4/manuscript/sec_discussion.tex:6-15](P4/manuscript/sec_discussion.tex)
- Empirical monotone growth with T_a: pooled supremum 4.4 m (T_a=5 s), 9.0 m (10 s), 20.6 m (20 s), i.e. 4.7×. With an open terminal window: 8.3/33.6/137.8 m, i.e. 7× the closed value at 20 s — [P4/manuscript/numbers.tex:6-9,189-193](P4/manuscript/numbers.tex); [P4/manuscript/sec_results.tex:112-121](P4/manuscript/sec_results.tex)
- The δ_adv budget is identical at 1/5/10% FPR (4.37 m, argmax fault mimic): "no attacker in the pool gains from looser thresholds in that range, not that thresholds never matter" — [P4/manuscript/sec_results.tex:158-163](P4/manuscript/sec_results.tex); [P4/results/e4_delta_adv.csv](P4/results/e4_delta_adv.csv)

**Experimental setup (Paper IV pilot)**
- Reduced-order lateral model:
  - V=8 m/s, 60 s segment;
  - drag-damped double integrator `p̈=u+c_d(w−ṗ)`, c_d=0.35 s⁻¹;
  - PD controller (k_p,k_d)=(1.2,1.8), saturated at 4 m/s²;
  - 3-state KF (position, velocity, accelerometer bias);
  - 20 Hz IMU, 10 Hz GNSS, anchor every T_a=5 s (σ 0.3 m).
- Environment: Dryden at 100 ft; envelope W_20∈[15,30] kt; severe 45–60 kt as a negative control.
- Faults: bias step p=0.3 σ=0.1; drift p=0.2 (×10 RW); LoE 10–30% p=0.2.
- GNSS: white 0.5 m; Gauss–Markov 0.8 m / τ=60 s; outages p=0.3 (mean 5 s); jamming noise ×3 for 10 s, p=0.2.
- Source: [P4/manuscript/main.tex:608-634](P4/manuscript/main.tex); [P4/experiments/constants.py:12-75](P4/experiments/constants.py); appendix constants table — [P4/manuscript/sec_appendix.tex:103-125](P4/manuscript/sec_appendix.tex)
- Statistics:
  - evasion rate;
  - attack-only contribution sup|e_adv| (additive benign inputs zeroed, parametric ones kept);
  - KS distance as a proxy for TV;
  - soundness via a one-sided binomial test of `H_0: Pr[fail∧U] ≤ p̄(s_m)`, Holm-adjusted across all operating points (violation = adjusted p<0.05);
  - Clopper–Pearson intervals on MCR.
  - Source: [P4/manuscript/main.tex:688-718](P4/manuscript/main.tex)
- Seed blocks by role: 1xxx calibration, 2xxx attacker optimisation, 3xxx held-out attacker, 4xxx held-out evaluation (E2x 4100+, E2b 4200+, E2c 4300+, E4 4400+, E2y 4500+, E5 4900+), 5xxx negative controls. New experiments take 6xxx, 7xxx, … recorded in `results/run_meta.json` — [P4/README.md:37](P4/README.md); [P4/RUNBOOK_CLAUDE_CODE.md §1.2](P4/RUNBOOK_CLAUDE_CODE.md)
- Compute: `run_meta.json` = {N_cal 4000, N_eval 1000, cem_gens 25, cem_K 48, cem_lambda 12, n_missions 1,839,600, wall_s 1637.3} — [P4/results/run_meta.json](P4/results/run_meta.json). The manuscript reports 1,909,600 missions in 29 min (`\nMissionsTotal`, `\nWallMin`) — [P4/manuscript/numbers.tex:135,224](P4/manuscript/numbers.tex). The difference of 70,000 missions is plausibly the E2y run (`mission_count_e2y.txt`); this is an inference, not confirmed.

**Headline results (Paper IV)**
- Calibration: wind and faults alone trip no detector (FPR 0.0%); GNSS alone produces up to 5.3%; severe wind raises D3 FPR to 8.2%. At 5% FPR, D2/D4 detect a 5 m step 100%/96%; D1/D3 detect it 7%/6% — [P4/manuscript/sec_results.tex:7-24](P4/manuscript/sec_results.tex)
- RQ1:
  - Every family evades every detector in **≥87%** of missions (`\nCrossEvMin`); benign no-alarm rate ≈94%.
  - With the anchor gate armed, frequent evasions are capped at 2.1–2.9 m; rare evasions reach up to 5.6 m (weather mimic vs D1, D3).
  - In 8 of 25 cells the own-target optimiser failed.
  - KS distance: evading 0.07 vs caught 0.99.
  - Source: [P4/manuscript/sec_results.tex:28-55](P4/manuscript/sec_results.tex); [P4/manuscript/numbers.tex](P4/manuscript/numbers.tex)
- Without the anchor gate, D2 caps every family at 9.9 m. D1/D3/D4 admit 73.9 m to the fault mimic; D1 admits 72.6 m (GNSS mimic) and 50.4 m (weather mimic); the ALL stack is capped at 10.5 m — [P4/manuscript/tab_disguise_nogate_body.tex](P4/manuscript/tab_disguise_nogate_body.tex)
- RQ3 at s=4 m:

  | Quantity | Value |
  |---|---|
  | Union vs RA (d=2) | agree within 0.001 |
  | RA gain (d=3) | 20% (0.639→0.513) |
  | Dependence gap | 4× |
  | Envelope gap | 2.2× |
  | Independent vs per-source sum | 1.09× |
  | Temporal gap | 16.6× (62 joint exceedances in 20,000 missions) |
  | (C5) held in | 99.63% of missions |

  Source: [P4/manuscript/sec_results.tex:125-154](P4/manuscript/sec_results.tex)
- RQ2/RQ4 (Table `tab:soundness`):
  - δ_adv = **4.37 m**;
  - **0 Holm-significant violations at 270 operating points** over 30,541 undetected-attack missions;
  - the held-out attacker exceeded δ_adv in 1 of 45 cells (5.13 m, fault mimic, 5% FPR, 1.17×);
  - superposition held in ≥94.4% of missions, and the unsaturated control in 100%;
  - certified 0.9 floor at m=10.0 m vs independence 8.5 m; 13.0 m with the network term.
  - Source: [P4/manuscript/sec_results.tex:158-196](P4/manuscript/sec_results.tex); [P4/manuscript/numbers.tex:118-121,203-213](P4/manuscript/numbers.tex). Rows of the soundness table (FPR, θ_net, m, p_U, p̄, p_⊥, obs, MCR_U, viol.): e.g. "5% & 0.25 & 5 & 1.000 & 1.000 & 1.0000 & 0.4250 & 0.508 & 0 & 0" — [P4/manuscript/tab_soundness_body.tex](P4/manuscript/tab_soundness_body.tex)
- Negative controls:
  - C2′ broken: up to 308.5 m; flagged at 4 of 6 points (fault and ramp);
  - C4 broken (severe wind): fault mimic reaches 96.7 m; flagged at m=20.
  - Source: [P4/manuscript/sec_results.tex:223-239](P4/manuscript/sec_results.tex); [P4/manuscript/tab_negative_body.tex](P4/manuscript/tab_negative_body.tex)

**Limitations and future work (Paper IV)**
- Reduced-order model, not EKF2 (R3 SITL needed);
- δ_adv is empirical, not a proof (R1, R8);
- a conservative bound with limited power;
- simulated marginals (R5);
- network term not simulated (R4);
- **"Covert attackers only. The bound covers undetected failure. An attacker indifferent to detection is bounded instead by detection latency and the failsafe, which we do not certify here."**;
- no IMU injection.
- Source: [P4/manuscript/sec_discussion.tex:45-72](P4/manuscript/sec_discussion.tex)
- Ethics: dual-use reasoning, mitigation paired in the same section, no RF emission, 90-day PX4/ArduPilot disclosure — [P4/manuscript/sec_ethics.tex](P4/manuscript/sec_ethics.tex). Paper V says an ethics section is mandatory (PV:320-324), so this is the template.

### Inferences
- **Mapping Paper V's 𝒜_adm(x_t) to δ_tot is not provided by Paper IV.** It must be built. The natural construction from the sources:
  - Paper III's protection level ρ_i(t)=e^{LT}γ_sup Δ_i(t) (P3) and Paper IV's tube `e^{LT_c}δ` (P4:239-257) both turn a perturbation budget into a position-error radius.
  - Paper IV's effective margin s_m = m − e^{LT_c}δ_net − δ_adv is the corridor tightening.
  - An admissible set "corridor shrunk by the deterministic budget, with a p̄-based chance tightening for the stochastic terms" is nested: 𝒜_adm(δ') ⊆ 𝒜_adm(δ) when δ' ≥ δ componentwise or in stochastic order.
- Given nestedness, Paper V Prop. 3 can be proven directly. Any agent output that triggers fallback at δ also triggers it at δ' ≥ δ, so the supremum over adaptive attackers of the induced fallback rate is monotone. This argument needs:
  - (1) deterministic terms entering as shifts (P4 Prop. 2(e));
  - (2) the stochastic-dominance monotonicity of p̄ (P4 Thm 1 proof / appendix);
  - (3) Paper III Prop. 2 (graded degradation is coverage-monotone in s) as the discrete precedent.
- **Notational hazard: "δ_tot shrinks 𝒜_adm" must specify how ⊕ is evaluated.**
  - Paper IV never reduces δ_tot to one scalar, because stochastic terms enter via p̄(s_m) at a chosen risk level.
  - Paper V should define a scalar effective tightening, e.g. `δ_tot^ε ≔ e^{LT_c}δ_net + δ_adv + s*(ε)` with p̄(s*(ε)) ≤ ε, mirroring Paper IV's design rule (sec_discussion.tex:13-15). It should then claim monotonicity in that scalar.
- **Which Paper IV channel does Paper V Prop. 3 compose with?** Paper IV's adversary is covert (bounded on {fail ∧ U}). Paper V's composed attacker (jam/spoof plus prompt injection) is not necessarily covert. Paper IV's own limitation says detection-indifferent attackers are not certified. Paper V must either:
  - restrict the concurrent sensing attacker to Paper IV's covert class (δ_adv valid under U and C2′); or
  - add a detection/failsafe argument.
  Otherwise Prop. 3 overstates what Paper IV supplies.
- δ_adv is empirical and was exceeded once (1.17×). Any Paper V claim "zero violations under composition" inherits that caveat and the R1/R8 dependency.

### Gaps
- No R_i(t), R_min, certified radius or admissible-set definition in either package. Paper V attributes "certified radius R_i(t) ≥ R_min" and "γ=1.625 m/s supremum" to the parent manuscript. Only γ is confirmed here (both papers, measured over 674 samples).
- The runbook (P4 R2.3) refers to "the Grönwall-amplified form (manuscript §4.3, Remark 2)", but main.tex has only one remark (after Thm 1, main.tex:532-540), and main_single.tex also has a single `\begin{remark}` (line 870). The referenced Remark 2 does not exist in the shipped manuscript.
- No statement that fallback, denial or MCR is monotone in δ_tot as a function. Only the pieces listed above exist.
- Paper IV evaluates one aircraft (lateral channel), not fleets. Composition with fleet-level allocation is untested in both papers.

---

## Q3. Which code modules and functions implement these, so a Paper V runbook can call them?

### Takeaway
Paper III's reusable core is `certcmdp/` (certificate process, closed forms, projection, CertSwarm env). Paper IV's reusable core is `constants.py`, `sim.py` (closed loop, detectors, disguise families), `depbounds.py` (union/RA bounds) and helper functions in `run_pilot.py` (`net_tube`, `pbar`, `cem`, `stealth_mask`, `holm`, `cp_interval`). Both use the same pipeline: CSVs in `results/`, then `make_numbers.py`, then `numbers.tex` and `figdata/*.dat`.

### Cited Findings

**Paper III (`P3/experiments/`)**
- `certcmdp/certificate.py`:
  - constants: `L_LOC=1.1814`, `T_C=1.0`, `GAMMA_SUP=1.625`, `S_SLACK=5.0`, `THETA_BENIGN=0.178`, `ALERT_LIMITS=(2,5,10,20)`, `KAPPA=exp(L_LOC*T_C)*GAMMA_SUP`;
  - functions: `rho_of_staleness(delta_s)`, `residual_pools()`, `gamma_samples()`, `write_constants_csv()`;
  - classes: `ThreatProfile` (dataclass of rates) and `CertificateProcess(B,N,prof,rng,spatial_jam)` with `.rho()` and `.step(dt, jam_mask)`. ρ = KAPPA·(benign+dr+relay).
  - Constants are read from parent `../../results` (`REPO/results/hop_ledger.csv`, `gamma_campaign_samples.csv`, `local_lipschitz.csv`), so the module needs the parent repo layout.
  - Source: [P3/experiments/certcmdp/certificate.py:32-44,47-165](P3/experiments/certcmdp/certificate.py)
- `certcmdp/combinatorics.py`:
  - closed forms: `count_profile`, `deficiency`, `max_coverage`, `coverage_margin`, `worst_case_deficiency(rho,alpha,b)`, `batch_deficiency`;
  - projections: `nested_greedy(rho,alpha,score,value)`, `nested_greedy_fast`, **`lexicographic_projection(elig, proposal, value=None, prev=None, eps_prev=0.0)`** (Hungarian via `linear_sum_assignment(Wf, maximize=True)`, ineligible weight 0 discarded post-solve);
  - **`eligibility(rho, alpha, holder_of=None, h=0.0, lookahead=0.0, eta=0.0, keep_lookahead=0.0)`** (acquire `rho+lookahead ≤ (1−eta)α−h`; keep `rho+keep_lookahead ≤ α`);
  - `resolve_conflicts`, `brute_max_matching` (Hopcroft–Karp oracle); `IDLE=-1`.
  - Source: [P3/experiments/certcmdp/combinatorics.py:16-222](P3/experiments/certcmdp/combinatorics.py)
- `certcmdp/env.py`:
  - `EnvConfig` (N=12, M=8, L=1000, speed 15, r_cap 30, dt 0.5, horizon 300, n_jammers 2, jam_radius 200, jam_speed 4);
  - `CertSwarm(B,cfg,seed)` with `reset`, `jam_mask`, `obs(blind)`, **`allocate(proposal, mode∈{project,mask,fixed_margin,none,gnp}, h, lookahead, design_rho, dwell_s, eta, keep_lookahead)`** and `step(executed)`. `step` judges violations "at execution time, on the current certificate".
  - Source: [P3/experiments/certcmdp/env.py:28-160](P3/experiments/certcmdp/env.py)
- Experiment scripts:
  - `e1_verify.py` (oracle; must report 0 disagreements after any combinatorics change);
  - `e2_degradation.py` (`graded_bound`, `part_a/b/c`, `p_full_iid`);
  - `e3_latency.py`;
  - `e4_dynamics.py` (`run(eta,H,Hkeep,…)`, `liars`);
  - `e5_marl.py` (`METHODS` dict, `Actor`, `Critic`, `action_mask`, `train(method,seed,updates,B,rollout)`, `references()`, `COST_LIMIT=0.005`, `FIXED_MARGIN_RHO`);
  - `e6_aggregate.py` (`iqm`, `strat_boot`, `cp_upper(k,n,a)`);
  - `export_figdata.py`, `make_numbers.py`, `run_all.sh`, `run_marl.sh` (`SEEDS`, `UPDATES`, `PAR` env vars; logs `results/e5_marl/log_<m>_<s>.txt`).
  - Source: [P3/experiments/](P3/experiments/) function listing; [P3/experiments/run_all.sh](P3/experiments/run_all.sh); [P3/experiments/run_marl.sh](P3/experiments/run_marl.sh); [P3/experiments/e5_marl.py:44-52](P3/experiments/e5_marl.py)

**Paper IV (`P4/experiments/`)**
- `constants.py`:
  - tags `[parent] [std] [model] [px4]`;
  - `GAMMA_SUP=1.625`, `SLACK_S=4.84`, `H_HOPS=2`, `L_LOC=1.1814`, `T_C=1.0`, `AMP=exp(L_LOC*T_C)`;
  - `dryden_lateral(w20_kt,h_ft)`;
  - detector constants `CONSEC_CHI2=3`, `CONSEC_INV=5`, `INV_WINDOW_S=4.0`, `CUSUM_KAPPA=1.0`, `ANCHOR_GATE=10.83`, `FPR_TARGET=0.05`;
  - `CORRIDOR_M=(2,5,10,20)`.
  - Source: [P4/experiments/constants.py:1-75](P4/experiments/constants.py)
- `sim.py`:
  - `ATTACK_FAMILIES=("none","step","ramp","fault_mimic","gnss_mimic","weather_mimic")`, `ATTACK_BOX`, `decode(family,u)`, `_dryden_ss`;
  - **`simulate(N, seed, *, w20, gnss, fault, attack, aparams, attack_seed, anchor=T_ANCHOR, env_on, w20_attacker, terminal=True, noise=True)`**, which returns per-rollout arrays. `anchor=None` violates C2′, and `noise=False` gives the attack-only counterfactual;
  - `DETECTORS=("D1".."D4")`, `alarms(out, th, stack)`.
  - Source: [P4/experiments/sim.py:43-92,287-290](P4/experiments/sim.py)
- `depbounds.py`: `tail`, **`union_bound(samples,s,grid=200)`**, `ra_worst_var(samples,alpha,N=2000,…)`, **`ra_bound(samples,s,N=2000,iters=30)`**, `indep_tail`, `comon_tail`. Docstring: "Deterministic (Dirac) terms enter only as a shift of s" — [P4/experiments/depbounds.py:1-112](P4/experiments/depbounds.py)
- `run_pilot.py`:
  - `STACKS`, `FAMILIES`, `FPR_GRID=(0.01,0.02,0.05,0.10,0.20)`, `OPS=(0.01,0.05,0.10)`;
  - `cp_interval`, `holm`, `e1_calibrate`, **`stealth_mask(o,cal,stack_name,fpr)`**, **`cem(family,stack_name,fpr,cal,seed,…)`**, `run_attack`, `e2_optimise`, `e2x_cross`, `e2_anchor`, `e3_budget`;
  - **`net_tube(theta_net)`**, **`pbar(marg,s,method∈{ra,union,indep})`** (returns 1.0 if s≤0), `e4`, `e5`, `main` (`--quick` flag per the runbook).
  - Source: [P4/experiments/run_pilot.py:41-382](P4/experiments/run_pilot.py)
- `e2y_no_anchor_gate.py` and `make_numbers.py`. `make_numbers.py` writes `numbers.tex`, `tab_*_body.tex` and `figdata/*.dat`; Paper IV has no separate `export_figdata.py`, although the runbook names one — [P4/README.md:7-25](P4/README.md)
- The result-CSV schema of `e4_soundness.csv` includes `delta_adv, net_tube, n_undetected, k_fail_undetected, pbar_ra, pbar_union, p_indep, f_cert_ra, …, superposition_frac, p_holm, violation` — [P4/results/e4_soundness.csv header](P4/results/e4_soundness.csv)

### Inferences
- A Paper V filter could take, as building blocks for its δ_tot-shrunk admissible set:
  - `combinatorics.eligibility(..., lookahead=L_ρ·H, keep_lookahead=L_ρ·Δt)` (Thm 3 look-ahead) as the discrete task-assignment admissible set when the LLM proposes *task assignments*;
  - `lexicographic_projection` as the discrete "min-deviation" filter for task proposals;
  - `pbar`/`net_tube` from Paper IV.
  The continuous waypoint/MPC part has no existing implementation.
- `lexicographic_projection` maximises agreement with the proposal only *after* cardinality and value. For Paper V's "transparent when a^LLM ∈ 𝒜_adm" property to hold for task proposals, either:
  - run it with `value=None` and accept that it may still reassign other aircraft to raise cardinality (so it is **not transparent** to a feasible but non-maximal LLM proposal); or
  - write a new minimal-deviation variant.
- Paper III's `certificate.py` paths resolve to `parents[3]/results` (the parent repo). Paper IV `run_pilot.py` writes to `parents[1]/results`. A Paper V runbook must keep the `paperV/` folder inside the same repository tree (`rogerpanel/RobustUAVs.ai`) for these imports to work.

### Gaps
- Package code was not executed, per instructions, so runtime behaviour and signatures beyond what is shown were not verified.
- No LLM-agent harness, MPC solver, or "platform" code (`platform/backend/app/corpus.py` is referenced in the P3 runbook R5) is included in either package.

---

## Q4. What is the template of RUNBOOK_CLAUDE_CODE.md (sections and conventions), so Paper V's runbook can follow the same format?

### Takeaway
Both runbooks share one skeleton:
1. Header: paper title, venue, repository and branch, folder.
2. Purpose paragraph, with the bold rule "Never type a number into main.tex".
3. §0 "What is already done (do not redo)": a table of Script | Output | What it establishes | Runtime (2 cores), plus the regenerate block and ranked "weak points" naming the load-bearing items.
4. §1 "Ground rules for every experiment": placement, provenance column, guarantee re-verification or soundness-is-the-claim, statistics, seeds and dual-use, commit format `paperX: R<n> <short result>`, honesty.
5. §2 Environment: venv and pip.
6. R1…R9/R10 work items, each with Goal / Grid or Steps / Changes / Outputs (CSV paths, provenance) / Acceptance / Manuscript hook. Load-bearing items are tagged **[load-bearing]**.
7. Build-and-submit section (Paper III §3) or data gates plus an acceptance checklist (Paper IV).

### Cited Findings
- Paper III header:
  - "Paper: … (target: NeurIPS, main track)";
  - "Repository: `rogerpanel/RobustUAVs.ai`, branch `claude/whelan-uavcas-ingest-u00isn`";
  - "Folder: `paperIII/` (`experiments/`, `results/`, `manuscript/`)";
  - purpose: "the drafting sandbox (2 CPU cores, 7 GB RAM, no GPU, no simulator) could only run in compact form. Every experiment writes a CSV to `paperIII/results/`. `make_numbers.py` turns those CSVs into LaTeX macros in `manuscript/numbers.tex` … **Never type a number into `main.tex`.**"
  - Source: [Project PaperIII/RUNBOOK_CLAUDE_CODE.md, header](PaperIII/RUNBOOK_CLAUDE_CODE.md)
- Paper IV header: work on a branch cut from `claude/whelan-uavcas-ingest-u00isn` "because that branch is scheduled for deletion (see `PENDING_ON_DATA.md` §0); `dev/whelan-uavcas-ingest` is the long-lived equivalent". **Paper V should use `dev/whelan-uavcas-ingest`** — [Project PaperIV/RUNBOOK_CLAUDE_CODE.md, header](PaperIV/RUNBOOK_CLAUDE_CODE.md)
- §0 tables: Paper III lists 7 scripts (certificate, e1–e6) with runtimes (e.g. `e5_marl.py` ≈65 min). Paper IV lists sim/depbounds/run_pilot E1–E5/e2y with runtimes (full pilot ≈27 min; `--quick` 9 min). Both include a "Regenerate" bash block and "Known weak points, in the order they would worry a NeurIPS/USENIX reviewer" — [both runbooks §0](PaperIV/RUNBOOK_CLAUDE_CODE.md)
- §1 ground rules:
  - Paper III: (1) Placement plus `provenance` column `measured | derived | assumption | sim | sitl | hardware`; (2) after any change to `certcmdp/combinatorics.py` run `e1_verify.py`, which must give 0 disagreements, "never relax the check"; (3) IQM with stratified-bootstrap CIs, per-step violations, CP bound with exposure; (4) latency on an idle machine; (5) commit `paperIII: R<n> <short result>` with a CSV diff summary in the body; (6) honest reporting ("not varied"; say so if the learned method does not beat the heuristic) — [PaperIII/RUNBOOK_CLAUDE_CODE.md §1](PaperIII/RUNBOOK_CLAUDE_CODE.md)
  - Paper IV: (1) Placement plus provenance `measured | physics_model | synthetic_alignment | sim | sitl | hardware`, matching `schema/uavsec_schema.json` `pairing_basis`; (2) seed discipline by role blocks; (3) "Soundness is the claim": a Holm-significant violation is a bug, and "Never widen a constant after looking at held-out data"; (4) statistics: CP on every MCR, Holm–Bonferroni, IQM/rliable, exact one-sided bound when zero; (5) dual-use: no transmit-capable SDR code, simulator interfaces only, evasion harness released only with mitigations; (6) commits `paperIV: R<n> …` — [PaperIV/RUNBOOK_CLAUDE_CODE.md §1](PaperIV/RUNBOOK_CLAUDE_CODE.md)
- R-items:
  - Paper III: R1 scale MARL **[load-bearing]**, R2 stronger baselines **[load-bearing]**, R3 measured-trace replay, R4 PX4 SITL v1.14.3 multi-vehicle, R5 W-MSR consensus, R6 vector certificates, R7 learned jammer, R8 embedded latency, R9 sensitivity, then §3 Building and submitting (style file, `% CHECK` bib entries, `tools/anonymise.py --out ../RobustUAVs-anon --init-git --zip`, NeurIPS checklist).
  - Paper IV: R1 stronger attackers **[load-bearing]** (acceptance "new δ_adv ≤1.25× pilot or regenerate floors"), R2 6-DoF/EKF2, R3 PX4 SITL **[load-bearing]** (acceptance Kendall τ ≥ 0.6; zero Holm-significant violations), R4 network coupling (γ vs γ_sup=1.625; undetected-delay supremum ≤4.84 s), R5 measured marginals, R6 artifact packaging (Docker, Zenodo, USENIX AE badges), R7 baselines table, R8 analytic stealth budget (SDP, cvxpy; adopt if <2× empirical), R9 signal-level (never transmit), R10 ethics and disclosure, then Data gates and the Acceptance checklist.
  - Source: both runbooks.
- Paper III R4 gives the PX4 toolchain shared with "Paper I E3": `PX4-Autopilot v1.14.3`, `mavsdk`, `pymavlink`, `failure gps off`, `GPS_INPUT` offset ramp, ground truth from `vehicle_local_position_groundtruth`. **The fallback (loiter/RTL) and agent-in-the-loop work in Paper V would naturally use this** — [PaperIII/RUNBOOK_CLAUDE_CODE.md R4](PaperIII/RUNBOOK_CLAUDE_CODE.md)

### Inferences
- A Paper V runbook in house format would be:
  - Header: target IEEE SaTML (fallback USENIX Security), repository, branch `dev/whelan-uavcas-ingest`, folder `paperV/`.
  - §0 a done/not-done table. Today this is mostly "to build", per PV:232-248.
  - §1 ground rules: provenance enum (add `llm` or `sim` qualifiers); seed-role blocks reusing Paper IV's partition and adding blocks for the LLM sampling seed and the adaptive-attacker optimisation; "zero physical violations is the claim; any violation is a bug" (PV:205-209 mirrors Paper IV §1.3); Holm/CP statistics; dual-use rules (the evasion harness is released only with the filter).
  - R-items: agent-in-loop harness, MPC filter, adaptive attack, composition sweep over δ_tot, benign cost, platform page, SITL.
  - Acceptance checklist.

### Gaps
- The Paper I and Paper II runbooks were not in scope and were not read, so the full cross-programme template variance is unknown.
- `PENDING_ON_DATA.md`, `schema/uavsec_schema.json` and `tools/anonymise.py` are referenced but not in the packages.

---

## Q5. Figure style (Figure 1 TikZ), LaTeX templates and venue classes, and consistency hazards for Paper V

### Takeaway
The two Figure 1 diagrams use different TikZ idioms:
- **Paper III**: four labelled horizontal bands (Inputs, Certificate, Allocation and learning, Guarantees), named styles `data/cert/cons/learn/outb` with xcolor `!6–!8` fills, dashed `lane` fit frames with rotated circled-number labels, and yellow `rq` tags.
- **Paper IV**: a phase-structured layout (I–V) on an explicit cm grid, a named colour-blind-safe palette (`cBlue…cGray`), parameterised styles `b={colour}{width}`, `d=colour`, a `dia` decision diamond, and a dashed red `fb` feedback arrow.

Neither package ships a venue class file. Both fall back to `article` with geometry. Paper V's SaTML target (IEEE) has no precedent in these packages.

### Cited Findings
- Paper III Figure 1 style block, verbatim keys:
  - `font=\sffamily\footnotesize`, `>={Stealth[length=2.2mm]}`;
  - `box/.style={draw, rounded corners=2pt, align=center, minimum height=10mm, text width=#1, inner sep=3pt, fill=white}`, `box/.default={31mm}`;
  - `data/.style={box=30mm, fill=blue!6, draw=blue!50!black}`;
  - `cert/.style={box=41mm, fill=orange!8, draw=orange!60!black}`;
  - `cons/.style={box=31mm, fill=green!7, draw=green!40!black}`;
  - `learn/.style={box=31mm, fill=violet!7, draw=violet!60!black}`;
  - `outb/.style={box=30mm, fill=red!5, draw=red!50!black}`;
  - `lane/.style={draw=black!30, dashed, rounded corners=4pt, inner xsep=6pt, inner ysep=5pt}`;
  - `lbl/.style={font=\sffamily\bfseries\scriptsize, rotate=90, anchor=south, …}`;
  - `rq/.style={draw=black!60, fill=yellow!30, rounded corners=1pt, inner sep=1.5pt, font=\sffamily\scriptsize\bfseries}`;
  - `lab/.style={font=\sffamily\scriptsize, fill=white, inner sep=1pt}`.
  - Layout: column x = 0/3.55/7.1/10.65 cm; band y = 0, −2.25, −4.5/−6.35, −9.2. The figure is wrapped in `\resizebox{\linewidth}{!}{…}` in `figure[t]`, with the caption read "top to bottom" using `\textcircled{\scriptsize n}`.
  - Source: [P3/manuscript/fig_framework.tex:1-100](P3/manuscript/fig_framework.tex)
- Paper IV palette and Figure 1 styles:
  - `\definecolor{cBlue}{HTML}{2C6E9B}`, `cGreen 3B8B5A`, `cOrange C77D1A`, `cRed B03A2E`, `cPurple 6A4C93`, `cGray 555555` ("colour-blind-safe palette") — [P4/manuscript/main.tex:29-35](P4/manuscript/main.tex)
  - TikZ: `font=\sffamily\scriptsize`, `>={Stealth[length=1.8mm]}`;
  - `b/.style 2 args={draw=#1!70!black, fill=#1!9, rounded corners=2pt, align=center, minimum height=8mm, text width=#2, inner sep=2pt, line width=0.5pt}`;
  - `d/.style={draw=#1!70!black, fill=#1!20, …, text width=21mm}`;
  - `dia/.style={draw=cRed!70!black, fill=cRed!8, diamond, aspect=2.2, …}`;
  - `phase/.style={draw=black!40, dashed, rounded corners=4pt, inner sep=5pt}`;
  - `ptitle/.style={font=\sffamily\bfseries\scriptsize, fill=white, inner sep=1.5pt, anchor=west}`;
  - `arr/.style={->, line width=0.6pt, draw=black!70}`;
  - `fb/.style={->, line width=0.6pt, draw=cRed!80!black, dashed}`;
  - `lab/.style={font=\sffamily\tiny, fill=white, …}`.
  - Phase frames are drawn `on background layer`. The figure uses `figure*` with `\resizebox{\textwidth}{!}` and needs the libraries positioning, arrows.meta, fit, backgrounds, shapes.geometric.
  - Source: [P4/manuscript/fig_framework.tex:1-106](P4/manuscript/fig_framework.tex)
- Results-plot styles:
  - Paper III pgfplots: `grid=major, grid style={black!10}`, `tick label style={font=\scriptsize}`, `label style={font=\small}`, series colours `red!70!black` (ours), `blue!70!black`, `orange!80!black`, `gray dashed`, marks `*`/`square*`/`triangle*`, groupplots and fillbetween — [P3/manuscript/main.tex:640-698](P3/manuscript/main.tex); [P3/manuscript/sec_results_marl.tex:22-54](P3/manuscript/sec_results_marl.tex)
  - Paper IV pgfplots: `\pgfplotsset{p4/.style={width=\columnwidth, height=4.6cm, grid=major, grid style={black!12}, tick label style={font=\scriptsize}, label style={font=\footnotesize}, legend style={font=\scriptsize, draw=none, fill=white, fill opacity=0.85, text opacity=1}, every axis plot/.append style={line width=0.9pt}}}`, with figures defined as macros (`\figROC`, `\figAnchor`, `\figGap`, `\figFloor`) reading `figdata/*.dat` — [P4/manuscript/fig_results.tex:1-110](P4/manuscript/fig_results.tex)
- Templates:
  - Paper III: `\documentclass[10pt]{article}` with `\IfFileExists{neurips_2027.sty}…{neurips_2026.sty}…` fallback `geometry` (textwidth 5.5in, textheight 9in) plus `times`; `natbib[numbers,sort&compress]`, `plainnat`, `cleveref[capitalise,noabbrev]`, `algorithm`+`algpseudocode`; `\input{numbers}` — [P3/manuscript/main.tex:18-47,916](P3/manuscript/main.tex)
  - Paper IV: `\documentclass[letterpaper,twocolumn,10pt]{article}` with `\IfFileExists{usenix-2020-09.sty}` fallback geometry (0.75in sides, columnsep 0.33in) plus `mathptmx`, `helvet[scaled=0.92]`, `courier`, `colortbl`, `cleveref[capitalize,nameinlink]`, `plain` bibstyle; a `\tabinput` primitive for table bodies; `main_single.tex` as a self-contained single-file edition — [P4/manuscript/main.tex:8-63,753](P4/manuscript/main.tex)
  - Paper V currently uses `\documentclass[11pt,a4paper]{article}` + `\input{proposal_preamble3}`, with `\bibliography{proposals3}` — [PV:9-16,354-355](PV)
- Theorem environments: Paper III has theorem, lemma, proposition, corollary, definition, assumption (definition style) and remark. Paper IV has definition, lemma, proposition, theorem, corollary and remark (no assumption env); conditions are written inline as (C1)–(C5) — [P3/manuscript/main.tex:67-75](P3/manuscript/main.tex); [P4/manuscript/main.tex:53-59](P4/manuscript/main.tex)
- Companion citation keys used by both: `parentpaper`, `paperI`, `paperII`; Paper III also cites `wabersich2021psf`, `sha2001simplex`, `hsu2024safetyfilter`, `markgraf2025actionprojection`, `clopper1934`, `agarwal2021precipice`, `holm1979` (Paper IV) — [P3/manuscript/main.tex](P3/manuscript/main.tex); [P4/manuscript/main.tex](P4/manuscript/main.tex)

### Inferences
- Notation collisions Paper V must resolve:
  - **κ**: Paper III `\nKappa` = L_ρ = 5.30 m/s; Paper IV's D3 CUSUM κ (code `CUSUM_KAPPA=1.0`); Paper V's "κ=0.25" is unexplained here.
  - **α**: Paper III alert limit α_j; Paper IV FPR budget α; RA confidence level α.
  - **ρ**: Paper III certified protection level ρ_i(t); Paper IV Grönwall tube radius ρ=δe^{LT_c}.
  - **H**: Paper III malicious hops H=2 *and* look-ahead horizon H; Paper IV malicious hops H; Paper V MPC horizon H.
  - **T**: Paper III T=1 s (Grönwall horizon); Paper IV T mission horizon and T_c=1 s certification horizon.
  - **𝒮/safe set vs corridor m**: Paper V's 𝒮 uses "corridor margin m", consistent with Paper IV's m.
  - **U**: Paper IV no-alarm event.
  Using Paper IV's T_c and m and Paper III's ρ_i(t) unchanged, and renaming Paper V's MPC horizon (e.g. N_H or T_H), would avoid clashes.
- For an IEEE SaTML submission, a third style idiom will be needed (IEEEtran conference, two-column). Paper IV's two-column `figure*` + `\resizebox{\textwidth}` Figure 1 and its `p4` column-width pgfplots style are the closer precedent to adapt. The colour-blind-safe `cBlue…cGray` palette is the more reusable choice.

### Gaps
- No `.sty` or `.cls` venue files are present in either package. Paper V's `proposal_preamble3.tex` and `proposals3.bib` were not provided, so the proposal's `\proposalheader`, `honestly` environment and `\code` macro definitions could not be checked.
- The rendered PDFs (`main.pdf`) were not visually inspected. Figure-style findings come from the TikZ source only.
