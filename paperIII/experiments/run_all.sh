#!/usr/bin/env bash
# Paper III: regenerate every result, figure-data file and number from the
# committed parent artifact (../../results/*.csv). ~10 min on 2 CPU cores for
# E1-E4; the MARL study (E5) is separate because it trains 25 policies:
#   bash run_marl.sh            (about 1 h on 2 cores; see RUNBOOK for scale-up)
set -euo pipefail
cd "$(dirname "$0")"
python3 certcmdp/certificate.py
python3 e1_verify.py
python3 e2_degradation.py
python3 e3_latency.py
python3 e4_dynamics.py
python3 e5_marl.py --references
python3 e6_aggregate.py || echo "no MARL runs yet"
python3 export_figdata.py
python3 r4_analysis.py > /dev/null || echo "no R4 SITL results yet"   # RQ8, from the committed SITL run
python3 r4b_analysis.py > /dev/null || echo "no R4b results yet"     # RQ8, pre-registered test (R4B_PROTOCOL.md)
python3 make_numbers.py
echo "Paper III results regenerated (results/, manuscript/figdata/, manuscript/numbers.tex)"
