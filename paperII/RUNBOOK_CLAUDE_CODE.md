# Paper II — Claude Code Runbook

**Paper:** *SoK: The Quantifier Gap Between Certified Robustness and Airworthiness Assurance* (IEEE S&P, SoK track)
**Repository:** `rogerpanel/RobustUAVs.ai`. Work on `main`, or on a new branch `paperII/full-study`. `PENDING_ON_DATA.md` marks `claude/whelan-uavcas-ingest-u00isn` as stale.
**Folder:** `paperII/`, containing `corpus/`, `experiments/`, `results/` and `manuscript/`

This runbook tells a Claude Code session how to turn the **pilot** in the manuscript into the **full study**. The drafting sandbox could not do this: it had no access to scholarly APIs (OpenAlex and Semantic Scholar were blocked) and no human coders. Every number in `manuscript/main.tex` is a macro that `experiments/make_numbers.py` writes from the CSVs in `results/`. Once the full study's codes replace the pilot codes, the paper updates itself. **Never type a number into `main.tex` by hand.**

---

## 0. What is already done (do not redo)

`bash paperII/experiments/run_all.sh` regenerates everything below in about 5 seconds. It uses only the standard library, Python 3.10 or later.

| Script | What it does | Outputs |
|---|---|---|
| `quantifier.py` | Type system, the lift graph (15 edges) and Dijkstra transfer. Self-checks Props. 1–2 exhaustively. | none (asserts) |
| `reliability.py` | κ, Krippendorff α, Gwet AC1, PABAK with bootstrap CIs, per field and per lift. `--test` runs the formula self-tests. | `reliability_C1_C2.csv`, `disagreements_C1_C2.csv` |
| `adjudicate.py` | Applies the logged decisions in `corpus/adjudication.csv` to C1. | `corpus/codes_ADJ.csv` |
| `corpus_analysis.py` | H1–H4, class states, the 17×6 transfer table and the agenda. | `distribution.csv`, `hypotheses.csv`, `transfer_table.csv`, `class_states.csv`, `agenda.csv`, … |
| `rate_arithmetic.py` | Props. 3–4: per-frame budgets, confirmation credit, the SORA ladder and test economy. | `rate_*.csv`, `sora_ladder.csv`, `test_economy.csv` |
| `evidence_pack.py` | SORA Annex A pack built from the **parent's** `results/*.csv`. | `evidence_pack.json`, `evidence_obligations.csv`, `evidence_contingency.csv`, `lift_chain.csv` |
| `make_numbers.py` | Writes macros, figure data and generated table bodies. | `manuscript/numbers.tex`, `figdata/*.dat`, `tab_*_body.tex` |
| `search_corpus.py` | OpenAlex search, dedup and snowballing. **Not yet run** (needs open internet). | `corpus/search_raw.jsonl`, `candidates.csv`, `search_log.jsonl` |

**Pilot status, which the paper states plainly:**
- 86 guarantees, seeded purposively (not sampled).
- Two **LLM** coders: C1 was the drafting session; C2 was an independent sub-agent that never saw C1's codes.
- 50 adjudicated field changes, logged.
- 22 objectives; 8 rest on secondary sources (marked † in Table IV).

Build the paper with `bash paperII/manuscript/build.sh` (pdfLaTeX + BibTeX; IEEEtran is required, from TeX Live `texlive-publishers` or Overleaf).

---

## 1. Ground rules

1. New code goes in `paperII/experiments/`; outputs go in `paperII/results/` or `paperII/corpus/`. Every corpus row carries `coder` and `provenance` (`pilot_llm | human | llm_third | adjudicated`).
2. **Never overwrite the pilot.** Write `codes_H1.csv`, `codes_H2.csv` (humans) and `codes_L3_run{1,2,3}.csv` (LLM). Keep `codes_C1.csv` and `codes_C2.csv` for the appendix.
3. **The LLM never excludes a paper on its own.** It may only flag a paper for human review.
4. **Freeze the codebook.** It is at v1.1 (`corpus/CODEBOOK.md`). If a rule must change during the full study, bump the version, log the change, and re-code the papers it affects.
5. **Stop rule for prose.** If a full-study result contradicts a sentence in the manuscript (not just a number), stop and summarise the contradiction before editing prose. These sentences are the likeliest to change:
   - the H1 tier-A perception share;
   - the H2 trend from 7 % to 26 %;
   - "no pilot paper uses L_sup".
