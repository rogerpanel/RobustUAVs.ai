# Paper I: What Authenticity Costs in Metres

A certified budget for cryptography and sensing in UAV navigation.

```
paperI/
  experiments/        Python models and simulations (~30 s end to end; needs numpy)
    constants.py        every input, with a provenance tag
    transport.py        CAN / CAN FD / MAVLink frame models, admissible rate, response-time bound, DES
    budget.py           gamma ratio, crossover (constant rate and measured envelopes), Delta_auth
    clock_freshness.py  freshness binding, oscillator holdover, GNSS time push
    induced_verification.py   forged-signature flood DES and amplification ratio
    amortise_select.py  batch signing and the certified selection rule
    e1_inertial_gamma.py      GNSS-outage dead reckoning on the benign flight's IMU log (raw data)
    e5_hcrl_bus.py      decoding of the HCRL UAVCAN capture (raw data)
    export_figdata.py   pgfplots .dat files
    make_numbers.py     manuscript/numbers.tex (one macro per quoted number)
    run_all.sh          regenerate everything
  results/            CSV outputs (shared inputs: ../results/gamma_campaign_samples.csv,
                      ../results/hcrl_type_signatures.csv)
  manuscript/         main.tex (IEEEtran), fig_*.tex (TikZ/pgfplots), figdata/, numbers.tex, refs.bib
```

## Rebuild

```bash
bash paperI/experiments/run_all.sh
cd paperI/manuscript && latexmk -pdf main.tex
```

For Overleaf, upload the `manuscript/` folder; the main file is `main.tex`.

The experiments that have and have not been run are listed in the paper's table "Validation
Status of the Inputs" and in the README at the root of the review artifact.
