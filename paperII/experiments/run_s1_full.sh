#!/usr/bin/env bash
# Paper II S1 on a machine with open internet: uncapped OpenAlex search, the 18
# venue sweeps, DOI-or-title deduplication, PRISMA counts and search sensitivity.
# Resilient: each stage resumes where it stopped (completed queries and venues
# are kept) and is retried up to 6 times; a stage that still cannot finish stops
# the pipeline rather than letting PRISMA count an incomplete retrieval.
#
#   export OPENALEX_MAILTO=you@example.org      # any address; OpenAlex sends no mail
#   setsid nohup bash run_s1_full.sh > ~/log-s1-full.txt 2>&1 < /dev/null &
set -uo pipefail
cd "$(dirname "$0")"
stage() {   # stage <name> <command...>
  local name=$1; shift
  for attempt in 1 2 3 4 5 6; do
    echo "== $name, attempt $attempt ($(date -u +%H:%M:%SZ))"
    "$@"; rc=$?
    [ "$rc" = 0 ] && return 0
    echo "== $name stopped (exit $rc); waiting 5 min before resuming"
    case " $* " in *" --resume "*) ;; *) set -- "$@" --resume ;; esac
    sleep 300
  done
  echo "== $name could not complete after 6 attempts; stopping. Rerun this script to resume."
  exit 3
}
RESUME=${RESUME:-}
stage search python3 -u search_corpus.py search $RESUME
stage venues python3 -u search_corpus.py venues $RESUME
python3 search_corpus.py dedup --inp ../corpus/search_raw.jsonl ../corpus/venue_raw.jsonl || exit 4
python3 prisma_counts.py || exit 5
python3 search_sensitivity.py || exit 6
echo "== S1 complete ($(date -u +%H:%M:%SZ))"
