# USENIX Security '27 — CFP requirements (extracted)

- **Source fetched:** https://www.usenix.org/conference/usenixsecurity27/call-for-papers (HTTP 200, fetched 2026-11-19)
- **Template downloaded:** https://www.usenix.org/sites/default/files/usenixsecurity2027_latex_templates.zip (HTTP 200, 6616 bytes, sha256 `7dc55fc858881a7d64a06d7c8277be25c6dcc6070b17f74ef0d8a6bed70aa38e`) — the link given in the CFP's "Formatting Requirements & Page Limit" section.
- Also fetched (for cross-check only): https://www.usenix.org/conferences/author-resources/paper-templates (HTTP 200). It links only the generic `usenix2019_v3.2.tex` / `usenix2019_v3.sty`; the conference-specific 2027 zip from the CFP was used instead.
- The CFP page also links a PDF version (`/sites/default/files/sec27_cfp_110926.pdf`); it was **not** fetched. All quotes below are from the HTML page.

Quotes are verbatim from the CFP unless marked *(note)*.

---

## 1. Submission cycles and dates (all AoE)

> "Important Information (AoE)"

| Milestone | Cycle 1 | Cycle 2 |
|---|---|---|
| Mandatory registration ("fixed title, fixed authors, tentative non-blank abstract, and fixed topics") | Tuesday, August 18, 2026 | **Tuesday, January 19, 2027** |
| Paper submissions due | Tuesday, August 25, 2026 | **Tuesday, January 26, 2027** |
| Submission artifacts due | Friday, August 28, 2026 | **Friday, January 29, 2027** |
| Early reject notification | Tuesday, October 6, 2026 | Tuesday, March 9, 2027 |
| Rebuttal period | Thursday, November 5–12, 2026 | Thursday, April 8–15, 2027 |
| Notification to authors | Thursday, December 3, 2026 | Thursday, May 6, 2027 |
| Shepherded approval due | Tuesday, December 15, 2026 | Tuesday, May 18, 2027 |
| Final papers due | Thursday, January 14, 2027 | Thursday, June 3, 2027 |
| Embargo request deadline | Thursday, February 11, 2027 | Thursday, July 1, 2027 |

Symposium: "The 36th USENIX Security Symposium will be held on August 11–13, 2027, in Denver, CO, USA."

*(note)* As of the fetch date Cycle 1 has passed; the **January 2027 deadline is Cycle 2** (registration Jan 19, paper Jan 26, artifacts Jan 29). The page lists only "USENIX Security '27 Cycle 1 Submission Site [https://sec27cycle1.usenix.hotcrp.com/]"; no Cycle 2 HotCRP link was present.

Registration rule:
> "All papers intended to be submitted must be registered with the fixed title, the fixed full list of authors including their ORCIDs, a tentative abstract, and fixed topics one week before the submission deadline. Any papers not registered at that time or those missing requirements will not be considered for review."

> "By submission time, all authors are required to (1) set up or update their HotCRP profile to include their ORCID and (2) confirm the submission terms within HotCRP. [...] papers for which at least one author fails to comply with the requirements will not be considered for review."

Submission limit:
> "Each author can submit at most seven papers per cycle to USENIX Security 2027."

## 2. Page limit, bibliography, appendices

> "Paper submissions can include up to 13 pages of body text"

> "The main body of the submission must not exceed 13 pages excluding References and any appendices."

> "The initial submission can contain unlimited appendices and references"

> "At submission time, there is no limit on the length of the bibliography and optional appendices, but reviewers are not required to read any optional appendices. Papers must be self-contained without the optional appendices."

Camera-ready:
> "Once accepted, papers must be reformatted to fit in 20 pages, including any "Ethical Considerations" or "Open Science" appendices, the bibliography, and any additional optional appendices."

*(note)* So at submission: 13 pages body; references and appendices excluded and unlimited; reviewers need not read *optional* appendices. Camera-ready: 20 pages total, everything included.

## 3. Formatting and desk-reject conditions

> "Submissions must be in PDF format, typeset using the USENIX Security template and style files: on U.S. letter-sized pages in two-column format in 10-point Times Roman type on 12-point leading (single-spaced), in a text block 7" x 9" deep."

