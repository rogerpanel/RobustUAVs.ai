# Paper I — What Authenticity Costs in Metres

A certified budget for cryptography and sensing in UAV navigation. This paper follows on from the parent manuscript "From Wire to Flight" (paper D).

```
paperI/
  experiments/        Python models and simulations (stdlib only; ~30 s end to end)
    constants.py        every input with a provenance tag
    transport.py        CAN / CAN FD / MAVLink frame models, r*, response-time bound, DES
    budget.py           gamma ratio, crossover (supremum and horizon-matched), Delta_auth
    clock_freshness.py  freshness binding, oscillator holdover, GNSS time push
    induced_verification.py   forged-signature flood DES and amplification ratio
    amortise_select.py  batch signing and the certified selection rule
    export_figdata.py   pgfplots .dat files
    make_numbers.py     manuscript/numbers.tex (one macro per quoted number)
    run_all.sh          regenerate everything
  results/            CSV outputs (inputs: ../results/gamma_campaign_samples.csv,
                      ../results/hcrl_type_signatures.csv)
  manuscript/         main.tex (IEEEtran), fig_*.tex (TikZ/pgfplots), figdata/, numbers.tex, refs.bib
  RUNBOOK_CLAUDE_CODE.md   experiments E1–E8 that need raw data, PX4 SITL or hardware
```

## Rebuild

```bash
bash paperI/experiments/run_all.sh
cd paperI/manuscript && latexmk -pdf main.tex
```

Overleaf: upload the `manuscript/` folder. IEEEtran ships with Overleaf, and the main file is `main.tex`.

## Before submission

- Entries marked `% VERIFY` in `refs.bib` need their bibliographic details checked. There are 13, including author lists for three items.
- γ_a is a proxy. Run E1 or E3 from the runbook before treating the sensing-side conclusions as final.
