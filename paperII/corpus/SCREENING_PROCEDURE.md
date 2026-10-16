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

## Amendment 4 (2026-10-15): full-text eligibility and coding by LLM coders, disclosed

Fixed before any full text was coded. Retrieval (`fetch_fulltext.py`, open
access only) gave 92/92 core and 195/208 remainder full texts: the remainder
stratum ran out of included records (all 233 tried; 38 had no open copy), so
287 papers are coded, and the weights in `coding_sample.csv` are recomputed
as estimated includes / papers coded per stratum. Open-access-only retrieval
is reported as a limitation.

- **Coders C1 and C2**: independent sub-agent runs on two different models.
  Each reads only `CODEBOOK.md` (v1.1), the inclusion rule
  (`SCREENING_RULE.md`), `classes.csv`, and a batch of full texts (the first
  80,000 characters of each, which covers abstract, method and evaluation for
  most papers; truncation is recorded). Neither sees the other's codes.
- **Fields**: full-text `eligible` (0/1) with a reason, then for eligible
  papers `class` (one of `classes.csv`, or `NEW:<label>` for a guarantee type
  the pilot classes do not cover) and the eight codebook fields.
- **Adjudication**: a third, independent LLM instance (ADJ) sees the full text
  and both codings, resolves every disagreement with a logged rationale, and
  may not change fields on which C1 and C2 agree.
- **Reliability**: per-field percent agreement, Cohen's kappa, Krippendorff's
  alpha, Gwet's AC1 and PABAK between C1 and C2 (`reliability.py`), reported
  as LLM-LLM agreement, i.e. a measure of codebook clarity, never as expert
  agreement.
- **Estimates**: corpus-level shares are weighted by stratum, with intervals.

- 2026-10-15: amendment 4 (this section).
- 2026-10-15: amendment 4, execution note (added after adjudication; it changes
  no rule). Agreement C1-C2: eligibility 257/287 (kappa 0.75); on papers both
  found eligible, Cohen's kappa 0.74 (class) to 0.97 (tier), lowest for
  `assumption` (0.47). ADJ resolved all 168 papers (30 eligibility, 219 field
  disagreements), 0 unresolved, 0 attempts to change an agreed field. ADJ ran on
  the same model as C2 and chose C2's value in 166 of the 219 field
  disagreements (C1 47, a third value 6). Because of this, every hypothesis
  quantity is also reported from C1's and from C2's codes alone
  (`hypotheses_full_C1.csv`, `hypotheses_full_C2.csv`), and a conclusion is
  stated only where all three agree.

## Amendment 5 (2026-10-15): snowballing iterations and the new classes, disclosed

Fixed before any snowballing data was retrieved, and after the full-study
estimates of amendment 4 were seen (so it is not blind to them; it fixes how the
stop rule of the manuscript is applied to a sampled corpus).

- **Seeds**: iteration 1 starts from the 191 full-text-eligible coded papers
  (`codes_full_final.csv`); iteration k > 1 from the eligible coded papers of
  iteration k - 1. Backward (references) and forward (citations) snowballing
  through OpenAlex, 2017-2026, by `search_corpus.py snowball`
  (`run_snowball.sh`). A work already among the 25,373 candidates or an earlier
  iteration (OpenAlex id, DOI, or normalised title) is not new.
- **Screening**: new candidates are screened by L1/L2 as in amendment 2. If an
  iteration yields more than 3,000 new candidates, they are ranked with the
  frozen ranker of `screen_rank.py` (not retrained) and screened as a core of
  ranks 1-1,500 plus a simple random sample of 500 of the rest (seed
  20261022 + k), estimated as in amendment 3.
- **Coding**: up to 100 included records per iteration, a stratified random
  sample allocated as in amendment 3 (seed 20261023 + k), full text open
  access only, coded by C1/C2 and adjudicated by ADJ exactly as in amendment 4.
- **Stop rule** (manuscript, Sec. IV-B), applied to estimates: an iteration is
  quiet when (a) its estimated new includes are below 2 % of the estimated
  eligible field before it, and (b) no coded paper occupies a scope x modality
  cell not seen before. Snowballing stops after two consecutive quiet
  iterations, or after three iterations; if it stops at the cap without two
  quiet iterations, the corpus is reported as not saturated.
- **Classes**: guarantee types coded `NEW:<label>` are grouped into new classes
  (`classes.csv`, marked as added in the full study), each with its quantifier
  type and lifts derived from the codebook as for the pilot's 17, so the
  transfer table covers them. The grouping is reported label by label
  (`corpus/new_class_map.csv`).

