#!/usr/bin/env bash
# R1 follow-up: the keep-logit prior (+3) was fixed while the action count grows
# with M, so the initial keep probability fell from 0.69 (N=12) to 0.38 (N=48)
# and the learned allocators thrashed at large N. Re-run ours and masking with
# the prior scaled to keep the N=12 initial keep probability:
#   bias = ln(0.69/0.31 * (A-1)),  A = actions (M+2 for the MLP, 18 for attention)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p ../results/logs_r
{
for s in 0 1 2 3 4; do for m in ours mask; do
  echo "--method $m --seed $s --updates 200 --N 48 --B 4 --eval-B 4 --keep-bias 4.30 --tag kbs --outdir e5_marl_N48"; done; done
for s in 0 1 2; do for m in ours mask; do
  echo "--method $m --seed $s --updates 150 --N 96 --B 2 --eval-B 4 --actor attn --keep-bias 3.63 --tag kbs --outdir e5_marl_N96"; done; done
} | xargs -P "${PAR:-4}" -I{} sh -c 'python3 e5_marl.py {} > ../results/logs_r/kbs_$(echo "{}" | tr " -" "__" | cut -c1-80).txt 2>&1 && echo "done {}" || echo "FAIL {}"'
echo "all kbs jobs finished"
