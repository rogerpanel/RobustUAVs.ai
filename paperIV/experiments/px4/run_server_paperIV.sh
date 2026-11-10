#!/usr/bin/env bash
# Paper IV: PX4 v1.14.3 SITL transfer study (protocol: paperIV/PX4_PREREG.md).
# Run on the PX4 machine used for Paper III, from a checkout of this repository.
#
#   bash paperIV/experiments/px4/run_server_paperIV.sh setup     # PX4 copy + patch + build (minutes; ~1 h without a build cache)
#   bash paperIV/experiments/px4/run_server_paperIV.sh smoke     # 4 missions: injection, anchor, replay, throughput
#   bash paperIV/experiments/px4/run_server_paperIV.sh e0 e1 e2 e3 e4neg
#   bash paperIV/experiments/px4/run_server_paperIV.sh all       # setup smoke e0 e1 e2 e3 e4neg pack
#   bash paperIV/experiments/px4/run_server_paperIV.sh pack      # results tarball in $HOME (no ULogs)
#
# Environment: K instances in parallel (default: half the cores, at most 12), SPEED (simulation
# speed factor, default 8), PX4_SRC (Paper III's PX4 tree, default ~/PX4-Autopilot; only copied,
# never modified), PX4_P4 (the patched copy, default ~/PX4-Autopilot-paperIV).
# A stage can be re-run: finished missions are skipped.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
RES="$REPO/paperIV/results/px4"
LOG="$RES/server_logs"
IMG_BASE="${PX4_IMG:-px4io/px4-dev-simulation-jammy:latest}"
IMG="p4sitl:1"
PX4_SRC="${PX4_SRC:-$HOME/PX4-Autopilot}"
PX4_P4="${PX4_P4:-$HOME/PX4-Autopilot-paperIV}"
NCPU="$(nproc)"
K="${K:-$(( NCPU / 2 > 12 ? 12 : (NCPU / 2 < 1 ? 1 : NCPU / 2) ))}"
SPEED="${SPEED:-8}"
STAGES="${*:-smoke}"
[ "$STAGES" = all ] && STAGES="setup smoke e0 e1 e2 e4neg e3 pack"
mkdir -p "$LOG"

say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG/run.txt"; }

image() {
  command -v docker >/dev/null || { say "docker is not installed"; exit 1; }
  if ! docker image inspect "$IMG" >/dev/null 2>&1; then
    say "building the driver image $IMG on $IMG_BASE (python deps for the fleet driver)"
    printf 'FROM %s\nRUN pip3 install -q numpy scipy pyulog "mavsdk<4" "empy==3.3.4"\n' "$IMG_BASE" \
      | docker build -q -t "$IMG" - > /dev/null
  fi
}

# run a command in the container: PX4 copy at /src, this repository at /repo
dock() {
  docker run --rm --network host -v "$PX4_P4":/src -v "$REPO":/repo "$IMG" \
    bash -lc "git config --global --add safe.directory '*' >/dev/null 2>&1; $*"
}

own() { dock "chown -R $(id -u):$(id -g) /repo/paperIV/results/px4 /repo/paperIV/experiments/px4/plans 2>/dev/null || true"; }

stage_setup() {
  image
  if [ ! -d "$PX4_P4" ]; then
    if [ -d "$PX4_SRC/.git" ]; then
      say "setup: copying Paper III's PX4 tree $PX4_SRC -> $PX4_P4 (with its build cache; the original is not touched)"
      docker run --rm -v "$(dirname "$PX4_SRC")":/h1 -v "$(dirname "$PX4_P4")":/h2 "$IMG" \
        cp -a "/h1/$(basename "$PX4_SRC")" "/h2/$(basename "$PX4_P4")"
    else
      say "setup: cloning PX4 v1.14.3 into $PX4_P4"
      git clone --recursive --branch v1.14.3 --depth 1 --shallow-submodules \
        https://github.com/PX4/PX4-Autopilot.git "$PX4_P4" > "$LOG/clone.txt" 2>&1
      NX="$PX4_P4/platforms/nuttx/NuttX/nuttx"
      git -C "$NX" fetch -q --depth 1 origin 'refs/tags/nuttx-*:refs/tags/nuttx-*' >> "$LOG/clone.txt" 2>&1 || true
    fi
  fi
  local ver
  ver="$(dock "cd /src && git describe --tags --always 2>/dev/null" | tail -1)"
  say "setup: PX4 tree at $PX4_P4 is $ver"
  case "$ver" in v1.14.3*) ;; *) say "setup: WARNING: expected v1.14.3 (the patch was written against v1.14.3)";; esac
  dock "cd /src && git status --porcelain --untracked-files=no | grep -v '^ M build' | head -20" > "$LOG/setup_dirty.txt" || true
  local P=/repo/paperIV/experiments/px4/px4_paperIV.patch
  if ! dock "cd /src && git apply --reverse --check $P" >/dev/null 2>&1; then
    # an earlier version of the patch may be applied: find it in the history and take it out
    local h
    for h in $(git -C "$REPO" log --format=%h -- paperIV/experiments/px4/px4_paperIV.patch); do
      git -C "$REPO" show "$h:paperIV/experiments/px4/px4_paperIV.patch" > "$LOG/patch_$h.patch"
      if dock "cd /src && git apply --reverse --check /repo/paperIV/results/px4/server_logs/patch_$h.patch" >/dev/null 2>&1; then
        dock "cd /src && git apply --reverse /repo/paperIV/results/px4/server_logs/patch_$h.patch"
        say "setup: removed the earlier patch version $h"
        break
      fi
    done
  fi
  if dock "cd /src && git apply --reverse --check $P" >/dev/null 2>&1; then
    say "setup: Paper IV patch already applied"
  elif dock "cd /src && git apply --check /repo/paperIV/experiments/px4/px4_paperIV.patch" > "$LOG/setup_patch.txt" 2>&1; then
    dock "cd /src && git apply /repo/paperIV/experiments/px4/px4_paperIV.patch"
    say "setup: Paper IV patch applied ($(grep -c '^+++ ' "$HERE/px4_paperIV.patch") files)"
  else
    say "setup: the patch does not apply to this tree; local changes:"; sed 's/^/    /' "$LOG/setup_dirty.txt" "$LOG/setup_patch.txt" | tee -a "$LOG/run.txt"
    exit 1
  fi
  say "setup: building px4_sitl_default (log: $PX4_P4/build_p4.log)"
  if ! dock "cd /src && { pip3 install -q 'empy==3.3.4' >/dev/null 2>&1 || true; } && make px4_sitl_default > /src/build_p4.log 2>&1"; then
    say "setup: BUILD FAILED; the first error:"
    { grep -n -B2 -A12 "error:" "$PX4_P4/build_p4.log" | head -60 || tail -n 40 "$PX4_P4/build_p4.log"; } | tee -a "$LOG/build_error.txt"
    say "setup: please send me $LOG/build_error.txt (or the lines above)"
    exit 1
  fi
  local n
  n="$(dock "grep -c -E 'name=\"(ATK|BEN)_' /src/build/px4_sitl_default/parameters.xml 2>/dev/null || true" | tail -1)"
  say "setup: build OK; Paper IV parameters in the firmware: ${n:-0} (expected 39)"
}

