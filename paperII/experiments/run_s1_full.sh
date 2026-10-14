#!/usr/bin/env bash
# Paper II S1 on a machine with open internet: uncapped OpenAlex search, the 18
# venue sweeps, DOI-or-title deduplication, PRISMA counts and search sensitivity.
#
# OpenAlex meters usage per day: a free API key (openalex.org/settings/api)
# buys about 1,000 search pages and 10,000 list pages a day; without one, about
# 10 searches. Put the key in ~/.config/openalex_key (chmod 600) or export
# OPENALEX_API_KEY -- never in the repository.
#
# Resilient: every stage resumes where it stopped. When the daily budget runs
# out (exit 75) the script sleeps until 00:05 UTC and resumes, for up to 7 days.
# Other failures are retried 6 times; a stage that still cannot finish stops the
# pipeline before PRISMA can count an incomplete retrieval.
#
#   setsid nohup bash run_s1_full.sh > ~/log-s1-full.txt 2>&1 < /dev/null &
set -uo pipefail
cd "$(dirname "$0")"
if [ -z "${OPENALEX_API_KEY:-}" ] && [ ! -s "$HOME/.config/openalex_key" ] && [ -z "${ALLOW_NO_KEY:-}" ]; then
  echo "No OpenAlex API key (OPENALEX_API_KEY or ~/.config/openalex_key). Without one OpenAlex allows"
  echo "about 10 searches a day. Get a free key at https://openalex.org/settings/api, or set ALLOW_NO_KEY=1."
  exit 2
fi
until_reset() {   # seconds until 00:05 UTC
  local now tgt; now=$(date -u +%s); tgt=$(date -u -d "tomorrow 00:05" +%s); echo $((tgt - now))
}
stage() {   # stage <name> <command...>
  local name=$1; shift
  local fails=0 days=0
  while :; do
    echo "== $name ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
    "$@"; rc=$?
    [ "$rc" = 0 ] && return 0
    case " $* " in *" --resume "*) ;; *) set -- "$@" --resume ;; esac
    if [ "$rc" = 75 ]; then
      days=$((days + 1)); [ "$days" -gt 7 ] && { echo "== $name: budget exhausted 7 days running; stopping"; exit 3; }
      s=$(until_reset); echo "== $name: OpenAlex daily budget spent; sleeping ${s}s until 00:05 UTC"
      sleep "$s"; continue
    fi
    fails=$((fails + 1))
    [ "$fails" -ge 6 ] && { echo "== $name could not complete after 6 attempts; stopping. Rerun to resume."; exit 3; }
    echo "== $name stopped (exit $rc); waiting 5 min before resuming"
    sleep 300
  done
}
RESUME=${RESUME:-}
REV=${REV:-0}          # 0 = protocol search (2026-10-14 run); 1 = F1 + F2 revision
python3 search_corpus.py budget || true
if [ "$REV" = 0 ]; then
  stage search python3 -u search_corpus.py search $RESUME
  stage venues python3 -u search_corpus.py venues $RESUME
  python3 search_corpus.py dedup --inp ../corpus/search_raw.jsonl ../corpus/venue_raw.jsonl || exit 4
  python3 prisma_counts.py || exit 5
  python3 search_sensitivity.py --label rev0 || exit 6
else
  stage search python3 -u search_corpus.py search --revision 1 --out ../corpus/search_raw_rev1.jsonl $RESUME
  stage venues python3 -u search_corpus.py venues --revision 1 --out ../corpus/venue_raw_rev1.jsonl $RESUME
  stage venues_dblp python3 -u search_corpus.py venues_dblp --revision 1 --out ../corpus/venue_dblp_raw.jsonl $RESUME
  python3 search_corpus.py dedup --inp ../corpus/search_raw_rev1.jsonl ../corpus/venue_raw_rev1.jsonl \
    ../corpus/venue_dblp_raw.jsonl || exit 4
  python3 prisma_counts.py --search search_raw_rev1.jsonl --venues venue_raw_rev1.jsonl venue_dblp_raw.jsonl || exit 5
  python3 search_sensitivity.py --label rev1 --raw search_raw_rev1.jsonl venue_raw_rev1.jsonl venue_dblp_raw.jsonl || exit 6
fi
echo "== S1 complete, revision $REV ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
