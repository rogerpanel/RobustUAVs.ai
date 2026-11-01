# The Quantifier Gap: artifact for review

This repository is the anonymised artifact for the paper *SoK: The Quantifier Gap Between
Certified Robustness and Airworthiness Assurance*. It contains the quantifier type system and
lift calculus, the search records, both screeners' decisions, both coders' codes, the
adjudication log, the objective corpus, the evidence generator, every result file, and the
scripts that turn those files into the numbers, tables and figures of the paper.

It is anonymised for double-blind review. Author names, affiliations and repository addresses
have been removed and will be restored on acceptance.

| | |
|---|---|
| Language | Python 3 (tested with 3.11) |
| Dependencies | `numpy`, `scipy` (`python3 -m pip install numpy scipy`); TeX Live 2022+ and `pdfinfo` to build the paper |
| Run time | about 40 seconds on a laptop CPU, no download, no GPU, no API key; the paper builds in about 5 seconds |
| Licence | MIT (`LICENSE`); the bibliographic records come from OpenAlex (CC0) |

## 1. Quick check (about 40 seconds)

```bash
python3 -m pip install numpy scipy
bash paperII/experiments/run_all.sh      # rewrites paperII/results/, manuscript/numbers.tex, tab_*_body.tex, figdata/
git status --short                       # expected: no output
bash paperII/manuscript/build.sh         # pdfLaTeX + BibTeX; prints errors, undefined references and pages
```

`run_all.sh` starts from the committed screening decisions and LLM codes. It merges and checks
both coders' batches, applies the adjudication, computes reliability, the weighted estimates
with their bootstrap intervals, the three snowballing iterations and the transfer table, and
then writes the paper's 964 number macros (`manuscript/numbers.tex`), the three generated
table bodies and the figure data. The bootstrap and sampling seeds are fixed, so an empty
`git status` after `run_all.sh` shows that the paper, the result files and the code agree.
`build.sh` should report `errors: 0  undefined: 0` and 19 pages.

## 2. Where each result comes from

Scripts are in `paperII/experiments/`. Result files are in `paperII/results/` unless a path says
otherwise; `corpus/` means `paperII/corpus/`.

| Result in the paper | Script | Result file |
|---|---|---|
| Search: 33,664 records identified, 8,291 duplicates, 25,373 candidates; the revised strings retrieve 63% of the pilot set (54/86) and 67% of its held-out half (29/43) | `search_corpus.py`, `prisma_counts.py`, `search_sensitivity.py` (search stage, committed) | `corpus/prisma_counts.csv`, `corpus/search_log.jsonl`, `search_sensitivity.csv`, `corpus/logs/s1_rev1_2026-10-15.txt` |
| Screening: 4,000 of 25,373 records screened (core of 2,750 plus a random sample of 1,250 of the remaining 22,623); screeners agree with κ = 0.91 | `screen_llm_merge.py` (screening stage, committed) | `corpus/screening/decisions.csv`, `screening_status.csv` |
| Coding: 287 papers coded, 191 eligible; the expanded field is 587 coded papers in 6 strata, an estimated 6,300 eligible papers | `coding_merge.py`, `adjudication_merge.py`, `corpus_estimates.py`, `field_estimates.py` | `corpus/codes_full_final.csv`, `corpus_estimates.csv`, `field_estimates.csv`, `field_strata.csv` |
| Reliability (Table V): Krippendorff's α = 0.89 [0.84, 0.94] for the type and 0.97 for the tier; assumption field 77% agreement, κ = 0.47, AC1 0.73; the adjudicator took the second coder's value in 166 of 219 field disagreements | `reliability.py full_C1 full_C2`, `adjudication_merge.py` | `reliability_full_C1_full_C2.csv`, `adjudication_status.csv`, `corpus/coding/adjudication_log.csv` |
| Snowballing: three iterations add an estimated 644, 1,089 and 535 eligible papers (16%, 23% and 9% of the field before each) and no new cell of the type plane | `snowball_screen.py`, `snowball_sample.py`, `snowball_stoprule.py` | `snowball_iter{1,2,3}_status.csv`, `corpus/snowball/` |
| Landscape: 30% of guarantees per input and 44% per population; conformal prediction is the largest class at 19% [15%, 23%] | `field_estimates.py` | `field_estimates.csv`, `distribution_field.csv`, `type_plane_field.csv` |
| H1 (Fig. 3): 53% of perception guarantees per input [45%, 61%] against 18% of control, 40% of control per trajectory; 58% of tier-A perception per input | `field_estimates.py` (with `hypotheses_full.py`) | `field_hypotheses.csv`, `field_hypotheses_C1.csv`, `field_hypotheses_C2.csv` |
| H2: 66% of guarantees use a lift; 21% [16%, 27%] of those account for its assumption (14% and 24% by coder; 28% in the searched corpus) | `field_estimates.py`, `hypotheses_full.py` | `field_hypotheses*.csv`, `hypotheses_full*.csv` |
| Transfer table (Table VI): 32 rows, 192 cells, 14 discharges, 120 lifts, 58 category errors; 27 rows reach T1, all through L_rate | `transfer_full.py --field` (calculus in `quantifier.py`) | `transfer_table_field.csv`, `class_states_field.csv`, `manuscript/tab_transfer_body.tex` |
| H3 and H4: only 1% [0%, 2%] of guarantees perform the rate lift; RTA is 8% [5%, 11%] of the field and the only class that discharges a per-operation objective directly | `field_estimates.py`, `transfer_full.py --field` | `field_hypotheses.csv`, `transfer_table_field.csv` |
| Proposition 2, and the scope monotonicity behind Proposition 1, checked exhaustively over all pairs of types; the least-obligation paths of Corollary 1 | `quantifier.py` | asserted and printed when run; `run_all.sh` stops if a check fails |
| Rate arithmetic (Fig. 4): p* = 9.3×10⁻¹⁰ per frame at 30 Hz for 10⁻⁴/FH; confirmation gain at most 6.75 against 10⁶ under independence; 3.2×10⁹ failure-free frames (29,957 h) for 10⁻⁴/FH; the SORA ladder is the rule of three within 0.15% | `rate_arithmetic.py` | `rate_requirements.csv`, `rate_correlation.csv`, `test_economy.csv`, `sora_ladder.csv` |
| Evidence pack (Table VII): γ = 1.625 m/s, δ = 0.81 m, tube ρ = 2.65 m (24.4 m under the kinematic worst case); 6 obligations, 2 open or assumed | `evidence_pack.py` | `evidence_pack.json`, `evidence_obligations.csv`, `evidence_contingency.csv`, `lift_chain.csv` |
| Objective corpus (Table IV): 22 objectives from nine documents, 14 checked against the primary text | `make_numbers.py` | `corpus/objectives.csv`, `manuscript/tab_objectives_body.tex` |

