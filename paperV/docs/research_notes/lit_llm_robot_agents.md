# LLM agents as robot/UAV planners, attacks on embodied LLM agents, and guardrails: literature map for Paper V

Provenance key, used throughout:
- **[V]**: verified this session by fetching the arXiv page or PDF. Claims and numbers come from that fetch.
- **[R]**: canonical arXiv id and venue recalled from prior knowledge and not re-fetched this session. The id is very likely correct, but check it before camera-ready.
- **[R?]**: recalled with lower confidence (id or title). Must be checked.
- **(preprint)**: no peer-reviewed venue was confirmed.

Blocked fetch: https://arxiv.org/abs/2410.13691 (RoboPAIR). The permission request timed out, so the RoboPAIR numbers below are recalled, apart from what RoboGuard reports about RoboPAIR.

---

## Q1. How LLMs are placed in robot and UAV planning loops

### Takeaway
LLMs enter the loop in three main ways:
- **Plan selector over a skill library:** SayCan, Inner Monologue, ProgPrompt.
- **Code or program writer that calls a robot API:** Code as Policies, ChatGPT for Robotics, TypeFly.
- **End-to-end action generator:** VLAs such as RT-2, OpenVLA, UAV-VLA and CognitiveDrone.

UAV work almost always uses the first two patterns. The LLM runs at roughly 0.1–1 Hz, or seconds per plan, above a conventional flight controller. Those controllers are the natural place for an LLM-independent safety filter that runs at control rate.

### Cited findings

