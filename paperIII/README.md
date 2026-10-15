# Paper III — Certificates as Constraints

*Feasibility-Preserving Multi-Agent Reinforcement Learning for UAV Swarms Whose Guarantees Degrade* (target: NeurIPS).

Each aircraft carries a certified protection level `ρ_i(t) = e^{LT}·γ_sup·Δ_i(t)`, taken from the parent certificate (paper D). A task with alert limit `α_j` may be held only while `ρ_i(t) ≤ α_j`. This folder holds the theory checks, the simulator, the multi-agent RL study and the manuscript.

```
paperIII/
  experiments/
    certcmdp/certificate.py    ρ_i(t) process; every constant read from ../../results (measured)
    certcmdp/combinatorics.py  closed forms (deficiency, margin, worst cases) + projection layers
    certcmdp/env.py            CertSwarm vectorised fleet environment
    e1_verify.py               brute-force oracle check of every closed form
    e2_degradation.py          coverage vs φ, graded worst case, population lift (RQ2, RQ6)
    e3_latency.py              real-time ceiling (RQ4)
    e4_dynamics.py             hysteresis, predictive rule, allocator rate, misreporting (RQ5)
    e5_marl.py                 PPO study: projection / masking / Lagrangian / blind (RQ1, RQ3)
    e6_aggregate.py            IQM + stratified bootstrap + Clopper–Pearson
    export_figdata.py, make_numbers.py, run_all.sh, run_marl.sh
  results/                     every CSV behind every number
  manuscript/                  main.tex, fig_framework.tex (Fig. 1, TikZ), sec_results_marl.tex,
                               refs.bib, numbers.tex + tab_main.tex (generated), figdata/ (generated)
  RUNBOOK.md                   scale-up and extension experiments R1–R9
```

## Reproduce

```bash
cd paperIII/experiments
bash run_all.sh          # E1–E4 + references + numbers (~5 min, 2 cores)
bash run_marl.sh         # E5: 5 methods × 5 seeds (~1 h, 2 cores)
cd ../manuscript && latexmk -pdf main.tex
```

Dependencies: `numpy`, `scipy`, `torch` (CPU is enough), and TeX Live with `pgfplots`.
