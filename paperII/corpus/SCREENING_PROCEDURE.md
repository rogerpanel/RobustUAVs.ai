# Title/abstract screening procedure (Paper II, S2) — amendment 1

**Fixed on 2026-10-15, before any ranking of the candidates was computed or
inspected.** The inclusion rule itself is unchanged (`SCREENING_RULE.md`); this
file changes only *which records are screened by humans, and in what order*.
Any later change is logged at the end of this file with its date and reason.

## Why the amendment

S1 revision 1 identified 33,664 records and left 25,373 unique candidates.
Full dual screening means about 50,000 human decisions. We measured, and
rejected, a mechanical shortcut: requiring a block-A phrase in the title or
abstract would keep 4,917 records but lose 17 of the 52 pilot papers the search
retrieved; stricter keyword rules lose more. We therefore screen in a
**prioritised order with a pre-registered stopping rule**, following the SAFE
procedure for active-learning screening (Boetje and van de Schoot, *Systematic
Reviews* 13:81, 2024).

## Ranking (fixed now)

- Model: TF-IDF over title + abstract (lower-cased words and word bigrams,
  sublinear term frequency, terms in at least 2 records), L2-regularised
  logistic regression (C = 1, balanced class weights). Code:
  `experiments/screen_rank.py`; numpy/scipy only; deterministic.
- Initial positives: the pilot papers of the **development half only** (odd
  gid) that the search retrieved. The held-out half (even gid) is **not** used
  for training; where its papers land in the ranking is reported as a check of
  the ranker, never used to choose the stopping point.
- Initial negatives: none are labelled yet, so the first ranking treats a fixed
  random sample of 2,000 unlabelled records (seed 20261015) as provisional
  negatives, averaged over 5 such samples (PU bagging).
- Active learning: after every block of 200 consensus decisions, the model is
  retrained on all human decisions so far (include = either human includes,
  after adjudication; exclude = both exclude) and the unscreened remainder is
  re-ranked. Every ranking is written to `corpus/screening/rank_vN.csv`.
- The LLM never ranks, and its output is never a training label.

## Who screens what

- H1 and H2 screen independently, in the same order, without seeing each
  other's decisions; disagreements go to adjudication (`adjudication.csv`).
- The LLM third screener (three runs per batch of 50, as in S2) screens every
  record the humans screen, and the tail sample below. Its output may only add
  a record to `screen_flags.csv` for human re-check. It never excludes.

## Stopping rule

**Phase A.** Screen in rank order until both hold:
1. at least 10% of the candidates (2,538 records) have been screened by both
   humans; and
2. the last 250 consecutive records were excluded by both humans.

**Phase B (model switch).** Retrain with a different representation (character
3–5-grams, same classifier) on all decisions so far, re-rank the unscreened
remainder, and screen until 100 consecutive records are excluded by both.

**Phase C (tail check).** Draw a simple random sample of 400 records from the
still-unscreened remainder (seed 20261016) and have both humans screen it.
- 0 or 1 includes: stop. Report the remainder as "not screened (stopping
  rule)", with the estimated number of missed includes and its one-sided 95%
  Clopper–Pearson upper bound.
- 2 or more includes: return to Phase B for another run of 250 consecutive
  excludes, then repeat Phase C with a fresh sample (seed + 1).

## Reporting

PRISMA reports records screened by humans, records not screened under the
stopping rule, the tail-sample estimate, the rank at which each held-out pilot
paper was reached, screening κ (H1 vs H2), LLM run-to-run agreement,
LLM-vs-human κ, and the number of records the LLM flags rescued.

## Change log

- 2026-10-15: amendment 1 (this file).
