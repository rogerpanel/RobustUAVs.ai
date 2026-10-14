# Paper IV — When the Attacker Is Indistinguishable from the Weather

*A Cross-Layer Benchmark and a Unified Perturbation Budget for Certified UAV Autonomy* (target: USENIX Security).

The paper formalises **adversarial equivalence**: from the navigation inputs alone, an attack, a fault and an environmental disturbance can be indistinguishable. It then builds a **source-agnostic, dependence-sharp floor** on mission completion from the budget δ_tot = δ_net ⊕ δ_adv ⊕ δ_gnss ⊕ δ_fault ⊕ δ_env.

```
paperIV/
  experiments/
    constants.py      every constant with a provenance tag ([parent] values read from paper D)
    sim.py            vectorised lateral closed loop: KF, Dryden wind, faults, GNSS drift/outage,
                      re-anchoring (C2'), detectors D1-D4 + anchor gate, five disguise families
    depbounds.py      union (standard) bound, Rearrangement Algorithm, independence, comonotone
    run_pilot.py      E1 calibration, E2/E2x attackers + cross-evaluation, E2b anchor sweep,
                      E2c terminal window, E3 gap decomposition, E4 bound + soundness (Holm),
                      saturation control, E5 negative controls
    e2y_no_anchor_gate.py   cross-evaluation with the anchor gate removed
    make_numbers.py   numbers.tex, tab_*_body.tex, figdata/*.dat
  results/            every CSV behind every number (+ run_meta.json)
  manuscript/         main.tex (USENIX style, single file with inputs), main_single.tex
                      (fully self-contained), fig_framework.tex (Fig. 1, TikZ),
                      fig_results.tex (pgfplots), sec_*.tex, refs.bib (reconciled, STATUS-tagged)
  RUNBOOK_CLAUDE_CODE.md   R1-R10: stronger attackers, 6-DoF/EKF2, PX4 SITL, network coupling,
                           measured marginals, packaging, baselines, analytic stealth bound
```

## Reproduce

```bash
cd paperIV/experiments
python3 run_pilot.py          # ≈ 27 min, 2 cores, < 1.5 GB RAM (numpy, scipy)
python3 e2y_no_anchor_gate.py
python3 make_numbers.py
cd ../manuscript && latexmk -pdf main.tex
```

Seed blocks: 1xxx calibration · 2xxx attacker optimisation (incl. E2b/E2c/E5) · 3xxx held-out attackers · 4xxx held-out evaluation (E2x 4100+, E2b 4200+, E2c 4300+, E4 4400+, E2y 4500+, E5 4900+).

## Before submission

- Run the runbook items **R1** (stronger attackers) and **R3** (PX4 SITL transfer). Both are load-bearing.
- Re-check every `[PRE]` and `[P]` entry in `manuscript/refs.bib`.
- Anonymise the artifact with `tools/anonymise.py`.
