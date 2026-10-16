#!/usr/bin/env python3
"""Build the Overleaf project and the anonymised reviewer artifact of a paper.

    python3 tools/package_papers.py --paper III            # from the working tree
    python3 tools/package_papers.py --paper II --ref origin/paperII/full-study

Per paper it writes, under dist/ (gitignored):

  paper<X>_overleaf.zip   flat manuscript project (main.tex, numbers.tex, tables,
                          figure data, refs.bib, README.txt). Verified by a clean
                          latexmk build: 0 errors, 0 undefined references.
  paper<X>_reviewer.zip   the subset of the repository a reviewer needs to
                          regenerate every number of the paper, passed through
                          tools/anonymise.py and re-scanned for identifiers, with
                          a fresh single-commit git history and REVIEWERS.md.

Nothing is rewritten in the original tree. A failed build or a surviving
identifier aborts with a non-zero exit code.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DIST = REPO / "dist"
sys.path.insert(0, str(REPO / "tools"))
import anonymise  # noqa: E402

BUILD_JUNK = {".aux", ".log", ".out", ".bbl", ".blg", ".fls", ".fdb_latexmk", ".synctex.gz",
              ".toc", ".bcf", ".run.xml"}

# What a reviewer needs, per paper (paths relative to the repository root).
SUBSETS = {
    "I": ["paperI", "results", "certificates", "data/fetch_kaggle.py", "requirements.txt", "LICENSE"],
    "II": ["paperII", "LICENSE"],
    "III": ["paperIII", "results", "data/fetch_kaggle.py", "platform/backend/app", "requirements.txt",
            "LICENSE"],
    "IV": ["paperIV", "results/gamma_campaign_samples.csv", "requirements.txt", "LICENSE"],
}
# Large or irrelevant artefacts left out of the reviewer copy.
EXCLUDE = [re.compile(p) for p in (r"\.pt$", r"/logs_r/", r"/server_logs/", r"/__pycache__/",
                                   r"\.pyc$", r"/_smoke", r"/node_modules/", r"\.pdf$",
                                   r"/paperIV/results/logs/")]

REVIEWERS = {
    "I": """# Artifact for Paper I (anonymised)

Regenerate every result, number and figure of the paper:

```bash
pip install -r requirements.txt
bash paperI/experiments/run_all.sh          # writes paperI/results/*.csv and manuscript/numbers.tex
cd paperI/manuscript && latexmk -pdf main.tex
```

E1 and E5 need the public corpus (`python3 data/fetch_kaggle.py --copy`); without it they print
SKIPPED and the literature fallbacks recorded in `paperI/results/provenance_paperI.csv` are used.
Every CSV carries a `provenance` column (measured, derived, assumption).
""",
    "II": """# Artifact for Paper II (anonymised)

```bash
bash paperII/experiments/run_all.sh
bash paperII/manuscript/build.sh
```

`run_all.sh` regenerates every result and number macro from the committed codes (~30 s,
Python 3 with numpy and scipy). The protocol and its six dated amendments are in
`paperII/corpus/SCREENING_PROCEDURE.md`; the codebook in `paperII/corpus/CODEBOOK.md`.

What is where (`paperII/corpus/`):
- `candidates.csv`: the 25,373 deduplicated search records; `search_log.jsonl`: every request.
- `screening/`: both LLM screeners' decisions per batch and the consensus (`decisions.csv`).
- `coding_sample.csv`, `fulltext_status.csv`: the stratified coding sample and retrieval status
  (full texts are third-party documents and are not included; sources are listed).
- `codes_full_C1.csv`, `codes_full_C2.csv`: both coders' codes; `coding/adjudication_log.csv`:
  every adjudicated value with its rationale; `codes_full_final.csv`: the final codes.
