#!/usr/bin/env bash
# Paper I: regenerate every result and figure-data file from committed inputs.
# Inputs: ../../results/{gamma_campaign_samples,hcrl_type_signatures}.csv
# (parent artifact) and the literature constants in constants.py.
set -euo pipefail
cd "$(dirname "$0")"
# Runbook experiments on the raw corpus. Each prints SKIPPED and writes nothing
# when its data is not staged, so a missing corpus degrades the run and never
# leaves a fabricated or stale result. constants.py then reads whichever
# measured CSVs exist and falls back otherwise.
python3 e5_hcrl_bus.py
python3 e1_inertial_gamma.py
python3 transport.py
python3 budget.py
python3 clock_freshness.py
python3 induced_verification.py
python3 amortise_select.py
python3 export_figdata.py
python3 make_numbers.py
python3 -c "import constants; constants.write_provenance()"
echo "Paper I results regenerated (results/, manuscript/figdata/, manuscript/numbers.tex)"
