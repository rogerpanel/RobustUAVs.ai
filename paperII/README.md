# Paper II — SoK: The Quantifier Gap Between Certified Robustness and Airworthiness Assurance

This is the IEEE S&P SoK track paper. It broadens proposal P3 of the parent manuscript ("From Wire to Flight").

```
paperII/
  corpus/        CODEBOOK.md (v1.1), corpus_index.csv (86 pilot guarantees), codes_C1/C2.csv (two
                 independent LLM coders), adjudication.csv (50 logged changes), codes_ADJ.csv,
                 classes.csv (17 classes), objectives.csv (22 objectives)
  experiments/   quantifier.py (type system + lift graph), reliability.py, adjudicate.py,
                 corpus_analysis.py, rate_arithmetic.py, evidence_pack.py, make_numbers.py,
                 search_corpus.py (full study), run_all.sh
  results/       every CSV the paper quotes, plus evidence_pack.json
  manuscript/    main.tex (IEEEtran), fig_framework.tex (Fig. 1), fig_lattice.tex, fig_results.tex,
                 numbers.tex + tab_*_body.tex + figdata/ (generated), refs.bib, build.sh
  RUNBOOK_CLAUDE_CODE.md   steps S1–S9 that turn the pilot into the full study
```

## Rebuild

```bash
bash paperII/experiments/run_all.sh      # ~5 s, stdlib only
bash paperII/manuscript/build.sh         # pdfLaTeX + BibTeX; prints errors/undefined/pages
```

For Overleaf, upload `manuscript/`. The main file is `main.tex`.

## Before submission

- The corpus figures are a **pilot**: a purposive seed, with LLM coders. Run the runbook's S1–S7 first.
- Check `refs.bib` entries marked `% VERIFY`. Three have authors still to be confirmed.
- Check the 8 objectives tagged `secondary` in `corpus/objectives.csv` against the primary PDFs (S5).
