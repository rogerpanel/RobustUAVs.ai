#!/usr/bin/env bash
# Paper III E5: 5 methods x SEEDS seeds, two runs in parallel.
set -euo pipefail
cd "$(dirname "$0")"
SEEDS=${SEEDS:-"0 1 2 3 4"}; UPDATES=${UPDATES:-200}; PAR=${PAR:-2}
for s in $SEEDS; do for m in ours lagrangian mask blind ours_nodev; do echo "$m $s"; done; done | \
  xargs -P "$PAR" -L 1 sh -c "python3 e5_marl.py --method \$0 --seed \$1 --updates $UPDATES > ../results/e5_marl/log_\$0_\$1.txt 2>&1"
python3 e6_aggregate.py && python3 export_figdata.py && python3 make_numbers.py
