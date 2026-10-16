# Paper V — The Untrusted Planner

*Keep Flying Whatever the Model Says: Predictive Safety Filtering for Language-Model UAV Agents under Adaptive Attack* (target: next IEEE SaTML cycle; fallback USENIX Security).

A predictive safety filter sits between a language-model planner and the fleet. It executes the planner's proposal only when a certified, tightened horizon plan exists that starts with it; otherwise it follows the continuation of the last certified plan, then a latched fallback. Safety of the *true* state then holds for every planner output sequence under the stated assumptions (bounded model mismatch, Paper III certificate with staleness look-ahead, covert sensing budget from Paper IV), so a prompt-injection attacker is reduced from causing violations to causing denial. Denial is split into filter-induced and in-envelope (stall) denial; the latter no filter can remove.

```
paperV/
  experiments/          seeded controllable fleet plant, admissible set + tightening,
                        filter (OSQP + Clarabel, continuation plan, latched fallback),
                        budget (Paper IV δ_tot wrapper), planners incl. MockLLM stub and
                        action-space oracle, CEM attacker search, campaign runner, stats,
                        figure-data export, run_all.sh
  results/              per-episode CSVs, summary cells, solve times, run_meta.json
  figdata/              pgfplots .dat files used by the manuscript
  results_summary.md    every pilot headline number with CIs and episode counts
  manuscript/           PaperV_main.tex (IEEEtran, TikZ Fig. 1, pgfplots), PaperV_refs.bib, PDF
  docs/research_report.md        programme extraction, corrections, literature, methodology
  docs/research_notes/           source notes (Papers I–IV, codebase map, three literature maps)
  RUNBOOK.md            phases P0–P6 with exit gates for the full campaign (real LLMs on a server)
```

## Status

- **Pilot done (non-LLM planners, simulation only):** 0 true-state violations in 3,608,500 aircraft-steps inside the assumptions (95% Clopper–Pearson upper bound 8.3e-7); filter-off oracle violates in every episode; violations appear only in cells that break an assumption.
- **Pending:** all real-LLM cells (A0–A5), detector-gated composition attacker, non-trivial baselines, δ_adv = 5.463 m cells (pilot used 4.371 m), platform Safety Filter page. Marked `\pending` in the manuscript.
- Dependencies beyond `requirements.txt`: `osqp`, `clarabel`, `scipy`, `numpy`.

## Reproduce the pilot

```bash
cd paperV/experiments
pip install osqp clarabel scipy numpy
bash run_all.sh        # ~35 min on 2 CPUs; writes ../results and ../figdata
```

Solver time limits are wall-clock, so liveness statistics are not bit-reproducible; violation counts are. The runbook switches to fixed iteration limits for the paper runs.
