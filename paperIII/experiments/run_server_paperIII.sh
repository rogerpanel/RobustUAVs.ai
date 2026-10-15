#!/usr/bin/env bash
# Paper III -- experiments that need the Hetzner server (or a board):
#   e3   E3 latency on an otherwise idle machine (runbook ground rule 4)
#   r3   measured-trace replay: stage the Kaggle corpus, extract GNSS staleness
#        traces, E2 part (c) and E5 with --process trace
#   r4   PX4 SITL multi-vehicle vignette (Docker; ~1 h first build)
#   r8   embedded latency: prints the one command to run on a Pi / Jetson
# Results come back as one tarball (the server's deploy key is read-only).
#
# Usage, from a separate worktree on the server (do NOT switch the branch of a
# checkout another job is using, e.g. ~/paper-work while Paper II runs):
#   git -C ~/paper-work fetch -q origin claude/whelan-uavcas-ingest-u00isn
#   git -C ~/paper-work worktree add -f -B p3 ~/paper3-work origin/claude/whelan-uavcas-ingest-u00isn
#   cd ~/paper3-work
#   bash paperIII/experiments/run_server_paperIII.sh e3 r3            # the quick part
#   bash paperIII/experiments/run_server_paperIII.sh r4               # the SITL part
#   scp deploy@<server>:~/paperIII-server-*.tgz .                     # bring results back
#
# Needs: python3 -m venv (numpy scipy torch pandas pyulog kagglehub mavsdk),
# Kaggle credentials in ~/.kaggle/kaggle.json (chmod 600) or KAGGLE_USERNAME /
# KAGGLE_KEY in the environment -- never in the repository.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
RES="$REPO/paperIII/results"
STAMP="$(date +%Y-%m-%d)"
LOG="$RES/server_logs"
VENV="${VENV:-$HOME/paper-venv}"
STAGES="${*:-e3 r3}"
mkdir -p "$LOG"

say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG/run.txt"; }

venv() {
  if [ ! -x "$VENV/bin/python" ]; then python3 -m venv "$VENV"; fi
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  pip install -q --upgrade pip
  pip install -q numpy scipy networkx pandas pyulog kagglehub mavsdk
  python -c "import torch" 2>/dev/null || pip install -q torch --index-url https://download.pytorch.org/whl/cpu || pip install -q torch
}

stage_e3() {
  say "E3: latency (machine must be idle)"
  load=$(cut -d' ' -f1 /proc/loadavg)
  if awk "BEGIN{exit !($load > 0.5)}"; then
    say "WARNING: load average $load > 0.5; stop other jobs (docker compose stop?) for a clean E3"
  fi
  echo "load_before=$load" > "$LOG/e3_load.txt"
  (cd "$HERE" && python3 e3_latency.py) > "$LOG/e3.txt" 2>&1
  cut -d' ' -f1 /proc/loadavg | sed 's/^/load_after=/' >> "$LOG/e3_load.txt"
  lscpu > "$LOG/e3_lscpu.txt" 2>/dev/null || true
  say "E3 done -> results/e3_latency.csv"
}

stage_r3() {
  say "R3: staging the Kaggle corpus (symlinks into the kagglehub cache; no second copy on disk)"
  (cd "$REPO" && python3 data/fetch_kaggle.py) > "$LOG/r3_fetch.txt" 2>&1 || {
    say "R3: Kaggle fetch failed (see $LOG/r3_fetch.txt); R3 skipped, nothing fabricated"; return 0; }
  (cd "$HERE" && python3 r3_extract_traces.py) > "$LOG/r3_extract.txt" 2>&1
  if [ ! -f "$RES/r3_staleness_traces.csv" ]; then
    say "R3: no GNSS traces extracted (see $LOG/r3_extract.txt); skipped"; return 0; fi
  say "R3: E2 part (c) with traces"
  (cd "$HERE" && python3 e2_degradation.py --process trace) > "$LOG/r3_e2.txt" 2>&1
  say "R3: E5 with traces (4 methods x 3 seeds, PAR=${PAR:-4})"
  for s in 0 1 2; do for m in ours mask lagrangian blind; do echo "$m $s"; done; done | \
    xargs -P "${PAR:-4}" -L 1 sh -c "cd '$HERE' && python3 e5_marl.py --method \$0 --seed \$1 --updates ${UPDATES:-200} --process trace --outdir e5_marl_trace > '$LOG/r3_e5_'\$0'_'\$1'.txt' 2>&1"
  (cd "$HERE" && python3 e5_marl.py --references --process trace --outdir e5_marl_trace) > "$LOG/r3_ref.txt" 2>&1
  (cd "$HERE" && python3 e6_aggregate.py --dir e5_marl_trace) > "$LOG/r3_e6.txt" 2>&1 || true
  say "R3 done"
}

