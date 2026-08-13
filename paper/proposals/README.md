# Research proposals — Overleaf bundle

Three follow-on research proposals from the composition theorem in
`paper/paperD_v3.tex`. Prose source of truth is
`docs/research_roadmap_2027.md`; these are the typeset versions, each written to
grow into its own paper.

## Files

| File | Proposal |
|---|---|
| `P1_certified_pnt_substitution.tex` | γ is a property of the navigation source, not the attack — alternative PNT as a sensor-selection rule |
| `P2_security_tax_pqc.tex` | Δ is agnostic about *why* the input is stale — post-quantum signing latency against the same budget an attacker spends |
| `P3_certificate_as_compliance.tex` | the certified window recast as a SORA / ED-324 evidence artifact |
| `proposal_preamble.tex` | shared preamble, `\input` by all three |
| `proposals.bib` | shared bibliography, self-contained |

## Overleaf

Upload the folder (or its zip) via **New Project → Upload Project**, then
**set the proposal you want as the main document** under Menu → Main document.
Overleaf will otherwise pick one alphabetically, which is fine but may not be
the one you meant. Compiler is pdfLaTeX; Overleaf runs BibTeX itself.

Each `.tex` is independently compilable — they share only the preamble and the
bibliography, and neither is a document. Locally:

```bash
pdflatex P1_certified_pnt_substitution && bibtex P1_certified_pnt_substitution \
  && pdflatex P1_certified_pnt_substitution && pdflatex P1_certified_pnt_substitution
```

`proposal_preamble.tex` uses `mathptmx` rather than `lmodern`, deliberately:
`lmodern` is absent from minimal TeX Live installs and this preamble should
compile anywhere without a package hunt.

## Verified state

All three build with **0 errors and 0 undefined citations** (P1 and P2 four
pages, P3 three).

## A note on the bibliography

`proposals.bib` follows the parent project's rule: where a field could not be
confirmed against the publisher of record, it is **omitted rather than
asserted**. Several entries — the post-quantum drone-network papers, the UTM
survey — therefore carry `note = {author list to be confirmed}` or similar
instead of an invented author list, and trade-press and vendor sources are
`@misc` with an access date rather than dressed up as peer-reviewed work. Those
placeholders must be resolved before any of these proposals becomes a
submission; they are honest gaps, not oversights.

One entry is MDPI (`pq_swarm_kyber`). Per the supervisor's guidance on the
parent manuscript, MDPI sources should be avoided unless core to the argument —
keep it only if the Kyber swarm scheme ends up load-bearing for P2, and drop it
otherwise.
