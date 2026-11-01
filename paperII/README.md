# Paper II: The Quantifier Gap

SoK: The Quantifier Gap Between Certified Robustness and Airworthiness Assurance.

```
paperII/
  corpus/             protocol and data of the systematic review
    CODEBOOK.md         codebook (v1.1)
    SCREENING_RULE.md   inclusion rule, verbatim from the paper
    SCREENING_PROCEDURE.md   screening and coding procedure with six dated amendments
    candidates.csv      the 25,373 deduplicated search records; search_log.jsonl: every request
    screening/          rankings, both screeners' batches and decisions (decisions.csv)
    coding/             coding batches, both coders' outputs, adjudication log, prompts
    codes_full_{C1,C2,final}.csv   both coders' codes and the adjudicated codes
    snowball/           the three snowballing iterations
    classes.csv, new_class_map.csv, objectives.csv   guarantee classes, objective corpus
    corpus_index.csv, codes_{C1,C2,ADJ}.csv, adjudication.csv   the pilot set
  experiments/        Python (~40 s end to end; needs numpy and scipy)
    quantifier.py       type system, lift calculus, least-obligation paths, self-checks
    reliability.py      kappa, Krippendorff's alpha, Gwet's AC1, PABAK with bootstrap intervals
    coding_merge.py, adjudication_merge.py   merge and check the codes, apply the adjudication
    corpus_estimates.py, hypotheses_full.py, field_estimates.py   weighted estimates and H1-H4
    snowball_screen.py, snowball_sample.py, snowball_stoprule.py   snowballing iterations
    transfer_full.py    the computed transfer table
    rate_arithmetic.py  per-flight-hour arithmetic and the SORA test-hour ladder
    evidence_pack.py    SORA Annex A-shaped evidence pack for the running example
    make_numbers.py     manuscript/numbers.tex, table bodies and figure data
    run_all.sh          regenerate everything from the committed codes
    search_corpus.py, run_s1_full.sh, run_snowball.sh, screen_*.py, fetch_fulltext.py
                        search, screening and full-text stages (need internet)
  results/            CSV outputs and evidence_pack.json (inputs of evidence_pack.py:
                      ../results/certified_floor_vs_theta.csv, local_lipschitz.csv,
                      gamma_campaign_bins.csv, mission_distribution.csv)
  manuscript/         main.tex (IEEEtran), fig_*.tex (TikZ/pgfplots), figdata/, numbers.tex,
                      tab_*_body.tex, refs.bib, build.sh
```

## Rebuild

```bash
bash paperII/experiments/run_all.sh
bash paperII/manuscript/build.sh         # pdfLaTeX + BibTeX; prints errors, undefined references and pages
```

For Overleaf, upload the `manuscript/` folder; the main file is `main.tex`.

The protocol, its amendments and the coding are described in `corpus/SCREENING_PROCEDURE.md`
and in the README at the root of the review artifact.