stage_r4() {
  say "R4: PX4 SITL (v1.14.3) in Docker, ${R4_VEHICLES:-6} vehicles"
  command -v docker >/dev/null || { say "R4: docker not installed; skipped"; return 0; }
  PX4="${PX4_DIR:-$HOME/PX4-Autopilot}"
  if [ ! -d "$PX4" ]; then
    git clone --recursive --branch v1.14.3 --depth 1 --shallow-submodules \
      https://github.com/PX4/PX4-Autopilot.git "$PX4" > "$LOG/r4_clone.txt" 2>&1
  fi
  IMG="${PX4_IMG:-px4io/px4-dev-simulation-jammy:latest}"
  docker pull -q "$IMG" > /dev/null
  # build once (SIH: physics inside PX4, no Gazebo, runs headless)
  # the container runs as root on a checkout owned by the host user: allow git to read it
  # (otherwise git stops with "dubious ownership" and PX4's version step fails).
  # PX4 v1.14's message generators need empy 3.x; empy 4 breaks the uORB header step.
  if ! docker run --rm -v "$PX4":/src -w /src "$IMG" bash -lc \
    "git config --global --add safe.directory '*' && \
     { pip3 install -q 'empy==3.3.4' > /src/pip_r4.log 2>&1 || true; } && \
     make px4_sitl_default > /src/build_r4.log 2>&1"; then
    say "R4: PX4 build failed, see $PX4/build_r4.log; its last lines:"
    { grep -n -A12 "FAILED" "$PX4/build_r4.log" | head -40 || true; tail -n 10 "$PX4/build_r4.log"; } \
      | sed 's/^/    /' | tee -a "$LOG/r4_build_tail.txt"
    return 0
  fi
  # launch N SIH quadrotors; instance i listens on UDP 14540+i for offboard
  docker rm -f px4sitl >/dev/null 2>&1 || true
  docker run -d --name px4sitl --network host -v "$PX4":/src -w /src "$IMG" bash -lc '
    git config --global --add safe.directory "*"
    cd build/px4_sitl_default
    for i in $(seq 0 '"$((${R4_VEHICLES:-6} - 1))"'); do
      mkdir -p rootfs/$i
      (cd rootfs/$i && PX4_SYS_AUTOSTART=10040 PX4_SIM_MODEL=sihsim_quadx \
        ../../bin/px4 -i $i -d ../../etc > out.log 2>&1 &)
    done
    sleep infinity' > /dev/null
  sleep 25
  say "R4: driving the fleet (5 Hz and 2 Hz, ${R4_DURATION:-240} s each)"
  (cd "$HERE" && python3 r4_sitl_fleet.py --vehicles "${R4_VEHICLES:-6}" --rate 5 2 \
     --duration "${R4_DURATION:-240}") > "$LOG/r4_driver.txt" 2>&1 || say "R4: driver error, see r4_driver.txt"
  docker stop px4sitl > /dev/null
  say "R4: closed-loop soundness check from the ULogs"
  (cd "$HERE" && python3 r4_sitl_fleet.py --soundness-only --logs "$PX4/build/px4_sitl_default/rootfs") \
     > "$LOG/r4_soundness.txt" 2>&1 || say "R4: soundness check error, see r4_soundness.txt"
  docker rm px4sitl > /dev/null
  say "R4 done"
}

stage_r8() {
  say "R8 needs the board itself (Raspberry Pi CM4/5, Jetson Orin Nano); the server cannot stand in."
  say "On the board:  git clone ... && pip install numpy scipy && \\"
  say "  python3 paperIII/experiments/e3_latency.py --board pi5     # or orin_nano"
  say "then copy paperIII/results/e3_latency_<board>.csv back."
}

venv
for s in $STAGES; do "stage_$s"; done

TGZ="$HOME/paperIII-server-$STAMP.tgz"
cd "$REPO"
tar czf "$TGZ" --ignore-failed-read \
  paperIII/results/e3_latency.csv paperIII/results/e3_latency_*.csv \
  paperIII/results/r3_*.csv paperIII/results/e2_lift_trace.csv paperIII/results/e5_marl_trace \
  paperIII/results/e6_main_e5_marl_trace.csv \
  paperIII/results/r4_*.csv paperIII/results/server_logs 2>/dev/null || true
say "results: $TGZ  (scp it back; R3 traces derive from the staged corpus, no raw data inside)"
