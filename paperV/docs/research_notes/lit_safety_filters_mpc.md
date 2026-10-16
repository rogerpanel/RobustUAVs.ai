# Safety Filters and Runtime Assurance for an Untrusted (Possibly Adversarial) UAV Planner: Control-Theoretic Literature Map

Verification legend (applies to every bibliographic entry below):
- **[V]** = title/authors/venue and/or technical content were checked against a primary page during this research session (link given).
- **[K]** = bibliographic details (volume/pages/DOI) come from the researcher's prior bibliographic knowledge and are linked via the DOI resolver, but were NOT re-fetched in this session. The DOI should be resolved once before submission. Technical summaries of [K] items are standard, widely restated results but should be checked against the paper before being quoted as a theorem.

---

## Q1. Predictive safety filters (PSF): recursive feasibility theorems and assumptions

### Takeaway
A PSF solves a finite-horizon problem "min ||u_0 - u_des||" subject to the nominal dynamics, state/input constraints and a terminal constraint x_N in S_f with S_f a control-invariant subset of the constraints; the shifted-sequence-plus-terminal-backup argument gives recursive feasibility, and hence constraint satisfaction for all time, for *any* desired input u_des. That is the formal basis for "safety invariant to an arbitrary planner". Soft-constrained and predictive-CBF variants keep the problem always feasible and recover from infeasibility. Probabilistic variants deal with stochastic model error.