Every hypothesis quantity is computed three times: from the adjudicated codes and from each
coder's codes alone (the `_C1` and `_C2` files), so a reader can check that a conclusion holds
in every reading. The pilot (86 guarantees in 17 classes) is in `corpus/corpus_index.csv`,
`codes_C1.csv`, `codes_C2.csv`, `adjudication.csv` and `codes_ADJ.csv`; `corpus_analysis.py`
computes its results, which the paper reports beside the full study.

The evidence generator reads four committed result files of the running example, the
certificate for delayed navigation input, from `results/` at the repository root:
`certified_floor_vs_theta.csv`, `local_lipschitz.csv`, `gamma_campaign_bins.csv` and
`mission_distribution.csv`. They are inputs here and are not regenerated.

## 3. Re-running from the sources

The quick check needs no network and no model access. The earlier stages, whose outputs are
committed, need the following.

- **Search and snowballing** (`search_corpus.py`, `run_s1_full.sh`, `run_snowball.sh`) query
  OpenAlex and need internet access. In practice they need a free OpenAlex API key, read from
  `OPENALEX_API_KEY` or `~/.config/openalex_key`; `run_s1_full.sh` stops without one unless
  `ALLOW_NO_KEY=1` is set. Every request is logged with a UTC timestamp in
  `corpus/search_log.jsonl`. The raw responses of the registered search are committed
  (`corpus/search_raw.jsonl.gz`, `corpus/venue_raw.jsonl.gz`), and the counts of the revised
  search, from which `corpus/candidates.csv` was built, are in `corpus/logs/s1_rev1_2026-10-15.txt`.
- **Full texts**: `fetch_fulltext.py` fetches open-access copies only. The texts are
  third-party documents and are not included; `corpus/fulltext_status.csv` and the
  `iter*_fulltext_status.csv` files list each record's source and status.
- **LLM screening, coding and adjudication** need an LLM agent that can read local files, on
  two different models. The prompts are released (`corpus/screening/llm/SCREENER_PROMPT.txt`,
  `corpus/coding/CODER_PROMPT.txt`, `corpus/coding/ADJ_PROMPT.txt`), with every batch
  (`*.cids`) and every output. `screen_llm_batches.py`, `coding_sample.py`,
  `snowball_coding_batches.py` and `adjudication_prep.py` write the batches, and the merge
  scripts check each output against its batch and the codebook vocabulary before using it.

None of these stages is needed to reproduce the numbers: `run_all.sh` starts from their
committed outputs.

## 4. Protocol, coding and extensions

