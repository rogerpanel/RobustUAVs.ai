#!/usr/bin/env bash
# Paper V, full P2 grid on the server (runbook P2.2). No LLM calls, no API keys.
#
#   cd ~/paper5-work/paperV/experiments && PAR=$(nproc) bash run_p2_server.sh
#
# Search cells print one line each when they finish (about 25-40 min per cell on 4 cores), so a
# quiet log during the search is normal. Every stage resumes: rerunning the script after an interruption skips finished episodes
# and finished search cells. Raw campaign logs stay in ../results/campaign/ (git-ignored);
# the script packs the aggregate CSVs and the raw logs into two archives in $HOME at the end.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONHASHSEED=0
PAR="${PAR:-$(nproc)}"
MISSIONS="${MISSIONS:-300}"
BASE_PLANNERS="${BASE_PLANNERS:-}"          # e.g. scripted,oracle:best to trim the baseline filters
BASE_MISSIONS="${BASE_MISSIONS:-0}"
OPT="${OPT:-cem,cma}"                        # optimisers of the primary search (12xxx)
HELDOUT_OPT="${HELDOUT_OPT:-$OPT}"           # optimisers of the held-out re-search (13xxx)
CURVE_MISSIONS="${CURVE_MISSIONS:-100}"
STAMP=$(date -u +%Y-%m-%d)
log() { echo "== $(date -u +%H:%M:%S) $*"; }
q() { grep -v --line-buffered "Polishing not needed" || true; }

log "P1 inputs (deterministic: must reproduce the committed files)"
python3 constants.py --write-csv
python3 plant.py --check-wbar --seeds 14000-14199
python3 budget.py --levels | tail -n 4
git -C ../.. diff --stat -- paperV/results/constants_paperV.csv paperV/results/budget_levels.csv paperV/results/wbar_heldout.csv
python3 -m pytest tests -q -x -p no:cacheprovider 2>&1 | q | tail -n 3

log "stealth monitor: A0 on 11000-11199"
python3 run_campaign.py --phase p2-budget --stage monitor --campaign-id p2_monitor \
    --margins 10,20 --btot b0,b1,b2,b3 --gamma 1.625 --missions 200 --resume --par "$PAR" 2>&1 | q

log "A6 search, primary (12xxx), CEM + CMA-ES"
python3 adaptive.py --attacker A6 --goals G1,G2,G3,G4 --btot b0,b1,b2,b3 --margins 10,20 \
    --opt "$OPT" --seed-block 12000 --par "$PAR" --out a6_search.csv 2>&1 | q

log "A6 re-search, held-out attackers (13xxx)"
python3 adaptive.py --attacker A6 --goals G1,G2,G3,G4 --btot b0,b1,b2,b3 --margins 10,20 \
    --opt "$HELDOUT_OPT" --seed-block 13000 --par "$PAR" --out a6_search_heldout.csv 2>&1 | q

log "held-out evaluation (14xxx), full fleets, every filter"
python3 run_campaign.py --phase p2 --planners scripted,random,oracle:best,oracle:heldout \
    --btot b0,b1,b2,b3 --margins 10,20 --gamma 1.625,15 --missions "$MISSIONS" --seed-block 14000 \
    --filters psf,none,simplex,cbf1,fixed_margin --baseline-planners "$BASE_PLANNERS" \
    --baseline-missions "$BASE_MISSIONS" --log-steps events --campaign-id p2_main --resume --par "$PAR" 2>&1 | q

log "attack-budget curve: b_att x hijacked aircraft"
python3 run_campaign.py --phase p2-budget --stage curve --campaign-id p2_budget --margins 10,20 \
    --btot b0,b1,b2,b3 --gamma 1.625 --missions "$CURVE_MISSIONS" --seed-block 14000 --resume --par "$PAR" 2>&1 | q

log "aggregate"
python3 stats.py --campaign p2_main,p2_budget --rq rq1,denial_envelope

cd ../..
tar -czf "$HOME/paperV-p2-results-$STAMP.tgz" paperV/results/*.csv paperV/results/*.json
tar -cf - paperV/results/campaign | zstd -q -T0 -o "$HOME/paperV_campaign_p2_$STAMP.tar.zst" 2>/dev/null \
    || tar -czf "$HOME/paperV_campaign_p2_$STAMP.tgz" paperV/results/campaign
log "done: $HOME/paperV-p2-results-$STAMP.tgz (aggregates) and the raw-log archive next to it"
