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

## Amendment 2 (2026-10-15): LLM screeners, disclosed

Fixed before any record was screened. No human screener is available for the
title/abstract stage. The stage is therefore performed by **two independent
LLM screeners**, reported as such everywhere (never as human screeners):

- **L1** and **L2**: separate sub-agent runs on two different models. Each
  reads only `SCREENING_RULE.md` and a batch of records, and never sees the
  other's output, the pilot set, or the ranking scores.
- **Decision**: a record is excluded only when both L1 and L2 exclude it;
  any include, and any disagreement, goes forward to full text (the
  screening convention: uncertainty is resolved at full text). This replaces
  the H1/H2 roles of amendment 1 for this stage, and it relaxes the S2 rule
  that LLM output may never exclude: two independent LLM excludes now can.
- **Order and stopping**: as in amendment 1, with L1/L2 in place of H1/H2.
  Phase A in rank order (`rank_v1.csv`, held fixed: no active learning, so
  no LLM decision ever becomes a ranking label); Phase B re-ranks with
  character 3-5-grams trained on the same development-half positives only;
  Phase C draws the 400-record random tail sample (seed 20261016).
- **Human check (recommended)**: the author screens a simple random sample of
  100 records excluded by both LLMs (seed 20261017), blind to the LLM
  decisions; agreement and any missed includes are reported. If it is not
  done, the paper reports the screening as LLM-only, as a limitation.
- **Outputs**: `screening/screen_L1.csv`, `screening/screen_L2.csv`
  (cid, include, reason), `screening/decisions.csv` (consensus), and a
  per-batch cost log.

- 2026-10-15: amendment 2 (this section).

## Amendment 3 (2026-10-15): core plus probability sample

Fixed before the sample below was drawn. After Phase A (ranks 1-2,750 of
`rank_v1.csv`), the consensus include rate had levelled off near 0.55 from
rank 1,500 onwards (`results/screening_status.csv`), so the 250-run stopping
condition is out of reach and exhaustive screening would send about 10,000
records to full text. The stopping rule (Phases B and C of amendments 1-2) is
therefore replaced by a sampling design; nothing already screened is changed.

- **Core stratum**: ranks 1-2,750, screened in full by L1/L2 (done).
- **Remainder stratum**: the other 22,623 candidates. A simple random sample
  of 1,000 (seed 20261018) is screened by L1/L2 exactly as the core. The number
  of includes in the remainder is estimated as N_rem x p_hat with a two-sided
  95% Clopper-Pearson interval.
- **Full-text and coding sample**: 300 included records, a stratified random
  sample (seed 20261019) allocated in proportion to the estimated number of
  includes in each stratum, at least 75 per stratum. Records whose full text
  cannot be retrieved are reported as "not retrieved" (PRISMA) and replaced
  from the same stratum in sample order. Corpus-level results are reported as
  weighted estimates with intervals, never as counts of the whole field.
- **Coverage**: snowballing from the coded sample continues until the type
  plane saturates (the manuscript's snowballing stop rule), so the sample can
  miss papers but should not miss a kind of guarantee.
- **Reporting**: PRISMA shows records screened (core + sample), records not
  screened (by design), and the estimated includes among them.

- 2026-10-15: amendment 3 (this section).
- 2026-10-15: amendment 3, execution note. The 1,000-record sample included
  186 records; proportional allocation of the coding sample asks for 208 from
  the remainder stratum. The sample is therefore extended by 250 records drawn
  without replacement from the not-yet-sampled remainder (seed 20261018 + 1),
  so the remainder sample stays a simple random sample (now 1,250). Decided
  from the include count only, before any coding.
