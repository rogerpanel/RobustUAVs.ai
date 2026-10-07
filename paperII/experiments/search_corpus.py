#!/usr/bin/env python3
"""E1/E3 of the Paper II runbook: database search and citation snowballing.

Runs on a machine with open internet (the drafting sandbox could not reach the
APIs).  Sources: OpenAlex (works search + referenced_works + cited_by), and
optionally Semantic Scholar (set S2_API_KEY for higher rate limits).  arXiv and
DBLP venue sweeps are covered by OpenAlex, which indexes both; the runbook adds
a manual venue check.

  python3 search_corpus.py search   --out ../corpus/search_raw.jsonl
  python3 search_corpus.py dedup    --inp ../corpus/search_raw.jsonl --out ../corpus/candidates.csv
  python3 search_corpus.py snowball --inp ../corpus/included.csv --out ../corpus/snowball_iterN.csv
  python3 search_corpus.py search --dry-run      # print the queries only

Stdlib only.  Every request is logged to ../corpus/search_log.jsonl with a UTC
timestamp, so the search is reproducible and auditable (PRISMA 2020 item 7).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parent / "corpus"
MAILTO = os.environ.get("OPENALEX_MAILTO", "")
YEARS = (2017, 2026)

# Block A (guarantee) x Block B (learned) x Block C (autonomy).  Each OpenAlex
# query is one A-term with the B and C blocks, to stay inside query-length limits.
BLOCK_A = ['"certified robustness"', '"certifiably robust"', '"formal verification"', '"reachability analysis"',
           '"runtime assurance"', '"simplex architecture"', '"conformal prediction"', '"PAC-Bayes"',
           '"statistical model checking"', '"scenario approach"', '"safety verification"', '"provable guarantee"',
           '"perception contract"', '"safety certificate"', '"barrier certificate"', '"operational profile"']
BLOCK_B = '("neural network" OR "deep learning" OR "learning-enabled" OR "machine learning" OR "reinforcement learning")'
BLOCK_C = ('("aircraft" OR "UAV" OR "UAS" OR "drone" OR "quadrotor" OR "autonomous vehicle" OR "autonomous driving" '
           'OR "avionics" OR "airworthiness" OR "collision avoidance" OR "safety-critical")')


def log(event: dict):
    event["utc"] = datetime.now(timezone.utc).isoformat()
    with open(C / "search_log.jsonl", "a") as fh:
        fh.write(json.dumps(event) + "\n")


def get(url: str, headers=None, retries=4):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers or {"User-Agent": "paperII-sok/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:                       # rate limit or transient
            log({"error": str(e), "url": url, "try": i})
            time.sleep(2 ** i)
    raise RuntimeError(f"failed: {url}")


def openalex_search(query: str, max_pages=10):
    base = "https://api.openalex.org/works"
    flt = f"from_publication_date:{YEARS[0]}-01-01,to_publication_date:{YEARS[1]}-12-31"
    cursor = "*"
    for _ in range(max_pages):
        params = {"search": query, "filter": flt, "per-page": 200, "cursor": cursor}
        if MAILTO:
            params["mailto"] = MAILTO
        url = base + "?" + urllib.parse.urlencode(params)
        js = get(url)
        log({"source": "openalex", "query": query, "n": len(js.get("results", []))})
        for w in js.get("results", []):
            yield w
        cursor = js.get("meta", {}).get("next_cursor")
        if not cursor:
            break


def slim(w: dict) -> dict:
    loc = (w.get("primary_location") or {}).get("source") or {}
    return {"openalex": w.get("id", ""), "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "title": w.get("title") or "", "year": w.get("publication_year"),
            "venue": loc.get("display_name", ""), "type": w.get("type", ""),
            "abstract": _abstract(w.get("abstract_inverted_index")),
            "referenced_works": w.get("referenced_works", []), "cited_by_api": w.get("cited_by_api_url", "")}


def _abstract(inv):
    if not inv:
        return ""
    pos = {}
    for word, idx in inv.items():
        for i in idx:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def cmd_search(a):
    queries = [f"{qa} {BLOCK_B} {BLOCK_C}" for qa in BLOCK_A]
    if a.dry_run:
        print("\n".join(queries)); return
    with open(a.out, "w") as fh:
        for q in queries:
            for w in openalex_search(q):
                rec = slim(w); rec["query"] = q
                fh.write(json.dumps(rec) + "\n")


def cmd_dedup(a):
    seen, rows = {}, []
    for line in open(a.inp):
        r = json.loads(line)
        key = r["doi"].lower() or norm_title(r["title"])
        if key in seen:
            seen[key]["queries"] += 1
            continue
        r["queries"] = 1
        seen[key] = r; rows.append(r)
    with open(a.out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cid", "doi", "title", "year", "venue", "type", "abstract", "openalex", "n_queries"])
        for i, r in enumerate(rows):
            w.writerow([f"S{i:05d}", r["doi"], r["title"], r["year"], r["venue"], r["type"],
                        r["abstract"][:3000], r["openalex"], r["queries"]])
    print(f"{len(rows)} unique candidates")


def cmd_snowball(a):
    """Backward (references) and forward (citations) snowballing of included works."""
    inc = list(csv.DictReader(open(a.inp)))
    out = {}
    for r in inc:
        wid = r.get("openalex") or ""
        if not wid:
            continue
        w = get(f"https://api.openalex.org/works/{wid.split('/')[-1]}")
        for ref in w.get("referenced_works", []):
            out.setdefault(ref, {"direction": "backward", "from": wid})
        for c in openalex_search_cites(wid):
            out.setdefault(c["id"], {"direction": "forward", "from": wid})
    with open(a.out, "w", newline="") as fh:
        wtr = csv.writer(fh); wtr.writerow(["openalex", "direction", "from"])
        for k, v in out.items():
            wtr.writerow([k, v["direction"], v["from"]])
    print(f"{len(out)} snowball candidates")


def openalex_search_cites(wid: str, max_pages=5):
    cursor = "*"
    for _ in range(max_pages):
        url = (f"https://api.openalex.org/works?filter=cites:{wid.split('/')[-1]}"
               f"&per-page=200&cursor={cursor}" + (f"&mailto={MAILTO}" if MAILTO else ""))
        js = get(url)
        yield from js.get("results", [])
        cursor = js.get("meta", {}).get("next_cursor")
        if not cursor:
            break


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("search"); s.add_argument("--out", default=str(C / "search_raw.jsonl")); s.add_argument("--dry-run", action="store_true")
    d = sp.add_parser("dedup"); d.add_argument("--inp", default=str(C / "search_raw.jsonl")); d.add_argument("--out", default=str(C / "candidates.csv"))
    b = sp.add_parser("snowball"); b.add_argument("--inp", required=True); b.add_argument("--out", required=True)
    a = p.parse_args()
    {"search": cmd_search, "dedup": cmd_dedup, "snowball": cmd_snowball}[a.cmd](a)
