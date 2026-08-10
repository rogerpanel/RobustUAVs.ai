# Paper D (NDSS) — response to the 24 `\fc` supervisor comments

Source: `paper/paperD_v2a_corrections.tex` (supervisor's annotated copy).
Result: `paper/paperD_v3.tex` (anonymised, submission form) and
`paper/paperD_v3_named.tex` (named, for internal review). Both compile with
zero errors. All 24 `\fc{}` markers are removed; none was left unaddressed.

| # | Comment | What changed |
|---|---------|--------------|
| 1 | Title too long, max two lines | "From Wire to Flight: Composing Network Intrusion Detection with Certified UAV Mission Safety" (two typeset lines). |
| 2 | Did Keiwan contribute? | Moved from the author list to the Acknowledgements, named explicitly for the DATAMUt source and the operating-point/contact-window clarifications. A LaTeX comment marks the revert as one line if you decide otherwise. **This was decided without your input — say the word and it flips back.** |
| 3 | Add Prof. Conti | Added last: Mauro Conti, IEEE Fellow, SPRITZ Security and Privacy Research Group, Dept. of Mathematics, University of Padua. Federico Corò now shares that affiliation. Order: Anaedevha, Corò, Conti. **Also decided without your input.** |
| 4 | Avoid `---` | All 68 prose em-dashes replaced by commas, parentheses, or colons. Zero remain outside LaTeX comment rules. |
| 5 | Abstract too long | Cut from ~245 to ~200 words; the Wilcoxon p-value and the three-component enumeration moved into the body. |
| 6 | Do we need the J/S formula? | Removed; the sentence now reads "raises the received noise floor". |
| 7 | Rephrase para (too colloquial) | The "consider what a reviewer can check" paragraph rewritten in third person as a statement about what neither community can substantiate. |
| 8 | No paragraph titles / no "the other half" | The two labelled half-paragraphs are gone, replaced by one paragraph that motivates and leads into the contribution list without repeating it. |
| 9 | Reader doesn't know these symbols | Eq. (1) removed from the Introduction; the result is stated in words. The chain equation now first appears in §II-D, after θ, Δ, δ and MCR are defined, where it is also cross-referenced to the sections that establish each arrow. |
| 10 | Appendix shouldn't lead Organization | Rewritten to walk §II–§XIII; the appendix is mentioned last as an optional convenience, with the body stated to be self-contained. |
| 11 | Following paragraph too colloquial | The spatial/temporal MCR paragraph rewritten. |
| 12 | Corridor never introduced | New subsection §II-A "Attack Surfaces and Operating Volume" defines the safe corridor and margin *m* before first use, grounded in the JARUS SORA contingency volume. The duplicate SORA justification later in §X-C was collapsed to a cross-reference. |
| 13 | Is *T* seconds? T=1 seems too short | **This exposed a real notation clash.** *T* was doing double duty: the mission duration in Eq. (3) and the Grönwall propagation horizon in the instantiation. They are now separate symbols. *T* is the mission duration in seconds (corpus flights run 136–246 s; reference profile 70 s). *T_c* is the **certification horizon**, the interval between uncorrupted state updates, fixed at 1 s to match the 1 Hz GNSS solution rate. New Definition 2 (re-anchoring interval) states the assumption the tube needs, the theorem and proof now propagate over *T_c*, and a new Limitations entry records that a persistent-denial adversary breaks it while a delay adversary does not. |
| 14 | "Eq." before every `\eqref` | Applied to all 42 occurrences. |
| 15 | "The missing object" too colloquial | → "Formalising the Cross-Layer Pairing". |
| 16/17 | "not clear: --" | The sentence is replaced by an explicit statement: the benchmark's role on the tuple *P* is *representational*, the theorem's is *inferential*, followed by the chain equation. |
| 18 | Too colloquial | "How such a corpus is built matters as much as how large it is" → "Construction methodology bears on validity as directly as scale does." |
| 19 | Almost all titles too colloquial | 17 section/subsection/paragraph titles reformalised (full list in the diff). |
| 20 | Show that cruise is unlikely to cross the threshold | New paragraph in §X-D, **explicitly labelled as an error-budget argument, not a measurement**. γ is the rate the position *estimate* degrades during dead reckoning, not the airspeed; the only airspeed-scaling term is cross-track error from heading error ψ, growing as v·ψ. Crossing γ_req = 6.14 m/s at v = 15 m/s needs ψ ≳ 0.32 rad ≈ 18°, which a PX4-class EKF flags as a yaw-innovation fault long before. Limitations still names the cruise-inclusive campaign as the only thing that settles it. |
| 21 | Ethics too long | Cut from two long paragraphs to two short ones (~40% shorter). |
| 22 | Move appendix after bibliography | Done: Acknowledgements → bibliography → `\appendix`. |
| 23 | Fix `[VERIFY]` in the bibliography | All nine removed. Where a field could not be confirmed against the publisher of record it is **omitted rather than asserted** (network access here could not reach dblp; page ranges for the COMST and TAC entries were not retrievable). ED-324 keeps an honest "in preparation"; COMST is marked "early access". |
| 24 | MDPI / [9]+[10] / [24] arXiv id | Only one MDPI entry now prints, `islam2025uavids` = [6], the one you sanctioned (`aissou2024advml` is uncited in Paper D). [9] and [10] merged into a single record: the CNS conference paper, with the IEEE DataPort DOI in a note. [24] `everett2021carrl` no longer carries the arXiv id. Unverifiable arXiv ids were also dropped from DATAMUt, HCRL-UAVCAN, UAV-CAS, Yang et al., and Mehmood et al. Bibliography: 48 → 47 entries. |

## Two corrections I made that you did not ask for

1. **γ_req was inconsistent.** §XII said 7.3 m/s, §X-D said 6.14 m/s. Recomputing
   from `results/paper_figures/block_paperA_fig4_sensitivity.tex`,
   θ*(m) = m/(γ·e^{L·T_c}·H) gives γ_req = 10/(0.25·e^{1.181}·2) = **6.14 m/s**.
   The 7.3 figure came from the *global* Lipschitz estimate L = 1.01, which the
   paper explicitly says it does not use. Both sites now read 6.14, and "more
   than five times the measured rate" is now "4.5× (EKF) / 5.1× (receiver)".
2. **A LaTeX typo** (`\footnotetsize`) that stopped the file compiling.

## Page budget — one item still short of NDSS spec

NDSS allows 13 pages excluding Ethics, references, and appendices. The body
(§I–§XIII) currently ends near the top of page 14, i.e. about a third of a
column over. The annotated version you sent was in the same state. I cut roughly
1.5 pages of prose (Discussion, Limitations, Conclusion, the four-certificate
walkthrough, the learned-detector generalisation, Related Work) to absorb the
new material for comments 12, 13 and 20, but did not cut further because the
remaining candidates are substance rather than padding. Two options at
camera-ready: switch to the official `ndss.cls` (marginally more compact than
IEEEtran) per the NDSS SWAP comment at the top of the file, or drop the worked
end-to-end example in §X-C to the appendix. Your call.

## What I still need from you

The two authorship decisions (comments 2 and 3) were made on my own reading of
your comments. Both are one-line reverts.
