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
    print("Paper I - UAVAuthentication")
    open_page(pg, "Paper I - UAVAuthentication")
    check("I: page title", wait_text(pg, r"What Authenticity Costs in Metres"))
    check("I: calculator shows the scheme list from dauth.csv", wait_text(pg, r"ed25519\s*·\s*[\d.]+\s*ms"))
    before = body(pg)
    pg.get_by_text(re.compile(r"^ed25519\s*·")).first.click()
    pg.wait_for_timeout(3000)
    after = body(pg)
    check("I: picking a signature scheme recomputes the budget", after != before)
    check("I: results browser lists the paper's CSVs", wait_text(pg, r"dauth\.csv"))
    check("I: the working is shown step by step", wait_text(pg, r"How ρ was computed")
          and wait_text(pg, r"error amplification over the horizon"))
    pg.get_by_text("none — unauthenticated", exact=True).first.click()
    pg.wait_for_timeout(3000)
    check("I: the sweep finds where the verdict flips (θ = 0.9442 s)",
          wait_text(pg, r"verdict changes from certified to not certified at\s*θ \(s\) = 0\.9442"))
    check("I: every scheme on the transport is run through the budget",
          wait_text(pg, r"Every signature scheme on can") and wait_text(pg, r"mldsa44"))
    pg.get_by_text("mav2", exact=True).first.click()
    check("I: tapping a scheme row loads it into the calculator",
          wait_text(pg, r"benefit of authenticating"))
    if shots:
        pg.screenshot(path=os.path.join(shots, "paperI.png"), full_page=True)


def paper2(pg, shots):
    print("Paper II - AirworthinessSoK")
    open_page(pg, "Paper II - AirworthinessSoK")
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
    pg.get_by_text("full study — adjudicated", exact=True).click()
    wait_text(pg, r"287 of 287 guarantees match")
    check("II: one paper is followed through every stage of the study",
          wait_text(pg, r"title and abstract screening") and wait_text(pg, r"coded by two coders independently")
          and wait_text(pg, r"adjudication"))
    check("II: coder agreement recomputed live matches the paper's file (kappa 0.753 ✓)",
          wait_text(pg, r"0\.753 ✓"))
    if shots:
        pg.screenshot(path=os.path.join(shots, "paperII.png"), full_page=True)


def paper3(pg, shots):
    print("Paper III - UAVCertification")
    open_page(pg, "Paper III - UAVCertification")
    check("III: page title", wait_text(pg, r"Certificates as Constraints"))
    pg.get_by_text("certify", exact=True).first.click()
    check("III: certify returns a deficiency and coverage", wait_text(pg, r"deficiency") and wait_text(pg, r"coverage"))
    check("III: MARL tables present", wait_text(pg, r"MARL"))
    check("III: the count profile explains the deficiency", wait_text(pg, r"the count profile \(Lemma 1\)"))
    pg.get_by_label("next", exact=True).first.click()      # the replay's step button, not the ▶ in the sidebar
    check("III: the attack replay steps to b = 1 and removes the smallest-ρ agent",
          wait_text(pg, r"b = 1 of 6") and wait_text(pg, r"agents removed\s*A0"))
    pg.get_by_text("simulate", exact=True).first.click()
    check("III: the Monte Carlo check agrees with the exact lift",
          wait_text(pg, r"exact value inside the simulated interval\?\s*yes"))
    if shots:
        pg.screenshot(path=os.path.join(shots, "paperIII.png"), full_page=True)


def paper4(pg, shots):
    print("Paper IV - UAVPerturbation")
    open_page(pg, "Paper IV - UAVPerturbation")
    check("IV: page title", wait_text(pg, r"Indistinguishable from the Weather"))
    pg.get_by_text("compute floor", exact=True).first.click()
    check("IV: m=10, R1 delta_adv, no tube gives floor_cp 0.541 (paper: r5_floor_sensitivity)",
          wait_text(pg, r"0\.541"))
    before = body(pg)
    pg.get_by_text(re.compile(r"^θ_net 0\.25 s")).first.click()
    pg.get_by_text("compute floor", exact=True).first.click()
    pg.wait_for_timeout(4000)
    check("IV: adding the network tube recomputes the floor", body(pg) != before)
    pg.get_by_text(re.compile(r"^θ_net 0 s")).first.click()
    pg.wait_for_timeout(4000)
    check("IV: the floor's split is shown term by term", wait_text(pg, r"Where the floor comes from")
          and wait_text(pg, r"sum of the three upper tails"))
    check("IV: the coupling comparison is computed", wait_text(pg, r"comonotone \(all move together\)"))
    check("IV: the sweep reproduces the paper's rows",
          wait_text(pg, r"the paper's rows: m = 5 → 0 · m = 10 → 0\.5413"))
    check("IV: the marginal tails are drawn", wait_text(pg, r"The three benign perturbations"))
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
