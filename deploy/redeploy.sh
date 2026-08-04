#!/usr/bin/env bash
# One command: pull, deploy, and leave it running detached.
#
#     ./deploy/redeploy.sh          # start it, return immediately
#     ./deploy/redeploy.sh --watch  # start it and follow the log
#
# Exists because the equivalent one-liner needs `setsid nohup ... &` with
# redirections in the right order, and getting that subtly wrong either
# foregrounds the build (so a dropped SSH session kills it) or backgrounds the
# `git pull` too. A script has no such ambiguity.
set -euo pipefail

REPO="${REPO:-/srv/robustuavs/repo}"
LOG="${LOG:-/tmp/deploy.log}"

cd "$REPO"

# If a deploy is already running, say so rather than starting a second one
# that would fight the first over the same working tree.
if pgrep -f "$REPO/deploy/deploy.sh" >/dev/null 2>&1; then
	echo "A deploy is already running. Follow it with:  tail -f $LOG"
	exit 0
fi

echo "==> pulling"
git pull --ff-only

echo "==> starting deploy (detached; survives a dropped session)"
setsid nohup "$REPO/deploy/deploy.sh" > "$LOG" 2>&1 < /dev/null &
sleep 1

cat <<MSG

Started. The build takes 3-8 minutes (npm install dominates).

  follow it     tail -f $LOG      # Ctrl-C stops WATCHING, not the deploy
  check later   tail -20 $LOG
  is it done?   pgrep -f deploy.sh >/dev/null && echo running || echo finished

MSG

if [ "${1:-}" = "--watch" ]; then
	tail -f "$LOG"
fi
