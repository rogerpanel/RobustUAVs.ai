# Research proposals — Overleaf bundle

Follow-on work from the composition theorem in the parent manuscript
(`paper/paperD_v7.tex`). Prose source of truth for the original three is
`docs/research_roadmap_2027.md`.

There are now **five conference papers** from this project, in three groups:

- **S&P track** — from the parent paper's own concepts (P1, P2, P3). See
  "three proposals → two IEEE S&P papers" below.
- **MSCA track** — from the CERTIFLIGHT MSCA proposal's concepts. See
  "two papers from the CERTIFLIGHT proposal" below.
- **Paper V** — `PaperV_safety_filter_llm_agent.tex` (IEEE SaTML). A
  predictive safety filter that keeps an LLM-driven UAV agent inside the
  certified envelope *regardless* of whether the language model is
  compromised — turning a safety attack into a (measurable) liveness attack.
  It is Paper III's projection layer lifted to continuous MPC with an
  *untrusted* planner and an *adaptive* attacker; Prop. 3 shows its attacker
  and Paper IV's share one perturbation budget. A two-page overview of all
  five is in `SUPERVISOR_BRIEF.tex` (currently covers I–IV; extend if needed).

All share `proposal_preamble.tex` and `proposals.bib`, and each `.tex`
compiles independently.

## MSCA track: CERTIFLIGHT concept → two papers (NeurIPS + USENIX)

| File | What it is |
|---|---|
| `MSCA_PAPERS_MAP.tex` | **Start here for this track.** Which CERTIFLIGHT objective/theorem becomes which paper, and how all four conference papers relate |
| `PaperIII_certified_constrained_marl.tex` | **Paper III** (NeurIPS) — from MSCA O3/T3/T4 (WP4). A formal robustness certificate used as a *time-varying, pointwise* multi-agent constraint, feasibility preserved during learning; linear-time feasibility and k-robustness via the nested structure of certified radii; coverage-degradation bound |
| `PaperIV_crosslayer_benchmark.tex` | **Paper IV** (USENIX Security) — from MSCA O1/O2, T1/T2 (WP2/WP3). The unified perturbation budget + cross-layer benchmark, reframed around the security point that an attacker can disguise interference as a fault or gust (adversarial equivalence) |

Paper III's two combinatorial results (maximum coverage, and the k-robust
condition) were **verified against a brute-force matching oracle over 3000
random instances — exact agreement on both**. That is a check on the math, not
evidence about flight.

Paper IV's theoretical hinge — that the union-bound tightness gap is the
Makarov / VaR-aggregation gap — is a **reduction to prove, not an assertion**;
the sound union bound is the stated fallback. Its benchmark and evasion study
stand regardless.

## S&P track: three proposals → two IEEE S&P papers

| File | What it is |
|---|---|
| `INTEGRATION_PLAN.tex` | **Start here.** The decision, and an element-by-element categorisation of where every part of P1, P2 and P3 goes |
| `PaperI_certified_budget.tex` | **Paper I** (S&P main track) — P1 + P2 merged. Authentication as both a credit (lower γ) and a debit (higher Δ) against one certified budget |
| `PaperII_sok_quantifier_gap.tex` | **Paper II** (S&P SoK track) — P3 broadened from "our certificate as evidence" to a systematisation of certified guarantees by what they quantify over |

The merge rests on one observation: P1 and P2 each attack one factor of the
parent's budget `ρ = Δ · γ · e^{L T_c} ≤ m`, and the same operation —
authentication — moves the two factors in opposite directions. Neither proposal
alone can ask which effect wins; together they answer it with a closed-form
crossover (Paper I, Proposition 1).

P3 does not merge: different contribution type, different audience, no shared
measurement. It becomes an SoK instead — but only after broadening, because as
written it maps one certificate rather than systematising a literature.

## Original proposals (kept unchanged, as the record)

| File | Proposal |
|---|---|
| `P1_certified_pnt_substitution.tex` | γ is a property of the navigation source, not the attack |
| `P2_security_tax_pqc.tex` | Δ is agnostic about *why* the input is stale |
| `P3_certificate_as_compliance.tex` | the certified window recast as a SORA / ED-324 evidence artifact |

**One stale number in P1:** it quotes γ = 1.195 m/s (receiver) and 1.365 m/s
(EKF). Those predate the interface-characterisation campaign; the certificate
now uses the campaign supremum **γ = 1.625 m/s**. Paper I uses the current
value. P1 is left as written because it is the historical record.

## Shared files

| File | Purpose |
|---|---|
| `proposal_preamble.tex` | shared preamble, `\input` by every document here |
| `proposals.bib` | shared bibliography, self-contained |

## Overleaf

Upload the folder (or its zip) via **New Project → Upload Project**, then set
the document you want under **Menu → Main document**. Compiler is pdfLaTeX;
Overleaf runs BibTeX itself. Every `.tex` here compiles independently.

```bash
pdflatex PaperI_certified_budget && bibtex PaperI_certified_budget \
  && pdflatex PaperI_certified_budget && pdflatex PaperI_certified_budget
```

## Verified state

All six documents build with **0 errors and 0 undefined citations**:
Integration Plan 5 pp, Paper I 7 pp, Paper II 5 pp; P1 and P2 4 pp, P3 3 pp.
The three new documents also have 0 overfull boxes. P1 has one pre-existing
13.7 pt overrun (an unbreakable `\code{}` token in its schema paragraph), left
alone because P1 is kept unchanged as the record.

## Numbers in Paper I, and how far to trust them

Paper I §4 contains two tables. They are not equally solid:

- **The authentication-budget table is derived** from constants the parent
  paper measured (H = 2, θ = 0.25 s, L = 1.181, T_c = 1 s, γ = 1.625 m/s). It
  reproduces the parent's γ_req = 6.14 m/s, which is the check that it uses the
  same numbers.
- **The CAN-occupancy table is a back-of-envelope estimate.** Signature sizes
  are from the FIPS standards, but the frame duration (~130 bits at 1 Mbit/s)
  and per-frame payload (7 bytes) are assumptions. It is labelled `[ESTIMATE]`
  in the document and must only ever appear in the paper as the prediction a
  measurement tested.

## A note on the bibliography

`proposals.bib` follows the parent project's rule: where a field could not be
confirmed against the publisher of record, it is **omitted rather than
asserted**. The six entries added for Papers I and II (TESLA, Reluplex,
β-CROWN, ACAS Xu, *Toward Verified AI*, and the anonymised parent) therefore
carry authors, title, venue and year but no pages or DOIs. Several older entries
carry `note = {author list to be confirmed}`. Those placeholders must be
resolved before either paper is submitted.

Paper II's corpus **has not been collected.** The bibliography holds only its
seed systems; the systematic search is the first task, and the SoK's claims
depend on it.

`pq_swarm_kyber` (MDPI) is no longer cited by either new paper: it concerns key
agreement rather than per-message authentication, so it is not load-bearing,
and the supervisor's guidance is to avoid MDPI unless core.
