# Prompt injection against LLM agents, defences, and adaptive-attack evaluation methodology (for Paper V, IEEE SaTML target)

Verification legend used throughout:
- **[V]** = verified this session against the primary source (arXiv abstract/HTML or publisher page) linked inline.
- **[M]** = bibliographic details from the researcher's prior knowledge, *not re-verified this session*; IDs/DOIs believed correct but the report writer should spot-check before camera-ready. Numbers marked [M] should not be quoted as headline figures without re-checking.
- "Preprint" = no peer-reviewed venue confirmed.

---

## Q1. Indirect prompt injection: foundational and optimisation-based attacks (incl. attacks on tool-using agents)

### Takeaway
The canonical lineage is Perez & Ribeiro 2022 (direct "goal hijacking"/"prompt leaking") -> Greshake et al. 2023 (indirect injection via retrieved data, AISec) -> Liu et al. USENIX Sec 2024 (formal framework + benchmark) -> optimised/universal injections (GCG-style, Automatic & Universal, Neural Exec) -> learned RL attackers (RL-Hammer, 2025) that reach 98% ASR on GPT-4o. For Paper V the key framing is: the threat model is *indirect* injection into the agent's observation channel (mission text, map annotations, sensor-derived captions), and the strongest attacker is an optimiser/RL policy, not a fixed string.

