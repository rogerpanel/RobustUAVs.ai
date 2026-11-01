# Paper III: Certificates as Constraints

A certified reference monitor for learned task allocation in UAV swarms under navigation attacks.

Each aircraft carries a certified protection level `ρ_i(t) = e^{L·T_c}·γ_sup·Δ_i(t)`, where
`Δ_i(t)` is the staleness of its navigation input. A task with alert limit `α_j` may be held only
while `ρ_i(t) ≤ α_j`. The certified projection layer sits between an untrusted allocator and the
fleet and executes only assignments that satisfy this constraint, with maximum coverage.

```
paperIII/
  experiments/          Python (numpy, scipy, torch on CPU)
    certcmdp/certificate.py    ρ_i(t) process; measured constants read from ../../results
    certcmdp/combinatorics.py  closed forms (deficiency, margin, worst cases) and projection layers
    certcmdp/env.py            CertSwarm, the vectorised fleet environment
    certcmdp/trace_process.py  certificate process driven by measured GNSS staleness traces
    e1_verify.py        brute-force oracle check of every closed form
    e2_degradation.py   coverage under collapse and graded degradation, population lift (RQ2, RQ6)
    e3_latency.py       latency of the monitor and the projection layer (RQ4)
    e4_dynamics.py      hysteresis, predictive rule, allocator rate, misreporting (RQ5)
    e5_marl.py          learning study: projection, masking, Lagrangian and QMIX baselines,
                        non-learned references incl. CBBA (RQ1, RQ3)
    e6_aggregate.py     IQM, stratified bootstrap, Clopper-Pearson bounds
    r5_consensus.py     Byzantine aircraft and W-MSR agreement (RQ7)
    r6_vector.py        vector certificates
    r3_extract_traces.py              GNSS staleness traces from the public flight logs
    r4_sitl_fleet.py, r4_analysis.py, r4b_analysis.py   PX4 software-in-the-loop flights (RQ8)
    export_figdata.py   manuscript/figdata/*.dat
    make_numbers.py     manuscript/numbers.tex and the generated tables
    run_all.sh, run_marl.sh, run_r_marl.sh, run_r1_kbs.sh, run_r1_kbs24.sh, run_server_paperIII.sh
  results/              every CSV behind every number (each row carries a provenance column)
  manuscript/           main.tex (IEEEtran), sec_results_marl.tex, fig_framework.tex, refs.bib;
                        numbers.tex, tab_*.tex and figdata/ are generated
  R4B_PROTOCOL.md       pre-registration of the first rerun of the closed-loop flights
  R4C_PROTOCOL.md       pre-registration of the third closed-loop run
```

## Rebuild

```bash
cd paperIII/experiments
bash run_all.sh          # closed forms, simulations, references, aggregation, numbers (~5 min)
bash run_marl.sh         # learning study, headline seeds 0-4 (~1 h on 2 cores)
cd ../manuscript && latexmk -pdf main.tex
```

For Overleaf, upload the `manuscript/` folder; the main file is `main.tex`.

The README at the root of the review artifact maps each result in the paper to its script and
result file, and lists the run time of every stage, including the extended learning runs and the
PX4 flights.
