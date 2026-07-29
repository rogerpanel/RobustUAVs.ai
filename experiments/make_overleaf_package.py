#!/usr/bin/env python3
"""Build self-contained Overleaf packages for both papers.

The in-repo papers \\input machine-generated figure/table blocks from
results/paper_figures/ via a ../ path that works for the repo build but NOT on
Overleaf (a project cannot reach above its root). This script produces, per
paper, a flat project folder that compiles anywhere:

    overleaf_paperX/
      paperX.tex     <- source with \\input paths rewritten to figures/...
      refs.bib
      figures/       <- every block_*.tex the paper uses (self-contained
                        pgfplots/TikZ fragments; still machine-generated,
                        never hand-edited)
      README.txt     <- upload instructions

and zips each folder as an Overleaf-uploadable project. Re-run after any
`make_paper_figures.py` regeneration so the packages track the data.

Output: dist/overleaf_paperA.zip, dist/overleaf_paperC.zip  (dist/ gitignored)
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAPER = REPO / "paper"
BLOCKS = REPO / "results" / "paper_figures"
DIST = REPO / "dist"

README = """How to compile this paper on Overleaf
=====================================

1. On Overleaf choose  New Project -> Upload Project  and upload this zip
   as-is (do NOT unzip it first; Overleaf unpacks it for you).
2. Overleaf detects {main} as the main document automatically (it holds
   \\documentclass). If asked, select {main}.
3. Set the compiler to pdfLaTeX (Menu -> Compiler) - the default on most
   accounts - and TeX Live 2022 or newer. Press Recompile.
   Overleaf runs bibtex automatically; no extra steps are needed.

What is in this project
-----------------------
{main}      - the full paper source.
refs.bib    - the shared bibliography.
figures/    - every chart, plot, and table body as a separate TikZ/pgfplots
              .tex fragment, loaded by the paper with \\input{{figures/...}}.
              These fragments are machine-generated from the experiment
              result files in the research repository
              (experiments/make_paper_figures.py); regenerate there rather
              than hand-editing, so every plotted number stays traceable to
              the committed campaign data.

Notes
-----
* Everything is vector TikZ/pgfplots - there are no bitmap images, so no
  \\includegraphics files are required and the figures stay crisp at any zoom.
* If you prefer PNG figures instead, render any figure page to PNG and swap
  the corresponding tikzpicture for \\includegraphics; the fragments under
  figures/ remain the source of truth for the data points.
"""


def package(paper: str) -> Path:
    src = PAPER / f"{paper}.tex"
    text = src.read_text()

    out = DIST / f"overleaf_{paper}"
    if out.exists():
        shutil.rmtree(out)
    (out / "figures").mkdir(parents=True)

    # collect the blocks this paper inputs and rewrite the paths
    used = re.findall(r"\\input\{\.\./results/paper_figures/([^}]+)\}", text)
    for name in used:
        shutil.copy2(BLOCKS / name, out / "figures" / name)
    text = text.replace("\\input{../results/paper_figures/",
                        "\\input{figures/")

    (out / f"{paper}.tex").write_text(text)
    shutil.copy2(PAPER / "refs.bib", out / "refs.bib")
    (out / "README.txt").write_text(README.format(main=f"{paper}.tex"))

    # verify the package compiles stand-alone (same toolchain as Overleaf)
    for cmd in (["pdflatex", "-interaction=nonstopmode", f"{paper}.tex"],
                ["bibtex", paper],
                ["pdflatex", "-interaction=nonstopmode", f"{paper}.tex"],
                ["pdflatex", "-interaction=nonstopmode", f"{paper}.tex"]):
        r = subprocess.run(cmd, cwd=out, capture_output=True, text=True)
    log = (out / f"{paper}.log").read_text(errors="ignore")
    n_err = log.count("\n!")
    pages = re.search(rf"Output written on {paper}\.pdf \((\d+) page", log)
    print(f"[overleaf] {paper}: {len(used)} figure blocks, "
          f"errors={n_err}, pages={pages.group(1) if pages else '?'}")
    if n_err or not pages:
        print(log[log.find("\n!"):log.find("\n!") + 500])
        raise SystemExit(f"{paper} package does not compile stand-alone")

    # ship sources only (drop build artifacts from the zip)
    for junk in out.glob(f"{paper}.*"):
        if junk.suffix not in (".tex",):
            junk.unlink()
    for junk in list(out.glob("*.aux")) + list(out.glob("*.bbl")) + \
            list(out.glob("*.blg")) + list(out.glob("*.out")):
        junk.unlink()

    zpath = DIST / f"overleaf_{paper}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(out))
    print(f"[overleaf] -> {zpath}")
    return zpath


def main() -> int:
    DIST.mkdir(exist_ok=True)
    for paper in ("paperA", "paperC"):
        package(paper)
    return 0


if __name__ == "__main__":
    sys.exit(main())
