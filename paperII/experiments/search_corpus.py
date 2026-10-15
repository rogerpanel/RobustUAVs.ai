#!/usr/bin/env python3
"""E1/E3 of the Paper II runbook: database search and citation snowballing.

Runs on a machine with open internet (the drafting sandbox could not reach the
APIs).  Sources: OpenAlex (works search + referenced_works + cited_by), and
optionally Semantic Scholar (set S2_API_KEY for higher rate limits).  arXiv and
DBLP venue sweeps are covered by OpenAlex, which indexes both; the runbook adds
a manual venue check.

  python3 search_corpus.py search   --out ../corpus/search_raw.jsonl
  python3 search_corpus.py dedup    --inp ../corpus/search_raw.jsonl --out ../corpus/candidates.csv
  python3 search_corpus.py snowball [--seeds ../corpus/codes_full_final.csv] [--out ../corpus/snowball/iter1]
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
# OpenAlex meters usage per day (search ~$0.001, list/filter ~$0.0001 per call;
# a free key from openalex.org/settings/api gives $1/day, no key about $0.01).
# Read from the environment or ~/.config/openalex_key -- never from the repository.
API_KEY = os.environ.get("OPENALEX_API_KEY", "")
if not API_KEY:
    _kf = Path.home() / ".config" / "openalex_key"
    if _kf.exists():
        API_KEY = _kf.read_text().strip()
BUDGET_EXIT = 75             # exit code: daily budget exhausted, resume after 00:00 UTC
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

# Revision 1 (F2). The uncapped revision-0 search found 56% of the pilot set.
# Terms were chosen from the misses of the DEVELOPMENT half of the pilot set only
# (odd gid numbers) -- control and cyber-physical phrasings of the same autonomy
# scope, and one guarantee phrase -- and recall is reported on the held-out even
# half, so the revision is not tuned to the set it is judged on.
# "formal analysis" is used ONLY as a title filter in the venue sweeps: as a
# database search term it matched the CRediT contributor role "Formal analysis"
# printed in the full text of most journal articles (>146,000 records on
# 2026-10-14 before it was stopped), so it is not a search term.
BLOCK_A_REV1 = BLOCK_A + ['"formal analysis"']       # title filter (venue sweeps)
BLOCK_C_REV1 = ('("aircraft" OR "UAV" OR "UAS" OR "drone" OR "quadrotor" OR "autonomous vehicle" OR "autonomous driving" '
                'OR "avionics" OR "airworthiness" OR "collision avoidance" OR "safety-critical" '
                'OR "aerospace" OR "autonomous system" OR "control system" OR "controller" OR "closed-loop" '
                'OR "cyber-physical" OR "hybrid system" OR "robot")')


def blocks(rev: int):
    """Database-search blocks. Revision 1 widens block C only (see above)."""
    return (BLOCK_A, BLOCK_C_REV1) if rev >= 1 else (BLOCK_A, BLOCK_C)


def log(event: dict):
    event["utc"] = datetime.now(timezone.utc).isoformat()
    with open(C / "search_log.jsonl", "a") as fh:
        fh.write(json.dumps(event) + "\n")


class BudgetExhausted(Exception):
    """OpenAlex refused with 429 because the daily usage budget is spent."""


def _redact(url: str) -> str:
    return re.sub(r"api_key=[^&]+", "api_key=***", url)


def get(url: str, headers=None, retries=10):
    """GET with retries. Backoff doubles up to 120 s and honours Retry-After.
    A 429 whose X-RateLimit-Remaining-USD is spent, or a 429 that persists through
    every retry, means the daily budget is gone: raise BudgetExhausted so the run
    stops cleanly and resumes after the midnight-UTC reset, instead of burning
    retries (or shrinking pages, which would only spend more calls)."""
    import urllib.error
    if API_KEY and "api_key=" not in url:
        url += ("&" if "?" in url else "?") + "api_key=" + urllib.parse.quote(API_KEY)
    n429 = 0
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers or {"User-Agent": "paperII-sok/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode())
        except Exception as e:                       # rate limit or transient
            wait = min(120, 2 ** i)
            status = getattr(e, "code", None)
            hdr = getattr(e, "headers", None) or {}
            if status == 429:
                n429 += 1
                left = hdr.get("X-RateLimit-Remaining-USD")
                try:
                    spent = left is not None and float(left) <= 0
                except ValueError:
                    spent = False
                if spent:
                    log({"error": str(e), "status": 429, "budget_exhausted": True,
                         "reset": hdr.get("X-RateLimit-Reset"), "url": _redact(url)})
                    raise BudgetExhausted(hdr.get("X-RateLimit-Reset") or "00:00 UTC")
            if status in (429, 503):
                ra = hdr.get("Retry-After")
                if ra and str(ra).isdigit():
                    wait = max(wait, min(600, int(ra)))
            log({"error": str(e), "status": status, "url": _redact(url), "try": i, "wait_s": wait})
            time.sleep(wait)
    if n429 == retries:
        raise BudgetExhausted("persistent 429")
    raise RuntimeError(f"failed: {_redact(url)}")


class Incomplete(Exception):
    """A query or venue could not be paged to the end; rerun with --resume."""


# Only the fields slim() reads: a full OpenAlex work carries authorships,
# concepts and locations that multiply the payload, and very large pages are
# what the API times out on.
SELECT = ("id,doi,title,publication_year,primary_location,type,abstract_inverted_index,"
          "referenced_works,cited_by_api_url")
PAGE_SIZES = (200, 50, 25)      # a page that keeps failing is retried smaller


def fetch_page(base: str, params: dict) -> dict:
    """One cursor page, falling back to smaller pages on persistent failure.
    The cursor marks a position in the result list, so a smaller page resumes
    from the same record; the next cursor continues from wherever it ended."""
    last = None
    for k, size in enumerate(PAGE_SIZES):
        p = dict(params, **{"per-page": size, "select": SELECT})
        if MAILTO:
            p["mailto"] = MAILTO
        try:
            return get(base + "?" + urllib.parse.urlencode(p),
                       retries=5 if k < len(PAGE_SIZES) - 1 else 10)
        except RuntimeError as e:
            last = e
            log({"page_size_fallback": size, "error": str(e)})
    raise last


def openalex_search(query: str, max_pages=0, extra_filter=""):
    """Cursor-page through every result. max_pages=0 means no cap (the
    full-study default); a positive value reproduces a capped pilot run."""
    base = "https://api.openalex.org/works"
    flt = f"from_publication_date:{YEARS[0]}-01-01,to_publication_date:{YEARS[1]}-12-31"
    if extra_filter:
        flt += "," + extra_filter
    cursor = "*"
    page = 0
    while not max_pages or page < max_pages:
        try:
            js = fetch_page(base, {"search": query, "filter": flt, "cursor": cursor})
        except RuntimeError as e:
            raise Incomplete(str(e)) from e
        entry = {"source": "openalex", "query": query, "n": len(js.get("results", []))}
        if page == 0:
            # Total hits before paging, so retrieved can be checked against
            # it. cap = 0 means uncapped; a positive cap truncates any query
            # whose total exceeds it, and PRISMA must then report that.
            entry["total_hits"] = js.get("meta", {}).get("count")
            entry["cap"] = max_pages * 200
        log(entry)
        for w in js.get("results", []):
            yield w
        cursor = js.get("meta", {}).get("next_cursor")
        page += 1
        if not cursor or not js.get("results"):
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


def _read_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    with p.open() as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _done_queries(records):
    """Queries finished in an earlier attempt: a query_done marker, or (for logs
    written before markers existed) as many records as its logged total_hits."""
    ev = _read_jsonl(C / "search_log.jsonl")
    done = {e["query_done"] for e in ev if e.get("query_done") and e.get("complete")}
    total = {}
    for e in ev:
        if e.get("source") == "openalex" and e.get("total_hits") is not None:
            total[e["query"]] = e["total_hits"]
    got = {}
    for r in records:
        got[r["query"]] = got.get(r["query"], 0) + 1
    done |= {q for q, t in total.items() if t and got.get(q, 0) >= t}
    return done


def cmd_search(a):
    ba, bc = blocks(a.revision)
    queries = [f"{qa} {BLOCK_B} {bc}" for qa in ba]
    if a.dry_run:
        print("\n".join(queries)); return
    done = set()
    if a.resume:
        old = _read_jsonl(a.out)
        done = _done_queries(old)
        keep = [r for r in old if r["query"] in done]       # drop partial queries; they are re-paged
        with open(a.out, "w") as fh:
            for r in keep:
                fh.write(json.dumps(r) + "\n")
        n_done = len(done & set(queries))       # the log also holds earlier revisions' queries
        print(f"resume: {n_done} of {len(queries)} queries complete ({len(keep)} records kept)")
    incomplete = []
    with open(a.out, "a" if a.resume else "w") as fh:
        for q in queries:
            if q in done:
                continue
            n = 0
            try:
                for w in openalex_search(q, max_pages=a.max_pages):
                    rec = slim(w); rec["query"] = q
                    fh.write(json.dumps(rec) + "\n"); n += 1
                fh.flush()
                log({"query_done": q, "retrieved": n, "complete": True})
                print(f"done  {n:>6}  {q[:60]}", flush=True)
            except BudgetExhausted as e:
                log({"query_done": q, "retrieved": n, "complete": False, "error": f"budget: {e}"})
                print(f"OpenAlex daily budget exhausted during: {q[:60]} -- resume after 00:00 UTC "
                      f"(`search --resume`)", flush=True)
                sys.exit(BUDGET_EXIT)
            except Incomplete as e:
                log({"query_done": q, "retrieved": n, "complete": False, "error": str(e)})
                print(f"INCOMPLETE after {n} records: {q[:60]}", flush=True)
                incomplete.append(q)
    if incomplete:
        print(f"{len(incomplete)} queries incomplete: rerun `search --resume`", file=sys.stderr)
        sys.exit(3)


TITLE_MIN = 25      # normalised title length below which titles never merge
YEAR_GAP = 2        # a title merge also needs publication years this close


def stable_id(r: dict) -> str:
    """O<number> from the OpenAlex work id: stable across re-runs, and no clash
    with the X/A/S/W prefixes the runbook reserves for database exports."""
    w = (r.get("openalex") or "").rsplit("/", 1)[-1]
    return "O" + w[1:] if w.startswith("W") else ""


def _pref(r: dict):
    """Which copy represents a merged group: a published version over a
    preprint, then a record with a DOI, then an abstract, then the earliest."""
    return (r.get("type") == "preprint", not r.get("doi"), not r.get("abstract"), r.get("_seq", 0))


def dedup_groups(records: list[dict]) -> list[list[dict]]:
    """Group records that share an OpenAlex id or a DOI, or share a normalised title (at least
    TITLE_MIN characters) with publication years within YEAR_GAP. Union-find,
    so a preprint and its venue version merge even when only one has a DOI or
    their DOIs differ."""
    parent = list(range(len(records)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        parent[find(i)] = find(j)

    by_oa, by_doi, by_title = {}, {}, {}
    for i, r in enumerate(records):
        oa = r.get("openalex") or ""
        if oa:                       # the same work returned by several queries
            if oa in by_oa:
                union(i, by_oa[oa])
            else:
                by_oa[oa] = i
        d = (r.get("doi") or "").lower()
        if d:
            if d in by_doi:
                union(i, by_doi[d])
            else:
                by_doi[d] = i
        t = norm_title(r.get("title"))
        if len(t) >= TITLE_MIN:
            by_title.setdefault(t, []).append(i)
    for idx in by_title.values():
        for a_i, i in enumerate(idx):
            for j in idx[:a_i]:
                yi, yj = records[i].get("year"), records[j].get("year")
                if yi is None or yj is None or abs(int(yi) - int(yj)) <= YEAR_GAP:
                    union(i, j)
    groups = {}
    for i in range(len(records)):
        groups.setdefault(find(i), []).append(records[i])
    return list(groups.values())


def cmd_dedup(a):
    import gzip
    records = []
    for inp in a.inp:
        opener = gzip.open if str(inp).endswith(".gz") else open
        for line in opener(inp, "rt"):
            if line.strip():
                r = json.loads(line)
                r["_seq"] = len(records)
                records.append(r)
    groups = dedup_groups(records)
    rows = []
    for g in groups:
        rep_ = min(g, key=_pref)
        others = sorted({x.get("openalex", "") for x in g} - {rep_.get("openalex", "")})
        found = sorted({x.get("found_by", "search") for x in g})
        rows.append((rep_, len(g), others, ";".join(found)))
    rows.sort(key=lambda t: t[0]["_seq"])
    with open(a.out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cid", "doi", "title", "year", "venue", "type", "abstract", "openalex",
                    "n_records", "merged_openalex", "found_by"])
        for r, n, others, found in rows:
            w.writerow([stable_id(r), r["doi"], r["title"], r["year"], r["venue"], r["type"],
                        (r.get("abstract") or "")[:3000], r["openalex"], n, ";".join(others), found])
    print(f"{len(records)} records -> {len(rows)} unique candidates "
          f"({len(records) - len(rows)} duplicates)")


# --------------------------------------------------------------------------
# Venue sweeps (PRISMA "other methods"): the 18 venues of Sec. IV-A, swept
# through OpenAlex. Each venue name resolves to every OpenAlex source whose
# display name contains it (proceedings are often one source per year); the
# resolution is written to venue_sources.csv for audit. Each source's full
# 2017-2026 table of contents is paged, and a paper is kept when its title
# contains a block-A phrase, as the runbook specifies.
# --------------------------------------------------------------------------
VENUES = [
    ("S&P", "Symposium on Security and Privacy"), ("USENIX Sec", "USENIX Security"),
    ("CCS", "Computer and Communications Security"), ("NDSS", "Network and Distributed System Security"),
    ("CAV", "Computer Aided Verification"),
    ("TACAS", "Tools and Algorithms for the Construction and Analysis of Systems"),
    ("HSCC", "Hybrid Systems: Computation and Control"), ("ICCPS", "Conference on Cyber-Physical Systems"),
    ("EMSOFT", "Embedded Software"), ("NFM", "NASA Formal Methods"),
    ("SAFECOMP", "Computer Safety, Reliability, and Security"), ("DSN", "Dependable Systems and Networks"),
    ("NeurIPS", "Neural Information Processing Systems"), ("ICML", "International Conference on Machine Learning"),
    ("ICLR", "International Conference on Learning Representations"), ("CoRL", "Conference on Robot Learning"),
    ("CDC", "Conference on Decision and Control"), ("DASC", "Digital Avionics Systems Conference"),
]
BLOCK_A_PLAIN = [q.strip('"').lower() for q in BLOCK_A]
BLOCK_A_PLAIN_REV1 = [q.strip('"').lower() for q in BLOCK_A_REV1]


def resolve_sources(phrase: str) -> list[dict]:
    out, cursor = [], "*"
    while cursor:
        params = {"search": phrase, "per-page": 200, "cursor": cursor}
        if MAILTO:
            params["mailto"] = MAILTO
        js = get("https://api.openalex.org/sources?" + urllib.parse.urlencode(params))
        for src in js.get("results", []):
            if phrase.lower() in (src.get("display_name") or "").lower():
                out.append({"id": src["id"], "display_name": src.get("display_name", ""),
                            "works_count": src.get("works_count", 0)})
        cursor = js.get("meta", {}).get("next_cursor") if js.get("results") else None
    return out


def title_hit(title: str, rev: int = 0) -> str:
    t = (title or "").lower()
    return next((p for p in (BLOCK_A_PLAIN_REV1 if rev >= 1 else BLOCK_A_PLAIN) if p in t), "")


def cmd_venues(a):
    src_rows, n_toc, n_kept, incomplete = [], 0, 0, []
    done = set()
    if a.resume:
        done = {e["venue"] for e in _read_jsonl(C / "search_log.jsonl")
                if e.get("source") == "openalex_venue" and e.get("complete", True)
                and e.get("revision", 0) == a.revision}
        old = _read_jsonl(a.out)
        keep = [r for r in old if r.get("found_by", "").removeprefix("venue:") in done]
        with open(a.out, "w") as fh:
            for r in keep:
                fh.write(json.dumps(r) + "\n")
        print(f"resume: {len(done)} of {len(VENUES)} venues complete ({len(keep)} records kept)")
    with open(a.out, "a" if a.resume else "w") as fh:
        for short, phrase in VENUES:
            try:
                srcs = resolve_sources(phrase)
            except BudgetExhausted:
                print("OpenAlex daily budget exhausted -- resume after 00:00 UTC (`venues --resume`)", flush=True)
                sys.exit(BUDGET_EXIT)
            except RuntimeError:
                incomplete.append(short); print(f"INCOMPLETE {short} (source lookup)"); continue
            for x in srcs:
                src_rows.append({"venue": short, "phrase": phrase, **x})
            if short in done:
                continue
            ids = [x["id"].rsplit("/", 1)[-1] for x in srcs]
            toc = kept = 0
            buf = []
            try:
                for i in range(0, len(ids), 50):            # OpenAlex OR-filter limit
                    flt = "primary_location.source.id:" + "|".join(ids[i:i + 50])
                    for w in openalex_search_filter(flt):
                        toc += 1
                        hit = title_hit(w.get("title"), a.revision)
                        if hit:
                            rec = slim(w); rec["found_by"] = f"venue:{short}"; rec["query"] = f"venue:{short}|{hit}"
                            buf.append(rec); kept += 1
            except BudgetExhausted:
                print(f"OpenAlex daily budget exhausted during {short} -- resume after 00:00 UTC "
                      f"(`venues --resume`)", flush=True)
                sys.exit(BUDGET_EXIT)
            except RuntimeError as e:
                log({"source": "openalex_venue", "venue": short, "complete": False, "error": str(e),
                     "revision": a.revision})
                print(f"INCOMPLETE {short} after {toc} papers", flush=True)
                incomplete.append(short)
                continue
            for rec in buf:                                # a venue is written only when complete
                fh.write(json.dumps(rec) + "\n")
            fh.flush()
            log({"source": "openalex_venue", "venue": short, "n_sources": len(srcs), "toc": toc, "kept": kept,
                 "complete": True, "revision": a.revision})
            print(f"{short:<11} {len(srcs):>4} sources  {toc:>7} papers 2017-2026  {kept:>5} block-A titles",
                  flush=True)
            n_toc += toc; n_kept += kept
    with open(C / "venue_sources.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["venue", "phrase", "id", "display_name", "works_count"])
        w.writeheader(); w.writerows(src_rows)
    print(f"venue sweep: {n_toc} papers scanned in this attempt, {n_kept} kept; sources -> {C / 'venue_sources.csv'}")
    if incomplete:
        print(f"{len(incomplete)} venues incomplete ({', '.join(incomplete)}): rerun `venues --resume`",
              file=sys.stderr)
        sys.exit(3)



# --------------------------------------------------------------------------
# F1: venue sweeps through DBLP. OpenAlex files LNCS proceedings (CAV, TACAS,
# NFM, SAFECOMP) under the book series and misses others (CDC, CoRL), so the
# OpenAlex sweep found 0-60 papers for those venues over ten years. DBLP keeps
# the authoritative table of contents of every volume. Each 2017-2026 main-
# proceedings volume is paged in full, a paper is kept when its title contains
# a block-A phrase, and kept papers with a DOI are completed from OpenAlex by a
# singleton lookup (free of charge) so abstracts are available for screening.
# --------------------------------------------------------------------------
DBLP_STREAMS = {
    "S&P": "conf/sp", "USENIX Sec": "conf/uss", "CCS": "conf/ccs", "NDSS": "conf/ndss",
    "CAV": "conf/cav", "TACAS": "conf/tacas", "HSCC": "conf/hybrid", "ICCPS": "conf/iccps",
    "EMSOFT": "conf/emsoft", "NFM": "conf/nfm", "SAFECOMP": "conf/safecomp", "DSN": "conf/dsn",
    "NeurIPS": "conf/nips", "ICML": "conf/icml", "ICLR": "conf/iclr", "CoRL": "conf/corl",
    "CDC": "conf/cdc", "DASC": "conf/dasc-avionics",
}


class SourceBlocked(RuntimeError):
    """The source answers with a bot-protection challenge instead of data. We do
    not try to get past such a challenge: the stage is recorded as not executed."""


def dblp_get(url: str, as_json=True, retries=8):
    import urllib.error
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "paperII-sok/1.0 (systematic review)"})
            with urllib.request.urlopen(req, timeout=90) as r:
                status = r.status
                body = r.read().decode("utf-8", "replace")
            time.sleep(1.0)                                   # DBLP asks for about 1 request/s
            if status == 202 or "not a bot" in body[:2000] or "/.within.website/" in body[:4000]:
                raise SourceBlocked(f"bot-protection challenge (HTTP {status}) at {url}")
            return json.loads(body) if as_json else body
        except SourceBlocked:
            raise
        except Exception as e:  # noqa: BLE001
            status = getattr(e, "code", None)
            if status == 404:
                return None
            wait = min(120, 2 ** i)
            hdr = getattr(e, "headers", None) or {}
            ra = hdr.get("Retry-After")
            if ra and str(ra).isdigit():
                wait = max(wait, min(600, int(ra)))
            log({"source": "dblp", "error": str(e), "status": status, "url": url, "try": i, "wait_s": wait})
            time.sleep(wait)
    raise RuntimeError(f"failed: {url}")


def toc_names(html: str, stream: str) -> set[str]:
    """Volume page names (e.g. cav2023-1) linked from a DBLP stream index, whatever
    the link form: https://dblp.org/db/conf/cav/cav2023-1.html, /db/conf/cav/...,
    db/conf/cav/... or a bare href="cav2023-1.html"."""
    name = r"([a-z][a-z0-9-]*?\d{4}(?:-\d+)?)\.html"
    out = set(re.findall(rf"{re.escape(stream)}/{name}", html))
    out |= set(re.findall(rf"href=\"{name}", html))
    return out


def dblp_tocs(stream: str) -> list[str]:
    """Main-proceedings volumes 2017-2026 of a DBLP stream, e.g. conf/cav/cav2023-1."""
    html = dblp_get(f"https://dblp.org/db/{stream}/index.html", as_json=False)
    if not html:
        return []
    out = []
    for n in sorted(toc_names(html, stream)):
        y = int(re.search(r"(\d{4})", n).group(1))
        if YEARS[0] <= y <= YEARS[1]:
            out.append(f"{stream}/{n}")
    if not out:
        # Never record an empty venue as complete: keep a sample of what came back.
        log({"source": "dblp_venue", "stream": stream, "error": "no volume links parsed",
             "html_len": len(html), "sample": re.findall(r'href="[^"]{0,120}"', html)[:40]})
    return out


def cmd_venues_dblp(a):
    rows, kept_total, toc_total, incomplete = [], 0, 0, []
    done = set()
    if a.resume:
        done = {e["venue"] for e in _read_jsonl(C / "search_log.jsonl")
                if e.get("source") == "dblp_venue" and e.get("complete") and e.get("tocs", 0) > 0}
        old = [r for r in _read_jsonl(a.out) if r.get("found_by", "").removeprefix("venue_dblp:") in done]
        with open(a.out, "w") as fh:
            for r in old:
                fh.write(json.dumps(r) + "\n")
        print(f"resume: {len(done)} of {len(DBLP_STREAMS)} venues complete ({len(old)} records kept)")
    try:
        dblp_get("https://dblp.org/search/publ/api?q=test&h=1&format=json")
    except SourceBlocked as e:
        log({"source": "dblp_venue", "blocked": True, "complete": False, "error": str(e)})
        print(f"DBLP venue sweep NOT EXECUTED: {e}. Recorded in search_log.jsonl; "
              "venue coverage rests on the OpenAlex venue sweeps and on snowballing.", flush=True)
        sys.exit(76)
    with open(a.out, "a" if a.resume else "w") as fh:
        for short, stream in DBLP_STREAMS.items():
            if short in done:
                continue
            try:
                tocs = dblp_tocs(stream)
                if not tocs:
                    raise RuntimeError(f"no 2017-2026 volumes parsed from the {stream} index "
                                       f"(see the 'sample' entry in search_log.jsonl)")
                buf, n_toc = [], 0
                for toc in tocs:
                    off, n_vol = 0, 0
                    while True:
                        q = urllib.parse.quote(f"toc:db/{toc}.bht:")
                        js = dblp_get(f"https://dblp.org/search/publ/api?q={q}&h=1000&f={off}&format=json")
                        hits = (((js or {}).get("result") or {}).get("hits") or {})
                        items = hits.get("hit", []) or []
                        for it in items:
                            info = it.get("info", {})
                            if info.get("type", "").startswith("Editorship"):
                                continue
                            n_vol += 1
                            title = re.sub(r"\.$", "", info.get("title", "") or "")
                            hit = title_hit(title, a.revision)
                            if not hit:
                                continue
                            doi = (info.get("doi") or "").lower()
                            rec = {"openalex": "", "doi": doi, "title": title, "year": int(info.get("year") or 0) or None,
                                   "venue": short, "type": info.get("type", ""), "abstract": "",
                                   "referenced_works": [], "cited_by_api": ""}
                            if doi:
                                try:
                                    w = get("https://api.openalex.org/works/doi:" + urllib.parse.quote(doi), retries=3)
                                    rec.update({k: v for k, v in slim(w).items() if v})
                                except (RuntimeError, BudgetExhausted):
                                    pass                  # keep the DBLP record; dedup merges on DOI/title
                            rec["found_by"] = f"venue_dblp:{short}"
                            rec["query"] = f"venue_dblp:{short}|{hit}"
                            buf.append(rec)
                        total = int(hits.get("@total", 0) or 0)
                        off += len(items)
                        if not items or off >= total:
                            break
                    n_toc += n_vol
                    rows.append({"venue": short, "toc": toc, "papers": n_vol})
            except RuntimeError as e:
                log({"source": "dblp_venue", "venue": short, "complete": False, "error": str(e)})
                print(f"INCOMPLETE {short}", flush=True)
                incomplete.append(short)
                continue
            for rec in buf:
                fh.write(json.dumps(rec) + "\n")
            fh.flush()
            log({"source": "dblp_venue", "venue": short, "tocs": len(tocs), "toc": n_toc, "kept": len(buf),
                 "complete": True})
            print(f"{short:<11} {len(tocs):>3} volumes {n_toc:>7} papers 2017-2026 {len(buf):>5} block-A titles",
                  flush=True)
            toc_total += n_toc; kept_total += len(buf)
    p = C / "venue_dblp_sources.csv"
    old = list(csv.DictReader(p.open())) if (a.resume and p.exists()) else []
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["venue", "toc", "papers"])
        w.writeheader(); w.writerows([r for r in old if r["venue"] in done] + rows)
    print(f"DBLP venue sweep: {toc_total} papers scanned in this attempt, {kept_total} kept")
    if incomplete:
        sys.exit(3)

def openalex_search_filter(flt: str):
    """Page every work matching a filter (no search term), 2017-2026, uncapped."""
    base = "https://api.openalex.org/works"
    full = f"from_publication_date:{YEARS[0]}-01-01,to_publication_date:{YEARS[1]}-12-31," + flt
    cursor = "*"
    while cursor:
        js = fetch_page(base, {"filter": full, "cursor": cursor})
        yield from js.get("results", [])
        cursor = js.get("meta", {}).get("next_cursor") if js.get("results") else None


def cmd_snowball(a):
    """Backward and forward snowballing (Wohlin 2014) from a seed set; resumable.

    Seeds: rows of --seeds with eligible == 1 (default corpus/codes_full_final.csv,
    the full-text-eligible coded sample), resolved to OpenAlex ids through
    candidates.csv or --pool files. Backward: each seed's referenced_works,
    fetched in batches of 50 and kept when published 2017-2026. Forward: every
    2017-2026 work that cites the seed. A work is new unless its OpenAlex id,
    DOI or normalised title is already among the candidates or an earlier
    iteration (--known). Each seed's records are appended to the raw file
    followed by a seed_done marker, so a rerun with --resume skips finished seeds.

    Out: <out>_raw.jsonl        slim records + direction, seed (one line per hit)
         <out>_candidates.csv   candidates.csv columns + direction, seeds (new works only)
    """
    csv.field_size_limit(10 ** 9)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    cand = list(csv.DictReader(open(C / "candidates.csv")))
    for k in a.known:
        cand += list(csv.DictReader(open(k)))
    known_ids, known_doi, known_title = set(), set(), set()
    oa_of = {}
    for r in cand:
        oa_of[r["cid"]] = r.get("openalex", "")
        for w in [r.get("openalex", "")] + (r.get("merged_openalex") or "").split(";"):
            if w:
                known_ids.add(w.rsplit("/", 1)[-1])
        if r.get("doi"):
            known_doi.add(r["doi"].lower())
        if len(norm_title(r.get("title"))) >= 30:
            known_title.add(norm_title(r["title"]))
    seeds = [r["cid"] for r in csv.DictReader(open(a.seeds)) if r.get("eligible", "1") == "1"]
    raw = Path(a.out + "_raw.jsonl")
    done = {e["seed_done"] for e in _read_jsonl(raw) if e.get("seed_done")} if a.resume else set()
    if not a.resume and raw.exists():
        sys.exit(f"{raw} exists; pass --resume to continue it")
    print(f"{len(seeds)} seeds, {len(done)} already done; {len(known_ids)} known OpenAlex ids", flush=True)

    def fetch_ids(ids):
        for i in range(0, len(ids), 50):
            flt = "ids.openalex:" + "|".join(ids[i:i + 50])
            yield from openalex_search_filter(flt)

    with raw.open("a") as fh:
        for k, cid in enumerate(seeds, 1):
            if cid in done:
                continue
            wid = (oa_of.get(cid) or "").rsplit("/", 1)[-1]
            if not wid:
                fh.write(json.dumps({"seed_done": cid, "note": "no OpenAlex id"}) + "\n"); continue
            try:
                w = get(f"https://api.openalex.org/works/{wid}?select=id,referenced_works")
                refs = [x.rsplit("/", 1)[-1] for x in w.get("referenced_works", [])]
                nb = nf = 0
                for x in fetch_ids([x for x in refs if x not in known_ids]):
                    fh.write(json.dumps({**slim(x), "direction": "backward", "seed": cid}) + "\n"); nb += 1
                for x in openalex_search_filter(f"cites:{wid}"):
                    if x.get("id", "").rsplit("/", 1)[-1] in known_ids:
                        continue
                    fh.write(json.dumps({**slim(x), "direction": "forward", "seed": cid}) + "\n"); nf += 1
            except BudgetExhausted:
                print("OpenAlex daily budget exhausted -- resume after 00:00 UTC (`snowball --resume`)", flush=True)
                sys.exit(BUDGET_EXIT)
            fh.write(json.dumps({"seed_done": cid, "refs": len(refs), "backward_new": nb, "forward_new": nf}) + "\n")
            fh.flush()
            log({"snowball_seed": cid, "openalex": wid, "refs": len(refs), "backward_new": nb, "forward_new": nf})
            print(f"[{k}/{len(seeds)}] {cid} refs={len(refs)} backward_new={nb} forward_new={nf}", flush=True)
    # deduplicate the new works among themselves, then drop any that match a known DOI or title
    recs = [e for e in _read_jsonl(raw) if e.get("openalex")]
    for i, r in enumerate(recs):
        r["_seq"] = i
    rows = []
    for g in dedup_groups(recs):
        rep_ = min(g, key=_pref)
        if (rep_.get("doi") or "").lower() in known_doi or norm_title(rep_.get("title")) in known_title:
            continue
        if any((x.get("doi") or "").lower() in known_doi for x in g):
            continue
        rows.append((rep_, g))
    rows.sort(key=lambda t: t[0]["_seq"])
    with open(a.out + "_candidates.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cid", "doi", "title", "year", "venue", "type", "abstract", "openalex",
                    "n_records", "merged_openalex", "found_by", "direction", "seeds"])
        for r, g in rows:
            others = sorted({x.get("openalex", "") for x in g} - {r.get("openalex", "")})
            w.writerow([stable_id(r), r["doi"], r["title"], r["year"], r["venue"], r["type"],
                        (r.get("abstract") or "")[:3000], r["openalex"], len(g), ";".join(others),
                        "snowball", ";".join(sorted({x["direction"] for x in g})),
                        ";".join(sorted({x["seed"] for x in g}))])
    print(f"{len(recs)} snowball hits -> {len(rows)} new unique candidates -> {a.out}_candidates.csv")


def openalex_search_cites(wid: str, max_pages=0):
    cursor = "*"
    page = 0
    while not max_pages or page < max_pages:
        url = (f"https://api.openalex.org/works?filter=cites:{wid.split('/')[-1]}"
               f"&per-page=200&cursor={cursor}" + (f"&mailto={MAILTO}" if MAILTO else ""))
        js = get(url)
        yield from js.get("results", [])
        cursor = js.get("meta", {}).get("next_cursor")
        page += 1
        if not cursor or not js.get("results"):
            break


def cmd_budget(a):
    """Print today's OpenAlex usage budget for the configured key."""
    if not API_KEY:
        print("no OPENALEX_API_KEY (or ~/.config/openalex_key): about $0.01/day, ~10 searches")
    try:
        js = get("https://api.openalex.org/rate-limit", retries=2)
        js.pop("api_key", None)               # never echo any part of the key into a log
        print(json.dumps(js, indent=1)[:1500])
    except Exception as e:  # noqa: BLE001
        print("rate-limit endpoint unavailable:", e)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("budget")
    s = sp.add_parser("search"); s.add_argument("--out", default=str(C / "search_raw.jsonl")); s.add_argument("--dry-run", action="store_true")
    s.add_argument("--resume", action="store_true", help="keep completed queries, re-page the rest")
    s.add_argument("--revision", type=int, default=0, help="0 = protocol search; 1 = F2 widened blocks")
    s.add_argument("--max-pages", type=int, default=0, help="0 = no cap (default); 10 reproduces the capped pilot run")
    d = sp.add_parser("dedup"); d.add_argument("--inp", nargs="+", default=[str(C / "search_raw.jsonl")],
                                             help="one or more raw files (.jsonl or .jsonl.gz), e.g. search + venue sweeps")
    d.add_argument("--out", default=str(C / "candidates.csv"))
    v = sp.add_parser("venues"); v.add_argument("--out", default=str(C / "venue_raw.jsonl"))
    v.add_argument("--resume", action="store_true", help="keep completed venues, sweep the rest")
    v.add_argument("--revision", type=int, default=0)
    vd = sp.add_parser("venues_dblp"); vd.add_argument("--out", default=str(C / "venue_dblp_raw.jsonl"))
    vd.add_argument("--resume", action="store_true"); vd.add_argument("--revision", type=int, default=1)
    b = sp.add_parser("snowball"); b.add_argument("--seeds", default=str(C / "codes_full_final.csv"))
    b.add_argument("--out", default=str(C / "snowball" / "iter1"), help="output prefix")
    b.add_argument("--known", nargs="*", default=[], help="candidate files of earlier iterations")
    b.add_argument("--resume", action="store_true")
    a = p.parse_args()
    {"search": cmd_search, "dedup": cmd_dedup, "venues": cmd_venues, "snowball": cmd_snowball,
     "budget": cmd_budget, "venues_dblp": cmd_venues_dblp}[a.cmd](a)
