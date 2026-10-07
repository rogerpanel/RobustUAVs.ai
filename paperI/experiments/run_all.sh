#!/usr/bin/env bash
# Paper I: regenerate every result and figure-data file from committed inputs.
# Inputs: ../../results/{gamma_campaign_samples,hcrl_type_signatures}.csv
# (parent artifact) and the literature constants in constants.py.
set -euo pipefail
cd "$(dirname "$0")"
python3 transport.py
python3 budget.py
python3 clock_freshness.py
python3 induced_verification.py
python3 amortise_select.py
python3 export_figdata.py
python3 make_numbers.py
echo "Paper I results regenerated (results/, manuscript/figdata/, manuscript/numbers.tex)"
