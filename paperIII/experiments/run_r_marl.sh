#!/usr/bin/env bash
# Paper III R1 (scale), R2 (baselines) and R9 (sensitivity) MARL runs.
# Resumable: a job is skipped when its *_eval.csv already exists.
#   PAR=4 bash run_r_marl.sh            # all three blocks
#   BLOCKS="r2" PAR=4 bash run_r_marl.sh
# Budget actually used for the paper (4 CPU cores, no GPU): see RUNBOOK R1/R2/R9.
set -euo pipefail
cd "$(dirname "$0")"
PAR=${PAR:-4}
BLOCKS=${BLOCKS:-"r2 n12 r1 r9"}
U=${UPDATES:-200}
JOBS=$(mktemp)
R=../results

add() {  # add <outdir> <name> <seed> <args...>
  local out=$1 name=$2 seed=$3; shift 3
  [ -f "$R/$out/${name}_s${seed}_eval.csv" ] && return 0
  echo "$out|${name}_s${seed}|$* --seed $seed --outdir $out" >> "$JOBS"
}

for blk in $BLOCKS; do case $blk in
  r2)   # stronger baselines at the headline size, 10 seeds
    for s in 0 1 2 3 4 5 6 7 8 9; do
      for m in pid_lag mappo_lag mappo_lag0 qmix qmix_mask; do
        add e5_marl $m $s --method $m --updates $U; done; done ;;
  n12)  # headline: seeds 5-9 on top of the committed seeds 0-4
    for s in 5 6 7 8 9; do
      for m in ours lagrangian mask blind ours_nodev; do
        add e5_marl $m $s --method $m --updates $U; done; done ;;
  r1)   # fleet size; agent-samples per update held at 150*192
    for N in 24 48 96; do
      B=$((192 / N)); EB=$(( B < 4 ? 4 : B )); ACT=mlp; UN=$U; SEEDS="0 1 2 3 4"
      if [ "$N" -ge 96 ]; then ACT=attn; UN=${UPDATES_N96:-150}; SEEDS="0 1 2"; fi
      for s in $SEEDS; do for m in ours mask lagrangian blind; do
        add e5_marl_N$N $m $s --method $m --updates $UN --N $N --B $B --eval-B $EB --actor $ACT
      done; done; done ;;
  r9)   # sensitivity, 3 seeds; the default of each knob is the committed E5 run
    for s in 0 1 2; do
      for v in 0.02 0.1 0.2; do add r9 ours-ldev$v $s --method ours --updates $U --lam-dev $v --tag ldev$v; done
      for v in 0 1; do add r9 ours-kb$v $s --method ours --updates $U --keep-bias $v --tag kb$v; done
      for v in 0 0.001 0.02; do add r9 lagrangian-cl$v $s --method lagrangian --updates $U --cost-limit $v --tag cl$v; done
      for v in 0.1 5; do add r9 lagrangian-ds$v $s --method lagrangian --updates $U --dual-step $v --tag ds$v; done
      for v in 0.5 2; do for m in ours lagrangian; do
        add r9 $m-thr$v $s --method $m --updates $U --threat-scale $v --tag thr$v; done; done
    done ;;
esac; done

echo "$(wc -l < "$JOBS") jobs"
mkdir -p "$R/logs_r"
# references per fleet size (cheap, deterministic)
python3 e5_marl.py --references > "$R/logs_r/ref_N12.txt" 2>&1
for N in 24 48 96; do
  B=$((192 / N)); EB=$(( B < 4 ? 4 : B ))
  mkdir -p "$R/e5_marl_N$N"
  [ -f "$R/e5_marl_N$N/references_eval.csv" ] || \
    python3 e5_marl.py --references --N $N --eval-B $EB --outdir e5_marl_N$N > "$R/logs_r/ref_N$N.txt" 2>&1
done
while IFS='|' read -r out key args; do
  echo "$key|$out|$args"
done < "$JOBS" | xargs -P "$PAR" -d '\n' -I{} sh -c '
  line="{}"; key=${line%%|*}; rest=${line#*|}; out=${rest%%|*}; args=${rest#*|}
  python3 e5_marl.py $args > ../results/logs_r/${out}_${key}.txt 2>&1 && echo "done $out $key" || echo "FAIL $out $key"'
rm -f "$JOBS"
echo "all R-MARL jobs finished"