- 2026-10-15: amendment 5 (this section).
- 2026-10-15: amendment 4, correction. "Retrieval gave 92/92 core" above is
  imprecise: 92 core full texts were retrieved after 117 core records were
  tried in sample order (25 had no open-access copy and were replaced, as
  amendment 3 prescribes). The remainder stratum tried all 233 included
  records and retrieved 195 (38 not retrieved). Per-record status:
  `fulltext_status.csv`.
- 2026-10-16: amendment 5, execution note for iteration 2 (written after the
  candidates were retrieved and ranked, before any of them was screened; it
  changes no rule). Iteration 2 found 3,522 new candidates from 77 seeds (10
  seeds had no references in OpenAlex), so the ranked design applies. "The
  frozen ranker" is the rank_v1 model (word TF-IDF, PU bagging on the
  development half of the pilot set, no screening labels, as amendment 2 held
  it fixed), fitted on `candidates.csv` and applied to the new records in its
  own vocabulary; it reproduces every score of `rank_v1.csv` (to the 6
  printed decimals). Core = ranks 1-1,500; the remainder of 2,022 is sampled
  by a simple random sample of 500 drawn from the sorted cids (seed
  20261024 = 20261022 + 2). Core and sample are screened in one random order
  from the same generator, so L1/L2 see neither rank nor stratum
  (`snowball/iter2_rank.csv`, `iter2_strata.csv`). The coding sample of 100 is
  allocated as in amendment 3, scaled: in proportion to estimated includes,
  at least 25 per stratum (75 of 300 in amendment 3). The stop-rule estimate
  of new eligible papers is stratified, with the bootstrap of
  `corpus_estimates.py` (B = 4000, seed 20261020).
- 2026-10-16: amendment 5, execution note for iteration 3 (changes no rule).
  2,226 candidates from 84 seeds (2 without OpenAlex references), so every
  record is screened. Two L2 outputs failed the merge check (N303: one cid
  mistyped; N318: one record missing). The merge then covered 2,000 records
  and a coding sample was drawn from it and committed (3c55177) before the
  check was read; it was never used. Each L2 run corrected its own file (the
  mistyped record's decision unchanged; the missing record screened), the
  merge was rerun on all 2,226, and the sample was redrawn with the same seed
  (20261025). `snowball_sample.py` now refuses to sample while any screening
  batch is pending or invalid. L1 gave a single generic exclusion reason in 15
  of 18 batches; its decisions remain per record.

## Amendment 6 (2026-10-16): field estimates over the searched corpus and the snowball strata, disclosed

Fixed after the screening of all three snowballing iterations and the coding
and adjudication of iterations 1-2, before iteration 3 was adjudicated and
before any estimate was computed with snowball strata. It is not blind: the
iteration 1-2 stop-rule results (16 % and 23 % new eligible papers, no new
type-plane cell, a falling tier-A share among the snowball papers) were seen
first. It changes no screening, coding or adjudication rule.

- **Why**: amendment 4 estimates shares of the searched corpus. Snowballing
  found an estimated 43 % more eligible papers after two iterations, so "share
  of the field" must cover them, or say that it does not.
- **Strata**: main core, main remainder (amendments 3-4); snowball1;
  snowball2_core and snowball2_remainder; snowball3. Strata are disjoint by
  construction (every snowball candidate was de-duplicated against the
  candidates and all earlier iterations). Each coded paper of stratum s stands
  for N_s / n_s records, N_s the stratum's estimated includes (screened in
  full: the count; sampled: N_rem x p_hat) and n_s its papers coded, eligible
  or not, exactly as amendment 4 weighs the main strata.
- **Intervals**: the stratified percentile bootstrap of `corpus_estimates.py`
  and `hypotheses_full.py` (B = 4000, their seeds 20261020 and 20261021),
  extended to all six strata: coded papers resampled within each stratum, and
  the include count of every sampled stratum redrawn as N_rem x Binomial(m,
  p_hat) / m.
- **What is reported**: every corpus-level share and every hypothesis quantity
  is reported on the expanded field (primary) and on the searched corpus
  (amendment 4, kept unchanged as a labelled column). A conclusion that differs
  between the two is reported as differing; neither is chosen after the fact.
  The C1-only and C2-only sensitivity runs are repeated on the expanded field.
- **What the expanded field is**: the searched corpus plus the citation
  neighbourhood reached by three snowballing iterations from coded seeds. The
  snowball strata are probability samples of that neighbourhood, not of the
  literature as a whole; the paper says so, and that the corpus is not
  saturated (amendment 5's stop rule was not met).
- **New classes**: the `NEW:` labels of iterations 1-3 are grouped label by
  label into classes as amendment 5 prescribes (an existing class, including
  the five added in the full study, when its grouping rule fits; otherwise a
  new added class), from the coded label and note only, before any estimate is
  recomputed; `new_class_map.csv` is extended and the transfer table covers
  any new class.

- 2026-10-16: amendment 6 (this section).