### Cited Findings
- **Greshake et al. 2023** [M bibliographic; arXiv id V via search ecosystem]: K. Greshake, S. Abdelnabi, S. Mishra, C. Endres, T. Holz, M. Fritz, "Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection," *Proc. 16th ACM Workshop on Artificial Intelligence and Security (AISec '23)*, pp. 79–90, DOI 10.1145/3605764.3623985, arXiv:2302.12173. Introduces indirect prompt injection (IPI): adversary plants instructions in data the LLM retrieves; taxonomy of impacts incl. data theft, worming, information-ecosystem contamination, and *availability* attacks — [arXiv 2302.12173](https://arxiv.org/abs/2302.12173)
- **Perez & Ribeiro 2022** [M]: F. Perez, I. Ribeiro, "Ignore Previous Prompt: Attack Techniques For Language Models," NeurIPS 2022 ML Safety Workshop, arXiv:2211.09527. Introduces PromptInject; two attack goals: *goal hijacking* and *prompt leaking* — [arXiv 2211.09527](https://arxiv.org/abs/2211.09527)
- **Liu et al. USENIX Security 2024** [M]: Y. Liu, Y. Jia, R. Geng, J. Jia, N. Z. Gong, "Formalizing and Benchmarking Prompt Injection Attacks and Defenses," *33rd USENIX Security Symposium*, 2024, arXiv:2310.12815. Gives a formal framework where existing attacks are special cases, proposes a "combined attack", and benchmarks 5 attacks x 10 defenses x 10 LLMs x 7 tasks (counts from memory) — [arXiv 2310.12815](https://arxiv.org/abs/2310.12815)
- **HouYi** [M, preprint]: Y. Liu, G. Deng, Y. Li, K. Wang, Z. Wang, X. Wang, T. Zhang, Y. Liu, H. Wang, Y. Zheng, Y. Liu, "Prompt Injection attack against LLM-integrated Applications," arXiv:2306.05499 (2023). Black-box, three-part injection (framework component, separator, disruptor); reported 31 of 36 real apps vulnerable (from memory — re-check) — [arXiv 2306.05499](https://arxiv.org/abs/2306.05499)
- **GCG** [M]: A. Zou, Z. Wang, N. Carlini, M. Nasr, J. Z. Kolter, M. Fredrikson, "Universal and Transferable Adversarial Attacks on Aligned Language Models," arXiv:2307.15043 (2023). Greedy Coordinate Gradient suffix optimisation; the de facto white-box baseline later reused for prompt injection — [arXiv 2307.15043](https://arxiv.org/abs/2307.15043)
- **Automatic and Universal Prompt Injection** [M, preprint]: X. Liu, Z. Yu, Y. Zhang, N. Zhang, C. Xiao, "Automatic and Universal Prompt Injection Attacks against Large Language Models," arXiv:2403.04957 (2024). Gradient-based, momentum-enhanced optimisation; universal injections from few training samples — [arXiv 2403.04957](https://arxiv.org/abs/2403.04957)
- **Neural Exec** [M]: D. Pasquini, M. Strohmeier, C. Troncoso, "Neural Exec: Learning (and Learning from) Execution Triggers for Prompt Injection Attacks," *AISec '24* (ACM CCS workshop), arXiv:2403.03792. Learns execution triggers via optimisation; triggers survive RAG pipelines and evade blacklist-style filters — [arXiv 2403.03792](https://arxiv.org/abs/2403.03792)
- **RL-Hammer** [V, preprint, Oct 2025]: Y. Wen, A. Zharmagambetov, I. Evtimov, N. Kokhlikyan, T. Goldstein, K. Chaudhuri, C. Guo, "RL Is a Hammer and LLMs Are Nails: A Simple Reinforcement Learning Recipe for Strong Prompt Injection," arXiv:2510.04885. Headline: **98% ASR against GPT-4o** and **72% against GPT-5 with Instruction Hierarchy**; attacker trained jointly on Llama-3.1-8B-Instruct + GPT-4o transfers at **70% ASR to Meta-SecAlign-70B** (never a training target); 98%/99% vs Meta-SecAlign-8B/-70B when they are training targets (Table 1) — [arXiv 2510.04885](https://arxiv.org/html/2510.04885v1)
- RL-Hammer on detectors [V]: detection rates of its injections — perplexity filter **0%**, Llama-Prompt-Guard-2 **16%**, ProtectAI-Guard **17%**, GPT-4o-mini LLM judge **85%**; with an added stealthiness reward the attacker reaches **0% detection across all four detectors while keeping 97% ASR** — [arXiv 2510.04885](https://arxiv.org/html/2510.04885v1)
- RL-Hammer on diversity [V]: diversity rewards are "reward-hacked" (superficial variation such as letter case or prepended irrelevant text; same underlying strategy) — [arXiv 2510.04885](https://arxiv.org/html/2510.04885v1)

### Inferences
- Paper V's adaptive attacker should be built in at least two flavours mirroring this lineage: (i) optimisation-based (GCG/universal-injection style, white-box on an open-weight planner) and (ii) RL-trained attacker policy (RL-Hammer recipe) with reward = filter-*passing* mission harm or filter-*triggered* mission denial. RL-Hammer's stealth-reward result directly motivates a "stealthy denial" attacker whose reward includes not tripping the filter's anomaly signals.
- RL-Hammer's diversity finding warns that a single attacker run may collapse to one strategy; report attack diversity or use multiple seeds/strategies.

### Gaps
- Exact table counts for Liu et al. (USENIX'24) and HouYi's "31/36" not re-verified this session.

---

## Q2. Agent security benchmarks and metrics (map to mission denial rate / benign intervention rate)

### Takeaway
AgentDojo's three-metric scheme (benign utility, utility under attack, targeted ASR) is the community standard and maps cleanly onto Paper V: benign utility -> mission completion without attack (and benign intervention rate as its filter-specific complement), utility under attack -> mission completion under attack (1 - mission denial rate), targeted ASR -> unsafe-action / hijack success rate. ASB adds a utility-security composite (Net Resilient Performance) and InjecAgent splits attacker goals into direct-harm vs data-exfiltration.

### Cited Findings
- **AgentDojo** [V]: E. Debenedetti, J. Zhang, M. Balunović, L. Beurer-Kellner, M. Fischer, F. Tramèr, "AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents," NeurIPS 2024 Datasets & Benchmarks Track, arXiv:2406.13352. **97 realistic tasks, 629 security test cases** — [arXiv 2406.13352](https://arxiv.org/abs/2406.13352)
- AgentDojo metrics [V]: *Benign Utility* = fraction of user tasks solved with no attack; *Utility Under Attack* = fraction of security cases (user task x injection task) where the agent solves the user task without adversarial side effects; *Targeted ASR* = fraction of security cases where the attacker goal is met — [arXiv 2406.13352](https://arxiv.org/abs/2406.13352)
- AgentDojo results [V]: LLMs solve <66% of tasks even without attack; a secondary prompt-injection detector reduces ASR to 8%; a tool-filter defence to ~7.5%; the "important message" attack reaches 47.69% targeted ASR on GPT-4o (Table 3). Note: the introduction's "<25% against the best agents" claim refers to the best-performing agent, not GPT-4o; quote the specific model when citing — [arXiv 2406.13352](https://arxiv.org/abs/2406.13352)
- **InjecAgent** [V numbers; venue from ACL Anthology listing]: Q. Zhan, Z. Liang, Z. Ying, D. Kang, "InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents," *Findings of ACL 2024* (2024.findings-acl.624), arXiv:2403.02691. **1,054 test cases, 17 user tools, 62 attacker tools, 30 LLM agents**; attack intents: direct harm to users and private-data exfiltration; ReAct-prompted GPT-4 ASR **24%** base, **47%** with "hacking prompt" enhanced setting — [arXiv 2403.02691v3](https://arxiv.org/html/2403.02691v3); [ACL Anthology](https://preview.aclanthology.org/dashboard/2024.findings-acl.624)
- **ASB (Agent Security Bench)** [V numbers; venue M]: H. Zhang, J. Huang, K. Mei, Y. Yao, Z. Wang, C. Zhan, H. Wang, Y. Zhang, "Agent Security Bench (ASB): Formalizing and Benchmarking Attacks and Defenses in LLM-based Agents," arXiv:2410.02644 (published at ICLR 2025 per prior knowledge; arXiv v2 page does not state venue). **10 scenarios (incl. autonomous driving), 10 agents, 400+ tools, 400 tasks, 27 attack/defence methods (10 prompt-injection, 1 memory-poisoning, 1 Plan-of-Thought backdoor, 4 mixed attacks, 11 defences), 13 LLM backbones, 7 metrics; highest average ASR 84.30%**; introduces **Net Resilient Performance (NRP)** to balance utility and security — [arXiv 2410.02644v2](https://arxiv.org/html/2410.02644v2)
- **b3 benchmark** [V, preprint]: J. Bazinska, M. Mathys, F. Casucci, M. Rojas-Carulla, X. Davies, A. Souly, N. Pfister, "Breaking Agent Backbones: Evaluating the Security of Backbone LLMs in AI Agents," arXiv:2510.22620 (Lakera, ETH Zürich, UK AISI, Oxford OATML). Introduces "threat snapshots" (isolating states in the agent execution flow where LLM vulnerabilities manifest); b3 built on **194,331 unique crowdsourced adversarial attacks**, evaluation uses a curated subset of **210**; **34 LLMs**; findings: enhanced reasoning improves security, model size does not correlate with security — [arXiv 2510.22620](https://arxiv.org/pdf/2510.22620v2); [Lakera blog](https://www.lakera.ai/blog/the-backbone-breaker-benchmark)
- **WASP** [M, preprint]: I. Evtimov, A. Zharmagambetov, A. Grattafiori, C. Guo, K. Chaudhuri, "WASP: Benchmarking Web Agent Security Against Prompt Injection Attacks," arXiv:2504.18575 (2025). From memory: agents begin following injected instructions in a large fraction of cases but fully complete attacker goals rarely ("security by incompetence") — exact percentages not re-verified — [arXiv 2504.18575](https://arxiv.org/abs/2504.18575)
- **AgentHarm** [M]: M. Andriushchenko, A. Souly, M. Dziemian, D. Duenas, M. Lin, J. Wang, D. Hendrycks, A. Zou, Z. Kolter, M. Fredrikson, E. Winsor, J. Wynne, Y. Gal, X. Davies, "AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents," ICLR 2025, arXiv:2410.09024. Measures *direct* misuse (malicious user), 110 base malicious tasks / 440 with augmentation across 11 harm categories (from memory). Relevant as the "malicious operator" contrast to IPI — [arXiv 2410.09024](https://arxiv.org/abs/2410.09024)

### Inferences
- Proposed metric mapping for Paper V (the writer can present this as a table):
  - *Benign mission success (BMS)* <-> AgentDojo Benign Utility.
  - *Benign intervention rate (BIR)* = fraction of benign missions where the safety filter overrides/modifies the plan; this is the filter analogue of a detector's false-positive rate (AgentDojo reports detector utility cost implicitly via benign utility drop).
  - *Mission denial rate (MDR) under attack* = 1 - Utility Under Attack restricted to cases where no unsafe action occurred; i.e., the attacker failed to cause harm but succeeded in preventing the mission (availability loss).
  - *Unsafe-action / safety-violation rate (SVR)* <-> Targeted ASR (attacker's physical goal achieved despite filter).
  - Composite: an NRP-style (ASB) utility x (1-ASR) score, or report the 2-D (SVR, MDR) Pareto pair per attacker level.
- Separating "attack caused a violation" from "attack caused denial" is exactly AgentDojo's split between targeted ASR and utility under attack; Paper V's novelty is to make the second one a first-class *attacker objective*.

### Gaps
- WASP and AgentHarm headline numbers not re-verified. ASB venue (ICLR 2025) not confirmed from the page fetched.

---

## Q3. Defences, especially system-level / architectural ("defence by design")

### Takeaway
The field has split into (a) model-level defences (StruQ, SecAlign, instruction hierarchy, spotlighting, detectors like PromptGuard/DataSentinel), which Q4 shows are repeatedly broken by adaptive attacks, and (b) system-level defences that bound what a compromised model can *do* (Dual LLM, CaMeL, IsolateGPT, f-secure, FIDES, Progent, design patterns). CaMeL offers provable security at a utility cost (77% vs 84% on AgentDojo). Paper V's predictive safety filter is the physical-layer analogue of (b): it secures the closed-loop system, not the model, and so inherits (b)'s argument that robustness should not depend on the LLM resisting injection.

### Cited Findings
- **CaMeL** [V, preprint]: E. Debenedetti, I. Shumailov, T. Fan, J. Hayes, N. Carlini, D. Fabian, C. Kern, C. Shi, A. Terzis, F. Tramèr, "Defeating Prompt Injections by Design," arXiv:2503.18813 (v1 24 Mar 2025, v2 24 Jun 2025). **Solves 77% of AgentDojo tasks with provable security vs 84% for the undefended system** — [arXiv 2503.18813](https://arxiv.org/abs/2503.18813)
- **Dual LLM pattern** [M]: S. Willison, "The Dual LLM pattern for building AI assistants that can resist prompt injection," blog post, 25 Apr 2023 — a privileged LLM never sees untrusted content; a quarantined LLM processes it and returns symbolic references — [simonwillison.net](https://simonwillison.net/2023/Apr/25/dual-llm-pattern/)
- **Design patterns** [M, preprint]: L. Beurer-Kellner, B. Buesser, A.-M. Creţu, E. Debenedetti, D. Dobos, D. Fabian, M. Fischer, D. Froelicher, K. Grosse, D. Naeff, E. Ozoani, A. Paverd, F. Tramèr, V. Volhejn, "Design Patterns for Securing LLM Agents against Prompt Injections," arXiv:2506.08837 (2025). Six patterns: Action-Selector, Plan-Then-Execute, LLM Map-Reduce, Dual LLM, Code-Then-Execute, Context-Minimization; explicit utility-security trade-off framing — [arXiv 2506.08837](https://arxiv.org/abs/2506.08837)
- **FIDES** [V, preprint]: M. Costa, B. Köpf, A. Kolluri, A. Paverd, M. Russinovich, A. Salem, S. Tople, L. Wutschitz, S. Zanella-Béguelin, "Securing AI Agents with Information-Flow Control," arXiv:2505.23643 (May 2025). Formal model of agent planners; characterises properties enforceable by dynamic taint-tracking; task taxonomy for security/utility; FIDES planner tracks confidentiality and integrity labels and enforces policies deterministically; AgentDojo evaluation "broadens the range of tasks that can be securely accomplished" — [Microsoft Research](https://www.microsoft.com/en-us/research/publication/securing-ai-agents-with-information-flow-control/); [arXiv 2505.23643](https://arxiv.org/abs/2505.23643)
- **f-secure** [M, preprint]: F. Wu, E. Cecchetti, C. Xiao, "System-Level Defense against Indirect Prompt Injection Attacks: An Information Flow Control Perspective," arXiv:2409.19091 (2024) — [arXiv 2409.19091](https://arxiv.org/abs/2409.19091)
- **IsolateGPT** [M]: Y. Wu, F. Roesner, T. Kohno, N. Zhang, U. Iqbal, "IsolateGPT: An Execution Isolation Architecture for LLM-Based Agentic Systems," NDSS 2025, arXiv:2403.04960 (earlier titled SecGPT) — [arXiv 2403.04960](https://arxiv.org/abs/2403.04960)
- **Progent** [M, preprint]: T. Shi, J. He, Z. Wang, L. Wu, H. Li, W. Guo, D. Song, "Progent: Programmable Privilege Control for LLM Agents," arXiv:2504.11703 (2025). Domain-specific language for fine-grained tool-call privilege policies, enforced deterministically (headline AgentDojo ASR reduction not re-verified) — [arXiv 2504.11703](https://arxiv.org/abs/2504.11703)
- **MELON** [M]: K. Zhu, X. Yang, J. Wang, W. Guo, W. Y. Wang, "MELON: Provable Defense Against Indirect Prompt Injection Attacks in AI Agents," ICML 2025, arXiv:2502.05174. Masked re-execution: re-runs the agent with the user prompt masked and flags tool calls that persist (i.e., are driven by tool outputs) — [arXiv 2502.05174](https://arxiv.org/abs/2502.05174)
- **StruQ** [M]: S. Chen, J. Piet, C. Sitawarin, D. Wagner, "StruQ: Defending Against Prompt Injection with Structured Queries," USENIX Security 2025, arXiv:2402.06363 — [arXiv 2402.06363](https://arxiv.org/abs/2402.06363)
- **SecAlign** [M]: S. Chen, A. Zharmagambetov, S. Mahloujifar, K. Chaudhuri, D. Wagner, C. Guo, "SecAlign: Defending Against Prompt Injection with Preference Optimization," ACM CCS 2025, arXiv:2410.05451; follow-up Meta SecAlign arXiv:2507.02735 — [arXiv 2410.05451](https://arxiv.org/abs/2410.05451). Note: RL-Hammer [V] reaches 98–99% ASR vs Meta-SecAlign when trained on it and 70% by transfer — [arXiv 2510.04885](https://arxiv.org/html/2510.04885v1)
- **Spotlighting** [M, preprint]: K. Hines, G. Lopez, M. Hall, F. Zarfati, Y. Zunger, E. Kıcıman, "Defending Against Indirect Prompt Injection Attacks With Spotlighting," arXiv:2403.14720 (2024); delimiting/datamarking/encoding of untrusted input — [arXiv 2403.14720](https://arxiv.org/abs/2403.14720)
- **Instruction hierarchy** [M, preprint]: E. Wallace, K. Xiao, R. Leike, L. Weng, J. Heidecke, A. Beutel, "The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions," arXiv:2404.13208 (2024). Broken at 72% ASR on GPT-5 by RL-Hammer [V] — [arXiv 2404.13208](https://arxiv.org/abs/2404.13208); [arXiv 2510.04885](https://arxiv.org/html/2510.04885v1)
- **Detectors** [M]: Meta Llama Prompt Guard / Prompt Guard 2 (model cards, 2024/2025); DataSentinel: Y. Liu, Y. Jia, J. Jia, D. Song, N. Z. Gong, "DataSentinel: A Game-Theoretic Detection of Prompt Injection Attacks," IEEE S&P 2025, arXiv:2504.11358 — [arXiv 2504.11358](https://arxiv.org/abs/2504.11358). Prompt-Guard-2 detects only 16% of RL-Hammer injections [V] — [arXiv 2510.04885](https://arxiv.org/html/2510.04885v1)

### Inferences
- Positioning sentence for Paper V: "Like CaMeL, FIDES and Progent, which enforce security at the system boundary rather than relying on the model to resist injection, our filter enforces a physical invariant (predicted state-constraint satisfaction) on whatever the LLM outputs; a fully compromised planner can at worst cause the filter to intervene." This then exposes the *new* attack surface: the attacker cannot violate safety but can force interventions -> denial of service (Q5).
- CaMeL's 84% -> 77% utility gap is the natural precedent for reporting Paper V's benign intervention rate / benign mission success cost.

### Gaps
- Progent, MELON, spotlighting headline numbers not re-verified (spotlighting is commonly cited as reducing ASR from >50% to <2%, but not confirmed this session).

---

## Q4. Adaptive-attack evaluation discipline and recommended reporting standards

### Takeaway
A decade of adversarial-ML experience (Carlini & Wagner 2017; Athalye et al. 2018; Carlini et al. 2019; Tramèr et al. 2020) has been replayed for prompt injection in 2025: Zhan et al. (NAACL Findings 2025) break all 8 IPI defences tested with >50% ASR, and Nasr, Carlini, ... Tramèr ("The Attacker Moves Second", USENIX Security 2026) break 12 jailbreak/prompt-injection defences, most at >90% ASR, many of which originally reported near-zero ASR. For SaTML, a defence paper must therefore include a defence-aware adaptive attacker with substantial compute and multiple attack families (gradient, RL, search, human red-teaming).

### Cited Findings
- **The Attacker Moves Second** [V]: M. Nasr, N. Carlini, C. Sitawarin, S. V. Schulhoff, J. Hayes, M. Ilie, J. Pluto, S. Song, H. Chaudhari, I. Shumailov, A. Thakurta, K. Y. Xiao, A. Terzis, F. Tramèr, "The Attacker Moves Second: Stronger Adaptive Attacks Bypass Defenses Against LLM Jailbreaks and Prompt Injections," arXiv:2510.09023 (Oct 2025); listed as a USENIX Security 2026 presentation. **Breaks 12 recent defences, ASR >90% for most; most originally reported near-zero ASR.** Attack families: gradient descent, reinforcement learning, random search, human-guided exploration (red-teaming). Recommendations: assume the attacker knows the defence; use strong, compute-intensive optimisation, not static attack sets; diversify attack methods; treat adaptive attacks as necessary for any robustness claim — [arXiv 2510.09023](https://arxiv.org/abs/2510.09023); [USENIX Sec '26](https://www.usenix.org/conference/usenixsecurity26/presentation/nasr)
- **Zhan et al. 2025** [V]: Q. Zhan, R. Fang, H. S. Panchal, D. Kang, "Adaptive Attacks Break Defenses Against Indirect Prompt Injection Attacks on LLM Agents," *Findings of NAACL 2025* (2025.findings-naacl.395), arXiv:2503.00061. **8 defences** (fine-tuned detector, LLM-based detector, perplexity filtering, instructional prevention, data-prompt isolation, sandwich prevention, paraphrasing, adversarial fine-tuning) **all bypassed with ASR >50%**. Average adaptive ASR 0.68 ± 0.15 (Vicuna-7B agent) and 0.57 ± 0.17 (Llama3-8B agent) (Table 4); perplexity filtering adaptive ASR 76%/61%, paraphrasing 79%/54%. Caveat: Table 4 lists original no-defence totals 0.50/0.40, inconsistent with the 56%/9% stated in Sec. 5.2 — quote carefully — [arXiv 2503.00061](https://arxiv.org/abs/2503.00061); [ACL Anthology](https://preview.aclanthology.org/dashboard/2025.findings-naacl.395)
- **Carlini & Wagner 2017** [M]: N. Carlini, D. Wagner, "Towards Evaluating the Robustness of Neural Networks," IEEE S&P 2017, pp. 39–57, DOI 10.1109/SP.2017.49, arXiv:1608.04644 — [arXiv 1608.04644](https://arxiv.org/abs/1608.04644)
- **Athalye, Carlini, Wagner 2018** [M]: "Obfuscated Gradients Give a False Sense of Security: Circumventing Defenses to Adversarial Examples," ICML 2018, PMLR 80:274–283, arXiv:1802.00420. Found 7 of 9 ICLR 2018 white-box defences relied on obfuscated gradients; circumvented 6 completely and 1 partially (from memory); introduced BPDA/EOT — [arXiv 1802.00420](https://arxiv.org/abs/1802.00420)
- **Carlini et al. 2019** [M, preprint]: N. Carlini, A. Athalye, N. Papernot, W. Brendel, J. Rauber, D. Tsipras, I. Goodfellow, A. Madry, A. Kurakin, "On Evaluating Adversarial Robustness," arXiv:1902.06705 — checklist: state threat model precisely, test adaptive attacks, verify attack success increases with budget, sanity checks (unbounded attack reaches 100%), report worst-case over attacks, release code — [arXiv 1902.06705](https://arxiv.org/abs/1902.06705)
- **Tramèr et al. 2020** [M]: F. Tramèr, N. Carlini, W. Brendel, A. Madry, "On Adaptive Attacks to Adversarial Example Defenses," NeurIPS 2020, arXiv:2002.08347; 13 published defences circumvented by individually tailored adaptive attacks — [arXiv 2002.08347](https://arxiv.org/abs/2002.08347)
- **Search/LLM-driven attackers** [M]: PAIR — P. Chao, A. Robey, E. Dobriban, H. Hassani, G. J. Pappas, E. Wong, "Jailbreaking Black Box Large Language Models in Twenty Queries," arXiv:2310.08419 (published SaTML 2025) — [arXiv 2310.08419](https://arxiv.org/abs/2310.08419); TAP — A. Mehrotra, M. Zampetakis, P. Kassianik, B. Nelson, H. Anderson, Y. Singer, A. Karbasi, "Tree of Attacks: Jailbreaking Black-Box LLMs Automatically," NeurIPS 2024, arXiv:2312.02119 — [arXiv 2312.02119](https://arxiv.org/abs/2312.02119); AutoDAN — X. Liu, N. Xu, M. Chen, C. Xiao, "AutoDAN: Generating Stealthy Jailbreak Prompts on Aligned Large Language Models," ICLR 2024, arXiv:2310.04451 — [arXiv 2310.04451](https://arxiv.org/abs/2310.04451); RL-Hammer [V] (Q1).

### Inferences
Concrete attacker capability ladder for Paper V (each level is a superset of the previous; report SVR and MDR per level):
- **L0 Non-adaptive:** static injection corpus (AgentDojo "important message", InjecAgent base/enhanced, HouYi templates) translated to UAV mission context.
- **L1 Black-box, filter-unaware:** PAIR/TAP-style LLM-driven search with planner outputs only.
- **L2 Black-box, filter-aware (knows filter exists and its constraint set, observes intervene/no-intervene bit):** search/RL with reward for (a) safety violation passing the filter, (b) maximal intervention (denial), (c) denial while keeping per-step anomaly score low (stealthy denial).
- **L3 White-box planner + full filter knowledge (model, horizon, constraint margins):** GCG/universal-injection gradient attacks on an open-weight planner, plus RL-Hammer-style trained attacker; scale compute and report ASR-vs-budget curves.
- **L4 Human red-team** (Nasr et al. include it explicitly).
- **L5 Composed attacker:** injection + sensor attack (GPS spoofing; Q6), which can invalidate the filter's state estimate — this is the honest limit of a physical-layer filter.
Reporting standard (synthesised from Carlini et al. 2019, Tramèr et al. 2020, Nasr et al. 2025): precise threat model; worst-case over all attacks per task (not average over attacks); budget sweeps showing attack saturation; sanity check that disabling the filter yields high SVR; benign utility and benign intervention rate on the same task set; confidence intervals over seeds/tasks; release code, attack prompts, and trained attacker checkpoints (where ethically appropriate).

### Gaps
- Nasr et al.'s per-defence ASR table not extracted (only "above 90% for most"). Precise Athalye/Tramèr counts not re-verified.

---

## Q5. Availability / denial-of-service attacks on LLMs and agents; safety vs liveness formalism

### Takeaway
There is an established line of *availability* attacks (sponge examples, Engorgio, agent malfunction amplification) and Greshake et al. already list availability as an IPI impact. Combined with the Lamport / Alpern–Schneider safety–liveness decomposition, this lets Paper V formalise: a filter that guarantees the safety property ("nothing bad happens") converts the attacker's best response into an attack on the liveness property ("something good eventually happens", i.e., mission completion) — "safety attack becomes liveness attack" — and a "stealthy denial" is a liveness violation achieved with per-step-plausible inputs.

### Cited Findings
- **Sponge examples** [M]: I. Shumailov, Y. Zhao, D. Bates, N. Papernot, R. Mullins, R. Anderson, "Sponge Examples: Energy-Latency Attacks on Neural Networks," IEEE EuroS&P 2021, arXiv:2006.03463 — [arXiv 2006.03463](https://arxiv.org/abs/2006.03463)
- **Engorgio** [M]: J. Dong et al., "An Engorgio Prompt Makes Large Language Model Babble on," ICLR 2025, arXiv:2412.19394 — crafted prompts that suppress EOS and inflate output length/compute — [arXiv 2412.19394](https://arxiv.org/abs/2412.19394)
- **Breaking Agents** [M, venue not verified]: B. Zhang, Y. Tan, Y. Shen, A. Salem, M. Backes, S. Zannettou, Y. Zhang, "Breaking Agents: Compromising Autonomous LLM Agents Through Malfunction Amplification," arXiv:2407.20859 (2024) — induces repetitive/irrelevant actions (looping) leading to task failure; LLM-based detection of such attacks is harder than for overtly harmful actions — [arXiv 2407.20859](https://arxiv.org/abs/2407.20859)
- **Greshake et al. 2023** [M]: lists availability/denial ("making the application useless") among IPI threat categories — [arXiv 2302.12173](https://arxiv.org/abs/2302.12173)
- **Safety vs liveness** [M]: L. Lamport, "Proving the Correctness of Multiprocess Programs," IEEE Trans. Software Eng. SE-3(2):125–143, 1977, DOI 10.1109/TSE.1977.229904 (introduces safety/liveness terminology); B. Alpern, F. B. Schneider, "Defining Liveness," Information Processing Letters 21(4):181–185, 1985, DOI 10.1016/0020-0190(85)90056-0 (every property is the intersection of a safety and a liveness property) — [DOI](https://doi.org/10.1016/0020-0190(85)90056-0)
- **DoS in security tradition** [M]: V. D. Gligor, "A Note on Denial-of-Service in Operating Systems," IEEE TSE SE-10(3):320–324, 1984 — classical availability framing — [DOI](https://doi.org/10.1109/TSE.1984.5010241)

### Inferences
- Formalisation for Paper V: let S = set of state-constraint-satisfying traces (safety, a closed set in the Alpern–Schneider topology) and L = traces in which the mission goal is eventually reached (liveness, dense). A sound filter enforces S regardless of planner input; the attacker's feasible objective is then to drive traces into S \ L (safe but non-completing). "Stealthy denial" = trace in S \ L whose per-step filter interventions/anomaly scores stay below a detection threshold (cf. RL-Hammer's stealth reward reaching 0% detection, Q1).
- Note: availability attacks in the LLM literature are mostly compute/latency (sponge, Engorgio) or task-looping (Breaking Agents); a *physical* mission-denial attack induced through a safety mechanism appears to be a gap Paper V can claim (no source found that does this for robots/UAVs — treat as an "I found no prior work" claim, to be re-checked).

### Gaps
- No primary source located (in this session) on LLM-robot/UAV denial attacks exploiting a safety filter. Breaking Agents' headline failure-rate numbers and venue not verified. Engorgio author list beyond first author not verified.

---

## Q6. UAV sensing attacks (composition context)

### Takeaway
GPS spoofing can capture/steer a UAV (Kerns et al. 2014), meaning a physical-layer filter that trusts its state estimate can be defeated or weaponised for denial by a composed sensing attack; this should be stated as an explicit out-of-scope or composition limitation.

### Cited Findings
- [M] A. J. Kerns, D. P. Shepard, J. A. Bhatti, T. E. Humphreys, "Unmanned Aircraft Capture and Control Via GPS Spoofing," Journal of Field Robotics 31(4):617–636, 2014, DOI 10.1002/rob.21513 — field demonstration of covertly capturing a UAV's navigation via spoofing — [DOI](https://doi.org/10.1002/rob.21513)
- [M] D. P. Shepard, J. A. Bhatti, T. E. Humphreys, A. A. Fansler, "Evaluation of Smart Grid and Civilian UAV Vulnerability to GPS Spoofing Attacks," Proc. ION GNSS 2012, pp. 3591–3605 — [ION](https://www.ion.org/publications/abstract.cfm?articleID=10275)

### Inferences
- Paper V threat model should state: attacker controls text/observation channel to the LLM (L0–L4); sensor integrity is assumed (or treated in an L5 composed experiment with bounded spoofing offset, which shifts the filter's predicted reachable set).

### Gaps
- Not researched further by design (brief context only).

---

## Q7. SaTML venue expectations (2025–2027 CFP)

### Takeaway
SaTML 2027: paper deadline **29 Sep 2026** (AoE), conference **8–10 May 2027, Reykjavík, Iceland** (aggregator; official CFP page could not be fetched). Page limits and artifact/ethics rules could not be verified this session.

### Cited Findings
- SaTML 2027 paper deadline 29 September 2026 23:59:59 UTC-12; conference May 8–10, 2027; Reykjavík, Iceland — [mldeadlines.com](https://mldeadlines.com/conference/satml/) (secondary aggregator; confirm on satml.org)
- Official CFP page https://satml.org/participate-cfp/ was **blocked** (permission request timed out) — page-limit/artifact/ethics text not retrieved.
- Venue norm signal: PAIR (a search-based jailbreak attacker) was published at SaTML 2025 [M] — [arXiv 2310.08419](https://arxiv.org/abs/2310.08419)

### Inferences
- Note the 2027 deadline (29 Sep 2026) has passed as of 15 Oct 2026; the next realistic SaTML target is SaTML 2028 (deadline likely ~Sep 2027) unless a second cycle exists — writer should check.
- Expected norms for an adaptive-attack-evaluated defence at SaTML (inferred from venue's community, i.e., Carlini/Tramèr et al. authors): explicit threat model section, adaptive attack section, released code/artifacts, ethics discussion of dual-use attacker release.

### Gaps
- Page limit, SoK category, artifact evaluation, and ethics-statement requirements for SaTML 2025–2027 not verified. From prior (unverified) recollection, SaTML uses IEEE two-column format with double-blind review and a main-body limit with unlimited references/appendices; do not cite without checking satml.org.

---

## BibTeX (keys requested; [M] entries should be spot-checked)

```bibtex
@inproceedings{greshake2023injection,
  author    = {Greshake, Kai and Abdelnabi, Sahar and Mishra, Shailesh and Endres, Christoph and Holz, Thorsten and Fritz, Mario},
  title     = {Not What You've Signed Up For: Compromising Real-World {LLM}-Integrated Applications with Indirect Prompt Injection},
  booktitle = {Proceedings of the 16th ACM Workshop on Artificial Intelligence and Security (AISec)},
  pages     = {79--90},
  year      = {2023},
  doi       = {10.1145/3605764.3623985},
  eprint    = {2302.12173}, archivePrefix = {arXiv}
}
@inproceedings{perez2022ignore,
  author = {Perez, F{\'a}bio and Ribeiro, Ian},
  title  = {Ignore Previous Prompt: Attack Techniques For Language Models},
  booktitle = {NeurIPS ML Safety Workshop}, year = {2022},
  eprint = {2211.09527}, archivePrefix = {arXiv}
}
@inproceedings{liu2024formalizing,
  author = {Liu, Yupei and Jia, Yuqi and Geng, Runpeng and Jia, Jinyuan and Gong, Neil Zhenqiang},
  title  = {Formalizing and Benchmarking Prompt Injection Attacks and Defenses},
  booktitle = {33rd USENIX Security Symposium}, year = {2024},
  eprint = {2310.12815}, archivePrefix = {arXiv}
}
@misc{liu2023houyi,
  author = {Liu, Yi and Deng, Gelei and Li, Yuekang and Wang, Kailong and Wang, Zihao and Wang, Xiaofeng and Zhang, Tianwei and Liu, Yepang and Wang, Haoyu and Zheng, Yan and Liu, Yang},
  title  = {Prompt Injection attack against {LLM}-integrated Applications},
  year = {2023}, eprint = {2306.05499}, archivePrefix = {arXiv}, note = {Preprint}
}
@misc{zou2023universal,
  author = {Zou, Andy and Wang, Zifan and Carlini, Nicholas and Nasr, Milad and Kolter, J. Zico and Fredrikson, Matt},
  title  = {Universal and Transferable Adversarial Attacks on Aligned Language Models},
  year = {2023}, eprint = {2307.15043}, archivePrefix = {arXiv}
}
@misc{liu2024automatic,
  author = {Liu, Xiaogeng and Yu, Zhiyuan and Zhang, Yizhe and Zhang, Ning and Xiao, Chaowei},
  title  = {Automatic and Universal Prompt Injection Attacks against Large Language Models},
  year = {2024}, eprint = {2403.04957}, archivePrefix = {arXiv}, note = {Preprint}
}
@inproceedings{pasquini2024neuralexec,
  author = {Pasquini, Dario and Strohmeier, Martin and Troncoso, Carmela},
  title  = {Neural Exec: Learning (and Learning from) Execution Triggers for Prompt Injection Attacks},
  booktitle = {Proceedings of the 17th ACM Workshop on Artificial Intelligence and Security (AISec)}, year = {2024},
  eprint = {2403.03792}, archivePrefix = {arXiv}
}
@misc{wen2025rlhammer,
  author = {Wen, Yuxin and Zharmagambetov, Arman and Evtimov, Ivan and Kokhlikyan, Narine and Goldstein, Tom and Chaudhuri, Kamalika and Guo, Chuan},
  title  = {{RL} Is a Hammer and {LLMs} Are Nails: A Simple Reinforcement Learning Recipe for Strong Prompt Injection},
  year = {2025}, eprint = {2510.04885}, archivePrefix = {arXiv}, note = {Preprint}
}
@inproceedings{debenedetti2024agentdojo,
  author = {Debenedetti, Edoardo and Zhang, Jie and Balunovi{\'c}, Mislav and Beurer-Kellner, Luca and Fischer, Marc and Tram{\`e}r, Florian},
  title  = {{AgentDojo}: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for {LLM} Agents},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS) Datasets and Benchmarks Track}, year = {2024},
  eprint = {2406.13352}, archivePrefix = {arXiv}
}
@inproceedings{zhan2024injecagent,
  author = {Zhan, Qiusi and Liang, Zhixiang and Ying, Zifan and Kang, Daniel},
  title  = {{InjecAgent}: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents},
  booktitle = {Findings of the Association for Computational Linguistics: ACL 2024}, year = {2024},
  eprint = {2403.02691}, archivePrefix = {arXiv}
}
@inproceedings{zhang2025asb,
  author = {Zhang, Hanrong and Huang, Jingyuan and Mei, Kai and Yao, Yifei and Wang, Zhenting and Zhan, Chenlu and Wang, Hongwei and Zhang, Yongfeng},
  title  = {Agent Security Bench ({ASB}): Formalizing and Benchmarking Attacks and Defenses in {LLM}-based Agents},
  booktitle = {International Conference on Learning Representations (ICLR)}, year = {2025},
  eprint = {2410.02644}, archivePrefix = {arXiv}, note = {Venue to verify}
}
@misc{bazinska2025b3,
  author = {Bazinska, Julia and Mathys, Max and Casucci, Francesco and Rojas-Carulla, Mateo and Davies, Xander and Souly, Alexandra and Pfister, Niklas},
  title  = {Breaking Agent Backbones: Evaluating the Security of Backbone {LLMs} in {AI} Agents},
  year = {2025}, eprint = {2510.22620}, archivePrefix = {arXiv}, note = {Preprint}
}
@misc{evtimov2025wasp,
  author = {Evtimov, Ivan and Zharmagambetov, Arman and Grattafiori, Aaron and Guo, Chuan and Chaudhuri, Kamalika},
  title  = {{WASP}: Benchmarking Web Agent Security Against Prompt Injection Attacks},
  year = {2025}, eprint = {2504.18575}, archivePrefix = {arXiv}, note = {Preprint}
}
@inproceedings{andriushchenko2025agentharm,
  author = {Andriushchenko, Maksym and Souly, Alexandra and Dziemian, Mateusz and Duenas, Derek and Lin, Maxwell and Wang, Justin and Hendrycks, Dan and Zou, Andy and Kolter, Zico and Fredrikson, Matt and Winsor, Eric and Wynne, Jerome and Gal, Yarin and Davies, Xander},
  title  = {{AgentHarm}: A Benchmark for Measuring Harmfulness of {LLM} Agents},
  booktitle = {International Conference on Learning Representations (ICLR)}, year = {2025},
  eprint = {2410.09024}, archivePrefix = {arXiv}
}
@misc{debenedetti2025camel,
  author = {Debenedetti, Edoardo and Shumailov, Ilia and Fan, Tianqi and Hayes, Jamie and Carlini, Nicholas and Fabian, Daniel and Kern, Christoph and Shi, Chongyang and Terzis, Andreas and Tram{\`e}r, Florian},
  title  = {Defeating Prompt Injections by Design},
  year = {2025}, eprint = {2503.18813}, archivePrefix = {arXiv}, note = {Preprint}
}
@misc{willison2023dualllm,
  author = {Willison, Simon},
  title  = {The Dual {LLM} Pattern for Building {AI} Assistants That Can Resist Prompt Injection},
  year = {2023}, howpublished = {\url{https://simonwillison.net/2023/Apr/25/dual-llm-pattern/}}
}
@misc{beurerkellner2025patterns,
  author = {Beurer-Kellner, Luca and Buesser, Beat and Cre{\c{t}}u, Ana-Maria and Debenedetti, Edoardo and Dobos, Daniel and Fabian, Daniel and Fischer, Marc and Froelicher, David and Grosse, Kathrin and Naeff, Daniel and Ozoani, Ezinwanne and Paverd, Andrew and Tram{\`e}r, Florian and Volhejn, V{\'a}clav},
  title  = {Design Patterns for Securing {LLM} Agents against Prompt Injections},
  year = {2025}, eprint = {2506.08837}, archivePrefix = {arXiv}, note = {Preprint}
}
@misc{costa2025fides,
  author = {Costa, Manuel and K{\"o}pf, Boris and Kolluri, Aashish and Paverd, Andrew and Russinovich, Mark and Salem, Ahmed and Tople, Shruti and Wutschitz, Lukas and Zanella-B{\'e}guelin, Santiago},
  title  = {Securing {AI} Agents with Information-Flow Control},
  year = {2025}, eprint = {2505.23643}, archivePrefix = {arXiv}, note = {Preprint}
}
@misc{wu2024fsecure,
  author = {Wu, Fangzhou and Cecchetti, Ethan and Xiao, Chaowei},
  title  = {System-Level Defense against Indirect Prompt Injection Attacks: An Information Flow Control Perspective},
  year = {2024}, eprint = {2409.19091}, archivePrefix = {arXiv}, note = {Preprint}
}
@inproceedings{wu2025isolategpt,
  author = {Wu, Yuhao and Roesner, Franziska and Kohno, Tadayoshi and Zhang, Ning and Iqbal, Umar},
  title  = {{IsolateGPT}: An Execution Isolation Architecture for {LLM}-Based Agentic Systems},
  booktitle = {Network and Distributed System Security Symposium (NDSS)}, year = {2025},
  eprint = {2403.04960}, archivePrefix = {arXiv}
}
@misc{shi2025progent,
  author = {Shi, Tianneng and He, Jingxuan and Wang, Zhun and Wu, Linyu and Li, Hongwei and Guo, Wenbo and Song, Dawn},
  title  = {Progent: Programmable Privilege Control for {LLM} Agents},
  year = {2025}, eprint = {2504.11703}, archivePrefix = {arXiv}, note = {Preprint}
}
@inproceedings{zhu2025melon,
  author = {Zhu, Kaijie and Yang, Xianjun and Wang, Jindong and Guo, Wenbo and Wang, William Yang},
  title  = {{MELON}: Provable Defense Against Indirect Prompt Injection Attacks in {AI} Agents},
  booktitle = {International Conference on Machine Learning (ICML)}, year = {2025},
  eprint = {2502.05174}, archivePrefix = {arXiv}
}
@inproceedings{chen2025struq,
  author = {Chen, Sizhe and Piet, Julien and Sitawarin, Chawin and Wagner, David},
  title  = {{StruQ}: Defending Against Prompt Injection with Structured Queries},
  booktitle = {34th USENIX Security Symposium}, year = {2025},
  eprint = {2402.06363}, archivePrefix = {arXiv}
}
@inproceedings{chen2025secalign,
  author = {Chen, Sizhe and Zharmagambetov, Arman and Mahloujifar, Saeed and Chaudhuri, Kamalika and Wagner, David and Guo, Chuan},
  title  = {{SecAlign}: Defending Against Prompt Injection with Preference Optimization},
  booktitle = {ACM Conference on Computer and Communications Security (CCS)}, year = {2025},
  eprint = {2410.05451}, archivePrefix = {arXiv}
}
@misc{hines2024spotlighting,
  author = {Hines, Keegan and Lopez, Gary and Hall, Matthew and Zarfati, Federico and Zunger, Yonatan and K{\i}c{\i}man, Emre},
  title  = {Defending Against Indirect Prompt Injection Attacks With Spotlighting},
  year = {2024}, eprint = {2403.14720}, archivePrefix = {arXiv}, note = {Preprint}
}
@misc{wallace2024hierarchy,
  author = {Wallace, Eric and Xiao, Kai and Leike, Reimar and Weng, Lilian and Heidecke, Johannes and Beutel, Alex},
  title  = {The Instruction Hierarchy: Training {LLMs} to Prioritize Privileged Instructions},
  year = {2024}, eprint = {2404.13208}, archivePrefix = {arXiv}, note = {Preprint}
}
@inproceedings{liu2025datasentinel,
  author = {Liu, Yupei and Jia, Yuqi and Jia, Jinyuan and Song, Dawn and Gong, Neil Zhenqiang},
  title  = {{DataSentinel}: A Game-Theoretic Detection of Prompt Injection Attacks},
  booktitle = {IEEE Symposium on Security and Privacy (S\&P)}, year = {2025},
  eprint = {2504.11358}, archivePrefix = {arXiv}
}
@inproceedings{carlini2017towards,
  author = {Carlini, Nicholas and Wagner, David},
  title  = {Towards Evaluating the Robustness of Neural Networks},
  booktitle = {IEEE Symposium on Security and Privacy (S\&P)}, pages = {39--57}, year = {2017},
  doi = {10.1109/SP.2017.49}, eprint = {1608.04644}, archivePrefix = {arXiv}
}
@inproceedings{athalye2018obfuscated,
  author = {Athalye, Anish and Carlini, Nicholas and Wagner, David},
  title  = {Obfuscated Gradients Give a False Sense of Security: Circumventing Defenses to Adversarial Examples},
  booktitle = {International Conference on Machine Learning (ICML)}, pages = {274--283}, year = {2018},
  eprint = {1802.00420}, archivePrefix = {arXiv}
}
@misc{carlini2019evaluating,
  author = {Carlini, Nicholas and Athalye, Anish and Papernot, Nicolas and Brendel, Wieland and Rauber, Jonas and Tsipras, Dimitris and Goodfellow, Ian and Madry, Aleksander and Kurakin, Alexey},
  title  = {On Evaluating Adversarial Robustness},
  year = {2019}, eprint = {1902.06705}, archivePrefix = {arXiv}
}
@inproceedings{tramer2020adaptive,
  author = {Tram{\`e}r, Florian and Carlini, Nicholas and Brendel, Wieland and Madry, Aleksander},
  title  = {On Adaptive Attacks to Adversarial Example Defenses},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS)}, year = {2020},
  eprint = {2002.08347}, archivePrefix = {arXiv}
}
@inproceedings{zhan2025adaptive,
  author = {Zhan, Qiusi and Fang, Richard and Panchal, Henil Shalin and Kang, Daniel},
  title  = {Adaptive Attacks Break Defenses Against Indirect Prompt Injection Attacks on {LLM} Agents},
  booktitle = {Findings of the Association for Computational Linguistics: NAACL 2025}, year = {2025},
  eprint = {2503.00061}, archivePrefix = {arXiv}
}
@inproceedings{nasr2026attacker,
  author = {Nasr, Milad and Carlini, Nicholas and Sitawarin, Chawin and Schulhoff, Sander V. and Hayes, Jamie and Ilie, Michael and Pluto, Juliette and Song, Shuang and Chaudhari, Harsh and Shumailov, Ilia and Thakurta, Abhradeep and Xiao, Kai Yuanqing and Terzis, Andreas and Tram{\`e}r, Florian},
  title  = {The Attacker Moves Second: Stronger Adaptive Attacks Bypass Defenses Against {LLM} Jailbreaks and Prompt Injections},
  booktitle = {35th USENIX Security Symposium}, year = {2026},
  eprint = {2510.09023}, archivePrefix = {arXiv}
}
@inproceedings{chao2025pair,
  author = {Chao, Patrick and Robey, Alexander and Dobriban, Edgar and Hassani, Hamed and Pappas, George J. and Wong, Eric},
  title  = {Jailbreaking Black Box Large Language Models in Twenty Queries},
  booktitle = {IEEE Conference on Secure and Trustworthy Machine Learning (SaTML)}, year = {2025},
  eprint = {2310.08419}, archivePrefix = {arXiv}
}
@inproceedings{mehrotra2024tap,
  author = {Mehrotra, Anay and Zampetakis, Manolis and Kassianik, Paul and Nelson, Blaine and Anderson, Hyrum and Singer, Yaron and Karbasi, Amin},
  title  = {Tree of Attacks: Jailbreaking Black-Box {LLMs} Automatically},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS)}, year = {2024},
  eprint = {2312.02119}, archivePrefix = {arXiv}
}
@inproceedings{liu2024autodan,
  author = {Liu, Xiaogeng and Xu, Nan and Chen, Muhao and Xiao, Chaowei},
  title  = {{AutoDAN}: Generating Stealthy Jailbreak Prompts on Aligned Large Language Models},
  booktitle = {International Conference on Learning Representations (ICLR)}, year = {2024},
  eprint = {2310.04451}, archivePrefix = {arXiv}
}
@inproceedings{shumailov2021sponge,
  author = {Shumailov, Ilia and Zhao, Yiren and Bates, Daniel and Papernot, Nicolas and Mullins, Robert and Anderson, Ross},
  title  = {Sponge Examples: Energy-Latency Attacks on Neural Networks},
  booktitle = {IEEE European Symposium on Security and Privacy (EuroS\&P)}, year = {2021},
  eprint = {2006.03463}, archivePrefix = {arXiv}
}
@inproceedings{dong2025engorgio,
  author = {Dong, Jianshuo and others},
  title  = {An Engorgio Prompt Makes Large Language Model Babble on},
  booktitle = {International Conference on Learning Representations (ICLR)}, year = {2025},
  eprint = {2412.19394}, archivePrefix = {arXiv}, note = {Complete author list before use}
}
@misc{zhang2024breakingagents,
  author = {Zhang, Boyang and Tan, Yicong and Shen, Yun and Salem, Ahmed and Backes, Michael and Zannettou, Savvas and Zhang, Yang},
  title  = {Breaking Agents: Compromising Autonomous {LLM} Agents Through Malfunction Amplification},
  year = {2024}, eprint = {2407.20859}, archivePrefix = {arXiv}, note = {Check for published version}
}
@article{lamport1977proving,
  author = {Lamport, Leslie},
  title  = {Proving the Correctness of Multiprocess Programs},
  journal = {IEEE Transactions on Software Engineering}, volume = {SE-3}, number = {2}, pages = {125--143}, year = {1977},
  doi = {10.1109/TSE.1977.229904}
}
@article{alpern1985liveness,
  author = {Alpern, Bowen and Schneider, Fred B.},
  title  = {Defining Liveness},
  journal = {Information Processing Letters}, volume = {21}, number = {4}, pages = {181--185}, year = {1985},
  doi = {10.1016/0020-0190(85)90056-0}
}
@article{gligor1984dos,
  author = {Gligor, Virgil D.},
  title  = {A Note on Denial-of-Service in Operating Systems},
  journal = {IEEE Transactions on Software Engineering}, volume = {SE-10}, number = {3}, pages = {320--324}, year = {1984},
  doi = {10.1109/TSE.1984.5010241}
}
@article{kerns2014gps,
  author = {Kerns, Andrew J. and Shepard, Daniel P. and Bhatti, Jahshan A. and Humphreys, Todd E.},
  title  = {Unmanned Aircraft Capture and Control Via {GPS} Spoofing},
  journal = {Journal of Field Robotics}, volume = {31}, number = {4}, pages = {617--636}, year = {2014},
  doi = {10.1002/rob.21513}
}
@inproceedings{shepard2012gps,
  author = {Shepard, Daniel P. and Bhatti, Jahshan A. and Humphreys, Todd E. and Fansler, Aaron A.},
  title  = {Evaluation of Smart Grid and Civilian {UAV} Vulnerability to {GPS} Spoofing Attacks},
  booktitle = {Proceedings of ION GNSS}, pages = {3591--3605}, year = {2012}
}
```
