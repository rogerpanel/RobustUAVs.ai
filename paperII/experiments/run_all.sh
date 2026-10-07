#!/usr/bin/env bash
# Regenerate every Paper II result, figure-data file and number macro (~5 s).
set -euo pipefail
cd "$(dirname "$0")"
python3 quantifier.py          > /dev/null   # calculus self-checks (Props. 1-2)
python3 reliability.py --test
python3 adjudicate.py
python3 reliability.py C1 C2   > /dev/null
python3 corpus_analysis.py     > /dev/null
python3 rate_arithmetic.py     > /dev/null
python3 evidence_pack.py       > /dev/null
python3 make_numbers.py
echo "paperII: all results regenerated"