**General robot LLM planners**
- SayCan [R]: an LLM scores candidate skills by "usefulness" and value functions score them by "affordance". The product of the two picks the next skill. Ahn et al., "Do As I Can, Not As I Say: Grounding Language in Robotic Affordances", CoRL 2022, arXiv:2204.01691. — [arXiv](https://arxiv.org/abs/2204.01691)
- Code as Policies [R]: the LLM writes Python policy code against perception and control APIs. Liang et al., ICRA 2023, arXiv:2209.07753. — [arXiv](https://arxiv.org/abs/2209.07753)
- ChatGPT for Robotics [R]: Vemprala, Bonatti, Bucker, Kapoor (Microsoft), arXiv:2306.17582, published in IEEE Access 12 (2024). It includes AirSim drone examples (inspection, obstacle-avoiding flight) and a real Tello drone. The paper explicitly keeps a human "in the loop" to inspect generated code before running it, which is a semantic and manual safeguard rather than a physical one. — [arXiv](https://arxiv.org/abs/2306.17582)
- Inner Monologue [R]: closed-loop replanning that feeds success detection and scene description back into the LLM. Huang et al., CoRL 2022, arXiv:2207.05608. — [arXiv](https://arxiv.org/abs/2207.05608)
- ProgPrompt [R]: programmatic prompts with assertions for situated task plans. Singh et al., ICRA 2023, arXiv:2209.11302. — [arXiv](https://arxiv.org/abs/2209.11302)
- VoxPoser [R]: an LLM/VLM composes 3D value maps that a motion planner uses for zero-shot trajectories. Huang et al., CoRL 2023, arXiv:2307.05973. — [arXiv](https://arxiv.org/abs/2307.05973)
- RT-2 [R]: a VLA that emits action tokens. Brohan et al., CoRL 2023, arXiv:2307.15818. From memory, the paper reports about 1–3 Hz for the 55B model and about 5 Hz for the 5B model, served from the cloud. Verify before citing. — [arXiv](https://arxiv.org/abs/2307.15818)
- OpenVLA [R]: Kim et al., CoRL 2024, arXiv:2406.09246. A 7B open VLA. — [arXiv](https://arxiv.org/abs/2406.09246)
- AutoRT [R]: Ahn et al. 2024, arXiv:2401.12963. A fleet-scale data-collection system whose LLM "robot constitution" (foundational, safety and embodiment rules) filters proposed tasks. It is a purely semantic, prompt-level filter. — [arXiv](https://arxiv.org/abs/2401.12963)

**UAV-specific LLM planners**
- TypeFly [V]: Chen, Yu, Zhong (Yale). arXiv:2312.14950 (preprint).
  - GPT-4 writes programs in a small DSL called MiniSpec for a Tello drone. Vision runs on an edge server, and only text goes to the cloud.
  - Planning latency is 1.0–5.7 s per task across 12 tasks. MiniSpec cuts output tokens by about 57% and planning time by about 54% compared with Python.
  - Its safety comes from a restricted language, a terminating program design, syntax and skill validation, and a user stop. Stabilization and obstacle avoidance are left to the drone. "Safety-aware task planning" is listed as future work.
  - [arXiv](https://arxiv.org/html/2312.14950v1)
- REAL [V]: Tagliabue, Kondo, Zhao, Peterson, Tewari, How (MIT). CoRL 2023, arXiv:2311.01403.
  - GPT-4 sits in the multirotor's mission-planning and control loop at about 0.1–1.0 Hz.
  - The LLM sets an additive term δu on an LQR (u = ū + K(x−x_ref) + δu), retunes the Q and R weights (the DARE is re-solved onboard), and can trigger emergency landing.
  - Because the LLM is slow, emergency landing handles loss of control.
  - This is the closest precedent for an LLM writing directly into the control law, and it has no LLM-independent safety filter.
  - [arXiv](https://arxiv.org/abs/2311.01403)
- UAV-VLA [R]: Sautenkov et al. 2025, arXiv:2501.05014 (HRI 2025 late-breaking report). Generates flight paths and action plans from satellite imagery plus language. — [arXiv](https://arxiv.org/abs/2501.05014)
- CognitiveDrone [R]: Lykov et al. 2025, arXiv:2503.01378 (preprint). A VLA for UAV cognitive tasks, with a reasoning VLM module, published with the CognitiveDroneBench simulation benchmark. — [arXiv](https://arxiv.org/abs/2503.01378)
- SAGE-LLM [V]: Zhao, Zhao, Liu, Jiang, Ma, Li, Li. arXiv:2602.23719, Feb 2026 (preprint).
  - A train-free two-layer architecture for UAV decisions: LLM high-level planning plus low-level control.
  - A "fuzzy CBF" verifies semantically augmented actions and claims "provable safety certification for LLM outputs". A graph-structured RAG supplies knowledge.
  - Evaluated in pursuit-evasion with unknown obstacles. The abstract mentions no adversarial or prompt-injection evaluation.
  - [arXiv](https://arxiv.org/abs/2602.23719)
- Surveys:
  - Javaid et al., "Large Language Models for UAVs: Current State and Pathways to the Future", arXiv:2405.01745 [R; IEEE Open J. Vehicular Technology 2024 per memory]. — [arXiv](https://arxiv.org/pdf/2405.01745)
  - Tian et al., "UAVs Meet LLMs: Overviews and Perspectives Towards Agentic Low-Altitude Mobility", arXiv:2501.02341 [R; Information Fusion 2025 per memory]. — [arXiv](https://arxiv.org/abs/2501.02341)
  - VLA review covering aerial robotics, arXiv:2607.06706 [title seen in search only]. — [arXiv](https://arxiv.org/pdf/2607.06706)
  - "Large Language Models in the Loop: A Stability- and Network-Aware Survey…", arXiv:2609.16599 [search only]. — [arXiv](https://arxiv.org/pdf/2609.16599)
  - "When control meets large language models: From words to dynamics", arXiv:2602.03433 [search only]. — [arXiv](https://arxiv.org/pdf/2602.03433)

**Latency and rate of LLMs in the loop**
- TypeFly: 1.0–5.7 s per plan with GPT-4, dominated by generation at about 100 ms per token. — [TypeFly](https://arxiv.org/html/2312.14950v1)
- REAL: 0.1–1.0 Hz LLM rate. — [REAL](https://arxiv.org/abs/2311.01403)
- Hafez et al.: LLM API rate limits capped updates at about 1.5 Hz, while the reachability filter ran in 0.04–0.22 s per step (about 4.5–25 Hz). — [arXiv 2503.03911](https://arxiv.org/html/2503.03911v1)
- Zhang et al. (UWA): LLM response time about 5.6 s per step, rising to 6.6–7.1 s with their prompt-level defence. — [arXiv 2509.02163](https://arxiv.org/html/2509.02163v1)

### Inferences
- Every UAV LLM system measured runs the LLM about 1–3 orders of magnitude slower than an attitude or position loop (100–1000 Hz). A predictive safety filter at control rate, between an asynchronous LLM planner and the low-level controller, therefore fits the existing architecture.
- REAL shows that LLMs are already given authority over control-law parameters (δu, Q and R). This widens the attack surface beyond waypoint selection, and a dynamics-aware filter (MPC or CBF) must also guard it.

### Gaps
- No systematic cross-paper latency table for VLAs on UAV hardware was found. The RT-2 Hz figures are recalled, not verified.
- PX4/Gazebo-based LLM drone papers were not specifically located in this pass.

---

## Q2. Known attacks on embodied LLM agents

### Takeaway
Jailbreaks (RoboPAIR, BadRobot, POEX), prompt injection through text or perception (Zhang et al. 2024, CHAI 2025/26), backdoors (TrojanRobot, BALD, Contextual Backdoor) and adversarial attacks on VLAs all reliably elicit unsafe physical actions, often with success rates above 70–90%.
- CHAI shows black-box physical indirect prompt injection against drone emergency landing and aerial tracking, using printed signs.
- These attacks target the LLM's semantic decision. None of them is constrained by a dynamics-level filter in the evaluated systems.

### Cited findings
- **RoboPAIR** [R; fetch blocked]: Robey, Ravichandran, Kumar, Hassani, Pappas, "Jailbreaking LLM-Controlled Robots", arXiv:2410.13691 (ICRA 2025 per memory). Attacked NVIDIA Dolphins (self-driving LLM), Clearpath Jackal + GPT-4o, and Unitree Go2. Reported success rates are near 100% (recalled).
  - RoboGuard's re-run [V] gives RoboPAIR ASR = 92.3% in simulation without guardrails, and 100% on a real Jackal. — [RoboGuard](https://www.alphaxiv.org/abs/2503.07885.md)
- **BadRobot** [R]: Zhang, H. et al., "BadRobot: Jailbreaking Embodied LLMs in the Physical World", arXiv:2407.20242 (ICLR 2025 per memory). Uses three vectors: contextual jailbreak, safety misalignment between language and action, and conceptual deception. The survey summary confirms the three vectors [V]. — [Survey 2601.02377](https://arxiv.org/pdf/2601.02377)
- **POEX** [R; listed in survey V]: Lu et al., arXiv:2412.16633. Adversarial suffixes optimized for *policy executability*, so that jailbreaks yield executable harmful robot policies. — [Survey](https://arxiv.org/pdf/2601.02377)
- **Adversarial vulnerabilities of VLAs** [R]: Wang et al., "Exploring the Adversarial Vulnerabilities of Vision-Language-Action Models in Robotics", arXiv:2411.13587 (ICCV 2025 per memory). Adversarial patches and objectives cause large drops in task success. — [arXiv](https://arxiv.org/abs/2411.13587)
- **Decision-level attacks (EIRAD)** [listed in survey V]: Liu et al., arXiv:2405.19802. GCG-based attacks on LLM-based embodied models. — [Survey](https://arxiv.org/pdf/2601.02377)
- **Embodied Red Teaming** [survey V]: arXiv:2411.18676. — [Survey](https://arxiv.org/pdf/2601.02377)
- **Backdoors** [survey V]:
  - Contextual Backdoor Attack, arXiv:2408.02882
  - TrojanRobot, arXiv:2411.11683
  - Robo-Troj, arXiv:2504.17070
  - BALD, arXiv:2405.20774 (word, scene and RAG triggers)
  - [Survey](https://arxiv.org/pdf/2601.02377)
- **Prompt injection on LLM mobile robots** [survey V]: Zhang et al., arXiv:2408.03515. Prompt and perception injection on LLM-integrated mobile robots. — [Survey](https://arxiv.org/pdf/2601.02377)
  - The follow-up by Zhang, Kong, Dewitt, Bräunl, Hong (UWA), arXiv:2509.02163 [V, preprint], evaluates Obvious Malicious Injection and Goal Hijacking Injection at attack rates of 0.3–1.0. Without defence, the GHI F1 score was 0.0. — [arXiv](https://arxiv.org/html/2509.02163v1)
- **CHAI** [V]: Burbano, Ortiz, Yang, Tu, Xie, Cardenas (UCSC), Sun, Cao (JHU), "CHAI: Command Hijacking against embodied AI", arXiv:2510.00181 (v2, Feb 2026). The page names no venue. Search results show a SaTML 2026 presentation PDF, which suggests it appeared at SaTML 2026, but this is unconfirmed.
  - **Threat model:** black-box physical *indirect prompt injection* through a printed sign or display in camera view. The attacker knows the task and system prompt but has no software access.
  - **Attack ASRs:**
    - CloudTrack aerial object tracking: up to 95.5%
    - DriveLM: up to 81.8%
    - Simulated drone emergency landing: up to 72.8%
    - Real robotic vehicle: at least 87%
  - Transferability averages above 70%. It is up to 10× more effective than SceneTAP and robust across lighting, languages and weather.
  - The paper evaluates no defences and calls for "provably robust defenses".
  - [arXiv](https://arxiv.org/html/2510.00181v2); [UCSC news](https://news.ucsc.edu/2026/01/misleading-text-can-hijack-ai-enabled-robots/); [SaTML slides](https://sos-vo.org/system/files/2026-04/satml_pres_0_0.pdf)
- **Drone physical-safety benchmark** [V]: Tang, Chen (IBM), Ho, "Defining and Evaluating Physical Safety for Large Language Models", arXiv:2411.02317 (preprint; no venue on the PDF).
  - **Dataset:** more than 400 drone-control instructions covering deliberate attacks, unintentional attacks, FAA Part-107 violations and utility. Code is executed in AirSim and scored by GPT-3.5 judges.
  - **Utility-safety trade-off:** GPT-3.5-turbo reaches 98.51% code fidelity and 93.75% utility, but only 12.50% self-assurance (refusal of harmful requests) and 31.25% regulatory compliance.
  - **Prompting helps:** in-context learning raises GPT-3.5 self-assurance to 87.20%.
  - **Scale helps:** CodeLlama self-assurance rises from 54.65% (7B) to 80.23% (34B).
  - **Unintentional attacks remain hard:** refusal is about 42% even at 13B and 34B.
  - [arXiv](https://arxiv.org/pdf/2411.02317v2); [project page](https://trustsafeai-llm-physical-safety.static.hf.space/)
- **Indirect prompt injection (general)** [R]: Greshake et al., "Not what you've signed up for…", AISec 2023, arXiv:2302.12173. The foundational threat model that CHAI extends to the physical world. — [arXiv](https://arxiv.org/abs/2302.12173)

### Inferences
- The threat model the Paper V filter needs, an untrusted LLM planner whose outputs are attacker-influenced through user prompts, tool or perception text, or physical signs, is well established by RoboPAIR, BadRobot and CHAI.
- CHAI already targets drone landing and tracking. It is the strongest UAV-specific motivation, and it explicitly leaves defences open.
- The Tang et al. finding that utility-strong LLMs refuse poorly, and that even large models refuse only about 42% of *unintentional* hazards, argues that alignment cannot be the safety mechanism.

### Gaps
- No attack paper found evaluates against a dynamics-level predictive filter (MPC or CBF). Attacks are measured only against undefended LLMs or semantic guardrails.
- No adaptive attack designed to defeat a physical safety filter was found. Examples would be steering the plan to the boundary of the safe set, or inducing liveness and denial-of-service failures through repeated filter interventions.
- Exact RoboPAIR per-platform ASRs were not verified (fetch blocked).

---

## Q3. Existing guardrails and safety layers for LLM-controlled robots

### Takeaway
Existing defences fall into four groups:
1. **Prompt or alignment hardening:** SafeEmbodAI, AutoRT constitution, NeMo Guardrails.
2. **LLM-judge or safety-agent oversight:** SAFER.
3. **Symbolic or temporal-logic plan verification:** Safety Chip, RoboGuard, SELP, nl2spec, AutoTAMP, conformal temporal-logic planning.
4. **Dynamics-level runtime filtering:** Hafez et al. reachability, SanDRA, SAFER's CBF, SAGE-LLM's fuzzy CBF, and the rule-based LiDAR gate in Zhang et al. 2025.

**Only RoboGuard evaluates against adaptive adversaries.** Its guarantee is semantic (LTL over a world model), and it still relies on a "root-of-trust" LLM to generate the specifications. The dynamics-level filters do give LLM-independent physical guarantees, but **none of them is evaluated against jailbreaks or prompt injection**. That combination is the gap Paper V fills.

### Cited findings (with the three questions from the brief: is the guarantee LLM-independent, is it tested against adaptive adversaries, and is the filtering semantic or physical)

- **RoboGuard** [V]: Ravichandran, Robey, Kumar, Pappas, Hassani, "Safety Guardrails for LLM-Enabled Robots", arXiv:2503.07885, accepted to IEEE RA-L, Feb 2026.
  - **How it works:** a root-of-trust LLM, shielded from user prompts, uses chain-of-thought to turn designer rules into LTL grounded in the semantic world model. A Büchi-automaton check then applies minimum-violation synthesis to the planner's plan.
  - **Results:**
    - RoboPAIR ASR: 92.3% → 2.3%
    - Template ASR: 82.3% → 0.9%
    - Adaptive RoboPAIR: 2.5% (black-box), 2.9% and 3.8% (gray-box), 5.2% (white-box)
    - Safe-task utility: 100%
    - Real Jackal: RoboPAIR success 100% → 0%
  - **Cost:** about 4,330 tokens and one LLM query per inference. No wall-clock timing is reported.
  - **Self-stated limitations:**
    - It needs an accurate world model, so corrupted perception can cause failures.
    - "LTL may not capture safety tied to system dynamics".
    - Specifications can be missed when the semantics are subtle.
  - **LLM-independent?** Partially. Synthesis is sound, but the specifications are LLM-generated.
  - **Adaptive?** Yes.
  - **Type:** semantic/temporal, not physical dynamics.
  - [arXiv](https://arxiv.org/pdf/2503.07885); [alphaXiv md](https://www.alphaxiv.org/abs/2503.07885.md)
- **Safe LLM-Controlled Robots with Formal Guarantees via Reachability Analysis** [V]: Hafez, Naderi Akhormeh, Hegazy, Alanwar (TUM), arXiv:2503.03911 (venue not stated on page).
  - **How it works:** data-driven reachability with constrained zonotopes, learned from 600 noisy offline steps. Collision checks use an LP. Unsafe plans are repaired by projected gradient descent, with a fallback to the previous safe plan or braking. The filter is receding-horizon and executes only the first action.
  - **Proof:** Theorem 1 proves safety by induction under its assumptions (static obstacles, complete sensing, bounded noise).
  - **Testbeds:** TurtleBot3 in Gazebo and a physical JetRacer, with GPT-4o.
  - **Timing:** 0.04–0.22 s per step, with the LLM capped at about 1.5 Hz.
  - **No adversarial, jailbreak or perception-attack evaluation.**
  - **LLM-independent?** Yes, physically.
  - **Adaptive?** No.
  - **Type:** physical (collision only).
  - [arXiv](https://arxiv.org/html/2503.03911v1)
- **SanDRA** [V]: Lin, Illing, Althoff (TUM), arXiv:2510.06717 (preprint). The LLM ranks driving actions. Actions are translated into temporal logic for traffic rules, and reachability analysis removes unsafe ones. It claims "provably safe and, where possible, legally compliant" actions and is tested open- and closed-loop in high-density traffic.
  - **LLM-independent?** Yes for safety.
  - **Adaptive?** None is mentioned.
  - **Type:** physical plus rules.
  - [arXiv](https://www.arxiv.org/abs/2510.06717)
- **SAFER** [V]: Khan, Andrev, Murtaza, Aguilera, Zhang, Ding, Hutchinson, Anwar, "Safety Aware Task Planning via Large Language Models in Robotics", arXiv:2503.15707 (preprint).
  - **How it works:** a safety-planning LLM runs alongside the task planner. An LLM-as-judge scores plans on 15 risk criteria, and a CBF-QP modifies the nominal control.
  - **Results:** about 47% fewer safety violations with GPT-4o and about 77.5% fewer with DeepSeek-r1 on COHERENT (40 tasks).
  - **No adversarial evaluation.**
  - The CBF constraints are parsed from LLM output (joint limits excepted), so the guarantee is *conditional on the LLM*.
  - **Adaptive?** No.
  - **Type:** mostly semantic, with an LLM-parameterized CBF.
  - [ar5iv](https://ar5iv.arxiv.org/html/2503.15707)
- **SAGE-LLM** [V, abstract only]: fuzzy-CBF verification of UAV LLM decisions, arXiv:2602.23719. The mechanism is not described in the abstract, and no adversarial evaluation is mentioned. — [arXiv](https://arxiv.org/abs/2602.23719)
- **Unified security and safety framework** [V]: Zhang, Kong, Dewitt, Bräunl, Hong (UWA), "Enhancing Reliability in LLM-Integrated Robotic Systems: A Unified Approach to Security and Safety", arXiv:2509.02163 (preprint).
  - **How it works:** a security-prefixed prompt, state management, and a deterministic LiDAR rule check on *Move* commands only. Failures re-query the LLM, up to 3 times.
  - **Evaluated against non-adaptive injections (OMI, GHI):**
    - GHI F1: 0.0 → 0.450
    - Physical Pioneer robot MOER: 0.36 → 0.50 (OMI) and 0.25 → 0.32 (GHI)
  - The gate is LLM-independent but myopic: no dynamics prediction, and *Turn* and *Stop* are assumed safe.
  - **Adaptive?** No.
  - **Type:** shallow physical rule plus semantic prompt defence.
  - [arXiv](https://arxiv.org/html/2509.02163v1)
- **SafeEmbodAI** [R; survey V]: Zhang et al. 2024, arXiv:2409.01630. Secure prompting, state management and a rule-based motion-feasibility check for mobile robots. This is the ISSREW-era precursor of the above. — [Survey](https://arxiv.org/pdf/2601.02377)
- **Safety Chip / "Plug in the Safety Chip"** [R]: Yang et al., ICRA 2024, arXiv:2309.09919. Translates natural-language constraints to LTL, prunes unsafe actions at runtime, and triggers replanning with explanations.
  - **LLM-independent?** Partially (the LTL translation is LLM-based).
  - **Adaptive?** No.
  - **Type:** semantic.
  - [arXiv](https://arxiv.org/abs/2309.09919)
- **SELP** [R]: Wu et al., "SELP: Generating Safe and Efficient Task Plans for Robot Agents with Large Language Models", arXiv:2409.19471 (ICRA 2025 per memory). Uses equivalence voting over LTL translations, constrained decoding with LTL, and domain-specific fine-tuning.
  - **Type:** semantic.
  - **Adaptive?** No.
  - [arXiv](https://arxiv.org/abs/2409.19471)
- **KnowNo** [R]: Ren et al., "Robots That Ask For Help: Uncertainty Alignment for LLM Planners", CoRL 2023, arXiv:2307.01928. Conformal prediction over multiple-choice next steps gives statistical task-completion coverage and asks a human when the prediction set is ambiguous. Coverage holds only under exchangeability, so it is **not** an adversarial guarantee. — [arXiv](https://arxiv.org/abs/2307.01928)
- **Conformal temporal-logic planning (HERACLEs)** [R?]: Wang, Kalluraya, Kantaros, arXiv:2309.10092. LLM planning for LTL missions with conformal-prediction help requests. Check the exact title and venue. — [arXiv](https://arxiv.org/abs/2309.10092)
- **nl2spec** [R]: Cosler et al., CAV 2023, arXiv:2303.04864. Interactive NL-to-temporal-logic translation with LLMs. — [arXiv](https://arxiv.org/abs/2303.04864)
- **AutoTAMP** [R]: Chen et al., ICRA 2024, arXiv:2306.06531. The LLM translates to STL, and a formal task-and-motion planner (with syntactic and semantic re-prompting) produces the plan. — [arXiv](https://arxiv.org/abs/2306.06531)
- **Semantically safe manipulation** [R?]: Brunke et al., "Semantically Safe Robot Manipulation: From Semantic Scene Understanding to Motion Safeguards", RA-L 2025, arXiv:2410.15185. Semantic constraints, partly from LLMs or VLMs, are enforced through CBF safety filters. — [arXiv](https://arxiv.org/abs/2410.15185)
- **NeMo Guardrails** [R]: Rebedea et al., EMNLP 2023 (demo), arXiv:2310.10501. Programmable text rails. Purely conversational and semantic, with no physical semantics. — [arXiv](https://arxiv.org/abs/2310.10501)
- **Survey** [V]: Huang, Karthick V B, Chen, Bryson, Chaffey, Chen, Choo, Manchester, "Trust in LLM-controlled Robotics: a Survey of Security Threats, Defenses and Challenges", arXiv:2601.02377 (Dec 2025). Its stated open gaps:
  - Symbolic specifications "do not cover continuous dynamics".
  - CBFs are decoupled from LLM reasoning.
  - Multi-LLM judges share alignment behavior and "lack robustness guarantees under adversarial prompt variation".
  - Evaluations rely on static metrics and simulation.
  - "No one-size-fits-all defense".
  - [arXiv](https://arxiv.org/pdf/2601.02377)

### Comparison matrix (from the cited findings above)

| Work | Layer | Guarantee independent of LLM? | Adaptive-adversary eval? | UAV? |
|---|---|---|---|---|
| AutoRT constitution, NeMo, SafeEmbodAI prompt | semantic/prompt | No | No | No |
| SAFER | LLM judge + LLM-parameterized CBF | No (constraints from LLM) | No | No |
| Safety Chip, SELP, nl2spec, AutoTAMP | LTL/STL plan | Partial (LLM translation) | No | No |
| KnowNo / conformal TL | statistical | Coverage only, under exchangeability | No | No |
| RoboGuard | LTL + root-of-trust LLM | Partial (LLM-generated specs) | **Yes** (black, gray, white-box RoboPAIR) | No (Jackal) |
| Hafez et al. reachability | physical, receding-horizon | **Yes** (under assumptions) | No | No (TurtleBot3, JetRacer) |
| SanDRA | reachability + TL | **Yes** | No | No (AV) |
| Zhang et al. 2025 UWA | LiDAR rule gate + prompt | Gate yes, myopic | Non-adaptive injection only | No |
| SAGE-LLM | fuzzy CBF | Claimed | Not mentioned | **Yes** (pursuit-evasion) |
| **Paper V (proposed)** | predictive (MPC/CBF) filter at control rate | **Yes** | **Yes** (adaptive prompt injection) | **Yes** |

### Inferences
- No found work combines all three properties:
  - a dynamics-aware predictive filter whose guarantee holds for *any* planner output, with no LLM in the safety path, even for specification generation;
  - evaluation against *adaptive* prompt injection or jailbreaks, including attackers who know the filter;
  - a UAV setting.
- RoboGuard is the closest on the adversarial axis. Hafez, SanDRA and SAGE-LLM are the closest on the physical-guarantee axis. Paper V can position itself as the intersection.
- RoboGuard explicitly lists "LTL may not capture safety tied to system dynamics" as a limitation. That is a direct hook for a dynamics-level filter, which can also be complementary to it (a semantic layer stacked over a physical layer).
- New threat dimensions that only arise once the filter is LLM-independent are under-studied and could be contributions:
  - **liveness:** the attacker causes perpetual intervention or freezes the mission;
  - **boundary-riding:** the attacker drives the state to the edge of the safe set;
  - **perception-channel attacks:** the filter still trusts state estimation, a caveat RoboGuard and Hafez both flag.

### Gaps
- The SAGE-LLM fuzzy-CBF mechanism and guarantee strength were not verified beyond the abstract.
- The ids marked [R?] (HERACLEs 2309.10092, Brunke 2410.15185) need checking.
- An "LLM-guided CBF" UAV paper with adversarial evaluation was searched for and not found. This absence is itself evidence of the gap, but the search was not exhaustive.

---

## Q4. Benchmarks and simulators for LLM robot/UAV agents

### Takeaway
Physical-safety evaluation of LLM drone control uses AirSim (Tang et al.; ChatGPT for Robotics). Embodied-agent safety benchmarks (SafeAgentBench, EARBench, IS-Bench) are household and semantic, with no dynamics. Paper V would need its own adaptive-attack harness on a drone simulator (gym-pybullet-drones, PX4/Gazebo or AirSim).

### Cited findings
- **AirSim** [R]: Shah et al., FSR 2017, arXiv:1705.05065. Used by Tang et al. [V] and ChatGPT for Robotics. Note that Microsoft archived AirSim in 2022; "Project AirSim" continued commercially (recalled). — [arXiv](https://arxiv.org/abs/1705.05065); [Tang et al.](https://arxiv.org/pdf/2411.02317v2)
- **gym-pybullet-drones** [R]: Panerati et al., IROS 2021, arXiv:2103.02142. — [arXiv](https://arxiv.org/abs/2103.02142)
- **Gazebo/ROS**: used by Hafez et al. (TurtleBot3) [V]. — [arXiv](https://arxiv.org/html/2503.03911v1)
- **Simulated drone emergency landing**: used by CHAI [V]. The simulator name was not extracted. — [arXiv](https://arxiv.org/html/2510.00181v2)
- **SafeAgentBench** [R]: Yin et al., arXiv:2412.13178. Hazardous household tasks for embodied LLM agents. — [arXiv](https://arxiv.org/abs/2412.13178)
- **EARBench** [R]: Zhu et al., arXiv:2408.04449. Physical risk awareness of embodied foundation models. — [arXiv](https://arxiv.org/abs/2408.04449)
- **IS-Bench** [R?]: interactive safety of VLM embodied agents in household tasks, arXiv:2506.16402. Verify. — [arXiv](https://arxiv.org/abs/2506.16402)
- **COHERENT**: multi-robot planning benchmark used by SAFER [V]. — [ar5iv](https://ar5iv.arxiv.org/html/2503.15707)
- **RoboGuard's benchmark** [V]: 7 harm categories × 10 rephrasings (70 adversarial prompts) plus 10 safe tasks, in randomized indoor and outdoor simulation. — [RoboGuard](https://www.alphaxiv.org/abs/2503.07885.md)
- **CognitiveDroneBench** [R]: released with CognitiveDrone, arXiv:2503.01378. — [arXiv](https://arxiv.org/abs/2503.01378)

### Inferences
- No benchmark combines UAV dynamics, an LLM planner and adaptive prompt-injection attackers. Releasing such a harness would be a secondary contribution of Paper V.
- The RoboGuard harm-category design and the Tang et al. risk taxonomy (human, object, infrastructure, FAA rules) can be reused as attack-goal specifications.

### Gaps
- No verified UAV-specific LLM safety benchmark with closed-loop dynamics was found beyond Tang et al. (AirSim, open-loop code checks plus simulation).

---

## BibTeX (provenance as marked; check every [R] and [R?] entry against arXiv before submission)

```bibtex
% ---------- Planners ----------
@inproceedings{ahn2022saycan, title={Do As I Can, Not As I Say: Grounding Language in Robotic Affordances}, author={Ahn, Michael and Brohan, Anthony and Brown, Noah and others}, booktitle={Conference on Robot Learning (CoRL)}, year={2022}, eprint={2204.01691}, archivePrefix={arXiv}} % [R]
@inproceedings{liang2023cap, title={Code as Policies: Language Model Programs for Embodied Control}, author={Liang, Jacky and Huang, Wenlong and Xia, Fei and Xu, Peng and Hausman, Karol and Ichter, Brian and Florence, Pete and Zeng, Andy}, booktitle={IEEE International Conference on Robotics and Automation (ICRA)}, year={2023}, eprint={2209.07753}, archivePrefix={arXiv}} % [R]
@article{vemprala2024chatgpt, title={{ChatGPT} for Robotics: Design Principles and Model Abilities}, author={Vemprala, Sai H. and Bonatti, Rogerio and Bucker, Arthur and Kapoor, Ashish}, journal={IEEE Access}, volume={12}, year={2024}, eprint={2306.17582}, archivePrefix={arXiv}} % [R]
@inproceedings{huang2022innermonologue, title={Inner Monologue: Embodied Reasoning through Planning with Language Models}, author={Huang, Wenlong and Xia, Fei and Xiao, Ted and others}, booktitle={CoRL}, year={2022}, eprint={2207.05608}, archivePrefix={arXiv}} % [R]
@inproceedings{singh2023progprompt, title={{ProgPrompt}: Generating Situated Robot Task Plans using Large Language Models}, author={Singh, Ishika and Blukis, Valts and Mousavian, Arsalan and others}, booktitle={ICRA}, year={2023}, eprint={2209.11302}, archivePrefix={arXiv}} % [R]
@inproceedings{huang2023voxposer, title={{VoxPoser}: Composable 3D Value Maps for Robotic Manipulation with Language Models}, author={Huang, Wenlong and Wang, Chen and Zhang, Ruohan and Li, Yunzhu and Wu, Jiajun and Fei-Fei, Li}, booktitle={CoRL}, year={2023}, eprint={2307.05973}, archivePrefix={arXiv}} % [R]
@inproceedings{brohan2023rt2, title={{RT-2}: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control}, author={Brohan, Anthony and others}, booktitle={CoRL}, year={2023}, eprint={2307.15818}, archivePrefix={arXiv}} % [R]
@inproceedings{kim2024openvla, title={{OpenVLA}: An Open-Source Vision-Language-Action Model}, author={Kim, Moo Jin and others}, booktitle={CoRL}, year={2024}, eprint={2406.09246}, archivePrefix={arXiv}} % [R]
@article{ahn2024autort, title={{AutoRT}: Embodied Foundation Models for Large Scale Orchestration of Robotic Agents}, author={Ahn, Michael and others}, journal={arXiv preprint arXiv:2401.12963}, year={2024}} % [R]
@article{chen2023typefly, title={{TypeFly}: Flying Drones with Large Language Model}, author={Chen, Guojun and Yu, Xiaojing and Zhong, Lin}, journal={arXiv preprint arXiv:2312.14950}, year={2023}} % [V] preprint
@inproceedings{tagliabue2023real, title={{REAL}: Resilience and Adaptation using Large Language Models on Autonomous Aerial Robots}, author={Tagliabue, Andrea and Kondo, Kota and Zhao, Tong and Peterson, Mason and Tewari, Claudius T. and How, Jonathan P.}, booktitle={CoRL}, year={2023}, eprint={2311.01403}, archivePrefix={arXiv}} % [V] (CoRL 2023 per arXiv comment; confirm main track vs workshop)
@article{sautenkov2025uavvla, title={{UAV-VLA}: Vision-Language-Action System for Large Scale Aerial Mission Generation}, author={Sautenkov, Oleg and others}, journal={arXiv preprint arXiv:2501.05014}, year={2025}} % [R]
@article{lykov2025cognitivedrone, title={{CognitiveDrone}: A {VLA} Model and Evaluation Benchmark for Real-Time Cognitive Task Solving and Reasoning in {UAVs}}, author={Lykov, Artem and others}, journal={arXiv preprint arXiv:2503.01378}, year={2025}} % [R]
@article{zhao2026sagellm, title={{SAGE-LLM}: Towards Safe and Generalizable {LLM} Controller with Fuzzy-{CBF} Verification and Graph-Structured Knowledge Retrieval for {UAV} Decision}, author={Zhao, Wenzhe and Zhao, Yang and Liu, Ganchao and Jiang, Zhiyu and Ma, Dandan and Li, Zihao and Li, Xuelong}, journal={arXiv preprint arXiv:2602.23719}, year={2026}} % [V] preprint
@article{javaid2024llmuav, title={Large Language Models for {UAVs}: Current State and Pathways to the Future}, author={Javaid, Shumaila and others}, journal={arXiv preprint arXiv:2405.01745}, year={2024}} % [R] (IEEE OJVT 2024 per memory)
@article{tian2025uavsmeetllms, title={{UAVs} Meet {LLMs}: Overviews and Perspectives Towards Agentic Low-Altitude Mobility}, author={Tian, Yonglin and others}, journal={arXiv preprint arXiv:2501.02341}, year={2025}} % [R]

% ---------- Attacks ----------
@inproceedings{robey2025robopair, title={Jailbreaking {LLM}-Controlled Robots}, author={Robey, Alexander and Ravichandran, Zachary and Kumar, Vijay and Hassani, Hamed and Pappas, George J.}, booktitle={ICRA}, year={2025}, eprint={2410.13691}, archivePrefix={arXiv}} % [R] fetch blocked
@inproceedings{zhang2025badrobot, title={{BadRobot}: Jailbreaking Embodied {LLMs} in the Physical World}, author={Zhang, Hangtao and others}, booktitle={ICLR}, year={2025}, eprint={2407.20242}, archivePrefix={arXiv}} % [R]
@article{lu2024poex, title={{POEX}: Policy Executable Embodied {AI} Jailbreak Attacks}, author={Lu, Xuancun and others}, journal={arXiv preprint arXiv:2412.16633}, year={2024}} % [R]
@article{wang2024vlaadv, title={Exploring the Adversarial Vulnerabilities of Vision-Language-Action Models in Robotics}, author={Wang, Taowen and others}, journal={arXiv preprint arXiv:2411.13587}, year={2024}} % [R] (ICCV 2025 per memory)
@article{liu2024eirad, title={Exploring the Robustness of Decision-Level Through Adversarial Attacks on {LLM}-Based Embodied Models}, author={Liu, Shuyuan and others}, journal={arXiv preprint arXiv:2405.19802}, year={2024}} % [R]
@article{zhang2024promptinjrobot, title={A Study on Prompt Injection Attack Against {LLM}-Integrated Mobile Robotic Systems}, author={Zhang, Wenxiao and Kong, Xiangrui and Dewitt, Conan and Br{\"a}unl, Thomas and Hong, Jin B.}, journal={arXiv preprint arXiv:2408.03515}, year={2024}} % [R] (ISSREW 2024 per memory)
@article{wang2024trojanrobot, title={{TrojanRobot}: Physical-World Backdoor Attacks Against {VLM}-Based Robotic Manipulation}, author={Wang, Xianlong and others}, journal={arXiv preprint arXiv:2411.11683}, year={2024}} % [R?] title
@article{burbano2025chai, title={{CHAI}: Command Hijacking against Embodied {AI}}, author={Burbano, Luis and Ortiz, Diego and Sun, Qi and Yang, Siwei and Tu, Haoqin and Xie, Cihang and Cao, Yinzhi and Cardenas, Alvaro A.}, journal={arXiv preprint arXiv:2510.00181}, year={2025}} % [V] (author order may differ; SaTML 2026 presentation found, venue unconfirmed)
@article{tang2024physicalsafety, title={Defining and Evaluating Physical Safety for Large Language Models}, author={Tang, Yung-Chen and Chen, Pin-Yu and Ho, Tsung-Yi}, journal={arXiv preprint arXiv:2411.02317}, year={2024}} % [V] preprint
@inproceedings{greshake2023indirect, title={Not What You've Signed Up For: Compromising Real-World {LLM}-Integrated Applications with Indirect Prompt Injection}, author={Greshake, Kai and Abdelnabi, Sahar and Mishra, Shailesh and Endres, Christoph and Holz, Thorsten and Fritz, Mario}, booktitle={ACM AISec Workshop}, year={2023}, eprint={2302.12173}, archivePrefix={arXiv}} % [R]

% ---------- Defenses ----------
@article{ravichandran2026roboguard, title={Safety Guardrails for {LLM}-Enabled Robots}, author={Ravichandran, Zachary and Robey, Alexander and Kumar, Vijay and Pappas, George J. and Hassani, Hamed}, journal={IEEE Robotics and Automation Letters}, year={2026}, eprint={2503.07885}, archivePrefix={arXiv}} % [V] accepted Feb 2026
@article{hafez2025reachllm, title={Safe {LLM}-Controlled Robots with Formal Guarantees via Reachability Analysis}, author={Hafez, Ahmad and Naderi Akhormeh, Alireza and Hegazy, Amr and Alanwar, Amr}, journal={arXiv preprint arXiv:2503.03911}, year={2025}} % [V]
@article{lin2025sandra, title={{SanDRA}: Safe Large-Language-Model-Based Decision Making for Automated Vehicles Using Reachability Analysis}, author={Lin, Yuanfei and Illing, Sebastian and Althoff, Matthias}, journal={arXiv preprint arXiv:2510.06717}, year={2025}} % [V]
@article{khan2025safer, title={Safety Aware Task Planning via Large Language Models in Robotics}, author={Khan, Azal Ahmad and Andrev, Michael and Murtaza, Muhammad Ali and Aguilera, Sergio and Zhang, Rui and Ding, Jie and Hutchinson, Seth and Anwar, Ali}, journal={arXiv preprint arXiv:2503.15707}, year={2025}} % [V]
@article{zhang2025unified, title={Enhancing Reliability in {LLM}-Integrated Robotic Systems: A Unified Approach to Security and Safety}, author={Zhang, Wenxiao and Kong, Xiangrui and Dewitt, Conan and Br{\"a}unl, Thomas and Hong, Jin B.}, journal={arXiv preprint arXiv:2509.02163}, year={2025}} % [V]
@article{zhang2024safeembodai, title={{SafeEmbodAI}: A Safety Framework for Mobile Robots in Embodied {AI} Systems}, author={Zhang, Wenxiao and Kong, Xiangrui and Br{\"a}unl, Thomas and Hong, Jin B.}, journal={arXiv preprint arXiv:2409.01630}, year={2024}} % [R]
@inproceedings{yang2024safetychip, title={Plug in the Safety Chip: Enforcing Constraints for {LLM}-Driven Robot Agents}, author={Yang, Ziyi and Raman, Shreyas S. and Shah, Ankit and Tellex, Stefanie}, booktitle={ICRA}, year={2024}, eprint={2309.09919}, archivePrefix={arXiv}} % [R]
@article{wu2024selp, title={{SELP}: Generating Safe and Efficient Task Plans for Robot Agents with Large Language Models}, author={Wu, Yi and others}, journal={arXiv preprint arXiv:2409.19471}, year={2024}} % [R]
@inproceedings{ren2023knowno, title={Robots That Ask For Help: Uncertainty Alignment for Large Language Model Planners}, author={Ren, Allen Z. and others}, booktitle={CoRL}, year={2023}, eprint={2307.01928}, archivePrefix={arXiv}} % [R]
@article{wang2023conformaltl, title={Conformal Temporal Logic Planning using Large Language Models}, author={Wang, Jun and Tong, Jiaming and Tan, Kaiyuan and Vorobeychik, Yevgeniy and Kantaros, Yiannis}, journal={arXiv preprint arXiv:2309.10092}, year={2023}} % [R?] authors/title unverified
@inproceedings{cosler2023nl2spec, title={nl2spec: Interactively Translating Unstructured Natural Language to Temporal Logics with Large Language Models}, author={Cosler, Matthias and Hahn, Christopher and Mendoza, Daniel and Schmitt, Frederik and Trippel, Caroline}, booktitle={CAV}, year={2023}, eprint={2303.04864}, archivePrefix={arXiv}} % [R]
@inproceedings{chen2024autotamp, title={{AutoTAMP}: Autoregressive Task and Motion Planning with {LLMs} as Translators and Checkers}, author={Chen, Yongchao and Arkin, Jacob and Dawson, Charles and Zhang, Yang and Roy, Nicholas and Fan, Chuchu}, booktitle={ICRA}, year={2024}, eprint={2306.06531}, archivePrefix={arXiv}} % [R]
@article{brunke2025semsafe, title={Semantically Safe Robot Manipulation: From Semantic Scene Understanding to Motion Safeguards}, author={Brunke, Lukas and others}, journal={IEEE Robotics and Automation Letters}, year={2025}, eprint={2410.15185}, archivePrefix={arXiv}} % [R?]
@inproceedings{rebedea2023nemo, title={{NeMo} Guardrails: A Toolkit for Controllable and Safe {LLM} Applications with Programmable Rails}, author={Rebedea, Traian and Dinu, Razvan and Sreedhar, Makesh and Parisien, Christopher and Cohen, Jonathan}, booktitle={EMNLP: System Demonstrations}, year={2023}, eprint={2310.10501}, archivePrefix={arXiv}} % [R]
@article{huang2025trustsurvey, title={Trust in {LLM}-controlled Robotics: a Survey of Security Threats, Defenses and Challenges}, author={Huang, Xinyu and Karthick V B, Shyam and Chen, Taozhao and Bryson, Mitch and Chaffey, Thomas and Chen, Huaming and Choo, Kim-Kwang Raymond and Manchester, Ian R.}, journal={arXiv preprint arXiv:2601.02377}, year={2025}} % [V] (first names partly inferred; check)

% ---------- Benchmarks / sims ----------
@inproceedings{shah2017airsim, title={{AirSim}: High-Fidelity Visual and Physical Simulation for Autonomous Vehicles}, author={Shah, Shital and Dey, Debadeepta and Lovett, Chris and Kapoor, Ashish}, booktitle={Field and Service Robotics}, year={2017}, eprint={1705.05065}, archivePrefix={arXiv}} % [R]
@inproceedings{panerati2021gympybullet, title={Learning to Fly---a Gym Environment with {PyBullet} Physics for Reinforcement Learning of Multi-agent Quadcopter Control}, author={Panerati, Jacopo and Zheng, Hehui and Zhou, SiQi and Xu, James and Prorok, Amanda and Schoellig, Angela P.}, booktitle={IROS}, year={2021}, eprint={2103.02142}, archivePrefix={arXiv}} % [R]
@article{yin2024safeagentbench, title={{SafeAgentBench}: A Benchmark for Safe Task Planning of Embodied {LLM} Agents}, author={Yin, Sheng and others}, journal={arXiv preprint arXiv:2412.13178}, year={2024}} % [R]
@article{zhu2024earbench, title={{EARBench}: Towards Evaluating Physical Risk Awareness for Task Planning of Foundation Model-based Embodied {AI} Agents}, author={Zhu, Zihao and others}, journal={arXiv preprint arXiv:2408.04449}, year={2024}} % [R]
@article{isbench2025, title={{IS-Bench}: Evaluating Interactive Safety of {VLM}-Driven Embodied Agents in Daily Household Tasks}, author={Lu, Xiaoya and others}, journal={arXiv preprint arXiv:2506.16402}, year={2025}} % [R?]
```