**Protocol.** The protocol is stated in Section IV of the paper: block search strings, two
inclusion tiers, a snowballing stop rule, an eight-field codebook and per-field reliability.
`corpus/SCREENING_RULE.md` holds the inclusion rule verbatim. `corpus/CODEBOOK.md` is the
codebook: version 1.0 was frozen on 2026-10-07, and version 1.1 adds three decision rules from
the pilot, frozen before the full study. `corpus/SCREENING_PROCEDURE.md` records six dated
amendments. Each is dated and states what it changes and when it was fixed relative to the data
it governs; later execution notes and corrections are appended with their dates.

| Amendment | Date | What it fixes |
|---|---|---|
| 1 | 2026-10-15 | Screening in a ranked order (TF-IDF and logistic regression trained on the development half of the pilot set) with a stopping rule; fixed before any ranking was computed |
| 2 | 2026-10-15 | Two independent LLM screeners on two different models; a record is excluded only when both exclude it; fixed before any record was screened |
| 3 | 2026-10-15 | A core of ranks 1–2,750 screened in full, a simple random sample of the remainder, and a stratified full-text sample; fixed before the sample was drawn |
| 4 | 2026-10-15 | Full-text eligibility and coding by two LLM coders, a third instance as adjudicator; fixed before any full text was coded |
| 5 | 2026-10-15 | Three snowballing iterations, the stop rule applied to estimates, and the grouping of new guarantee classes; fixed before any snowballing data was retrieved |
| 6 | 2026-10-16 | Field estimates over all six strata, reported beside the searched-corpus estimates; fixed before iteration 3 was adjudicated |

**Coding.** Two coders, C1 and C2, code every sampled paper independently from the codebook,
the inclusion rule and the class list, and neither sees the other's codes. A third instance
(ADJ) resolves every disagreement with a logged rationale and may not change a field on which
the coders agree (`adjudication_merge.py` enforces this and logs any attempt). All three are
LLM instances, so their agreement is reported as a measure of codebook clarity. Because the
adjudicator ran on the second coder's model, the paper reports every hypothesis quantity from
each coder alone as well, and states a conclusion only where the readings agree.

**Extensions.** Natural extensions, and where each one enters the pipeline (after which
`run_all.sh` regenerates every number):

- a human coder in place of either LLM coder, on the released coding sample: the batch files
  list the papers (`fetch_fulltext.py` retrieves their open-access texts), `coding_merge.py`
  checks the codes against the codebook vocabulary, and `adjudication_prep.py` writes out the
  disagreements to adjudicate;
- the human check that amendment 2 specifies: a blind screen of 100 records excluded by both
  screeners (seed 20261017);
- further snowballing iterations beyond the three in the protocol: `run_snowball.sh` and the
  snowballing scripts take the iteration number (`--iter`);
- searches of other databases, such as Scopus and Web of Science: `prisma_counts.py` already
  counts rows appended to `corpus/candidates.csv` from other sources;
- a sweep of the 18 venues' DBLP tables of contents, beside the OpenAlex venue sweeps;
- a different calculus: the lifts are the edge set in `quantifier.py` (`_edges()`), so adding
  or removing an edge recomputes the transfer table, and a deficit weighted by evidence kind
  replaces the unit weights of `shortest_path()`;
- the eight objectives that rest on secondary sources (`source_check` in
  `corpus/objectives.csv`), checked against the primary text;
- evidence packs for other configurations of the running example (`THETA`, `H` and the
  mappings at the top of `evidence_pack.py`).

## 5. Layout

```
paperII/experiments/   quantifier.py (types, lifts, dominance, shortest paths), reliability.py,
                       coding_merge.py, adjudication_merge.py, corpus_estimates.py,
                       hypotheses_full.py, field_estimates.py, transfer_full.py,
                       snowball_*.py, rate_arithmetic.py, evidence_pack.py, make_numbers.py,
                       run_all.sh; search, screening and full-text stages: search_corpus.py,
                       run_s1_full.sh, run_snowball.sh, screen_*.py, fetch_fulltext.py
paperII/corpus/        CODEBOOK.md, SCREENING_RULE.md, SCREENING_PROCEDURE.md (amendments 1-6);
                       candidates.csv, search_log.jsonl, search_raw.jsonl.gz, prisma_counts.csv;
                       screening/ (rankings, both screeners' batches and decisions);
                       coding_sample.csv, fulltext_status.csv, codes_full_{C1,C2,final}.csv;
                       coding/ (batches, both coders' outputs, adjudication log, prompts);
                       snowball/iter{1,2,3}_*; classes.csv, new_class_map.csv, objectives.csv;
                       pilot: corpus_index.csv, codes_{C1,C2,ADJ}.csv, adjudication.csv
paperII/results/       result files (CSV) and evidence_pack.json
paperII/manuscript/    main.tex (IEEEtran), fig_*.tex (TikZ/pgfplots), figdata/, numbers.tex,
                       tab_*_body.tex, refs.bib, build.sh
results/               committed results of the running example's certificate (inputs only)
```
