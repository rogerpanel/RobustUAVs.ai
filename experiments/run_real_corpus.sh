#!/usr/bin/env bash
# One-shot real-corpus pipeline: fetch -> stage -> ingest -> validate ->
# calibrate -> compose -> figures. Idempotent; skips a stage whose inputs
# are absent and says so (never fabricates). Run from repo root.
#
#   experiments/run_real_corpus.sh            # use whatever is under data/raw
#   FETCH=1 experiments/run_real_corpus.sh    # also try data/fetch_kaggle.py first
#
# Every dataset is independent: a missing one (e.g. UAV-CAS stat) is reported
# and skipped, the rest still run. Exit code is non-zero only on a real error
# in a stage whose inputs WERE present.
set -uo pipefail
cd "$(dirname "$0")/.."
RAW=data/raw
STG=data/staging
V="python3 ingest/validate.py"
fail=0
have() { [ -e "$1" ]; }
say() { printf '\n=== %s\n' "$*"; }

if [ "${FETCH:-0}" = "1" ]; then
  say "fetch (data/fetch_kaggle.py)"
  python3 data/fetch_kaggle.py || echo "  fetch failed/blocked; using whatever is already under $RAW"
fi

say "1/6 UAV-EW-Bench (autonomy anchor)"
PF="$RAW/uav_ew_bench_2026/UAV-EW-Bench-2026/data/per_flight.csv"
if have "$PF"; then
  python3 ingest/ingest_ewbench.py "$PF" "$STG/ewbench" && \
    $V "$STG/ewbench/events.jsonl" "$STG/ewbench/windows.jsonl" || fail=1
  python3 experiments/ewbench_anchor.py || fail=1
else echo "  SKIP: $PF absent"; fi

say "2/6 Whelan (measured bridge + delta calibration)"
if have "$RAW/uav_attack_whelan/benign/gps.csv"; then
  python3 ingest/ingest_whelan.py "$STG/whelan_real" --manifest ingest/whelan_manifest.json && \
    $V "$STG/whelan_real/events.jsonl" || fail=1
  python3 experiments/whelan_delta_calibration.py || fail=1
else echo "  SKIP: $RAW/uav_attack_whelan/*/gps.csv absent"; fi

say "3/6 UAVIDS-2025 (swarm mesh)"
for csv in "$RAW"/uavids_2025/UAVIDS-2025_*.csv; do
  have "$csv" || { echo "  SKIP: no UAVIDS shards"; break; }
  part=$(echo "$csv" | grep -oE '_[0-9]+\.csv$' | tr -dc 0-9)
  python3 ingest/ingest_uavids.py "$csv" "$STG/uavids_$part" --part "$part" && \
    $V "$STG/uavids_$part/events.jsonl" "$STG/uavids_$part/windows.jsonl" || fail=1
done

say "4/6 HCRL UAVCAN (bus; data-derived attack map)"
if have "$RAW/hcrl_uavcan/type1_label.bin"; then
  python3 experiments/hcrl_type_signatures.py || fail=1
  for i in $(seq 1 10); do
    f="$RAW/hcrl_uavcan/type${i}_label.bin"
    have "$f" && { python3 ingest/ingest_hcrl.py "$f" "$STG/hcrl/type$i" --scenario "type$i" --limit 20000 || fail=1; }
  done
  $V "$STG/hcrl/type1/events.jsonl" "$STG/hcrl/type1/windows.jsonl" || fail=1
else echo "  SKIP: $RAW/hcrl_uavcan/*.bin absent"; fi

say "5/6 UAV-CAS (swarm digital twin; stat only, ts out of scope)"
CAS="$RAW/uav_cas/UAV-CAS_stat.csv"
if have "$CAS"; then
  python3 ingest/ingest_uavcas.py "$CAS" "$STG/uavcas_stat" && \
    $V "$STG/uavcas_stat/events.jsonl" "$STG/uavcas_stat/windows.jsonl" || fail=1
  CFG="$RAW/uav_cas/UAV-CAS_stat_cfg.csv"
  have "$CFG" && { python3 ingest/ingest_uavcas.py "$CFG" "$STG/uavcas_stat_cfg" && \
    $V "$STG/uavcas_stat_cfg/events.jsonl" || fail=1; }
else echo "  SKIP: $CAS absent (see docs/data_staging_layout.md and PENDING_ON_DATA.md)"; fi

say "6/6 DATAMUt sweep + composition + figures"
if [ -x build/datamut_demo ]; then
  python3 experiments/sweep_full.py || fail=1
  python3 experiments/compose_certified.py || fail=1
  python3 experiments/make_paper_figures.py || fail=1
else
  echo "  build/datamut_demo missing; building..."
  mkdir -p build && cp third_party/datamut/* build/ && ( cd build && \
    patch -p0 < ../patches/datamut_epsilon.patch && \
    g++ -O2 -std=c++17 datamut_paper_exact_demo.cc -o datamut_demo ) && \
    python3 experiments/sweep_full.py && python3 experiments/compose_certified.py && \
    python3 experiments/make_paper_figures.py || fail=1
fi

say "DONE (fail=$fail). Provenance ledger: results/paper_figures/README.md"
exit $fail