> "Authors must meet page limits through the modification of content alone. Any attempts to remove whitespace (e.g., negative vspaces, savetrees, titlesec, removing author blocks, etc.) or change the formatting defaults (e.g., fonts) are forbidden and may result in rejection."

> "Submissions must be in standard PDF format. Please ensure your submission is intelligible when printed/rendered in grayscale."

Desk rejection:
> "The chairs reserve the right to desk-reject papers for any reason they deem necessary, including, but not limited to: severe editorial issues, scope/fit issues, insufficient quality, fabricated references, failure to adhere to the CFP, etc."

> "Papers without a clear application to security or privacy of computing systems will be considered out of scope and may be rejected without full review at the discretion of the chairs."

> "Papers that are not properly anonymized may be rejected without review or during the review process."

ML papers: "Read the Submitting ML Work to USENIX Security [https://www.usenix.org/conference/usenixsecurity27/submitting-ml-work-usenix-security] page to prevent desk rejection." *(note: that page was not fetched.)*

SoK papers: "These submissions must have their title prefixed with “SoK: ”."

Template summary *(note)*: files `usenix.sty` + `usenixsecurity2027.tex`; the template's bibliography is inlined via `filecontents` (`\jobname.bib`) and uses `\bibliographystyle{plainurl}`.

## 4. Required / recommended sections

Summary box on the CFP:
> "Papers must include an “Open Science” Appendix on submission"
> "An Appendix discussing Ethics is recommended"

"Summary of main changes from previous edition":
> "Ethics appendix is no longer mandatory (but is strongly encouraged)."

### Ethical Considerations (recommended, appendix)
> "Authors are strongly encouraged to include a well-labeled section in the Appendix (e.g., "Ethics", "Ethical Considerations", etc.) that discusses the ethical considerations and implications of their work. We may work with authors throughout the review process, and authors who do not include an adequate discussion of ethics may be asked to provide additional information."

> "Reviewers will be asked to evaluate the ethics of both the research and the implications of all submissions. At the co-chairs’ and PC’s discretion, papers may be rejected on ethical grounds."

### Open Science (mandatory, appendix)
> "all USENIX Security '27 submissions must include an Open Science Appendix describing the artifacts and how to access them or an explicit description of why artifacts cannot be provided."

### Placement, page counting, length
- **Placement:** both are appendices. In the official template they come *after* Acknowledgments and `\appendix`, as `\section*{Ethical Considerations}` then `\section*{Open Science}`, and **before** `\bibliography` (i.e. before the references).
- **Page limit at submission:** appendices are excluded from the 13-page body limit (CFP: "excluding References and any appendices"). At camera-ready they count toward the 20 pages.
- **Length:** the CFP itself gives no length limit for these sections. The official template text says:
  - Ethics: "We strongly encourage that you use this appendix, up to one page, to explain the ethical considerations of your work."
  - Open Science: "Within up to one page, this appendix must list all artifacts necessary to evaluate the contribution of the paper and make clear how the review committees can access each artifact."
- *(note)* The CFP says reviewers need not read "optional appendices"; the Open Science appendix is mandatory, so it is not optional in that sense.

## 5. Anonymisation

> "Papers must be submitted for anonymous review: no author names or affiliations may appear on the title page and authors must not reveal their identity in the text."

> "When referring to your previous work, do so in the third person, as though it were written by someone else."

> "Only blind the reference itself in the (unusual) case that a third-person reference is infeasible."

> "For provided artifacts, neither the link in the paper nor the website itself may suggest the authors' identities nor track reviewers accessing them."

Preprints / talks / websites:
> "While submitted papers must be anonymous, authors may choose to give talks about their work, post a preprint of the paper online, disclose security vulnerabilities to vendors or the public, etc., during the review process. While the PC will not go out of its way to attempt to deanonymize papers, authors should take care to avoid timing of publicity or public announcements of work, and avoid other behaviors that appear to intentionally aim to inform reviewers of their identity."

Template (Acknowledgments): "Do not include any acknowledgements in your submission which may deanonymize you (e.g., because of specific affiliations or grants you acknowledge)"

