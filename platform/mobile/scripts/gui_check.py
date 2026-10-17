#!/usr/bin/env python3
"""Click-test the Papers I-IV pages in a real browser (Playwright + Chromium).

    pip install playwright && python -m playwright install chromium     # once, on any machine
    python3 platform/mobile/scripts/gui_check.py --url https://robustuavs.ai [--shots DIR]

For each page it opens the sidebar entry, performs the page's main interaction and checks
that the result the paper's code returns is what the page shows. Any /api/ response >= 500,
any browser console error, or any failed check makes the script exit non-zero.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

from playwright.sync_api import sync_playwright

RESULTS: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  -- ' + detail) if detail else ''}", flush=True)


def body(pg):
    return pg.inner_text("body")


def wait_text(pg, pattern, timeout=60000):
    """Wait until the page text matches a regex; returns the match or None."""
    rx = re.compile(pattern, re.I)
    step = 500
    for _ in range(timeout // step):
        m = rx.search(body(pg))
        if m:
            return m
        pg.wait_for_timeout(step)
    return None


def open_page(pg, nav):
    pg.get_by_text(nav, exact=True).first.click()
    pg.wait_for_timeout(1500)


def paper1(pg, shots):
    print("Paper I · Auth budget")
    open_page(pg, "Paper I · Auth budget")
    check("I: page title", wait_text(pg, r"What Authenticity Costs in Metres"))
    check("I: calculator shows the scheme list from dauth.csv", wait_text(pg, r"ed25519\s*·\s*[\d.]+\s*ms"))
    before = body(pg)
    pg.get_by_text(re.compile(r"^ed25519\s*·")).first.click()
    pg.wait_for_timeout(3000)
    after = body(pg)
    check("I: picking a signature scheme recomputes the budget", after != before)
    check("I: results browser lists the paper's CSVs", wait_text(pg, r"dauth\.csv"))
    if shots:
        pg.screenshot(path=os.path.join(shots, "paperI.png"), full_page=True)


def paper2(pg, shots):
    print("Paper II · Corpus")
    open_page(pg, "Paper II · Corpus")
    check("II: page title", wait_text(pg, r"Quantifier Gap"))
    m = wait_text(pg, r"(\d+) of (\d+) guarantees match")
    check("II: full study is the default table (287 coded papers)", m and m.group(2) == "287",
          m.group(0) if m else "no count line")
    check("II: PRISMA shows the full-study flow", wait_text(pg, r"eligible after full text\s*191"))
    check("II: snowballing iterations listed", wait_text(pg, r"snowballing 3: screened"))
    pg.get_by_text("A", exact=True).first.click()                 # tier = A
    m = wait_text(pg, r"77 of 287 guarantees match")
    check("II: filtering tier A gives the coded count (77)", m)
    pg.get_by_text("clear all filters", exact=True).click()
    wait_text(pg, r"287 of 287 guarantees match")
    pg.get_by_text("pilot — adjudicated", exact=True).click()
    check("II: switching to the pilot table loads 86 rows", wait_text(pg, r"86 of 86 guarantees match"))
    pg.get_by_text("snowballing 2 — adjudicated", exact=True).click()
    check("II: snowballing 2 table loads 100 rows", wait_text(pg, r"100 of 100 guarantees match"))
    if shots:
        pg.screenshot(path=os.path.join(shots, "paperII.png"), full_page=True)


def paper3(pg, shots):
    print("Paper III · Certificates")
    open_page(pg, "Paper III · Certificates")
    check("III: page title", wait_text(pg, r"Certificates as Constraints"))
    pg.get_by_text("certify", exact=True).first.click()
    check("III: certify returns a deficiency and coverage", wait_text(pg, r"deficiency") and wait_text(pg, r"coverage"))
    check("III: MARL tables present", wait_text(pg, r"MARL"))
    if shots:
        pg.screenshot(path=os.path.join(shots, "paperIII.png"), full_page=True)


def paper4(pg, shots):
    print("Paper IV · Budget floor")
    open_page(pg, "Paper IV · Budget floor")
    check("IV: page title", wait_text(pg, r"Indistinguishable from the Weather"))
    pg.get_by_text("compute floor", exact=True).first.click()
    check("IV: m=10, R1 delta_adv, no tube gives floor_cp 0.541 (paper: r5_floor_sensitivity)",
          wait_text(pg, r"0\.541"))
    before = body(pg)
    pg.get_by_text(re.compile(r"^θ_net 0\.25 s")).first.click()
    pg.get_by_text("compute floor", exact=True).first.click()
    pg.wait_for_timeout(4000)
    check("IV: adding the network tube recomputes the floor", body(pg) != before)
    if shots:
        pg.screenshot(path=os.path.join(shots, "paperIV.png"), full_page=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://robustuavs.ai")
    ap.add_argument("--shots", default="")
    ap.add_argument("--chromium", default=os.environ.get("CHROMIUM_PATH", ""))
    a = ap.parse_args()
    if a.shots:
        os.makedirs(a.shots, exist_ok=True)
    api_errors, console_errors = [], []
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": a.chromium} if a.chromium else {}))
        pg = b.new_page(viewport={"width": 1440, "height": 1000})
        pg.on("response", lambda r: api_errors.append(f"{r.status} {r.url}")
              if "/api/" in r.url and r.status >= 500 else None)
        pg.on("console", lambda m: console_errors.append(m.text[:200]) if m.type == "error" else None)
        pg.goto(a.url, wait_until="networkidle")
        pg.wait_for_timeout(1500)
        if pg.get_by_text("I have read and understand", exact=False).count():   # ethics gate
            pg.get_by_text("I have read and understand", exact=False).click()
            pg.get_by_text("I agree to report", exact=False).click()
            pg.get_by_text("I Agree", exact=False).last.click()
            pg.wait_for_timeout(1500)
        for fn in (paper1, paper2, paper3, paper4):
            try:
                fn(pg, a.shots)
            except Exception as e:                       # a missing control is a failed check, not a crash
                check(f"{fn.__name__}: completed", False, f"{type(e).__name__}: {str(e)[:200]}")
        b.close()
    check("no /api/ response >= 500", not api_errors, "; ".join(api_errors[:5]))
    check("no browser console errors", not console_errors, "; ".join(console_errors[:5]))
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