### Cited Findings
- **PSF definition (CSM 2023 survey).** At each step k the PSF chooses the input sequence closest to the desired input, subject to: the prediction starts at the current state, follows the discrete-time dynamics, satisfies the state and input constraints, and ends in a terminal safe set. Only the first input is applied. The system never has to follow the backup plan; it only has to remain able to reach the terminal set. — [Wabersich et al., CSM preprint (NSF PAR)](https://par.nsf.gov/servlets/purl/10473415) [V]
- **Recursive feasibility conditions (exact structure).** (i) The terminal set must be a *discrete-time control-invariant* subset of the state constraints: for every x in S_f there is an admissible u with f(x,u) in S_f (an equilibrium is a trivial choice; CLF-based sets are larger). (ii) Shift argument: feasibility at k−1 implies that the tail of the previous optimal sequence, plus one admissible input keeping the state in S_f, is feasible at k. By induction, initial feasibility implies feasibility and constraint satisfaction for all k. (iii) The feasible set of the PSF problem is itself control invariant, so no explicit safe-set representation is needed. — [Wabersich et al., CSM preprint](https://par.nsf.gov/servlets/purl/10473415) [V]
- **Soft-constrained PSF.** Slack variables relax the state and terminal constraints, and the cost penalises them (quadratic plus linear). The problem is feasible for every state. With a large enough linear (exact-penalty) weight the slacks are zero whenever the hard problem is feasible. However, the slacks are *not* guaranteed to vanish in closed loop, so the system can leave the implicit safe set. — [Wabersich et al., CSM preprint](https://par.nsf.gov/servlets/purl/10473415) [V]
- **Predictive control barrier functions (PCBF).** An auxiliary soft-constrained predictive problem is always feasible and *asymptotically stabilises the feasible set* of the original PSF, which gives a recovery mechanism. It is built from "a simple constraint tightening combined with a terminal control barrier function", and the authors show the auxiliary problem is a discrete-time "predictive" CBF. arXiv:2105.10241 (v3 2022). — [arXiv abs](https://arxiv.org/abs/2105.10241v3) [V for content]. Published as IEEE TAC 68(5):2638–2651, 2023, doi:[10.1109/TAC.2022.3175628](https://doi.org/10.1109/TAC.2022.3175628) [K]
- **Nonlinear PSF (the Automatica paper).** Wabersich & Zeilinger, "A predictive safety filter for learning-based control of constrained nonlinear dynamical systems", Automatica 129:109597, 2021, doi:[10.1016/j.automatica.2021.109597](https://doi.org/10.1016/j.automatica.2021.109597), arXiv:1812.05506 [K]. Handles nonlinear dynamics with a learned/uncertain model through a tube-based tightening around a nominal model and a terminal safe set. It is listed in the [ETH Research Collection](https://research-collection.ethz.ch/handle/20.500.11850/534919?show=full) [V, existence only].
- **Linear PSF (2018).** Wabersich & Zeilinger, "Linear model predictive safety certification for learning-based control", IEEE CDC 2018, pp. 7130–7135, doi:[10.1109/CDC.2018.8619829](https://doi.org/10.1109/CDC.2018.8619829), arXiv:1803.08552 [K]. It uses a tube-MPC-style tightening for linear systems with bounded disturbance.
- **Probabilistic PSF.** Wabersich, Hewing, Carron, Zeilinger, "Probabilistic model predictive safety certification for learning-based control", IEEE TAC 67(1):176–188, 2022, doi:[10.1109/TAC.2021.3049335](https://doi.org/10.1109/TAC.2021.3049335), arXiv:1906.10417 [K]. It gives chance-constraint satisfaction with probabilistic reachable sets.
- **Application PSF (racing).** Tearle, Wabersich, Carron, Zeilinger, "A predictive safety filter for learning-based racing control", IEEE RA-L 6(4):7635–7642, 2021, arXiv:2102.11907 — [arXiv](https://arxiv.org/pdf/2102.11907) [V existence]; doi:[10.1109/LRA.2021.3097073](https://doi.org/10.1109/LRA.2021.3097073) [K]
- **Learning-based MPC review.** Hewing, Wabersich, Menner, Zeilinger, "Learning-based model predictive control: Toward safe learning in control", *Annual Review of Control, Robotics, and Autonomous Systems* 3:269–296, 2020, doi:[10.1146/annurev-control-090419-075625](https://doi.org/10.1146/annurev-control-090419-075625) [K]. NOTE: the venue is the *Annual Review of Control, Robotics, and Autonomous Systems*, not *Annual Reviews in Control* as the brief says.
- **Textbook for the formal MPC machinery.** Rawlings, Mayne, Diehl, *Model Predictive Control: Theory, Computation, and Design*, 2nd ed., Nob Hill Publishing, 2017, ISBN 978-0-9759377-3-0 [K]. It covers the standard recursive-feasibility, terminal-set and ISS theory used in PSF proofs.

### Inferences
- **The "arbitrary planner" theorem follows directly.** In every PSF/CBF-QP the planner's output u_des appears *only in the cost*, never in the constraints. The feasible set, and hence the recursive-feasibility induction, is therefore independent of u_des. The manuscript can state: *for every planner signal u_des: N → U (including adversarially chosen, history-dependent signals), if the PSF is feasible at x(0), the closed loop satisfies the constraints for all k.* The proof is the shift argument above, quantified universally over u_des. Two caveats should be stated explicitly. (1) The guarantee covers the *plant model* used in the filter; mismatch needs Q2. (2) The planner must not be able to alter the filter's state estimate, constraints or model; see Q6, where sensor-channel attacks break this.
- A soft-constrained PSF gives liveness of the *software* (always a solution), but under persistent mismatch it gives only practical/recovery guarantees (PCBF). The manuscript should say which one it claims.

### Gaps
- The exact theorem numbers and assumption lists in the 2021 Automatica PSF paper were not re-read this session (the arXiv full text was not fetched). Quote from the PDF before submission.
- arXiv:2401.11183 (Didier, Zanelli, Wabersich, Zeilinger, Jan 2024) appeared in search results, but its exact title was not confirmed. It may be a predictive stability filter or approximate-PCBF paper. Verify before citing.

---

## Q2. Simplex and runtime assurance (RTA), including UAV-specific RTA

### Takeaway
RTA comes in two families. Simplex switching (explicit/region-based or implicit/simulation-based) is "zero-order". ASIF/optimization filters (explicit CBF, or implicit backup-trajectory based) are "first-order", minimally invasive and smoother. Black-box Simplex removes the need to verify the backup controller by certifying backup trajectories at runtime. ASTM F3269 is the aviation RTA standard and is Simplex-based.

### Cited Findings
- **RTA taxonomy (Hobbs et al.).** In Simplex, a monitor and decision logic switch control from the primary controller to a verified backup controller. The switch is discrete, so the output can chatter, which hysteresis mitigates. *Explicit* Simplex uses a predefined invariant set and switches if the next state would leave it. *Implicit* Simplex simulates backup trajectories online, and "the backup controller does not need to be verified" for this to hold. ASIF is an optimisation filter (typically a QP) that returns the input closest to the desired one subject to barrier constraints. Explicit ASIF uses h(x) (a CBF); implicit ASIF uses the trajectories of a backup controller to a backup set. All variants can be latched or unlatched. — [Hobbs et al., arXiv:2110.03506](https://arxiv.org/abs/2110.03506) [V]. Published as Hobbs, Mote, Abate, Coogan, Feron, "Runtime assurance for safety-critical systems: An introduction to safety filtering approaches for complex control systems", IEEE Control Systems Magazine 43(2):28–65, 2023, doi:[10.1109/MCS.2022.3234380](https://doi.org/10.1109/MCS.2022.3234380) [K]
- **ASTM F3269.** It is the first ASTM standard for RTA in unmanned aircraft and is based on the Simplex architecture. A later iteration "opens the door" to filtering RTA designs and shows multiple recovery functions at the same level of the control hierarchy. — [Hobbs et al.](https://arxiv.org/abs/2110.03506) [V]. The standard is F3269-21, "Standard Practice for Methods to Safely Bound Behavior of Aircraft Systems Containing Complex Functions Using Run-Time Assurance", active, last updated 19 Nov 2021, superseding F3269-17. — [ASTM store F3269-21](https://store.astm.org/f3269-21.html); [F3269-17](https://store.astm.org/f3269-17.html); [BSI listing](https://knowledge.bsigroup.com/products/standard-practice-for-methods-to-safely-bound-behavior-of-aircraft-systems-containing-complex-functions-using-run-time-assurance) [V]
- **Black-box Simplex.** Mehmood, Sheikhi, Bak, Smolka, Stoller, "The Black-Box Simplex Architecture for Runtime Assurance of Autonomous CPS", arXiv:2102.12981 — [arXiv](https://arxiv.org/abs/2102.12981v3) [V existence]. Published in NASA Formal Methods (NFM) 2022, LNCS 13260, pp. 231–250, doi:[10.1007/978-3-031-06773-0_12](https://doi.org/10.1007/978-3-031-06773-0_12) [K]. Core idea: both the advanced and backup controllers are black boxes. At each step the decision module checks at runtime that a proposed command plus the backup's continuation produces a verified safe trajectory (a "certificate"), and it keeps the last valid certificate to fall back on. This is the closest architectural match to "untrusted planner plus fallback" [K, summary].
- **Original Simplex.** Seto, Krogh, Sha, Chutinan, "The Simplex architecture for safe online control system upgrades", Proc. ACC 1998, vol. 6, pp. 3504–3508, doi:[10.1109/ACC.1998.703255](https://doi.org/10.1109/ACC.1998.703255) [K]. Sha, "Using simplicity to control complexity", IEEE Software 18(4):20–28, 2001, doi:[10.1109/MS.2001.936213](https://doi.org/10.1109/MS.2001.936213) [K]. The classic recovery region is a Lyapunov sublevel set {x: xᵀPx ≤ 1} inside the constraints under the verified safety controller (LMI design).
- **Sandboxing / real-time reachability Simplex.** Bak, Manamcheri, Mitra, Caccamo, "Sandboxing controllers for cyber-physical systems", ICCPS 2011, pp. 3–12, doi:[10.1109/ICCPS.2011.25](https://doi.org/10.1109/ICCPS.2011.25) [K]. Bak, Johnson, Caccamo, Sha, "Real-time reachability for verified Simplex design", RTSS 2014, doi:[10.1109/RTSS.2014.21](https://doi.org/10.1109/RTSS.2014.21) [K]
- **ASIF / backup CBFs.** Gurriet, Mote, Ames, Feron, "An online approach to active set invariance", CDC 2018, pp. 3592–3599, doi:[10.1109/CDC.2018.8619139](https://doi.org/10.1109/CDC.2018.8619139) [K]. Gurriet, Mote, Singletary, Nilsson, Feron, Ames, "A scalable safety critical control framework for nonlinear systems", IEEE Access 8:187249–187275, 2020, doi:[10.1109/ACCESS.2020.3025248](https://doi.org/10.1109/ACCESS.2020.3025248) — existence confirmed in [Caltech Authors](https://resolver.caltech.edu/CaltechAUTHORS:20200925-104734853) and [DOAJ (IEEE Access, 2020)](https://doaj.org/article/5cd11f0ddc8b4f6a9ebf14c88d4d727e) [V existence; DOI K]. Chen, Jankovic, Santillo, Ames, "Backup control barrier functions: Formulation and comparative study", CDC 2021, doi:[10.1109/CDC45484.2021.9683111](https://doi.org/10.1109/CDC45484.2021.9683111), arXiv:2104.11332 [K]. Mechanism: the safe set is implicitly S = {x: φ^{u_b}(τ,x) ∈ S_safe for all τ ∈ [0,T], φ^{u_b}(T,x) ∈ S_b}, where S_b is a small invariant backup set under backup law u_b. CBF constraints are imposed on sampled points of the backup flow, using its sensitivity matrix.
- **UAV / aerospace RTA.** Schierman et al., "Runtime assurance for autonomous aerospace systems", Journal of Guidance, Control, and Dynamics 43(12):2205–2217, 2020, doi:[10.2514/1.G004862](https://doi.org/10.2514/1.G004862) [K]. AFRL-funded Schierman/Barron Associates RTA framework for adaptive flight control (AFRL technical report, 2015) [K; report number not verified]. A collection chapter on aerospace RTA, [doi:10.1007/978-3-030-55754-6_21](https://dx.doi.org/10.1007/978-3-030-55754-6_21), surfaced alongside F3269 searches [V existence only; content not read].

### Inferences
- For a fleet with an untrusted planner, implicit ASIF with backup CBFs, or Black-box Simplex, avoids having to compute an explicit invariant set in 12×12-dimensional state space. The certificate is a short backup trajectory per UAV (e.g., brake-to-hover).
- "Induced fallback rate" maps naturally onto Simplex switching frequency. For ASIF it maps to the fraction of steps where the barrier constraint is active.

### Gaps
- No primary source was retrieved for NASA-specific UAS RTA (e.g., NASA "Expandable Variable Autonomy Architecture"/EVAA, or ICAROUS). Verify independently if needed.

---

## Q3. Control barrier functions: robust, ISSf, backup, multi-agent, and CBF-QP vs MPC-CBF

### Takeaway
The CBF condition sup_u [L_f h + L_g h u] ≥ −α(h) gives forward invariance of C = {h ≥ 0}. The CBF-QP is the pointwise min-norm filter on u_des. Robust and ISSf variants give either exact invariance under a disturbance bound or invariance of an inflated set C_δ with δ = γ(||d||∞). Pairwise multi-agent CBFs (Wang–Ames–Egerstedt) scale to swarms. A discrete-time CBF can be embedded in an MPC (Zeng et al.) as a predictive alternative.

### Cited Findings (all [K] unless noted)
- Ames, Xu, Grizzle, Tabuada, "Control barrier function based quadratic programs for safety critical systems", IEEE TAC 62(8):3861–3876, 2017, doi:[10.1109/TAC.2016.2638961](https://doi.org/10.1109/TAC.2016.2638961). Zeroing CBF: if h is a ZCBF with extended class-K α, any Lipschitz u(x) ∈ K_cbf(x) = {u: L_f h + L_g h u + α(h) ≥ 0} renders C forward invariant, and C is asymptotically stable when h < 0 (robustness).
- Ames, Coogan, Egerstedt, Notomista, Sreenath, Tabuada, "Control barrier functions: Theory and applications", ECC 2019, pp. 3420–3431, doi:[10.23919/ECC.2019.8796030](https://doi.org/10.23919/ECC.2019.8796030).
- Xu, Tabuada, Grizzle, Ames, "Robustness of control barrier functions for safety critical control", IFAC-PapersOnLine 48(27):54–61, 2015, doi:[10.1016/j.ifacol.2015.11.152](https://doi.org/10.1016/j.ifacol.2015.11.152). Under model perturbation, ZCBF controllers keep the state in a *larger* set C_δ, with the size determined by the perturbation bound.
- Kolathaya & Ames, "Input-to-state safety with control barrier functions", IEEE Control Systems Letters 3(1):108–113, 2019, doi:[10.1109/LCSYS.2018.2853698](https://doi.org/10.1109/LCSYS.2018.2853698). For ẋ = f + g(u + d), the ISSf-CBF condition L_f h + L_g h u ≥ −α(h) + ||L_g h||²/ε makes C_δ = {h ≥ −γ(||d||∞)} forward invariant, with γ explicit in ε.
- Alan, Taylor, He, Orosz, Ames, "Safe controller synthesis with tunable input-to-state safe control barrier functions", IEEE L-CSS 6:908–913, 2022, doi:[10.1109/LCSYS.2021.3087443](https://doi.org/10.1109/LCSYS.2021.3087443). The ε(h) tuning reduces conservatism away from the boundary.
- Jankovic, "Robust control barrier functions for constrained stabilization of nonlinear systems", Automatica 96:359–367, 2018, doi:[10.1016/j.automatica.2018.07.004](https://doi.org/10.1016/j.automatica.2018.07.004).
- Agrawal & Sreenath, "Discrete control barrier functions for safety-critical control of discrete systems with application to bipedal robot navigation", RSS 2017, doi:[10.15607/RSS.2017.XIII.073](https://doi.org/10.15607/RSS.2017.XIII.073). DT-CBF condition: h(x_{k+1}) ≥ (1−γ)h(x_k), with γ ∈ (0,1].
- Zeng, Zhang, Sreenath, "Safety-critical model predictive control with discrete-time control barrier function", ACC 2021, pp. 3882–3889, doi:[10.23919/ACC50511.2021.9483029](https://doi.org/10.23919/ACC50511.2021.9483029), arXiv:2007.11718. Compared with MPC using distance constraints (MPC-DC), MPC-CBF achieves safety with a *shorter horizon*, because the DT-CBF constraint enforces safety beyond the horizon. Compared with a one-step CBF-QP, it is less myopic.
- **Multi-agent / swarm.** Borrmann, Wang, Ames, Egerstedt, "Control barrier certificates for safe swarm behavior", IFAC ADHS 2015, IFAC-PapersOnLine 48(27):68–73, doi:[10.1016/j.ifacol.2015.11.154](https://doi.org/10.1016/j.ifacol.2015.11.154). Wang, Ames, Egerstedt, "Safety barrier certificates for collisions-free multirobot systems", IEEE T-RO 33(3):661–674, 2017, doi:[10.1109/TRO.2017.2659727](https://doi.org/10.1109/TRO.2017.2659727). Pairwise h_ij for double integrators with acceleration bounds; decentralised QP with each agent taking half of the pairwise constraint. Wang, Ames, Egerstedt, "Safe certificate-based maneuvers for teams of quadrotors using differential flatness", ICRA 2017, pp. 3293–3298, doi:[10.1109/ICRA.2017.7989375](https://doi.org/10.1109/ICRA.2017.7989375).
- **Learned graph CBFs for large swarms.** Zhang, So, Garg, Fan, "GCBF+: A neural graph control barrier function framework for distributed safe multi-agent control", arXiv:2401.14554, IEEE T-RO 2025 [K; DOI not verified].

### Inferences
- **Mapping to the parent model's Lipschitz constant L.** If the model error satisfies ||f_true(x,u) − f_model(x,u)|| ≤ w̄, then for a CBF with Lipschitz gradient one can bound |ḣ_true − ḣ_model| ≤ ||∇h|| w̄. Replacing α(h) with α(h) − ||∇h|| w̄ (a robust CBF) gives exact invariance. ISSf instead gives inflated-set invariance without needing w̄ in the filter.

### Gaps
- No quantitative CBF-QP vs MPC-CBF solve-time table was retrieved for quadrotors.

---

## Q4. Robust / tube MPC for model-plant mismatch and bounded disturbances

### Takeaway
There are three standard ways to carry a mismatch margin. (1) Linear tube MPC: tighten by an RPI set, X ⊖ Z with Z = mRPI of x⁺ = (A+BK)x + w. (2) Chisci-style tightening by reachable sets of the disturbance under a fixed feedback. (3) Nonlinear Lipschitz/incremental-stability tightening: either the Limón et al. Σ L^i tightening, which uses the open-loop Lipschitz constant L directly (conservative if L > 1), or the Köhler et al. tightening with contraction rate ρ < 1 (tube s_{k+1} = ρ s_k + w̄).

### Cited Findings
- **Köhler, Soloperto, Müller, Allgöwer** (arXiv:1910.12081). Assumption 2 (local incremental stabilisability): there exist κ and an incremental Lyapunov function V_δ with c_{δ,l}||x−z||² ≤ V_δ ≤ c_{δ,u}||x−z||² and V_δ(x⁺,z⁺,v⁺) ≤ ρ² V_δ(x,z,v), ρ ∈ (0,1). The offline design needs only the scalars (ρ, c_{δ,l}, c_{δ,u}, δ_loc, κ_max, c_j). Tube dynamics: s_{k+1} = ρ s_k + w_k. Tightened constraints: g_j(x_{k|t},u_{k|t}) + c_j s_{k|t} ≤ 0. For constant additive disturbance: g_j + c_j·((1−ρ^k)/(1−ρ))·w̄ ≤ 0, with w̄ = sup √V_δ(f(z,v)+d_w, f(z,v), v⁺). Theorem 1: under Assumptions 1–6, initial feasibility implies recursive feasibility, constraint satisfaction, and practical asymptotic stability of the origin. — [arXiv:1910.12081](https://arxiv.org/pdf/1910.12081) [V]. Published in IEEE TAC 66(2):794–801, 2021, doi:[10.1109/TAC.2020.2982585](https://doi.org/10.1109/TAC.2020.2982585) [K]
- Köhler, Müller, Allgöwer, "A novel constraint tightening approach for nonlinear robust model predictive control", ACC 2018, pp. 728–734, doi:[10.23919/ACC.2018.8431439](https://doi.org/10.23919/ACC.2018.8431439) [K]. The conference precursor; it improves on Lipschitz-based tightening by using incremental stability.
- Limón Marruedo, Álamo, Camacho, "Input-to-state stable MPC for constrained discrete-time nonlinear systems with bounded additive uncertainties", CDC 2002, pp. 4619–4624, doi:[10.1109/CDC.2002.1185106](https://doi.org/10.1109/CDC.2002.1185106) [K]. Lipschitz-based tightening X_j = X ⊖ B(μ Σ_{i=0}^{j−1} L^i), where L is the Lipschitz constant of the model and μ the disturbance bound. This applies *directly* when the parent model gives a constant L, but the margin grows geometrically when L > 1.
- Mayne, Seron, Raković, "Robust model predictive control of constrained linear systems with bounded disturbances", Automatica 41(2):219–224, 2005, doi:[10.1016/j.automatica.2004.08.019](https://doi.org/10.1016/j.automatica.2004.08.019) [K]. Tube MPC: u = v + K(x − z), with z the nominal state. Constraints are tightened by an RPI set Z; robust exponential stability of Z holds.
- Chisci, Rossiter, Zappa, "Systems with persistent disturbances: predictive control with restricted constraints", Automatica 37(7):1019–1028, 2001, doi:[10.1016/S0005-1098(01)00051-6](https://doi.org/10.1016/S0005-1098(01)00051-6) [K]. Tightening X_k = X ⊖ ⊕_{i=0}^{k−1}(A+BK)^i W.
- Raković, Kerrigan, Kouramas, Mayne, "Invariant approximations of the minimal robust positively invariant set", IEEE TAC 50(3):406–410, 2005, doi:[10.1109/TAC.2005.843854](https://doi.org/10.1109/TAC.2005.843854) [K].
- Mayne, Kerrigan, van Wyk, Falugi, "Tube-based robust nonlinear model predictive control", Int. J. Robust Nonlinear Control 21(11):1341–1353, 2011, doi:[10.1002/rnc.1758](https://doi.org/10.1002/rnc.1758) [K].

### Inferences
- **Recommended for the manuscript.** Write the plant as x⁺ = f̂(x,u) + w, with ||w|| ≤ w̄ ("model-mismatch margin"). If only a Lipschitz constant L of f̂ is available, use the Limón tightening ε_k = w̄ Σ_{i<k} L^i. If a stabilising tracking feedback (e.g., quadrotor position/attitude controller) gives contraction ρ < 1, use Köhler's ε_k = c_j w̄ (1−ρ^k)/(1−ρ) ≤ c_j w̄/(1−ρ), which stays bounded in the horizon. Either one, inserted into the PSF of Q1 with a robust control-invariant terminal set, gives the "safe for any planner AND any w with ||w|| ≤ w̄" theorem.

### Gaps
- Not retrieved: UAV-specific robust PSF results with measured w̄ (e.g., Crazyflie model-mismatch identification).

---

## Q5. Hamilton–Jacobi reachability safety filters and the unified view

### Takeaway
HJ reachability yields the maximal robust control-invariant set (the zero super-level set of the value function V) under worst-case disturbance. The least-restrictive filter applies u_des whenever V(x) > ε and switches to the optimal safe control on the boundary (Fisac et al. 2019). Hsu, Hu & Fisac (2024) unify HJ, CBF and PSF filters as "monitor plus intervention" and formalise least-restrictive vs. smooth (minimally invasive) filtering.

### Cited Findings
- Hsu, Hu, Fisac, "The safety filter: A unified view of safety-critical control in autonomous systems", Annual Review of Control, Robotics, and Autonomous Systems, 2024, doi:10.1146/annurev-control-071723-102940; arXiv:2309.05837 — [Annual Reviews](https://annualreviews.org/doi/abs/10.1146/annurev-control-071723-102940); [arXiv](https://arxiv.org/abs/2309.05837v1); [Princeton](https://collaborate.princeton.edu/en/publications/the-safety-filter-a-unified-view-of-safety-critical-control-in-au/) [V existence; volume 7 pp. 47–72 is K].
- Fisac, Akametalu, Zeilinger, Kaynama, Gillula, Tomlin, "A general safety framework for learning-based control in uncertain robotic systems", IEEE TAC 64(7):2737–2752, 2019, doi:[10.1109/TAC.2018.2876389](https://doi.org/10.1109/TAC.2018.2876389) [K]. Least-restrictive switching filter on the robust safe set, computed by HJ against a disturbance set D. D is learned online with GP confidence bounds, and the set is recomputed when the data falsify the bound.
- Bansal, Chen, Herbert, Tomlin, "Hamilton–Jacobi reachability: A brief overview and recent advances", CDC 2017, pp. 2242–2253, doi:[10.1109/CDC.2017.8263977](https://doi.org/10.1109/CDC.2017.8263977) [K].
- Mitchell, Bayen, Tomlin, "A time-dependent Hamilton–Jacobi formulation of reachable sets for continuous dynamic games", IEEE TAC 50(7):947–957, 2005, doi:[10.1109/TAC.2005.851439](https://doi.org/10.1109/TAC.2005.851439) [K].
- Herbert, Chen, Han, Bansal, Fisac, Tomlin, "FaSTrack: A modular framework for fast and guaranteed safe motion planning", CDC 2017, pp. 1517–1522, doi:[10.1109/CDC.2017.8263867](https://doi.org/10.1109/CDC.2017.8263867) [K]. This is *highly relevant*. HJ is solved offline on relative (tracker − planner) dynamics and gives a tracking-error bound (TEB) that holds for *any* planner trajectory in a planning model. Obstacles are then inflated by the TEB. It is planner-agnostic by construction.
- Choi, Lee, Sreenath, Tomlin, Herbert, "Robust control barrier–value functions for safety-critical control", CDC 2021, doi:[10.1109/CDC45484.2021.9683085](https://doi.org/10.1109/CDC45484.2021.9683085) [K]. This bridges HJ and CBF.
- Hsu, Ren, Nguyen, Majumdar, Fisac, "Sim-to-Lab-to-Real: Safe reinforcement learning with shielding and generalization guarantees", Artificial Intelligence 314:103811, 2023, doi:[10.1016/j.artint.2022.103811](https://doi.org/10.1016/j.artint.2022.103811) [K].

### Inferences
- FaSTrack's quantifier structure ("for every planner trajectory, the tracking error stays in the TEB") is the closest existing template for the "arbitrary planner" theorem when the planner emits references rather than inputs.

### Gaps
- HJ grid methods do not scale to 12 coupled UAVs. Only pairwise or decomposed HJ is practical. No fleet-scale HJ timing data was retrieved.

---

## Q6. Liveness, conservatism, deadlock and "induced fallback rate"

### Takeaway
Minimal-intervention CBF-QP filters can create *spurious asymptotically stable equilibria* on the boundary of the safe set, even for linear systems with one convex obstacle (Reis et al.). In multi-robot settings they cause deadlock, analysed as a property of the QP's KKT conditions (Grover et al.). Recent work characterises undesired equilibria, limit cycles and unbounded trajectories induced by CBF filters. These results give a formal handle on "filter-induced denial/fallback".

### Cited Findings
- Reis, Aguiar, Tabuada, "Control barrier function based quadratic programs introduce undesirable asymptotically stable equilibria", IEEE Control Systems Letters (L-CSS) 5(2):731–736, 2021, doi:10.1109/LCSYS.2020.3004797, arXiv:2003.07819. CLF–CBF QPs can add closed-loop equilibria besides the CLF minimum, often on the boundary of the unsafe set. Explicit conditions are given for their asymptotic stability, and the effect occurs even for linear systems with one convex unsafe set. A modified QP unifying CLF and CBF removes the boundary equilibria. — [arXiv](https://arxiv.org/abs/2003.07819v3) [V; volume/pages K]
- Grover, Liu, Sycara, "Deadlock analysis and resolution for multi-robot systems", WAFR 2020 (Springer Proc. Advanced Robotics vol. 17), arXiv:1911.09146 — [arXiv](https://arxiv.org/pdf/1911.09146); [CMU RI](https://www.ri.cmu.edu/publications/deadlock-analysis-and-resolution-for-multi-robot-systems) [V existence]. Deadlock is characterised as equilibria of the CBF-QP closed loop with active constraints, with a geometric resolution strategy. Companion paper: "Why does symmetry cause deadlocks?" — [CMU RI](https://www.ri.cmu.edu/publications/why-does-symmetry-cause-deadlocks) [V existence].
- Mestres et al., arXiv:2501.09289 (2025), on CBF-based safety filters: characterisation of undesired equilibria, unbounded trajectories and limit cycles — [arXiv HTML](https://arxiv.org/html/2501.09289v1) [V existence; full author list/title not confirmed].
- arXiv:2402.08027 appeared under the query "undesired equilibria … safety filters" — [arXiv](https://arxiv.org/abs/2402.08027v1). It is likely the paper titled "On the undesired equilibria induced by control barrier function based safety filters" (believed to be Tan & Dimarogonas, 2024), but the title and authors were NOT verified.
- Stability analysis with multiple CBFs: arXiv:2503.15823 — [arXiv](https://arxiv.org/html/2503.15823v2) [V existence].
- **Least-restrictive vs. smooth.** Least-restrictive (switching) filters intervene only on the boundary of the maximal safe set but chatter. QP filters intervene earlier and continuously. — [Hobbs et al.](https://arxiv.org/abs/2110.03506) [V]; [Hsu et al.](https://arxiv.org/abs/2309.05837v1) [V existence]

### Inferences
- **Formalising "induced fallback rate".** Define, over a horizon T, FR = (1/T) Σ_k 1[||u_applied(k) − u_des(k)|| > η] (filter activity), or, for Simplex, the switching frequency. A useful structural lemma follows from Q1: if u_des(k) keeps x in the PSF feasible set with the tail of the previous plan, the filter returns u_des exactly (zero intervention). Therefore FR > 0 *only* when the planner proposes inputs that leave the robust viability kernel. FR thus measures the planner's "unsafety" plus the conservatism gap (maximal invariant set minus tightened feasible set). The conservatism gap shrinks as w̄ → 0 and as the horizon N grows.
- An adversarial planner can *force* FR → 1 (persistent denial). It cannot violate safety, but it can produce liveness failure or deadlock at boundary equilibria (Reis et al.; Grover et al.). The paper should separate safety (guaranteed) from liveness (not guaranteed against an adversary) and propose a liveness-recovery mode (e.g., a timeout to a mission-safe backup).

### Gaps
- No published, standardised "intervention rate" metric with theory was found. The definitions above are inferences.

---

## Q7. Safety filters under adversarial inputs and attacks

### Takeaway
The literature focuses on attacks on the *sensing* channel (false-data injection, spoofing), which *can* defeat CBF filters stealthily. Adversarial *reference/command* channels are covered implicitly, because filter guarantees are universal over u_des. Hence the threat model for an untrusted planner should assume the planner cannot touch the estimator.

### Cited Findings
- Arnström & Teixeira (Uppsala), "Stealthy deactivation of safety filters", arXiv:2403.17861 (code repository "ecc24-sf" suggests ECC 2024, not confirmed). A false-data injection on measurements biases the observer estimate deeper into the safe set, so the CBF filter accepts unsafe inputs. Closed form for 2-norm stealth: y^a = h(x̂) + δ Kᵀ∇h_S/||Kᵀ∇h_S||₂, which keeps the residual within the detector threshold δ. The attacker must know the observer gain K, the measurement map h, δ and the safety function. Countermeasure: a detector that thresholds alignment of residuals with ∇h_S (detected after about 0.2 s in a double-integrator example). — [arXiv](https://arxiv.org/abs/2403.17861) [V]
- "Data-driven and stealthy deactivation of safety filters", arXiv:2412.01346 (data-driven extension) — [arXiv](https://arxiv.org/pdf/2412.01346) [V existence].
- Tan, Sundar, Bruzzone, Ong, Lunardi, Andreoni, Tabuada, Ames, "Secure safety filter: Towards safe flight control under sensor attacks", arXiv:2505.06845. A secure state reconstructor produces a set of plausible states, and a robust CBF-QP stays safe over all of them. A reduced-order horizontal quadrotor model is used. PX4/Gazebo SITL and Holybro X500 hardware tests use constant/noise/scale/shift attacks. Feasibility under every attack is *not* guaranteed; on infeasibility the drone falls back to a zero-velocity command. — [arXiv](https://arxiv.org/abs/2505.06845) [V]
- "Computationally efficient safe control of linear systems under severe sensor attacks", arXiv:2502.20718 — [arXiv](https://arxiv.org/pdf/2502.20718) [V existence].
- Classical secure CPS [K]: Fawzi, Tabuada, Diggavi, "Secure estimation and control for cyber-physical systems under adversarial attacks", IEEE TAC 59(6):1454–1467, 2014, doi:[10.1109/TAC.2014.2303233](https://doi.org/10.1109/TAC.2014.2303233). Teixeira, Shames, Sandberg, Johansson, "A secure control framework for resource-limited adversaries", Automatica 51:135–148, 2015, doi:[10.1016/j.automatica.2014.10.067](https://doi.org/10.1016/j.automatica.2014.10.067).
- Shielding (RL) [K]: Alshiekh, Bloem, Ehlers, Könighofer, Niekum, Topcu, "Safe reinforcement learning via shielding", AAAI 2018, doi:[10.1609/aaai.v32i1.11797](https://doi.org/10.1609/aaai.v32i1.11797).

### Inferences
- The manuscript's threat model should be: the adversary controls u_des (or reference r) only, with arbitrary values and timing. The filter's state estimate, model, constraints and code are trusted (the TCB). Arnström & Teixeira show what fails if the estimator is also compromised. This is a clean, citable boundary of the claim.
- If the planner outputs *references* rather than inputs, the guarantee must be stated for the reference-to-input loop. FaSTrack (Q5) and reference governors are the right templates.

### Gaps
- No paper was found that analyses a safety filter specifically against an *adversarial reference/setpoint* generator with formal persistence/denial bounds. This appears to be an open niche that the manuscript can claim, but this was not exhaustively verified.

---

## Q8. Fast solvers and timings for fleet-scale real-time filtering

### Takeaway
QP-based filters (OSQP, HPIPM via acados) and decentralised per-UAV problems are the realistic route to 12 UAVs at 50–100 Hz. The only verified multi-drone timing is SwarmGPT's distributed safety filter: about 2.9 ms per drone with 10 drones and about 23.1 ms per drone with 200 drones, run at 8 Hz.

### Cited Findings
- SwarmGPT filter: a distributed multi-agent receding-horizon trajectory optimisation, solved independently per drone each step using neighbours' predicted positions. Constraints: position/speed bounds, collective thrust, ellipsoidal collision and downwash avoidance. Non-convex QCQP solved by alternating minimisation with polar reparameterisation, in JAX, centrally computed. ~2.9 ms/drone (10 drones), ~23.1 ms/drone (200 drones), recomputed at 8 Hz. Up to 200 drones in simulation and 20 Crazyflie 2.1 in hardware. — [Schuck et al., RA-L 2025 PDF](https://www.dynsyslab.org/wp-content/papercite-data/pdf/schuck-ral25.pdf) [V]
- Solver references [K]: Stellato, Banjac, Goulart, Bemporad, Boyd, "OSQP: an operator splitting solver for quadratic programs", Math. Prog. Comp. 12(4):637–672, 2020, doi:[10.1007/s12532-020-00179-2](https://doi.org/10.1007/s12532-020-00179-2). Verschueren et al., "acados—a modular open-source framework for fast embedded optimal control", Math. Prog. Comp. 14:147–183, 2022, doi:[10.1007/s12532-021-00208-8](https://doi.org/10.1007/s12532-021-00208-8). Andersson, Gillis, Horn, Rawlings, Diehl, "CasADi: a software framework for nonlinear optimization and optimal control", Math. Prog. Comp. 11(1):1–36, 2019, doi:[10.1007/s12532-018-0139-4](https://doi.org/10.1007/s12532-018-0139-4). Frison & Diehl, "HPIPM: a high-performance quadratic programming framework for model predictive control", IFAC-PapersOnLine 53(2):6563–6569, 2020, doi:[10.1016/j.ifacol.2020.12.073](https://doi.org/10.1016/j.ifacol.2020.12.073). Bemporad, Morari, Dua, Pistikopoulos, "The explicit linear quadratic regulator for constrained systems", Automatica 38(1):3–20, 2002, doi:[10.1016/S0005-1098(01)00174-1](https://doi.org/10.1016/S0005-1098(01)00174-1).
- Multi-UAV DMPC [K]: Luis & Schoellig, "Trajectory generation for multiagent point-to-point transitions via distributed model predictive control", IEEE RA-L 4(2):375–382, 2019, doi:[10.1109/LRA.2018.2890572](https://doi.org/10.1109/LRA.2018.2890572).

### Inferences
- For 12 UAVs, use one QP per UAV: a CBF-QP has 3–4 variables with 11 pairwise constraints plus box constraints. OSQP or a closed-form/active-set solver should give sub-millisecond solves. A per-UAV linearised PSF (horizon about 10–20, double-integrator model) in acados/HPIPM is plausibly about 1 ms. These numbers are *estimates* and must be benchmarked.

### Gaps
- No verified, peer-reviewed solve-time table for OSQP/acados CBF-QP or PSF on quadrotors was retrieved this session. Benchmarks must be run or cited from the solver papers.

---

## Q9. Recent (2024–2026) safety filters with learned or language-based planners for drones

### Takeaway
There is a clear 2025–2026 trend of LLM planners whose outputs pass through a CBF or MPC safety layer. SwarmGPT (RA-L 2025) is the strongest peer-reviewed drone-fleet example. SAFER and SAGE-LLM are arXiv preprints with CBF verification layers.

### Cited Findings
- Schuck, Dahanaggamaarachchi, Sprenger, Vyas, Zhou, Schoellig, "SwarmGPT: Combining large language models with safe motion planning for drone swarm choreography", IEEE RA-L 10(11), Nov 2025. LLM reference trajectories pass through an optimisation-based minimal-correction safety filter (no CBF). — [PDF](https://www.dynsyslab.org/wp-content/papercite-data/pdf/schuck-ral25.pdf) [V; DOI and pages not retrieved]
- Khan, Andrev, Murtaza, Aguilera, Zhang, Ding, Hutchinson, Anwar, "Safety aware task planning via large language models in robotics" (SAFER), arXiv:2503.15707, Mar 2025. A Safety Agent LLM gives feedback to the planner LLM, "LLM-as-a-Judge" scores safety violations, and CBFs are integrated for formal guarantees. Tested on heterogeneous robots (not drone-specific). — [arXiv](https://arxiv.org/abs/2503.15707v1) [V]
- Zhao, Zhao, Liu, Jiang, Ma, Li, Li, "SAGE-LLM: Towards safe and generalizable LLM controller with fuzzy-CBF verification and graph-structured knowledge retrieval for UAV decision", arXiv:2602.23719, Feb 2026. A fuzzy-CBF stage verifies LLM-proposed UAV actions ("provable safety certification for LLM outputs"), evaluated in pursuit-evasion. Implementation details of rejection/modification are unclear. — [arXiv](https://arxiv.org/abs/2602.23719) [V]
- Further 2026 related preprints surfaced but were not read: arXiv:2602.01226 — [link](https://arxiv.org/pdf/2602.01226); arXiv:2409.10283 — [link](https://www.arxiv.org/pdf/2409.10283); arXiv:2603.14403 (adversarial/safety filter topic) — [link](https://arxiv.org/html/2603.14403v1); arXiv:2607.28830 "Closed-loop model-based control barrier functions with application to robust flight envelope protection" — [link](https://arxiv.org/pdf/2607.28830); arXiv:2507.07805 "Tunable real-time safety filters via set-based control barrier functions" — [link](https://arxiv.org/pdf/2507.07805) [existence only].

### Inferences
- None of the verified LLM-drone works states a theorem universally quantified over an *adversarial* planner. They treat the LLM as error-prone, not adversarial. This is a positioning gap that Paper V can occupy.

### Gaps
- DOIs for SwarmGPT (RA-L 2025) were not retrieved. The contents of arXiv:2602.01226, 2409.10283 and 2603.14403 were not inspected.

---

## BibTeX (ready to paste; [K] fields should be DOI-resolved once before submission)

```bibtex
@article{wabersich2021psf,
  author={Wabersich, Kim P. and Zeilinger, Melanie N.},
  title={A predictive safety filter for learning-based control of constrained nonlinear dynamical systems},
  journal={Automatica}, volume={129}, pages={109597}, year={2021},
  doi={10.1016/j.automatica.2021.109597}, eprint={1812.05506}, archivePrefix={arXiv}}
@inproceedings{wabersich2018linear,
  author={Wabersich, Kim P. and Zeilinger, Melanie N.},
  title={Linear model predictive safety certification for learning-based control},
  booktitle={Proc. 57th IEEE Conf. Decision and Control (CDC)}, pages={7130--7135}, year={2018},
  doi={10.1109/CDC.2018.8619829}, eprint={1803.08552}, archivePrefix={arXiv}}
@article{wabersich2023pcbf,
  author={Wabersich, Kim P. and Zeilinger, Melanie N.},
  title={Predictive control barrier functions: Enhanced safety mechanisms for learning-based control},
  journal={IEEE Trans. Automatic Control}, volume={68}, number={5}, pages={2638--2651}, year={2023},
  doi={10.1109/TAC.2022.3175628}, eprint={2105.10241}, archivePrefix={arXiv}}
@article{wabersich2022probabilistic,
  author={Wabersich, Kim P. and Hewing, Lukas and Carron, Andrea and Zeilinger, Melanie N.},
  title={Probabilistic model predictive safety certification for learning-based control},
  journal={IEEE Trans. Automatic Control}, volume={67}, number={1}, pages={176--188}, year={2022},
  doi={10.1109/TAC.2021.3049335}, eprint={1906.10417}, archivePrefix={arXiv}}
@article{wabersich2023datadriven,
  author={Wabersich, Kim P. and Taylor, Andrew J. and Choi, Jason J. and Sreenath, Koushil and Tomlin, Claire J. and Ames, Aaron D. and Zeilinger, Melanie N.},
  title={Data-driven safety filters: {Hamilton-Jacobi} reachability, control barrier functions, and predictive methods for uncertain systems},
  journal={IEEE Control Systems Magazine}, volume={43}, number={5}, pages={137--177}, year={2023},
  doi={10.1109/MCS.2023.3291885}}
@article{tearle2021racing,
  author={Tearle, Ben and Wabersich, Kim P. and Carron, Andrea and Zeilinger, Melanie N.},
  title={A predictive safety filter for learning-based racing control},
  journal={IEEE Robotics and Automation Letters}, volume={6}, number={4}, pages={7635--7642}, year={2021},
  doi={10.1109/LRA.2021.3097073}, eprint={2102.11907}, archivePrefix={arXiv}}
@article{hewing2020mpclearning,
  author={Hewing, Lukas and Wabersich, Kim P. and Menner, Marcel and Zeilinger, Melanie N.},
  title={Learning-based model predictive control: Toward safe learning in control},
  journal={Annual Review of Control, Robotics, and Autonomous Systems}, volume={3}, pages={269--296}, year={2020},
  doi={10.1146/annurev-control-090419-075625}}
@book{rawlings2017mpc,
  author={Rawlings, James B. and Mayne, David Q. and Diehl, Moritz M.},
  title={Model Predictive Control: Theory, Computation, and Design}, edition={2nd},
  publisher={Nob Hill Publishing}, address={Madison, WI}, year={2017}, isbn={978-0-9759377-3-0}}
@inproceedings{seto1998simplex,
  author={Seto, Danbing and Krogh, Bruce and Sha, Lui and Chutinan, Alongkrit},
  title={The {Simplex} architecture for safe online control system upgrades},
  booktitle={Proc. American Control Conf. (ACC)}, volume={6}, pages={3504--3508}, year={1998},
  doi={10.1109/ACC.1998.703255}}
@article{sha2001simplex,
  author={Sha, Lui}, title={Using simplicity to control complexity},
  journal={IEEE Software}, volume={18}, number={4}, pages={20--28}, year={2001}, doi={10.1109/MS.2001.936213}}
@inproceedings{bak2011sandbox,
  author={Bak, Stanley and Manamcheri, Karthik and Mitra, Sayan and Caccamo, Marco},
  title={Sandboxing controllers for cyber-physical systems},
  booktitle={Proc. IEEE/ACM Int. Conf. Cyber-Physical Systems (ICCPS)}, pages={3--12}, year={2011},
  doi={10.1109/ICCPS.2011.25}}
@inproceedings{bak2014rtreach,
  author={Bak, Stanley and Johnson, Taylor T. and Caccamo, Marco and Sha, Lui},
  title={Real-time reachability for verified {Simplex} design},
  booktitle={Proc. IEEE Real-Time Systems Symp. (RTSS)}, year={2014}, doi={10.1109/RTSS.2014.21}}
@inproceedings{mehmood2022bbsimplex,
  author={Mehmood, Usama and Sheikhi, Sanaz and Bak, Stanley and Smolka, Scott A. and Stoller, Scott D.},
  title={The Black-Box {Simplex} Architecture for Runtime Assurance of Autonomous {CPS}},
  booktitle={NASA Formal Methods (NFM)}, series={LNCS}, volume={13260}, pages={231--250}, year={2022},
  doi={10.1007/978-3-031-06773-0_12}, eprint={2102.12981}, archivePrefix={arXiv}}
@inproceedings{gurriet2018online,
  author={Gurriet, Thomas and Mote, Mark and Ames, Aaron D. and Feron, Eric},
  title={An online approach to active set invariance},
  booktitle={Proc. IEEE CDC}, pages={3592--3599}, year={2018}, doi={10.1109/CDC.2018.8619139}}
@article{gurriet2020scalable,
  author={Gurriet, Thomas and Mote, Mark and Singletary, Andrew and Nilsson, Petter and Feron, Eric and Ames, Aaron D.},
  title={A scalable safety critical control framework for nonlinear systems},
  journal={IEEE Access}, volume={8}, pages={187249--187275}, year={2020}, doi={10.1109/ACCESS.2020.3025248}}
@inproceedings{chen2021backupcbf,
  author={Chen, Yuxiao and Jankovic, Mrdjan and Santillo, Mario and Ames, Aaron D.},
  title={Backup control barrier functions: Formulation and comparative study},
  booktitle={Proc. IEEE CDC}, pages={6835--6841}, year={2021},
  doi={10.1109/CDC45484.2021.9683111}, eprint={2104.11332}, archivePrefix={arXiv}}
@article{hobbs2023rta,
  author={Hobbs, Kerianne L. and Mote, Mark L. and Abate, Matthew C. L. and Coogan, Samuel D. and Feron, Eric M.},
  title={Runtime assurance for safety-critical systems: An introduction to safety filtering approaches for complex control systems},
  journal={IEEE Control Systems Magazine}, volume={43}, number={2}, pages={28--65}, year={2023},
  doi={10.1109/MCS.2022.3234380}, eprint={2110.03506}, archivePrefix={arXiv}}
@techreport{astm2021f3269,
  author={{ASTM International}},
  title={{ASTM F3269-21}: Standard Practice for Methods to Safely Bound Behavior of Aircraft Systems Containing Complex Functions Using Run-Time Assurance},
  institution={ASTM International}, address={West Conshohocken, PA}, year={2021}, doi={10.1520/F3269-21}}
@article{schierman2020rta,
  author={Schierman, John D. and DeVore, Michael D. and Richards, Nathan D. and Clark, Matthew A.},
  title={Runtime assurance for autonomous aerospace systems},
  journal={Journal of Guidance, Control, and Dynamics}, volume={43}, number={12}, pages={2205--2217}, year={2020},
  doi={10.2514/1.G004862}, note={Author list from memory; verify}}
@article{ames2017cbf,
  author={Ames, Aaron D. and Xu, Xiangru and Grizzle, Jessy W. and Tabuada, Paulo},
  title={Control barrier function based quadratic programs for safety critical systems},
  journal={IEEE Trans. Automatic Control}, volume={62}, number={8}, pages={3861--3876}, year={2017},
  doi={10.1109/TAC.2016.2638961}}
@inproceedings{ames2019cbf,
  author={Ames, Aaron D. and Coogan, Samuel and Egerstedt, Magnus and Notomista, Gennaro and Sreenath, Koushil and Tabuada, Paulo},
  title={Control barrier functions: Theory and applications},
  booktitle={Proc. European Control Conf. (ECC)}, pages={3420--3431}, year={2019}, doi={10.23919/ECC.2019.8796030}}
@article{xu2015robustness,
  author={Xu, Xiangru and Tabuada, Paulo and Grizzle, Jessy W. and Ames, Aaron D.},
  title={Robustness of control barrier functions for safety critical control},
  journal={IFAC-PapersOnLine}, volume={48}, number={27}, pages={54--61}, year={2015}, doi={10.1016/j.ifacol.2015.11.152}}
@article{kolathaya2019issf,
  author={Kolathaya, Shishir and Ames, Aaron D.},
  title={Input-to-state safety with control barrier functions},
  journal={IEEE Control Systems Letters}, volume={3}, number={1}, pages={108--113}, year={2019}, doi={10.1109/LCSYS.2018.2853698}}
@article{alan2022tunable,
  author={Alan, Anil and Taylor, Andrew J. and He, Chaozhe R. and Orosz, G{\'a}bor and Ames, Aaron D.},
  title={Safe controller synthesis with tunable input-to-state safe control barrier functions},
  journal={IEEE Control Systems Letters}, volume={6}, pages={908--913}, year={2022}, doi={10.1109/LCSYS.2021.3087443}}
@article{jankovic2018robust,
  author={Jankovic, Mrdjan},
  title={Robust control barrier functions for constrained stabilization of nonlinear systems},
  journal={Automatica}, volume={96}, pages={359--367}, year={2018}, doi={10.1016/j.automatica.2018.07.004}}
@inproceedings{agrawal2017dtcbf,
  author={Agrawal, Ayush and Sreenath, Koushil},
  title={Discrete control barrier functions for safety-critical control of discrete systems with application to bipedal robot navigation},
  booktitle={Robotics: Science and Systems (RSS)}, year={2017}, doi={10.15607/RSS.2017.XIII.073}}
@inproceedings{zeng2021mpccbf,
  author={Zeng, Jun and Zhang, Bike and Sreenath, Koushil},
  title={Safety-critical model predictive control with discrete-time control barrier function},
  booktitle={Proc. American Control Conf. (ACC)}, pages={3882--3889}, year={2021},
  doi={10.23919/ACC50511.2021.9483029}, eprint={2007.11718}, archivePrefix={arXiv}}
@article{borrmann2015swarm,
  author={Borrmann, Urs and Wang, Li and Ames, Aaron D. and Egerstedt, Magnus},
  title={Control barrier certificates for safe swarm behavior},
  journal={IFAC-PapersOnLine}, volume={48}, number={27}, pages={68--73}, year={2015}, doi={10.1016/j.ifacol.2015.11.154}}
@article{wang2017multirobot,
  author={Wang, Li and Ames, Aaron D. and Egerstedt, Magnus},
  title={Safety barrier certificates for collisions-free multirobot systems},
  journal={IEEE Trans. Robotics}, volume={33}, number={3}, pages={661--674}, year={2017}, doi={10.1109/TRO.2017.2659727}}
@inproceedings{wang2017quadrotors,
  author={Wang, Li and Ames, Aaron D. and Egerstedt, Magnus},
  title={Safe certificate-based maneuvers for teams of quadrotors using differential flatness},
  booktitle={Proc. IEEE ICRA}, pages={3293--3298}, year={2017}, doi={10.1109/ICRA.2017.7989375}}
@article{zhang2025gcbfplus,
  author={Zhang, Songyuan and So, Oswin and Garg, Kunal and Fan, Chuchu},
  title={{GCBF+}: A neural graph control barrier function framework for distributed safe multi-agent control},
  journal={IEEE Trans. Robotics}, year={2025}, eprint={2401.14554}, archivePrefix={arXiv}, note={DOI to verify}}
@article{mayne2005tube,
  author={Mayne, David Q. and Seron, Mar{\'\i}a M. and Rakovi{\'c}, Sa{\v s}a V.},
  title={Robust model predictive control of constrained linear systems with bounded disturbances},
  journal={Automatica}, volume={41}, number={2}, pages={219--224}, year={2005}, doi={10.1016/j.automatica.2004.08.019}}
@article{chisci2001,
  author={Chisci, Luigi and Rossiter, J. Anthony and Zappa, Giovanni},
  title={Systems with persistent disturbances: predictive control with restricted constraints},
  journal={Automatica}, volume={37}, number={7}, pages={1019--1028}, year={2001}, doi={10.1016/S0005-1098(01)00051-6}}
@article{rakovic2005mrpi,
  author={Rakovi{\'c}, Sa{\v s}a V. and Kerrigan, Eric C. and Kouramas, Konstantinos I. and Mayne, David Q.},
  title={Invariant approximations of the minimal robust positively invariant set},
  journal={IEEE Trans. Automatic Control}, volume={50}, number={3}, pages={406--410}, year={2005}, doi={10.1109/TAC.2005.843854}}
@article{mayne2011nonlineartube,
  author={Mayne, David Q. and Kerrigan, Eric C. and van Wyk, E. J. and Falugi, Paola},
  title={Tube-based robust nonlinear model predictive control},
  journal={Int. J. Robust and Nonlinear Control}, volume={21}, number={11}, pages={1341--1353}, year={2011}, doi={10.1002/rnc.1758}}
@inproceedings{limon2002iss,
  author={Lim{\'o}n Marruedo, Daniel and {\'A}lamo, Teodoro and Camacho, Eduardo F.},
  title={Input-to-state stable {MPC} for constrained discrete-time nonlinear systems with bounded additive uncertainties},
  booktitle={Proc. 41st IEEE CDC}, pages={4619--4624}, year={2002}, doi={10.1109/CDC.2002.1185106}}
@inproceedings{kohler2018tightening,
  author={K{\"o}hler, Johannes and M{\"u}ller, Matthias A. and Allg{\"o}wer, Frank},
  title={A novel constraint tightening approach for nonlinear robust model predictive control},
  booktitle={Proc. American Control Conf. (ACC)}, pages={728--734}, year={2018}, doi={10.23919/ACC.2018.8431439}}
@article{kohler2021robust,
  author={K{\"o}hler, Johannes and Soloperto, Raffaele and M{\"u}ller, Matthias A. and Allg{\"o}wer, Frank},
  title={A computationally efficient robust model predictive control framework for uncertain nonlinear systems},
  journal={IEEE Trans. Automatic Control}, volume={66}, number={2}, pages={794--801}, year={2021},
  doi={10.1109/TAC.2020.2982585}, eprint={1910.12081}, archivePrefix={arXiv}}
@inproceedings{bansal2017hj,
  author={Bansal, Somil and Chen, Mo and Herbert, Sylvia and Tomlin, Claire J.},
  title={{Hamilton-Jacobi} reachability: A brief overview and recent advances},
  booktitle={Proc. IEEE CDC}, pages={2242--2253}, year={2017}, doi={10.1109/CDC.2017.8263977}}
@article{mitchell2005hj,
  author={Mitchell, Ian M. and Bayen, Alexandre M. and Tomlin, Claire J.},
  title={A time-dependent {Hamilton-Jacobi} formulation of reachable sets for continuous dynamic games},
  journal={IEEE Trans. Automatic Control}, volume={50}, number={7}, pages={947--957}, year={2005}, doi={10.1109/TAC.2005.851439}}
@article{fisac2019general,
  author={Fisac, Jaime F. and Akametalu, Anayo K. and Zeilinger, Melanie N. and Kaynama, Shahab and Gillula, Jeremy and Tomlin, Claire J.},
  title={A general safety framework for learning-based control in uncertain robotic systems},
  journal={IEEE Trans. Automatic Control}, volume={64}, number={7}, pages={2737--2752}, year={2019}, doi={10.1109/TAC.2018.2876389}}
@inproceedings{herbert2017fastrack,
  author={Herbert, Sylvia L. and Chen, Mo and Han, SooJean and Bansal, Somil and Fisac, Jaime F. and Tomlin, Claire J.},
  title={{FaSTrack}: A modular framework for fast and guaranteed safe motion planning},
  booktitle={Proc. IEEE CDC}, pages={1517--1522}, year={2017}, doi={10.1109/CDC.2017.8263867}}
@inproceedings{choi2021cbvf,
  author={Choi, Jason J. and Lee, Donggun and Sreenath, Koushil and Tomlin, Claire J. and Herbert, Sylvia L.},
  title={Robust control barrier-value functions for safety-critical control},
  booktitle={Proc. IEEE CDC}, year={2021}, doi={10.1109/CDC45484.2021.9683085}}
@article{hsu2024safetyfilter,
  author={Hsu, Kai-Chieh and Hu, Haimin and Fisac, Jaime F.},
  title={The safety filter: A unified view of safety-critical control in autonomous systems},
  journal={Annual Review of Control, Robotics, and Autonomous Systems}, volume={7}, pages={47--72}, year={2024},
  doi={10.1146/annurev-control-071723-102940}, eprint={2309.05837}, archivePrefix={arXiv}}
@article{hsu2023sim2lab2real,
  author={Hsu, Kai-Chieh and Ren, Allen Z. and Nguyen, Duy Phuong and Majumdar, Anirudha and Fisac, Jaime F.},
  title={Sim-to-Lab-to-Real: Safe reinforcement learning with shielding and generalization guarantees},
  journal={Artificial Intelligence}, volume={314}, pages={103811}, year={2023}, doi={10.1016/j.artint.2022.103811}}
@article{reis2021undesired,
  author={Reis, Matheus F. and Aguiar, A. Pedro and Tabuada, Paulo},
  title={Control barrier function-based quadratic programs introduce undesirable asymptotically stable equilibria},
  journal={IEEE Control Systems Letters}, volume={5}, number={2}, pages={731--736}, year={2021},
  doi={10.1109/LCSYS.2020.3004797}, eprint={2003.07819}, archivePrefix={arXiv}}
@inproceedings{grover2020deadlock,
  author={Grover, Jaskaran Singh and Liu, Changliu and Sycara, Katia},
  title={Deadlock analysis and resolution for multi-robot systems},
  booktitle={Algorithmic Foundations of Robotics XIV (WAFR 2020)}, series={Springer Proc. Advanced Robotics}, volume={17}, year={2021},
  eprint={1911.09146}, archivePrefix={arXiv}}
@misc{mestres2025undesired,
  title={Control barrier function-based safety filters: characterization of undesired equilibria, unbounded trajectories, and limit cycles},
  author={Mestres, Pol and others}, year={2025}, eprint={2501.09289}, archivePrefix={arXiv}, note={Title/authors to verify}}
@inproceedings{arnstrom2024stealthy,
  author={Arnstr{\"o}m, Daniel and Teixeira, Andr{\'e} M. H.},
  title={Stealthy deactivation of safety filters},
  booktitle={Proc. European Control Conf. (ECC)}, year={2024}, eprint={2403.17861}, archivePrefix={arXiv}, note={Venue inferred; verify}}
@misc{tan2025securesf,
  author={Tan, Xiao and Sundar, Junior and Bruzzone, Renzo and Ong, Pio and Lunardi, Willian T. and Andreoni, Martin and Tabuada, Paulo and Ames, Aaron D.},
  title={Secure safety filter: Towards safe flight control under sensor attacks}, year={2025}, eprint={2505.06845}, archivePrefix={arXiv}}
@article{fawzi2014secure,
  author={Fawzi, Hamza and Tabuada, Paulo and Diggavi, Suhas},
  title={Secure estimation and control for cyber-physical systems under adversarial attacks},
  journal={IEEE Trans. Automatic Control}, volume={59}, number={6}, pages={1454--1467}, year={2014}, doi={10.1109/TAC.2014.2303233}}
@article{teixeira2015secure,
  author={Teixeira, Andr{\'e} and Shames, Iman and Sandberg, Henrik and Johansson, Karl H.},
  title={A secure control framework for resource-limited adversaries},
  journal={Automatica}, volume={51}, pages={135--148}, year={2015}, doi={10.1016/j.automatica.2014.10.067}}
@inproceedings{alshiekh2018shielding,
  author={Alshiekh, Mohammed and Bloem, Roderick and Ehlers, R{\"u}diger and K{\"o}nighofer, Bettina and Niekum, Scott and Topcu, Ufuk},
  title={Safe reinforcement learning via shielding},
  booktitle={Proc. AAAI Conf. Artificial Intelligence}, volume={32}, number={1}, year={2018}, doi={10.1609/aaai.v32i1.11797}}
@article{stellato2020osqp,
  author={Stellato, Bartolomeo and Banjac, Goran and Goulart, Paul and Bemporad, Alberto and Boyd, Stephen},
  title={{OSQP}: an operator splitting solver for quadratic programs},
  journal={Mathematical Programming Computation}, volume={12}, number={4}, pages={637--672}, year={2020}, doi={10.1007/s12532-020-00179-2}}
@article{verschueren2022acados,
  author={Verschueren, Robin and Frison, Gianluca and Kouzoupis, Dimitris and Frey, Jonathan and van Duijkeren, Niels and Zanelli, Andrea and Novoselnik, Branimir and Albin, Thivaharan and Quirynen, Rien and Diehl, Moritz},
  title={acados---a modular open-source framework for fast embedded optimal control},
  journal={Mathematical Programming Computation}, volume={14}, pages={147--183}, year={2022}, doi={10.1007/s12532-021-00208-8}}
@article{andersson2019casadi,
  author={Andersson, Joel A. E. and Gillis, Joris and Horn, Greg and Rawlings, James B. and Diehl, Moritz},
  title={{CasADi}: a software framework for nonlinear optimization and optimal control},
  journal={Mathematical Programming Computation}, volume={11}, number={1}, pages={1--36}, year={2019}, doi={10.1007/s12532-018-0139-4}}
@article{frison2020hpipm,
  author={Frison, Gianluca and Diehl, Moritz},
  title={{HPIPM}: a high-performance quadratic programming framework for model predictive control},
  journal={IFAC-PapersOnLine}, volume={53}, number={2}, pages={6563--6569}, year={2020}, doi={10.1016/j.ifacol.2020.12.073}}
@article{bemporad2002explicit,
  author={Bemporad, Alberto and Morari, Manfred and Dua, Vivek and Pistikopoulos, Efstratios N.},
  title={The explicit linear quadratic regulator for constrained systems},
  journal={Automatica}, volume={38}, number={1}, pages={3--20}, year={2002}, doi={10.1016/S0005-1098(01)00174-1}}
@article{luis2019dmpc,
  author={Luis, Carlos E. and Schoellig, Angela P.},
  title={Trajectory generation for multiagent point-to-point transitions via distributed model predictive control},
  journal={IEEE Robotics and Automation Letters}, volume={4}, number={2}, pages={375--382}, year={2019}, doi={10.1109/LRA.2018.2890572}}
@article{schuck2025swarmgpt,
  author={Schuck, Martin and Dahanaggamaarachchi, Dinushka Orrin and Sprenger, Ben and Vyas, Vedant and Zhou, Siqi and Schoellig, Angela P.},
  title={{SwarmGPT}: Combining large language models with safe motion planning for drone swarm choreography},
  journal={IEEE Robotics and Automation Letters}, volume={10}, number={11}, year={2025}, note={DOI/pages to verify}}
@misc{khan2025safer,
  author={Khan, Azal Ahmad and Andrev, Michael and Murtaza, Muhammad Ali and Aguilera, Sergio and Zhang, Rui and Ding, Jie and Hutchinson, Seth and Anwar, Ali},
  title={Safety aware task planning via large language models in robotics}, year={2025}, eprint={2503.15707}, archivePrefix={arXiv}}
@misc{zhao2026sagellm,
  author={Zhao, Wenzhe and Zhao, Yang and Liu, Ganchao and Jiang, Zhiyu and Ma, Dandan and Li, Zihao and Li, Xuelong},
  title={{SAGE-LLM}: Towards safe and generalizable {LLM} controller with fuzzy-{CBF} verification and graph-structured knowledge retrieval for {UAV} decision},
  year={2026}, eprint={2602.23719}, archivePrefix={arXiv}}
```
