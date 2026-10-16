#!/usr/bin/env bash
# Paper V non-LLM pipeline (P0-P2). Every seed is fixed by its block (runbook §1.2).
#   PAR=4 bash run_all.sh            # container: reduced P2 grid
#   PAR=32 FULL=1 bash run_all.sh    # server: full P2 grid
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONHASHSEED=0
PAR="${PAR:-4}"
python3 constants.py --write-csv
python3 plant.py --calibrate-wbar --seeds 11000-11199 --inflate 1.2
python3 plant.py --check-wbar --seeds 14000-14199
python3 budget.py --levels
python3 -m pytest tests -q -x
python3 filter.py --latency --n 20000 --seed 10001
python3 run_campaign.py --phase p1-timing --quick
python3 run_campaign.py --phase p1-property --episodes 2000 --campaign-id p1_property --resume --par "$PAR"
if [ "${FULL:-0}" = 1 ]; then MARGINS=10,20; BTOT=b0,b1,b2,b3; OPT=cem,cma; MISSIONS=300; else MARGINS=10,20; BTOT=b0,b1; OPT=cem; MISSIONS=100; fi
python3 run_campaign.py --phase p2-budget --stage monitor --campaign-id p2_monitor --margins "$MARGINS" --btot "$BTOT" --gamma 1.625 --missions 200 --resume --par "$PAR"
python3 adaptive.py --attacker A6 --goals G1,G2,G3,G4 --btot "$BTOT" --margins "$MARGINS" --opt "$OPT" --seed-block 12000 --par "$PAR" --out a6_search.csv
python3 adaptive.py --attacker A6 --goals G1,G2,G3,G4 --btot "$BTOT" --margins "$MARGINS" --opt "$OPT" --seed-block 13000 --par "$PAR" --out a6_search_heldout.csv
python3 run_campaign.py --phase p2 --planners scripted,random,oracle:best,oracle:heldout --btot "$BTOT" --margins "$MARGINS" \
    --gamma 1.625,15 --missions "$MISSIONS" --seed-block 14000 --filters psf,none,simplex,cbf1,fixed_margin \
    --campaign-id p2_main --resume --par "$PAR"
python3 run_campaign.py --phase p2-budget --stage curve --campaign-id p2_budget --margins "$MARGINS" --btot "$BTOT" --gamma 1.625 \
    --missions 50 --seed-block 14000 --resume --par "$PAR"
python3 stats.py --campaign p1_property,p2_main,p2_budget --rq rq1,denial_envelope
