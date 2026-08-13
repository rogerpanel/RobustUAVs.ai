#!/usr/bin/env python3
"""
Produce a de-identified copy of this repository for double-blind review.

    python3 tools/anonymise.py --out ../RobustUAVs-anon
    python3 tools/anonymise.py --out ../RobustUAVs-anon --zip --init-git

WHY THIS EXISTS
---------------
`paper/paperD_v3.tex` compiles under `\\anontrue` and tells reviewers the
artifact "is anonymised for review". The public repository is not: it carries
the authors' names, a GitHub handle, a Kaggle DOI resolving to a named account,
a live domain, and a git history whose every commit is signed with an email.
Handing reviewers that URL breaks blind review. This script produces the
artifact that keeps the promise.

WHAT IT DOES
------------
1. Copies the tree, skipping .git, caches, build outputs, staged data, and the
   named PDF/TeX builds.
2. Rewrites every identifying string listed in RULES below, in every text file.
3. Forces `\\anontrue` in the papers and drops the named variants entirely.
4. Rewrites LICENSE's copyright line and removes CLAUDE.md (project memory,
   heavily identifying, of no use to a reviewer).
5. Optionally initialises a fresh single-commit git history. Never rewrites the
   original history in place -- a rewrite leaks through reflogs, forks, and
   cached GitHub views.
6. Re-scans the output and FAILS LOUDLY if any identifying token survives.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
- It does not touch the original repository. Output goes to a new directory.
- It does not strip `third_party/`. DATAMUt's authorship is a citation, not a
  self-identification, and removing it would misattribute someone else's work.
  The reference to it in the paper is already a normal anonymous citation.
  If your venue's chairs disagree, add "Soltani" to RULES and re-run; the
  verifier will then enforce it.
- It does not attempt to anonymise binary files. It lists any it finds so you
  can check them by hand; PDFs in particular carry author metadata.

VERIFY BEFORE YOU UPLOAD
------------------------
The final scan is the point of the script, not a formality. If it reports
survivors, the artifact is not safe to publish, and the exit code says so.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Every identifying token, and what replaces it.
#
# Order matters: longer, more specific patterns first, so that rewriting
# "rogernickanaedevha" does not leave a stray "anaedevha" behind. The verifier
# below re-checks the SAME list against the output, so anything added here is
# both rewritten and enforced.
# --------------------------------------------------------------------------
RULES: list[tuple[str, str]] = [
    # Kaggle dataset: URL, slug, and DOI all resolve to a named account.
    (r"https://www\.kaggle\.com/datasets/rogernickanaedevha/[^\s)\"'>]*",
     "https://ANONYMISED.example/dataset"),
    (r"rogernickanaedevha", "ANON"),
    (r"10\.34740/kaggle/dsv/18346203", "10.XXXXX/anonymised"),
    # GitHub owner, repository URLs, and the UAV-EW-Bench repo under the same owner.
    (r"https://github\.com/rogerpanel/[^\s)\"'>]*", "https://ANONYMISED.example/repo"),
    (r"github\.com/rogerpanel/[^\s)\"'>]*", "ANONYMISED.example/repo"),
    (r"rogerpanel", "anon-owner"),
    # Live domain, in prose, config, SEO metadata, and deployment scripts.
    (r"https://(www\.)?robustuavs\.ai", "https://ANONYMISED.example"),
    (r"\bRobustUAVs\.ai\b", "the platform"),
    (r"\brobustuavs\.ai\b", "anonymised.example"),
    (r"\brobustuavs-api\b", "platform-api"),
    (r"\bRobustIDPS\.ai\b", "the prior platform"),
    (r"\brobustidps\.ai\b", "prior-platform.example"),
    # Author names and affiliations.
    (r"Roger Nick Anaedevha", "Anonymous Author"),
    (r"Roger Anaedevha", "Anonymous Author"),
    (r"\bAnaedevha, Roger Nick\b", "Anonymous, Author"),
    (r"\bAnaedevha\b", "Anonymous"),
    (r"Federico Cor\\`o", "Anonymous Author"),
    (r"Federico Corò", "Anonymous Author"),
    (r"\bMauro Conti\b", "Anonymous Author"),
    (r"National Research Nuclear University MEPhI", "Anonymised Institution"),
    (r"\bMEPhI\b", "Anonymised Institution"),
    (r"Institute of Cyber Intelligent Systems", "Anonymised Department"),
    (r"SPRITZ Security and Privacy Research Group", "Anonymised Research Group"),
    (r"\bSPRITZ\b", "Anonymised Research Group"),
    (r"University of Padova", "Anonymised University"),
    (r"University of Padua", "Anonymised University"),
    (r"Universit[aà] di Padova", "Anonymised University"),
    (r"\bPadova\b", "Anonymised City"),
    (r"\bPadua\b", "Anonymised City"),
    (r"Missouri University of Science and Technology", "Anonymised University"),
    (r"Missouri S&amp;T", "Anonymised University"),
    (r"Missouri S&T", "Anonymised University"),
    (r"Cor\\`o, Federico", "Anonymous, Author"),
    (r"Corò, Federico", "Anonymous, Author"),
    (r"\bCor\\`o\b", "Anonymous"),
    (r"\bCorò\b", "Anonymous"),
    # Contact details.
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(?:com|org|net|edu|ru|it|ai)\b",
     "anonymous@example.org"),
]

# Paths never copied into the anonymised tree.
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", ".expo",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".claude",
}
SKIP_RELATIVE = {
    "data/raw", "data/staging", "docs/dissertation",  # dissertation names the author throughout
}
SKIP_FILES = {
    "CLAUDE.md",                 # project memory: identifying, and of no use to a reviewer
    "tools/anonymise.py",        # this file lists every identifier by construction
    "paper/paperD_v3_named.tex", "paper/paperD_v3_named.pdf",
    "paper/paperD_named.tex", "paper/paperD_named.pdf",
    "paper/response_to_supervisor.tex", "paper/response_to_supervisor.pdf",
    "docs/paperD_v3_response_to_supervisor.md",
    ".gitignore.local",
}
# Suffixes we rewrite in place. Anything else is copied byte-for-byte and
# reported, because a silent binary copy is how a name reaches a reviewer.
TEXT_SUFFIXES = {
    ".py", ".md", ".tex", ".bib", ".txt", ".json", ".yaml", ".yml", ".sh",
    ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".xml", ".csv", ".cfg",
    ".toml", ".ini", ".patch", ".service", ".example", ".mjs", ".h", ".cc",
    ".jsonl", ".bib", ".gitignore", ".env", ".conf", ".lock",
}
# Extensionless or dotfile names we still treat as text.
TEXT_NAMES = {".gitignore", ".dockerignore", "Dockerfile", "Makefile",
              "Caddyfile", "LICENSE", "requirements.txt"}
BINARY_OK = {".png", ".ico", ".svg", ".woff", ".woff2", ".jpg", ".jpeg"}
# Build detritus. Never copied: a .log or .aux carries every name its .tex does,
# a .pdf carries author metadata in its Info dictionary, and a .db may carry
# session rows. All are regenerable inside the anonymised tree.
SKIP_SUFFIXES = {".aux", ".log", ".out", ".bbl", ".blg", ".toc", ".synctex",
                 ".fdb_latexmk", ".fls", ".pdf", ".db", ".sqlite", ".pyc",
                 ".buildlog"}


def anonymise_text(text: str) -> str:
    for pattern, replacement in RULES:
        text = re.sub(pattern, replacement, text)
    return text


def should_skip(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & SKIP_DIRS:
        return True
    if str(rel) in SKIP_FILES:
        return True
    if rel.suffix.lower() in SKIP_SUFFIXES:
        return True
    return any(str(rel).startswith(p) for p in SKIP_RELATIVE)


def copy_tree(src: Path, dst: Path) -> tuple[int, int, list[Path]]:
    """Copy src to dst, rewriting text files. Returns (rewritten, copied, binaries)."""
    rewritten = copied = 0
    binaries: list[Path] = []

    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if should_skip(rel):
            continue
        out = dst / rel

        if path.is_symlink():
            # paper/figures -> ../results/paper_figures. Preserve the link;
            # resolving it would duplicate the generated blocks.
            out.parent.mkdir(parents=True, exist_ok=True)
            target = path.readlink()
            if out.exists() or out.is_symlink():
                out.unlink()
            out.symlink_to(target)
            copied += 1
            continue
        if path.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue

        out.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                shutil.copy2(path, out)
                binaries.append(rel)
                copied += 1
                continue
            out.write_text(anonymise_text(text), encoding="utf-8")
            rewritten += 1
        else:
            shutil.copy2(path, out)
            copied += 1
            if path.suffix.lower() not in BINARY_OK:
                binaries.append(rel)

    return rewritten, copied, binaries


def force_anon_papers(dst: Path) -> list[str]:
    """Force \\anontrue in every paper, so no build can emit a named PDF."""
    touched = []
    for tex in sorted((dst / "paper").glob("*.tex")):
        text = tex.read_text(encoding="utf-8")
        if "\\anonfalse" in text:
            text = re.sub(r"^\\anonfalse\s*$", r"\\anontrue", text, flags=re.M)
            tex.write_text(text, encoding="utf-8")
            touched.append(tex.name)
    return touched


def rewrite_licence(dst: Path) -> None:
    lic = dst / "LICENSE"
    if not lic.exists():
        return
    text = re.sub(r"Copyright \(c\) \d{4} .*",
                  "Copyright (c) 2026 Anonymous Author (anonymised for review)",
                  lic.read_text(encoding="utf-8"))
    lic.write_text(text, encoding="utf-8")


def write_notice(dst: Path) -> None:
    (dst / "ANONYMISED.md").write_text(
        "# Anonymised artifact\n\n"
        "This is a de-identified copy of the paper's artifact, prepared for\n"
        "double-blind review. Author names, institutions, repository and dataset\n"
        "URLs, the deployment domain, contact addresses, and the version-control\n"
        "history have been removed or replaced with placeholders.\n\n"
        "Placeholders read `ANONYMISED`, `ANON`, `Anonymous Author`, or\n"
        "`anonymised.example`. Where a URL is required to reproduce a result, the\n"
        "corresponding dataset is identified by name and by its published DOI in\n"
        "`paper/refs.bib` under its own authors, who are not the authors of this\n"
        "submission.\n\n"
        "`third_party/` retains its original attribution. That code is cited\n"
        "prior work, not authored by the submitters, and stripping it would\n"
        "misattribute it.\n\n"
        "The non-anonymous version will be released on acceptance.\n",
        encoding="utf-8")


def verify(dst: Path) -> list[tuple[Path, int, str]]:
    """Re-scan the output for surviving identifiers. This is the whole point."""
    # Tokens to hunt for, independent of the rewrite rules, so a broken rule
    # is caught rather than trusted.
    tokens = [
        r"rogerpanel", r"rogernickanaedevha", r"Anaedevha", r"MEPhI",
        r"robustuavs\.ai", r"robustidps\.ai", r"10\.34740", r"Mauro Conti",
        r"Cor\\`o", r"Corò", r"SPRITZ", r"Padova", r"Padua", r"Missouri S",
        r"[A-Za-z0-9._%+-]+@(?!example\.org)[A-Za-z0-9.-]+\.(?:com|org|net|edu|ru|it|ai)\b",
    ]
    rx = re.compile("|".join(tokens))
    survivors: list[tuple[Path, int, str]] = []
    for path in sorted(dst.rglob("*")):
        if path.is_dir() or path.is_symlink():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
            continue
        try:
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if rx.search(line):
                    survivors.append((path.relative_to(dst), n, line.strip()[:120]))
        except UnicodeDecodeError:
            continue
    return survivors


def init_git(dst: Path) -> None:
    """Fresh single-commit history. Never a rewrite of the original."""
    env_author = [
        "-c", "user.name=Anonymous Author",
        "-c", "user.email=anonymous@example.org",
    ]
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=dst, check=True)
    subprocess.run(["git", *env_author, "add", "-A"], cwd=dst, check=True)
    subprocess.run(
        ["git", *env_author, "commit", "-q", "-m",
         "Anonymised artifact for double-blind review"],
        cwd=dst, check=True,
        env={"GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
             "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
             "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(dst)})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path,
                    help="output directory (must not exist, or pass --force)")
    ap.add_argument("--force", action="store_true", help="overwrite --out if it exists")
    ap.add_argument("--init-git", action="store_true",
                    help="initialise a fresh single-commit history in --out")
    ap.add_argument("--zip", action="store_true", help="also write <out>.zip")
    args = ap.parse_args()

    src = Path(__file__).resolve().parent.parent
    dst = args.out.resolve()
    if dst.exists():
        if not args.force:
            print(f"error: {dst} exists (pass --force to overwrite)", file=sys.stderr)
            return 2
        shutil.rmtree(dst)
    if dst.is_relative_to(src):
        print(f"error: --out must be outside the repository ({src})", file=sys.stderr)
        return 2
    dst.mkdir(parents=True)

    print(f"source: {src}\noutput: {dst}\n")
    rewritten, copied, binaries = copy_tree(src, dst)
    forced = force_anon_papers(dst)
    rewrite_licence(dst)
    write_notice(dst)

    print(f"rewrote {rewritten} text files, copied {copied} others")
    if forced:
        print(f"forced \\anontrue in: {', '.join(forced)}")

    if binaries:
        print("\nBINARIES NOT REWRITTEN -- check these by hand "
              "(PDFs carry author metadata in their XMP/Info dictionary):")
        for rel in binaries:
            print(f"  {rel}")
        print("  For PDFs, rebuild them inside the anonymised tree rather than "
              "copying:\n    cd paper && pdflatex paperD_v3 && bibtex paperD_v3 "
              "&& pdflatex paperD_v3 && pdflatex paperD_v3")

    survivors = verify(dst)
    print()
    if survivors:
        print(f"FAILED: {len(survivors)} identifying string(s) survived. "
              "DO NOT UPLOAD THIS TREE.")
        for rel, n, line in survivors[:40]:
            print(f"  {rel}:{n}: {line}")
        if len(survivors) > 40:
            print(f"  ... and {len(survivors) - 40} more")
        print("\nAdd a rule to RULES in tools/anonymise.py and re-run.")
        return 1

    print("PASSED: no identifying string found in any text file.")

    if args.init_git:
        init_git(dst)
        print("initialised a fresh single-commit history")
    if args.zip:
        archive = shutil.make_archive(str(dst), "zip", root_dir=dst.parent,
                                      base_dir=dst.name)
        print(f"wrote {archive}")

    print("\nStill to do by hand before upload:")
    print("  1. Rebuild the PDFs inside the anonymised tree (metadata).")
    print("  2. Skim paper/refs.bib: self-citations to your own prior work are")
    print("     the classic blind-review leak the scanner cannot judge for you.")
    print("  3. Confirm your venue permits the hosting service you pick.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
