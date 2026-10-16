#!/usr/bin/env python3
"""S3 (full text): retrieve open-access full texts for the coding sample.

Reads corpus/coding_sample.csv and walks each stratum in its random order
until the stratum's quota (in_first_300) of retrieved texts is met; a record
whose full text cannot be retrieved is recorded as "not retrieved" and the
next record of the same stratum replaces it (amendment 3).

Sources, in order: OpenAlex best open-access location (pdf_url, then
landing-page oa_url when it is a PDF), and arXiv for arXiv DOIs. Only openly
available copies are fetched; nothing behind a paywall or bot check is
attempted. PDFs are converted to text with pdftotext (poppler) or, if absent,
pypdf; the PDFs themselves are deleted after conversion.

Outputs  corpus/fulltext/<cid>.txt            (not committed: third-party text)
         corpus/fulltext_status.csv           cid, stratum, order, status, source, chars
Usage    python3 fetch_fulltext.py            (resumable: done cids are skipped)
         python3 fetch_fulltext.py --iter 1   (snowballing iteration 1: corpus/snowball/iter1_*,
                                               texts to corpus/fulltext_snowball1/)
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

C = Path(__file__).resolve().parent.parent / "corpus"
OUT = C / "fulltext"
UA = {"User-Agent": "paperII-sok/1.0 (systematic review; open-access full texts only)"}
API_KEY = os.environ.get("OPENALEX_API_KEY", "")
_kf = Path.home() / ".config" / "openalex_key"
if not API_KEY and _kf.exists():
    API_KEY = _kf.read_text().strip()


def get(url: str, binary=False, timeout=60, max_bytes=40_000_000):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ctype = r.headers.get("Content-Type", "")
        data = r.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("too large")
    return (data, ctype) if binary else json.loads(data.decode("utf-8", "replace"))


def oa_urls(row: dict, oa_id: str) -> list[str]:
    urls = []
    doi = (row.get("doi") or "").lower()
    if oa_id:
        q = f"https://api.openalex.org/works/{oa_id}?select=best_oa_location,open_access,locations"
        if API_KEY:
            q += "&api_key=" + urllib.parse.quote(API_KEY)
        try:
            w = get(q)
            best = w.get("best_oa_location") or {}
            for u in (best.get("pdf_url"), (w.get("open_access") or {}).get("oa_url")):
                if u and u not in urls:
                    urls.append(u)
            for loc in w.get("locations") or []:
                u = loc.get("pdf_url")
                if u and loc.get("is_oa") and u not in urls:
                    urls.append(u)
        except Exception as e:  # noqa: BLE001
            print(f"  openalex lookup failed for {oa_id}: {type(e).__name__}", flush=True)
    m = re.match(r"10\.48550/arxiv\.(.+)", doi)
    if m:
        urls.append(f"https://arxiv.org/pdf/{m.group(1)}")
    return urls


def to_text(pdf: Path) -> str:
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-layout", "-q", str(pdf), "-"], capture_output=True, timeout=120)
        return r.stdout.decode("utf-8", "replace")
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("Install poppler-utils (sudo apt install poppler-utils) or pypdf (pip install pypdf).")
    return "\n".join((p.extract_text() or "") for p in PdfReader(str(pdf)).pages)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--iter", type=int, default=0)
    it = ap.parse_args().iter
    csv.field_size_limit(10 ** 9)
    global OUT
    if it:
        S = C / "snowball"
        OUT = C / f"fulltext_snowball{it}"
        cand = {r["cid"]: r for r in csv.DictReader((S / f"iter{it}_candidates.csv").open())}
        sample = list(csv.DictReader((S / f"iter{it}_coding_sample.csv").open()))
        strata = (f"snowball{it}",)
        sp = S / f"iter{it}_fulltext_status.csv"
    else:
        cand = {r["cid"]: r for r in csv.DictReader((C / "candidates.csv").open())}
        sample = list(csv.DictReader((C / "coding_sample.csv").open()))
        strata = ("core", "remainder")
        sp = C / "fulltext_status.csv"
    OUT.mkdir(exist_ok=True)
    quota = {s: sum(1 for r in sample if r["stratum"] == s and r["in_first_300"] == "1") for s in strata}
    status = {r["cid"]: r for r in csv.DictReader(sp.open())} if sp.exists() else {}
    fields = ["cid", "stratum", "order", "status", "source", "chars"]
    for stratum in strata:
        rows = sorted((r for r in sample if r["stratum"] == stratum), key=lambda r: int(r["order"]))
        got = sum(1 for r in rows if status.get(r["cid"], {}).get("status") == "retrieved")
        for r in rows:
            if got >= quota[stratum]:
                break
            if r["cid"] in status:
                continue
            c = cand[r["cid"]]
            oa_id = (c.get("openalex") or "").rsplit("/", 1)[-1]
            rec = {"cid": r["cid"], "stratum": stratum, "order": r["order"], "status": "not retrieved",
                   "source": "", "chars": 0}
            for u in oa_urls(c, oa_id):
                try:
                    data, ctype = get(u, binary=True)
                    if not data.startswith(b"%PDF"):
                        continue
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
                        fh.write(data); tmp = Path(fh.name)
                    txt = to_text(tmp); tmp.unlink(missing_ok=True)
                    if len(txt.strip()) < 2000:
                        continue
                    (OUT / f"{r['cid']}.txt").write_text(txt)
                    rec.update(status="retrieved", source=u, chars=len(txt))
                    break
                except Exception:  # noqa: BLE001
                    continue
                finally:
                    time.sleep(1.0)
            status[r["cid"]] = rec
            got += rec["status"] == "retrieved"
            print(f"{stratum:<9} #{r['order']:>4} {rec['status']:<13} {got}/{quota[stratum]}", flush=True)
            with sp.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n"); w.writeheader()
                w.writerows(status.values())
        print(f"== {stratum}: {got} of {quota[stratum]} retrieved", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
