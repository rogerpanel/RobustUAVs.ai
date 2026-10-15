#!/usr/bin/env bash
# Paper II amendment 5: one snowballing iteration on a machine with open internet.
#
#   ITER=1 setsid nohup bash run_snowball.sh > ~/log-snowball.txt 2>&1 < /dev/null &
#
# ITER=1 seeds from the full-text-eligible coded sample (corpus/codes_full_final.csv).
# ITER=k>1 seeds from corpus/snowball/iter<k-1>_codes_final.csv and excludes the
# candidates of every earlier iteration. Resumable: when the OpenAlex daily
# budget runs out (exit 75) it sleeps until 00:05 UTC and resumes (up to 7 days);
# other failures are retried 6 times. At the end it writes an archive to $HOME.
set -uo pipefail
cd "$(dirname "$0")"
ITER=${ITER:-1}
if [ -z "${OPENALEX_API_KEY:-}" ] && [ ! -s "$HOME/.config/openalex_key" ]; then
  echo "No OpenAlex API key (OPENALEX_API_KEY or ~/.config/openalex_key)."; exit 2
fi
until_reset() { local now tgt; now=$(date -u +%s); tgt=$(date -u -d "tomorrow 00:05" +%s); echo $((tgt - now)); }
SEEDS=../corpus/codes_full_final.csv
KNOWN=()
if [ "$ITER" -gt 1 ]; then
  SEEDS=../corpus/snowball/iter$((ITER - 1))_codes_final.csv
  for k in $(seq 1 $((ITER - 1))); do KNOWN+=(../corpus/snowball/iter${k}_candidates.csv); done
  [ -s "$SEEDS" ] || { echo "missing $SEEDS (code iteration $((ITER - 1)) first)"; exit 2; }
fi
OUT=../corpus/snowball/iter$ITER
python3 search_corpus.py budget || true
fails=0; days=0; RES=""
[ -s "${OUT}_raw.jsonl" ] && RES="--resume"
while :; do
  echo "== snowball iteration $ITER ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
  python3 -u search_corpus.py snowball --seeds "$SEEDS" --out "$OUT" ${KNOWN[@]+--known "${KNOWN[@]}"} $RES; rc=$?
  RES="--resume"
  [ "$rc" = 0 ] && break
  if [ "$rc" = 75 ]; then
    days=$((days + 1)); [ "$days" -gt 7 ] && { echo "budget exhausted 7 days running; stopping"; exit 3; }
    s=$(until_reset); echo "== OpenAlex daily budget spent; sleeping ${s}s until 00:05 UTC"; sleep "$s"; continue
  fi
  fails=$((fails + 1)); [ "$fails" -ge 6 ] && { echo "could not complete after 6 attempts; rerun to resume"; exit 3; }
  echo "== stopped (exit $rc); waiting 5 min before resuming"; sleep 300
done
ARCH="$HOME/paperII-snowball-iter${ITER}-$(date -u +%Y-%m-%d).tar.xz"
tar -C .. -cJf "$ARCH" corpus/snowball/iter${ITER}_candidates.csv corpus/search_log.jsonl
echo "== done: $(wc -l < ${OUT}_candidates.csv) lines in ${OUT}_candidates.csv; archive $ARCH ($(du -h "$ARCH" | cut -f1))"