plans() { dock "cd /repo/paperIV/experiments/px4 && python3 p4_plan.py $*" | tee -a "$LOG/run.txt"; }

fleet() {   # fleet <exp> [args...]
  local exp="$1"; shift
  say "$exp: flying ($K instances, speed $SPEED); log: $LOG/$exp.txt"
  dock "cd /repo/paperIV/experiments/px4 && python3 -u p4_fleet.py --exp $exp --px4 /src --out /repo/paperIV/results/px4 -k $K --speed $SPEED $*" \
    2>&1 | tee -a "$LOG/$exp.txt" || true
  own
}

analyze() { dock "cd /repo/paperIV/experiments/px4 && python3 p4_analyze.py $*" 2>&1 | tee -a "$LOG/run.txt"; own; }

stage_smoke() {
  image; plans smoke
  K_SAVE="$K"; K=2
  fleet smoke --plan plans/smoke.jsonl --keep-ulog all
  K="$K_SAVE"
  analyze smoke
  tail -n 6 "$LOG/smoke.txt" | sed 's/^/    /'
  say "smoke: per-mission wall time above; throughput with K=$K instances is about K x 60 / wall_s missions per minute"
}

stage_e0() { image; plans e0; fleet e0 --plan plans/e0.jsonl; analyze calibrate; }
stage_e1() { image; plans e1; fleet e1 --plan plans/e1.jsonl; analyze e1; }
stage_e2() { image; plans e2; fleet e2 --plan plans/e2.jsonl; analyze e2; }
stage_e3() {
  image
  [ -f "$RES/calibration.json" ] || { say "e3 needs the E0 calibration (run e0 first)"; return 1; }
  fleet e3 --cem --calibration /repo/paperIV/results/px4/calibration.json --gens "${E3_GENS:-10}" --lam "${E3_LAM:-8}" --K "${E3_K:-16}"
  plans e3eval; fleet e3eval --plan plans/e3eval.jsonl; analyze e3
}
# corrected analysis (PX4_PREREG.md deviations 1 and 3): no flights
stage_reanalyze() { image; analyze calibrate e1 e2 e4neg e3select; }
# E3 re-selection and re-evaluation (deviation 2): 300 missions
stage_e3fix() {
  image
  [ -f "$RES/e3/cem_state_clean.json" ] || analyze e3select
  plans e3eval; fleet e3eval2 --plan plans/e3eval.jsonl; analyze e3
}
# E5: the design rule at a 1 s re-anchoring interval (1,300 missions, about 1.75 h at K=3, speed 10)
stage_ta1() { image; plans ta1; fleet ta1 --plan plans/ta1.jsonl; analyze ta1; }
stage_e4neg() { image; plans e4neg; fleet e4neg --plan plans/e4neg.jsonl; analyze e4neg; }

stage_pack() {
  local out="$HOME/paperIV_px4_results_$(date +%Y%m%d_%H%M).tgz"
  tar -C "$REPO/paperIV/results" --exclude='px4/*/ulg' --exclude='px4/*/fail_logs' -czf "$out" px4
  # small archive to attach in the chat: tables, calibration, per-mission rows, logs (no series, no ULogs)
  local tab="$HOME/paperIV_px4_tables_$(date +%Y%m%d_%H%M).tgz"
  (cd "$REPO/paperIV/results" && tar -czf "$tab" px4/*.csv px4/*.json px4/*/missions.jsonl px4/*/cem_state*.json \
     px4/server_logs 2>/dev/null || true)
  say "pack: full results $out ($(du -h "$out" | cut -f1)); tables to send back $tab ($(du -h "$tab" | cut -f1))"
}

for s in $STAGES; do
  say "=== stage $s ==="
  "stage_$s"
done
