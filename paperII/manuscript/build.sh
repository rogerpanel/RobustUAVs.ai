#!/usr/bin/env bash
# Build main.pdf (pdfLaTeX + BibTeX). Usage: bash build.sh
set -e
cd "$(dirname "$0")"
rm -f main.aux main.bbl main.blg
pdflatex -interaction=nonstopmode main.tex >/dev/null || true
bibtex main >/dev/null || true
pdflatex -interaction=nonstopmode main.tex >/dev/null || true
pdflatex -interaction=nonstopmode main.tex >/dev/null || true
echo "errors: $(grep -c '^!' main.log)  undefined: $(grep -c 'undefined' main.log)  overfull: $(grep -c Overfull main.log)  pages: $(pdfinfo main.pdf | awk '/Pages/{print $2}')"