- `new_class_map.csv`: how guarantee types outside the pilot classes were grouped.
- `snowball/iter{1,2,3}_*`: the three snowballing iterations (candidates, screening decisions,
  coding samples, both coders' codes, final codes); `results/snowball_iter*_status.csv`: the
  stop-rule check per iteration; `results/field_*.csv`: the expanded-field estimates (amendment 6).

The search and snowballing (`experiments/search_corpus.py`, `run_s1_full.sh`,
`run_snowball.sh`) need internet access and an OpenAlex API key, and are not needed to
reproduce the numbers.
""",
    "III": """# Artifact for Paper III (anonymised)

```bash
pip install numpy scipy networkx torch pandas
cd paperIII/experiments
bash run_all.sh                      # E1-E4, references, aggregation, numbers (~10 min)
bash run_marl.sh                     # E5 headline seeds 0-4 (~1 h on 2 cores)
PAR=4 bash run_r_marl.sh             # R1 fleet size, R2 baselines, R9 sensitivity (~6 h on 4 cores)
python3 r5_consensus.py              # R5 Byzantine agreement
python3 r6_vector.py                 # R6 vector certificates
for d in e5_marl_N24 e5_marl_N48 e5_marl_N96 r9; do python3 e6_aggregate.py --dir $d; done
python3 e6_aggregate.py && python3 export_figdata.py && python3 make_numbers.py
cd ../manuscript && latexmk -pdf main.tex
```

`python3 e1_verify.py` must report 0 disagreements. Experiments that need a flight simulator,
the public flight corpus or embedded boards (R3, R4, R8, E3 on an idle machine) are driven by
`run_server_paperIII.sh`; see `paperIII/RUNBOOK.md` for what was and was not run.
Every result CSV carries a `provenance` column.
""",
    "IV": """# Artifact for Paper IV (anonymised)

```bash
pip install numpy scipy cma optuna
cd paperIV/experiments
python3 run_pilot.py                 # E1-E5 pilot (~27 min on 2 cores; --quick for a smoke run)
python3 e2y_no_anchor_gate.py        # anchor gate removed
python3 r1_attackers.py --par 4      # R1: CMA-ES / TPE / mixed family, scaled E4 (~10 CPU-h)
python3 r1_attackers.py --par 4 --stage optimise_tail && python3 r1_attackers.py --par 4 --stage delta \
  && python3 r1_attackers.py --par 4 --stage e4
python3 r1_diagnose.py               # the scaled-E4 violations, mission by mission
python3 r8_analytic_bound.py --par 4 --anchors 5 --out r8_ta5.csv  # R8 at T_a = 5 s, the rows the paper uses
python3 r8_analytic_bound.py --par 4 # R8 full T_a sweep (5, 10, 20 s, none): ~14 h on 4 cores
python3 r5_measured_gnss.py          # R5: measured GNSS envelope (uses results/gamma_campaign_samples.csv)
python3 e4_revised.py --par 4        # revised instantiation on fresh seeds (~30 min on 4 cores)
python3 make_numbers.py
cd ../manuscript && latexmk -pdf main.tex
```

Seeds are partitioned by role; `paperIV/results/run_meta.json` records every block. Every result CSV
carries a `provenance` column (sim, physics_model, measured). `paperIV/RUNBOOK.md` states what
was and was not run.
""",
}


def tree_from_ref(ref: str, dst: Path) -> Path:
    """Export a git ref into dst (no history) so a branch can be packaged without checkout."""
    dst.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(["git", "archive", ref], cwd=REPO, check=True, capture_output=True)
    subprocess.run(["tar", "-x", "-C", str(dst)], input=p.stdout, check=True)
    return dst


def manuscript_files(ms: Path):
    for p in sorted(ms.rglob("*")):
        if p.is_dir() or p.suffix in BUILD_JUNK or p.name.endswith(".synctex.gz"):
            continue
        if p.name == "main.pdf":
            continue
        yield p


def build_ok(folder: Path) -> tuple[bool, str]:
    r = subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "main.tex"], cwd=folder,
                       capture_output=True, text=True)
    log = (folder / "main.log").read_text(errors="replace") if (folder / "main.log").exists() else ""
    errs = len(re.findall(r"^! ", log, re.M))
    undef = len(re.findall(r"(?:Reference|Citation|control sequence).*undefined|Undefined control", log, re.I))
    pages = ""
    if (folder / "main.pdf").exists():
        info = subprocess.run(["pdfinfo", "main.pdf"], cwd=folder, capture_output=True, text=True).stdout
        pages = next((ln.split()[-1] for ln in info.splitlines() if ln.startswith("Pages")), "")
    ok = r.returncode == 0 and errs == 0 and undef == 0
    return ok, f"latexmk={r.returncode} errors={errs} undefined={undef} pages={pages}"


def zip_dir(folder: Path, out: Path, prefix: str = ""):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                z.write(p, (Path(prefix) / p.relative_to(folder)).as_posix() if prefix
                        else p.relative_to(folder).as_posix())


def overleaf(paper: str, src: Path, work: Path) -> Path:
    ms = src / f"paper{paper}" / "manuscript"
    proj = work / f"paper{paper}_overleaf"
    for p in manuscript_files(ms):
        if p.name == "build.sh":
            continue
        q = proj / p.relative_to(ms)
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, q)
    (proj / "README.txt").write_text(
        "Upload this zip to Overleaf (New Project -> Upload Project). Main file: main.tex;\n"
        "compiler: pdfLaTeX; TeX Live 2022 or newer. numbers.tex, tab_*.tex and figdata/ are\n"
        "machine-generated from the artifact's result files: regenerate them, never edit them.\n")
    for rel, n, line in anonymise.verify(proj):
        # the Overleaf project is the authors' own copy; what reviewers see is the PDF
        print(f"[Paper {paper}] note (source only, checked in the PDF below): {rel}:{n}: {line[:70]}")
    test = work / f"paper{paper}_overleaf_buildtest"
    shutil.copytree(proj, test)
    ok, msg = build_ok(test)
    print(f"[Paper {paper}] Overleaf clean build: {msg}")
    if not ok:
        raise SystemExit(f"Overleaf build failed for Paper {paper}; see {test}/main.log")
    txt = subprocess.run(["pdftotext", "main.pdf", "-"], cwd=test, capture_output=True, text=True).stdout
    meta = subprocess.run(["pdfinfo", "main.pdf"], cwd=test, capture_output=True, text=True).stdout
    rx = re.compile(r"rogerpanel|rogernickanaedevha|Anaedevha|robustuavs|robustidps|10\.34740"
                    r"|MEPhI|Padova|Claude", re.I)
    leaks = rx.findall(txt + meta)
    if leaks:
        raise SystemExit(f"identifier visible in the Paper {paper} PDF: {sorted(set(leaks))}")
    print(f"[Paper {paper}] PDF text and metadata: no identifier")
    if (test / "main.pdf").exists():
        shutil.copy2(test / "main.pdf", DIST / f"paper{paper}_main.pdf")
    out = DIST / f"paper{paper}_overleaf.zip"
    zip_dir(proj, out)
    return out


def reviewer(paper: str, src: Path, work: Path) -> Path:
    anon = work / "anon_full"
    if not anon.exists():
        subprocess.run([sys.executable, str(REPO / "tools" / "anonymise.py"), "--src", str(src),
                        "--out", str(anon)], check=True, capture_output=True)
    out_dir = work / f"paper{paper}_reviewer"
    for rel in SUBSETS[paper]:
        s = anon / rel
        if not s.exists():
            print(f"[Paper {paper}] note: {rel} not in tree, skipped")
            continue
        files = [s] if s.is_file() else [p for p in s.rglob("*") if p.is_file()]
        for p in files:
            r = p.relative_to(anon).as_posix()
            if any(x.search("/" + r) for x in EXCLUDE):
                continue
            q = out_dir / r
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)
    (out_dir / "REVIEWERS.md").write_text(REVIEWERS[paper])
    hits = anonymise.verify(out_dir)
    if hits:
        raise SystemExit(f"identifier survives in reviewer artifact: {hits[:5]}")
    anonymise.init_git(out_dir)
    out = DIST / f"paper{paper}_reviewer.zip"
    zip_dir(out_dir, out, prefix=f"paper{paper}-artifact")
    n = sum(1 for _ in out_dir.rglob("*") if _.is_file())
    print(f"[Paper {paper}] reviewer artifact: {n} files, identifier scan clean")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", choices=("I", "II", "III", "IV"), required=True)
    ap.add_argument("--ref", default=None, help="package a git ref instead of the working tree")
    ap.add_argument("--skip-reviewer", action="store_true")
    a = ap.parse_args()
    DIST.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        src = tree_from_ref(a.ref, work / "src") if a.ref else REPO
        print("wrote", overleaf(a.paper, src, work))
        if not a.skip_reviewer:
            print("wrote", reviewer(a.paper, src, work))
    return 0


if __name__ == "__main__":
    sys.exit(main())
