# Paper IV: When the Attacker Is Indistinguishable from the Weather

A unified perturbation budget for certified UAV autonomy.

From the navigation inputs alone, an attack, a sensor fault and an environmental disturbance can
be indistinguishable (*adversarial equivalence*). The paper bounds the probability of undetected
mission failure with a source-agnostic, dependence-sharp budget
δ_tot = δ_net ⊕ δ_adv ⊕ δ_gnss ⊕ δ_fault ⊕ δ_env, and tests it against optimised attackers in five
disguise families.

```
paperIV/
  experiments/          Python simulations and analyses (numpy, scipy; cma and optuna for the
                        scaled attacker study)
    constants.py          every input, with a provenance tag
    sim.py                lateral closed loop: KF, Dryden wind, faults, GNSS drift, outages and
                          jamming noise, re-anchoring, detectors D1-D4, anchor gate, saturation
                          alarm, five disguise families
    depbounds.py          union bound, Rearrangement Algorithm, independence, comonotone,
                          finite-sample (Clopper-Pearson) band
    run_pilot.py          pilot: calibration, attackers and cross-evaluation, anchor sweep,
                          terminal window, marginals and gaps, soundness, negative controls
                          (~27 min on 2 cores)
    e2y_no_anchor_gate.py   cross-evaluation with the anchor gate removed
    r1_attackers.py       scaled attacker study and soundness test
    r1_diagnose.py        diagnosis of the scaled test's violations
    r8_analytic_bound.py  analytic (LP) stealth budget; r8_assemble.py assembles its table
    r5_measured_gnss.py   measured jamming marginal (uses ../results/gamma_campaign_samples.csv)
    e4_revised.py         revised instantiation on fresh seeds
    make_numbers.py       manuscript/numbers.tex, tab_*_body.tex, figdata/*.dat
  results/              result files behind every number, and run_meta.json (seed blocks, budgets)
  manuscript/           main.tex (IEEEtran), sec_*.tex, fig_*.tex (TikZ/pgfplots), figdata/,
                        numbers.tex, tab_*_body.tex, refs.bib
```

## Rebuild

```bash
cd paperIV/experiments
python3 make_numbers.py               # numbers, tables and figure data from results/
cd ../manuscript && latexmk -pdf main.tex
```

The full re-run (pilot, ablation, scaled attacker study, analytic stealth budget, measured
marginal, revised instantiation), its run times and its seed blocks are described in the README at
the root of the review artifact. For Overleaf, upload the `manuscript/` folder; the main file is
`main.tex`.
