#!/usr/bin/env bash
# R1 follow-up for N=24 (A=18 actions -> keep bias 3.63); waits for run_r1_kbs.sh, then runs.
cd "$(dirname "$0")"
while pgrep -f "bash run_r1_kbs.sh" >/dev/null; do sleep 30; done
for s in 0 1 2 3 4; do for m in ours mask; do
  echo "--method $m --seed $s --updates 200 --N 24 --B 8 --eval-B 8 --keep-bias 3.63 --tag kbs --outdir e5_marl_N24"; done; done | \
  xargs -P 4 -I{} sh -c 'python3 e5_marl.py {} > ../results/logs_r/kbs24_$(echo "{}" | tr " -" "__" | cut -c1-60).txt 2>&1 && echo "done {}" || echo "FAIL {}"'
echo "all kbs24 jobs finished"