6. Commit per experiment, with a message of the form `paperII: S<n> <short result>`.

---

## S1 — Search (PRISMA "identification")

Needs open internet. Optionally set `OPENALEX_MAILTO=<email>` to use OpenAlex's polite pool.

```bash
cd paperII/experiments
python3 search_corpus.py search --dry-run          # check the 16 queries
python3 search_corpus.py search                    # -> ../corpus/search_raw.jsonl (+ search_log.jsonl)
python3 search_corpus.py dedup                     # -> ../corpus/candidates.csv
```

Then add the databases that OpenAlex does not cover well:

- **IEEE Xplore, ACM DL, Scopus, Web of Science.** Run the same three blocks through the web UI or institutional API. Export to CSV and append to `candidates.csv`, using the `cid` prefixes `X`, `A`, `S` and `W`.
- **Venue sweeps (DBLP).** Pull TOCs for 2017–2026 of: S&P, USENIX Sec, CCS, NDSS, CAV, TACAS, HSCC, ICCPS, EMSOFT, NFM, SAFECOMP, DSN, NeurIPS, ICML, ICLR, CoRL, CDC and DASC. Filter titles with block A.

**Output.** Write `corpus/prisma_counts.csv` with columns `stage,n`. The stages are identified, duplicates, screened, full-text and included.

**Manuscript hook.** Add a PRISMA flow figure (`fig_prisma.tex`) driven by new macros `\nIdentified` … `\nIncluded`. Put it in Sec. IV-A.

## S2 — Screening (title/abstract)

1. **Two humans** (H1, H2) screen `candidates.csv` independently against the inclusion rule in Sec. IV-A. Each writes `screen_H1.csv` / `screen_H2.csv` with columns `cid,include{0,1},reason`.
2. **LLM third screener.**
   - Spawn one Claude Code sub-agent per batch of 50 papers. It reads only `CODEBOOK.md` and the batch, and never the human files.
   - Run it three times per batch → `screen_L3_run{1,2,3}.csv`.
   - The LLM's output may **only** add a paper to `screen_flags.csv` for human re-check. It may never remove one.
3. Report screening κ (H1 vs H2), LLM run-to-run agreement, and the LLM-vs-human κ. Also report how many papers the LLM's flags rescued. Use:
   `python3 reliability.py H1 H2` (adapt `FIELDS` to `include`).

## S3 — Snowballing

```bash
python3 search_corpus.py snowball --inp ../corpus/included_iter0.csv --out ../corpus/snowball_iter1.csv
```

Screen each iteration exactly as in S2.

**Stop rule:** stop when two consecutive iterations each add fewer than 2 % new inclusions **and** no new (scope × modality) cell appears. Log each iteration in `corpus/snowball_log.csv` with columns `iter,candidates,included,new_cells`.

## S4 — Full-text coding (the study proper)

1. Two humans code every included paper on the 8 fields of `CODEBOOK.md` v1.1 → `codes_H1.csv`, `codes_H2.csv`. The header is identical to `codes_C1.csv`.
2. The LLM third coder (three runs) → `codes_L3_run*.csv`. Give it the paper PDF or abstract plus the codebook only.
3. Compute reliability:
   ```bash
   python3 reliability.py H1 H2
   python3 reliability.py H1 L3_run1
   python3 reliability.py L3_run1 L3_run2
   ```
   **Acceptance:** α ≥ 0.80 on `scope`, `modality` and `scope_x_modality`, and ≥ 0.667 on `assumption`. If a field fails, refine the codebook (bump the version), re-code a fresh 20 % calibration set, and repeat.
4. **Adjudicate.** Log every decision in `corpus/adjudication_full.csv` (gid, field, value, rationale). Then generalise `adjudicate.py` to take `--base H1 --log adjudication_full.csv --out codes_ADJ.csv`.
5. Assign each included paper to a class in `corpus/classes.csv`. Add new classes if a new cell appears, for example certified optical flow or learned DAA.

