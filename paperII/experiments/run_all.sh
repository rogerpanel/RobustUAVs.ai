#!/usr/bin/env bash
# Regenerate every Paper II result, figure-data file and number macro (~30 s).
set -euo pipefail
cd "$(dirname "$0")"
python3 quantifier.py          > /dev/null   # calculus self-checks (Props. 1-2)
python3 reliability.py --test
python3 adjudicate.py
python3 reliability.py C1 C2   > /dev/null
python3 corpus_analysis.py     > /dev/null
python3 rate_arithmetic.py     > /dev/null
python3 evidence_pack.py       > /dev/null
# full study (amendments 1-5): from the committed LLM codes to the weighted estimates
python3 coding_merge.py        > /dev/null
python3 adjudication_merge.py  > /dev/null
python3 reliability.py full_C1 full_C2 > /dev/null
python3 corpus_estimates.py    > /dev/null
for c in codes_full_final.csv codes_full_C1.csv codes_full_C2.csv; do python3 hypotheses_full.py "$c" > /dev/null; done
python3 transfer_full.py       > /dev/null
python3 make_numbers.py
echo "paperII: all results regenerated"