Own concurrent work:
> "Citations to simultaneously submitted papers should be anonymized; non-anonymous versions of these citations must, however, be emailed to the program co-chairs at sec27chairs@usenix.org."

## 6. Generative AI policy and disclosure

> "The use of AI tools to assist in preparing submissions is permitted, and human authors are ultimately responsible for all submitted content and results, ensuring their accuracy, originality, and integrity."

> "Upon submitting to USENIX Security '27, authors acknowledge that they have reviewed all content that was generated by AI as if they had written it themselves, including text, code, experimental data, and references."

> "Any violation to this policy which results in fabrications or hallucinations, including non-existing references or incorrect authors, invented claims, and falsified results is considered academic misconduct and might lead to the paper being desk rejected or other sanctions."

> "Authors are encouraged to evaluate their submissions using the same open-source tools that we will use [https://github.com/gianlucasb/hallucinator]."

*(note)* The CFP states no explicit in-paper AI-disclosure section requirement; the acknowledgement is implicit upon submission.

## 7. Artifacts / open science at submission time

> "To preserve double-blind review, artifacts must be shared through anonymous links with no tracking mechanisms. Authors are solely responsible for ensuring no identifying information is exposed (e.g., usernames, organization names, commit history). For source code repositories, we recommend https://anonymous.4open.science, using the conference ID "SEC27" to apply the current cycle’s expiration deadline. Check any expiration times carefully: files must remain accessible for the entire evaluation period, until the shepherd approval deadline."

> "Anonymous URLs should be included in the paper's Open Science Appendix. After the submission deadline, URLs are final, but a 3-day grace period is provided to anonymize and upload artifacts. During this period, the paper itself cannot be modified. Once the grace period ends, artifacts are considered frozen and must not be updated."

> "We expect all submitted artifacts to be available publicly on paper acceptance [...] if at all possible, submit the artifacts and note in the Open Science Appendix those which will not be made public. If submission of artifacts is not possible (e.g., due to NDA or legal constraints), the Open Science Appendix must explain such omissions explicitly."

> "For all submitted artifacts that can be made public, paper acceptance is conditional on their public availability. Camera-ready paper versions will include an Open Science Appendix that includes a non-anonymous, stable artifact link. Artifact availability will be re-verified by the Artifact Evaluation Committee."

> "Authors of accepted papers are additionally encouraged to optionally register their artifacts to be checked for functionality and reproducibility by the Artifact Evaluation Committee."

## 8. Resubmission and concurrent submission

> "Papers rejected from either cycle of USENIX Security ‘26 may be submitted. Papers rejected from the first cycle of USENIX Security '27 may not be submitted to the second cycle of USENIX Security '27."

> "Simultaneous submission of the same work to multiple venues with archived proceedings, submission of previously published work, and plagiarism constitute dishonesty or fraud. This includes cases in which preliminary reviews from another venue indicate likely rejection but the paper is still considered under submission to the venue. [...] See the USENIX Conference Submissions Policy [https://www.usenix.org/conferences/author-resources/submissions-policy] for details."

> "All submitted papers are considered to be under review for USENIX Security '27 until authors are notified of a decision by the program committee or the program co-chairs approve a request for withdrawal."

> "Authors must relate their submission to all related work they are aware of in their paper, including their own work that is currently under submission (either at USENIX Security or another conference) or have already been accepted (but not yet published). [...] Failure to point out and explain overlap with published, accepted, or simultaneously submitted papers will be grounds for rejection."

*(note)* The CFP has no explicit rule on papers rejected at *other* venues (beyond USENIX Sec '26/'27); such papers are allowed as long as they are no longer under review elsewhere.

---

## Template files placed in repo

`paperIV/manuscript_usenix/template/` — copied unmodified from the zip above:

| File | sha256 |
|---|---|
| `usenix.sty` | `2278c83173e084a00fcf76d3227acb971f5137ecea993a5b4e13a9b2bd67b45e` |
| `usenixsecurity2027.tex` | `e0617d4e1d3d2b9fc96747d8ced84cd0e3f46182843e4b7c55ace2a5b97bf1e5` |

The zip contained only these two files; there is **no separate example `.bib`** — the example bibliography is embedded in `usenixsecurity2027.tex` via a `filecontents` environment.