## S5 — Objective corpus verification

For each of the 8 `secondary` rows in `corpus/objectives.csv`, check the wording against the primary PDF:

- EASA Issue 02, LM-04 / LM-12 / LM-13 (pp. ~67–88)
- Proposed Issue 03 (oversight system)
- AMC 25.1309
- SORA 2.5 Annex A
- ED-324 (if it is published by the time you run this)
- DO-326A

Set `source_check=primary` and add a `page` column. If a document changed after 7 Oct 2026, move the freeze date in `main.tex` (Sec. IV-D) **and** in this runbook.

## S6 — Regenerate and rebuild

```bash
# point the pipeline at the full study:
#   reliability.py H1 H2 -> results/reliability_H1_H2.csv
#   make_numbers.py: read reliability_H1_H2.csv instead of _C1_C2 (one-line change, keep pilot as appendix table)
bash paperII/experiments/run_all.sh
bash paperII/manuscript/build.sh
```

Report which macros changed in `numbers.tex`, and by how much (`git diff --word-diff manuscript/numbers.tex`).

## S7 — Sensitivity analyses (Sec. XI)

Add `experiments/sensitivity.py`. It recomputes `hypotheses.csv` under each of these:

- (a) tier A only;
- (b) excluding arXiv-only papers;
- (c) a strict assumption rule, where `S` counts as unaccounted, versus a loose rule, where `S` counts as accounted;
- (d) leave-one-venue-out;
- (e) pre/post-2022 split, with a Fisher exact test on accounted versus not;
- (f) the transfer table with obligations weighted by kind (statistical = 2, model = 1.5, architectural = 1, proof = 0.5).

**Output:** `results/sensitivity.csv`. Add a small table to the appendix.

## S8 — Evidence pack refresh (Sec. VIII)

`evidence_pack.py` reads the parent's `results/`. Re-run it whenever the parent or Paper I updates γ, L or the mission distribution. In particular, re-run it if Paper I's E1 or E3 (SITL dead-reckoning, cruise) lands. The `O_cal` status should move from *partially evidenced* only if platform or flight mode becomes varied.

**Optional.** Export the pack as a GSN fragment (`evidence_pack.gsn.yaml`):
- each obligation becomes an Assumption node;
- each lift becomes a Strategy node;
- each status becomes an Assurance Claim Point.

## S9 — Artifact

Run `python3 tools/anonymise.py --out ../RobustUAVs-anon --init-git --zip` from the repo root. Check that `paperII/` is scrubbed, then rebuild the PDF inside the anonymised tree.

---

## Order and effort

| Order | Step | Needs | Effort | Moves headline? |
|---|---|---|---|---|
| 1 | S1–S3 search, screen, snowball | internet, 2 humans | 2–3 weeks | corpus size, H1 shares |
| 2 | S4 coding + reliability | 2 humans, Claude Code sub-agents | 3–4 weeks | **H1–H4, transfer table** |
| 3 | S5 objective verification | EASA/JARUS PDFs | 2 days | Table IV daggers |
| 4 | S7 sensitivity | none | 1 day | robustness of H2 trend |
| 5 | S6/S8/S9 rebuild, pack, anonymise | none | 0.5 day | — |

## Prompt to paste into Claude Code

> You are working in `rogerpanel/RobustUAVs.ai` on `main` (create branch `paperII/full-study`). Read `paperII/RUNBOOK_CLAUDE_CODE.md`, `paperII/corpus/CODEBOOK.md` and `paperII/experiments/quantifier.py`. Run `bash paperII/experiments/run_all.sh` and `bash paperII/manuscript/build.sh` to confirm the pilot reproduces (0 errors, 0 undefined). Then execute S1 (search, dedup) and stop to show me `prisma_counts.csv` before screening. For screening and coding, spawn independent sub-agents as the LLM third coder exactly as S2/S4 specify; never let LLM output exclude a paper. Keep the pilot files untouched. Do not edit numbers in `main.tex` by hand. If a full-study result contradicts a sentence in the manuscript, stop and summarise the contradiction before changing prose.
