#!/usr/bin/env bash
# Paper V NON-LLM pilot: full pipeline. All seeds are fixed inside the code.
#   SCALE=1.0 WORKERS=2 ./run_all.sh      (~35 min on 2 CPUs)
#   SCALE=0.05 ./run_all.sh               (smoke test, ~6 min)
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONHASHSEED=0
SCALE="${SCALE:-1.0}" WORKERS="${WORKERS:-2}" python3 run_campaign.py cem main hand budget mismatch negative nested
python3 aggregate.py
python3 export_figdata.py
python3 make_summary.py
