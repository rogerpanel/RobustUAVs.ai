"""The follow-on papers as an experimentable surface.

Paper I    paperI/    what authenticity costs in metres (the authentication budget)
Paper II   paperII/   the quantifier-gap SoK (the coded corpus and its PRISMA flow)
Paper III  paperIII/  certificates as constraints (nested-eligibility allocation)
Paper IV   paperIV/   the attacker indistinguishable from the weather (the unified
                      perturbation budget and its dependence-uncertainty floor)

Two kinds of thing are served here, and the module keeps them apart:

  results    every CSV a paper's harness wrote under `paper*/results/`, served
             as-is (JSON rows or the file itself). Nothing is summarised or
             rounded on the way out, so an export is the committed file.
  live       a small number of calculators that call the papers' OWN code --
             `paperI/experiments/constants.py`, `paperIII/experiments/certcmdp`,
             `e2_degradation.p_full_iid` and `paperIV/experiments/depbounds.py`
             -- rather than a re-implementation of it. The one exception is Paper I's budget, which is a single
             product (rho = (Delta + Delta_auth) * gamma * e^{L T_c}) that the
             paper computes inline in budget.py and exposes no function for.

The platform conventions apply unchanged: a file or a paper folder that is not
present in this deployment raises `Unavailable` (a 503 at the route, "not
produced", never a 500), and every number traces to a file or a live call.

Paper code is imported lazily, inside the handler, with its directory pushed
onto sys.path and bytecode writing switched off for the duration -- importing
must not leave `__pycache__` files behind in a paper's tree. If the import
fails (a dependency missing, the paper's tree mid-edit), the endpoint degrades
to a 503 that says which file could not be imported and why.
"""
from __future__ import annotations

import contextlib
import csv
import functools
import importlib
import importlib.util
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

from . import results

REPO = results.REPO

PAPERS = {"I": "paperI", "II": "paperII", "III": "paperIII", "IV": "paperIV"}

# Never listed and never served: run logs, checkpoints, the raw-run scratch
# directories the MARL launcher writes next to its results.
SKIP_DIRS = {"logs", "logs_r", "server_logs", "__pycache__"}

# Request-size ceilings for the live calculators. The closed forms are
# O(N log N) but the Hungarian projection is cubic, and this is a shared host.
MAX_AGENTS = 2000
MAX_TASKS = 2000
MAX_LIFT_N = 200
# Paper IV's floor: the largest margin accepted. The paper evaluates m <= 20 m;
# beyond its CP split grid (depbounds.S_MAX) the bound is evaluated at S_MAX.
MAX_FLOOR_M = 40.0


class Unavailable(results.ResultUnavailable):
    """Something a paper endpoint needs is not present in this deployment."""

    def __init__(self, name: str, detail: Optional[str] = None):
        self.name = name
        Exception.__init__(
            self, detail or f"'{name}' is not present in this deployment. It is "
                            "produced by that paper's experiment harness.")


class UnknownPaper(KeyError):
    pass


class BadRequest(ValueError):
    """Calculator input the endpoint understands but refuses (-> 422)."""


class PathRejected(BadRequest):
    """A result path that is not a .csv inside the paper's results/ (-> 400)."""


# ================================================================ helpers ===

def _paper_dir(pid: str) -> Path:
    folder = PAPERS.get(pid)
    if folder is None:
        raise UnknownPaper(pid)
    return REPO / folder


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        return p.name


def _finite(v: Any) -> Any:
    """JSON has no inf/nan, and Starlette refuses to encode them. The papers
    write 'inf' for an infeasible transport and 'nan' for an interval that was
    not computed; keep that information as a string rather than dropping it."""
    if isinstance(v, float) and not math.isfinite(v):
        return "nan" if math.isnan(v) else ("inf" if v > 0 else "-inf")
    return v


def _num(v: Any) -> Optional[float]:
    """A float for arithmetic, or None. Accepts the 'inf' strings _finite makes."""
    if isinstance(v, bool) or v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@functools.lru_cache(maxsize=256)
def _parse(path: str, mtime_ns: int, size: int) -> tuple[list[str], list[dict]]:
    # Keyed on mtime and size, not just the name: experiments are still
    # writing into these trees, and a name-keyed cache would serve stale rows.
    with open(path, newline="") as fh:
        rd = csv.DictReader(fh)
        cols = list(rd.fieldnames or [])
        rows = [{k: _finite(results._coerce(v)) for k, v in r.items() if k is not None}
                for r in rd]
    return cols, rows


def read_table(p: Path) -> tuple[list[str], list[dict]]:
    if not p.is_file():
        raise Unavailable(_rel(p))
    st = p.stat()
    return _parse(str(p), st.st_mtime_ns, st.st_size)


def _provenance(cols: list[str], rows: list[dict]) -> tuple[Optional[str], list[str]]:
    """Distinct values of the file's provenance column. Paper III and Paper I's
    E1 write `provenance`; Paper I's older outputs write the same thing as `tag`."""
    for c in ("provenance", "tag"):
        if c in cols:
            return c, sorted({str(r[c]) for r in rows if r.get(c) not in (None, "")})
    return None, []


def _results_dir(pid: str) -> Path:
    base = _paper_dir(pid) / "results"
    if not base.is_dir():
        raise Unavailable(f"{PAPERS[pid]}/results/",
                          f"{PAPERS[pid]}/results/ is not present in this deployment, "
                          "so this paper has no result files to serve here.")
    return base


def _csv_files(base: Path) -> Iterable[Path]:
    for p in sorted(base.rglob("*.csv")):
        rel = p.relative_to(base)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        if p.is_file():
            yield p


@contextlib.contextmanager
def _paper_imports(directory: Path):
    """sys.path insertion without leaving bytecode in the paper's tree."""
    d = str(directory)
    if d not in sys.path:
        sys.path.insert(0, d)
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        yield
    finally:
        sys.dont_write_bytecode = old


# ============================================================== catalogue ===

def _latex_title(tex: Path) -> Optional[str]:
    try:
        src = tex.read_text(errors="replace")
    except OSError:
        return None
    i = src.find("\\title{")
    if i < 0:
        return None
    j, depth = i + len("\\title{"), 1
    k = j
    while k < len(src) and depth:
        depth += {"{": 1, "}": -1}.get(src[k], 0)
        k += 1
    body = src[j:k - 1]
    body = body.replace("\\\\", " ").replace("~", " ")
    body = re.sub(r"\\[a-zA-Z]+\*?\{([^{}]*)\}", r"\1", body)   # \emph{x} -> x
    body = re.sub(r"\\[a-zA-Z]+\*?", "", body)                  # stray macros
    body = body.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", body).strip() or None


def _readme_title(md: Path) -> Optional[str]:
    try:
        for line in md.read_text(errors="replace").splitlines():
            if line.startswith("#"):
                return line.lstrip("#").strip() or None
    except OSError:
        return None
    return None


def paper_title(pid: str) -> tuple[Optional[str], Optional[str]]:
    d = _paper_dir(pid)
    for path, fn in ((d / "manuscript" / "main.tex", _latex_title),
                     (d / "README.md", _readme_title)):
        t = fn(path) if path.exists() else None
        if t:
            return t, _rel(path)
    return None, None


def catalogue() -> dict:
    papers = []
    for pid, folder in PAPERS.items():
        d = REPO / folder
        title, title_source = paper_title(pid)
        files = []
        base = d / "results"
        if base.is_dir():
            for p in _csv_files(base):
                try:
                    _, rows = read_table(p)
                except (Unavailable, OSError, csv.Error, UnicodeDecodeError):
                    continue
                files.append({"name": str(p.relative_to(base)), "rows": len(rows)})
        papers.append({
            "id": pid, "folder": folder, "present": d.is_dir(),
            "title": title, "title_source": title_source,
            "results_dir": f"{folder}/results/" if base.is_dir() else None,
            "n_result_files": len(files), "result_files": files,
            "note": None if d.is_dir() else
                    f"{folder}/ is not checked out in this deployment.",
        })
    return {"papers": papers, "source": "paper*/manuscript/main.tex, paper*/results/"}


def results_index(pid: str) -> dict:
    base = _results_dir(pid)
    files = []
    for p in _csv_files(base):
        try:
            cols, rows = read_table(p)
        except (OSError, csv.Error, UnicodeDecodeError) as exc:
            files.append({"name": str(p.relative_to(base)), "error": str(exc)})
            continue
        pcol, prov = _provenance(cols, rows)
        files.append({
            "name": str(p.relative_to(base)), "rows": len(rows), "columns": cols,
            "provenance_column": pcol, "provenance": prov,
            "bytes": p.stat().st_size,
        })
    return {"paper": pid, "folder": PAPERS[pid], "results_dir": _rel(base),
            "n_files": len(files), "files": files}


def resolve_result(pid: str, name: str) -> Path:
    """The one place a client-supplied path becomes a filesystem path.

    Resolved (symlinks followed) and required to stay inside the paper's
    results directory; only `.csv`; never inside a skipped directory.
    """
    base = _results_dir(pid).resolve()
    if not name or "\x00" in name or not name.lower().endswith(".csv"):
        raise PathRejected("only .csv files under the paper's results/ are served")
    p = (base / name).resolve()
    if not p.is_relative_to(base):
        raise PathRejected("path escapes the paper's results directory")
    if any(part in SKIP_DIRS for part in p.relative_to(base).parts[:-1]):
        raise PathRejected("run logs are not served")
    if not p.is_file():
        raise Unavailable(f"{PAPERS[pid]}/results/{name}")
    return p


def result_file(pid: str, name: str, limit: Optional[int] = None) -> dict:
    p = resolve_result(pid, name)
    cols, rows = read_table(p)
    pcol, prov = _provenance(cols, rows)
    return {"paper": pid, "name": name, "source": _rel(p), "columns": cols,
            "rows": rows if limit is None else rows[:limit],
            "n_rows": len(rows), "truncated": limit is not None and len(rows) > limit,
            "provenance_column": pcol, "provenance": prov}


# ======================================================= Paper I: budget ===

def _paperI_constants():
    exp = REPO / "paperI" / "experiments"
    src = exp / "constants.py"
    if not src.exists():
        raise Unavailable("paperI/experiments/constants.py")
    name = "_robustuavs_paperI_constants"
    if name in sys.modules:
        return sys.modules[name]
    # Loaded under a private name rather than as `constants`, which is generic
    # enough to collide with something else on sys.path.
    try:
        with _paper_imports(exp):
            spec = importlib.util.spec_from_file_location(name, src)
            mod = importlib.util.module_from_spec(spec)
            # @dataclass resolves its class's module through sys.modules, so
            # the module must be registered before its body runs.
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001 -- any failure is "not available here"
        sys.modules.pop(name, None)
        raise Unavailable("paperI/experiments/constants.py",
                          f"Paper I's constants could not be imported in this "
                          f"deployment ({type(exc).__name__}: {exc}).") from exc
    return mod


def _constant_tag(src: str, name: str) -> tuple[Optional[str], Optional[str]]:
    """The `[tag]` and comment constants.py writes beside a constant, or, for
    a block, on the comment line heading it."""
    lines = src.splitlines()
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(name)}\s*=", line):
            m = re.search(r"#\s*(.*?)\s*\[([^\]]+)\]\s*$", line)
            if m:
                return m.group(2), m.group(1) or None
            for back in range(i - 1, max(-1, i - 12), -1):
                prev = lines[back].strip()
                if not prev.startswith("#"):
                    if prev:
                        continue
                    break
                m = re.search(r"#\s*(.*?)\s*\[([^\]]+)\]", prev)
                if m:
                    return m.group(2), m.group(1) or None
            return None, None
    return None, None


def _dauth_rows() -> list[dict]:
    try:
        _, rows = read_table(REPO / "paperI" / "results" / "dauth.csv")
    except Unavailable:
        return []
    return rows


def _provenance_rows() -> list[dict]:
    try:
        _, rows = read_table(REPO / "paperI" / "results" / "provenance_paperI.csv")
    except Unavailable:
        return []
    return rows


def budget_defaults() -> dict:
    C = _paperI_constants()
    src = (REPO / "paperI" / "experiments" / "constants.py").read_text(errors="replace")
    alert = 10.0 if 10.0 in C.MARGINS else float(C.MARGINS[-1])

    def c(name, value, unit, note=None, prov=None, source="paperI/experiments/constants.py"):
        tag, comment = _constant_tag(src, name) if prov is None else (prov, None)
        return {"constant": name, "value": value, "unit": unit, "provenance": tag,
                "comment": comment, "note": note, "source": source}

    return {
        "fields": {
            "theta_s": c("THETA_OP", C.THETA_OP, "s", "detector operating point"),
            "delta_s": c("delta_theta(THETA_OP)", C.delta_theta(C.THETA_OP), "s",
                         f"Lemma 1 of the parent: H*min(theta, S_SLACK), "
                         f"H = {C.H}, S_SLACK = {C.S_SLACK}", prov="derived"),
            "delta_auth_s": c("Delta_auth", 0.0, "s",
                              "0 = unauthenticated; pick a scheme x transport to read "
                              "its certified Delta_auth from paperI/results/dauth.csv",
                              prov="assumption"),
            "gamma_m_s": c("GAMMA_SPOOF_EKF_SUP", C.GAMMA_SPOOF_EKF_SUP, "m/s",
                           "gamma_u: unauthenticated rate, spoofing flight EKF supremum"),
            "L": c("L_LOC", C.L_LOC, "1/s", "local Lipschitz constant"),
            "T_c_s": c("T_C", C.T_C, "s", "certification horizon"),
            "alert_limit_m": c("MARGINS", alert, "m",
                               f"one of MARGINS = {list(C.MARGINS)}; 10 m is the "
                               "margin crossover_curves.csv reports (B10)"),
        },
        "margins_m": list(C.MARGINS),
        "gamma_scenarios": [{"name": s.name, "gamma_u": s.gamma_u, "gamma_a": s.gamma_a,
                             "ratio": round(s.ratio, 4), "tag": s.tag, "note": s.note}
                            for s in C.GAMMA_SCENARIOS],
        "schemes": [{"transport": r["transport"], "scheme": r["scheme"],
                     "dauth_cert_ms": r["dauth_cert_ms"],
                     "rate_feasible": r.get("rate_feasible"),
                     "pq": r.get("pq"), "source_auth": r.get("source_auth")}
                    for r in _dauth_rows()],
        "constants_provenance": _provenance_rows(),
        "formula": "rho = (Delta + Delta_auth) * gamma * exp(L * T_c) <= m",
        "source": "paperI/experiments/constants.py, paperI/results/dauth.csv, "
                  "paperI/results/provenance_paperI.csv",
    }


def budget(req: dict) -> dict:
    """rho = (Delta + Delta_auth) * gamma * e^{L T_c}, checked against m.

    Every input defaults to the paper's own constant. `delta_s` wins over
    `theta_s` (Delta is derived from theta by the parent's Lemma 1 otherwise);
    an explicit `delta_auth_s` wins over a `scheme`/`transport` lookup in
    dauth.csv; an explicit `gamma_m_s` wins over the scenario's gamma. With
    authentication in play (Delta_auth > 0 or a scheme chosen) the default
    gamma is the scenario's gamma_a, and the unauthenticated rho is returned
    beside it, because the paper's question is whether the swap pays.
    """
    C = _paperI_constants()
    d = budget_defaults()
    f = {k: v["value"] for k, v in d["fields"].items()}
    used: dict[str, dict] = {}
    overrides = []

    def take(key, given, default, prov, source, note=None):
        if given is not None:
            v = float(given)
            if not math.isfinite(v):
                raise BadRequest(f"{key} must be finite")
            overrides.append(key)
            used[key] = {"value": v, "provenance": "user", "source": "request"}
            return v
        used[key] = {"value": default, "provenance": prov, "source": source,
                     **({"note": note} if note else {})}
        return default

    fd = d["fields"]
    theta = take("theta_s", req.get("theta_s"), f["theta_s"],
                 fd["theta_s"]["provenance"], fd["theta_s"]["source"])
    if req.get("delta_s") is not None:
        delta = take("delta_s", req["delta_s"], None, None, None)
    else:
        delta = C.delta_theta(theta)       # the paper's own function
        used["delta_s"] = {"value": delta, "provenance": "derived",
                           "source": "paperI/experiments/constants.py:delta_theta",
                           "note": f"H*min(theta, S_SLACK) at theta = {theta} s"}

    scheme, transport = req.get("scheme"), req.get("transport") or "can"
    if req.get("delta_auth_s") is not None:
        dauth = take("delta_auth_s", req["delta_auth_s"], None, None, None)
    elif scheme:
        row = next((r for r in d["schemes"]
                    if r["scheme"] == scheme and r["transport"] == transport), None)
        if row is None:
            if not d["schemes"]:
                raise Unavailable("paperI/results/dauth.csv")
            raise BadRequest(f"no dauth.csv row for scheme '{scheme}' on transport "
                             f"'{transport}'")
        ms = _num(row["dauth_cert_ms"])
        dauth = math.inf if ms is None else ms / 1e3
        used["delta_auth_s"] = {"value": _finite(dauth), "provenance": "derived",
                                "source": "paperI/results/dauth.csv",
                                "note": f"dauth_cert_ms for {scheme} on {transport}"}
    else:
        dauth = take("delta_auth_s", None, 0.0, "assumption", "unauthenticated")
    authenticated = dauth > 0 or bool(scheme)

    scen_name = req.get("gamma_scenario") or "headline"
    scen = next((s for s in C.GAMMA_SCENARIOS if s.name == scen_name), None)
    if scen is None:
        raise BadRequest(f"unknown gamma_scenario '{scen_name}'; one of "
                         f"{[s.name for s in C.GAMMA_SCENARIOS]}")
    gamma_default = scen.gamma_a if authenticated else scen.gamma_u
    gamma = take("gamma_m_s", req.get("gamma_m_s"), gamma_default, scen.tag,
                 "paperI/experiments/constants.py:GAMMA_SCENARIOS",
                 f"{scen.name}: {'gamma_a' if authenticated else 'gamma_u'} -- {scen.note}")
    L = take("L", req.get("L"), f["L"], fd["L"]["provenance"], fd["L"]["source"])
    Tc = take("T_c_s", req.get("T_c_s"), f["T_c_s"], fd["T_c_s"]["provenance"],
              fd["T_c_s"]["source"])
    m = take("alert_limit_m", req.get("alert_limit_m"), f["alert_limit_m"],
             fd["alert_limit_m"]["provenance"], fd["alert_limit_m"]["source"])

    if delta < 0 or dauth < 0 or gamma < 0 or Tc < 0 or m <= 0:
        raise BadRequest("Delta, Delta_auth, gamma and T_c must be >= 0 and m > 0")
    if L * Tc > 700:
        raise BadRequest("L * T_c is too large to exponentiate")

    E = math.exp(L * Tc)
    rho = (delta + dauth) * gamma * E
    budget_s = m / (gamma * E) - delta if gamma > 0 else math.inf
    out = {
        "rho_m": _finite(rho),
        "alert_limit_m": m,
        "margin_m": _finite(m - rho),
        "pass": bool(rho <= m),
        "amplification": E,
        "dauth_budget_s": _finite(budget_s),
        "dauth_budget_note": "largest Delta_auth that still certifies at this "
                             "Delta, gamma and m: m / (gamma e^{L T_c}) - Delta",
        "authenticated": authenticated,
        "inputs": used,
        "overrides": overrides,
        "formula": d["formula"],
        "constants_provenance": d["constants_provenance"],
        "source": d["source"],
    }
    if authenticated:
        rho_u = delta * scen.gamma_u * E
        out["unauthenticated"] = {
            "gamma_u_m_s": scen.gamma_u, "rho_m": rho_u,
            "pass": bool(rho_u <= m),
            "benefit_m": _finite(rho_u - rho),
            "note": "same Delta with no authentication delay, at the scenario's gamma_u",
        }
    return out


# ========================================================= Paper II: corpus ===

CODE_FIELDS_FALLBACK = ("tier", "component", "scope", "modality", "perturbation",
                        "lifts", "assumption", "evidence")
LIST_FIELDS = {"lifts"}


def _codebook(path: Path) -> tuple[Optional[str], dict[str, list[str]]]:
    """Field -> closed vocabulary, parsed from CODEBOOK.md's table."""
    if not path.exists():
        return None, {}
    text = path.read_text(errors="replace")
    # The heading names the version it was frozen at; later additions are
    # headed "vX.Y additions". The highest version mentioned is the current one.
    vers = re.findall(r"\bv(\d+\.\d+)\b", text)
    ver = max(vers, key=lambda v: tuple(int(x) for x in v.split("."))) if vers else None
    out: dict[str, list[str]] = {}
    for line in text.splitlines():
        m = re.match(r"^\|\s*`([a-z_]+)`\s*\|(.*?)\|", line)
        if m:
            out[m.group(1)] = re.findall(r"`([^`]+)`", m.group(2))
    return ver, out


def corpus(table: str = "ADJ", filters: Optional[dict[str, str]] = None,
           year_min: Optional[int] = None, year_max: Optional[int] = None) -> dict:
    d = _paper_dir("II")
    cdir, rdir = d / "corpus", d / "results"
    if not d.is_dir():
        raise Unavailable("paperII/", "paperII/ is not checked out in this deployment "
                          "(it lives on the paperII/full-study branch), so the coded "
                          "corpus and PRISMA counts are not available here.")
    if not re.fullmatch(r"[A-Za-z0-9_]+", table or ""):
        raise BadRequest("table must be a coder id such as ADJ, C1, C2, H1")
    codes_p, index_p = cdir / f"codes_{table}.csv", cdir / "corpus_index.csv"
    for p in (codes_p, index_p):
        if not p.is_file():
            raise Unavailable(_rel(p))

    ver, book = _codebook(cdir / "CODEBOOK.md")
    code_cols, codes = read_table(codes_p)
    _, index = read_table(index_p)
    fields = [f for f in (book or {}) if f in code_cols] or \
             [f for f in CODE_FIELDS_FALLBACK if f in code_cols]

    filters = {k: v for k, v in (filters or {}).items() if v not in (None, "")}
    unknown = sorted(set(filters) - set(fields))
    if unknown:
        raise BadRequest(f"unknown filter field(s) {unknown}; filterable: {fields}")

    by_gid = {str(r["gid"]): r for r in index}
    joined = []
    for r in codes:
        meta = by_gid.get(str(r["gid"]), {})
        joined.append({"gid": r["gid"], "year": meta.get("year"),
                       "venue": meta.get("venue"), "bibkey": meta.get("bibkey"),
                       "title": meta.get("title"),
                       **{k: v for k, v in r.items() if k != "gid"}})

    def values(row, f):
        v = row.get(f)
        if v is None:
            return []
        return [x.strip() for x in str(v).split(";") if x.strip()] if f in LIST_FIELDS \
            else [str(v)]

    def keep(row):
        y = _num(row.get("year"))
        if year_min is not None and (y is None or y < year_min):
            return False
        if year_max is not None and (y is None or y > year_max):
            return False
        return all(v in values(row, f) for f, v in filters.items())

    rows = [r for r in joined if keep(r)]
    counts = {f: {} for f in fields}
    for r in rows:
        for f in fields:
            for v in values(r, f):
                counts[f][v] = counts[f].get(v, 0) + 1
    counts = {f: dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))
              for f, c in counts.items()}
    years = [int(y) for y in (_num(r.get("year")) for r in joined) if y is not None]

    sources = [_rel(codes_p), _rel(index_p)]
    missing = []

    def optional(p: Path):
        try:
            _, rr = read_table(p)
            sources.append(_rel(p))
            return rr
        except Unavailable:
            missing.append(_rel(p))
            return None

    prisma = optional(cdir / "prisma_counts.csv")
    sensitivity = optional(rdir / "search_sensitivity.csv")
    tables = sorted(p.stem[len("codes_"):] for p in cdir.glob("codes_*.csv"))
    return {
        "table": table, "tables_available": tables,
        "codebook_version": ver, "codebook": book, "fields": fields,
        "filters": filters, "year_min": year_min, "year_max": year_max,
        "year_range": [min(years), max(years)] if years else None,
        "n_total": len(joined), "n_filtered": len(rows),
        "counts": counts, "rows": rows,
        "prisma": prisma, "search_sensitivity": sensitivity,
        "missing": missing,
        "source": ", ".join(sources),
    }


# =================================================== Paper III: certificate ===

def _paperIII(module: str):
    exp = REPO / "paperIII" / "experiments"
    rel = module.replace(".", "/") + ".py"
    if not (exp / rel).exists():
        raise Unavailable(f"paperIII/experiments/{rel}")
    try:
        with _paper_imports(exp):
            return importlib.import_module(module)
    except Exception as exc:  # noqa: BLE001
        raise Unavailable(f"paperIII/experiments/{rel}",
                          f"Paper III's {rel} could not be imported in this "
                          f"deployment ({type(exc).__name__}: {exc}).") from exc


def _vector(name: str, xs, cap: int, allow_empty=False) -> list[float]:
    if xs is None:
        raise BadRequest(f"{name} is required")
    try:
        out = [float(x) for x in xs]
    except (TypeError, ValueError):
        raise BadRequest(f"{name} must be a list of numbers")
    if not out and not allow_empty:
        raise BadRequest(f"{name} must not be empty")
    if len(out) > cap:
        raise BadRequest(f"{name} has {len(out)} entries; the limit is {cap}")
    if not all(math.isfinite(x) for x in out):
        raise BadRequest(f"{name} must be finite")
    return out


def certify_defaults() -> dict:
    cert = _paperIII("certcmdp.certificate")
    return {
        "constants": {
            "KAPPA_m_per_s": cert.KAPPA, "THETA_BENIGN_s": cert.THETA_BENIGN,
            "L_LOC": cert.L_LOC, "T_C_s": cert.T_C, "GAMMA_SUP_m_s": cert.GAMMA_SUP,
            "S_SLACK_s": cert.S_SLACK,
        },
        "alert_limits_m": list(cert.ALERT_LIMITS),
        "rho_of_staleness": "rho = KAPPA * (THETA_BENIGN + staleness_s)",
        "limits": {"N": MAX_AGENTS, "M": MAX_TASKS, "lift_N": MAX_LIFT_N},
        "lift_reference": _lift_reference(),
        "source": "paperIII/experiments/certcmdp/certificate.py",
    }


def _lift_reference() -> list[dict]:
    try:
        _, rows = read_table(REPO / "paperIII" / "results" / "e2_lift.csv")
    except Unavailable:
        return []
    return [r for r in rows if r.get("event") == "d=0"]


def certify(req: dict) -> dict:
    import numpy as np

    cert = _paperIII("certcmdp.certificate")
    comb = _paperIII("certcmdp.combinatorics")

    alpha = _vector("alpha", req.get("alpha"), MAX_TASKS)
    if req.get("rho") is not None and req.get("staleness_s") is not None:
        raise BadRequest("give rho or staleness_s, not both")
    if req.get("staleness_s") is not None:
        st = _vector("staleness_s", req["staleness_s"], MAX_AGENTS)
        if any(x < 0 for x in st):
            raise BadRequest("staleness_s must be >= 0")
        rho = [float(cert.KAPPA * (cert.THETA_BENIGN + x)) for x in st]
        rho_from = "staleness"
    else:
        rho = _vector("rho", req.get("rho"), MAX_AGENTS)
        rho_from = "rho"
    N, M = len(rho), len(alpha)
    r, a = np.asarray(rho, float), np.asarray(alpha, float)

    b = req.get("b")
    if b is not None:
        try:
            b = int(b)
        except (TypeError, ValueError):
            raise BadRequest("b must be an integer")
        if not 0 <= b <= N:
            raise BadRequest(f"b must lie in [0, N = {N}]")

    order = np.argsort(a, kind="stable")
    greedy = comb.nested_greedy_fast(r, a)
    out = {
        "N": N, "M": M, "rho_from": rho_from,
        "rho": [float(x) for x in r],
        "alpha": [float(x) for x in a],
        "alpha_sorted": [float(x) for x in a[order]],
        "count_profile": [int(x) for x in comb.count_profile(r, a)],
        "deficiency": int(comb.deficiency(r, a)),
        "max_coverage": int(comb.max_coverage(r, a)),
        "coverage_margin": int(comb.coverage_margin(r, a)),
        "b": b,
        "worst_case_deficiency": None if b is None
            else int(comb.worst_case_deficiency(r, a, b)),
        "worst_case_curve": [{"b": k, "deficiency": int(comb.worst_case_deficiency(r, a, k))}
                             for k in range(0, min(N, 20) + 1)],
        "greedy_assignment": [int(x) for x in greedy],
        "greedy_covered": int((greedy >= 0).sum()),
        "projection": None,
        "constants": {"KAPPA_m_per_s": cert.KAPPA, "THETA_BENIGN_s": cert.THETA_BENIGN},
        "eligibility": "agent i may hold task j iff rho_i <= alpha_j",
        "source": "paperIII/experiments/certcmdp/combinatorics.py "
                  "(count_profile, deficiency, max_coverage, coverage_margin, "
                  "worst_case_deficiency, nested_greedy_fast, lexicographic_projection)",
    }

    if req.get("proposal") is not None:
        prop = req["proposal"]
        try:
            prop = [int(x) for x in prop]
        except (TypeError, ValueError):
            raise BadRequest("proposal must be a list of task indices (-1 = idle)")
        if len(prop) != N:
            raise BadRequest(f"proposal must have one entry per agent (N = {N})")
        if any(x < -1 or x >= M for x in prop):
            raise BadRequest(f"proposal entries must lie in [-1, {M - 1}]")
        P = np.asarray(prop, dtype=int)
        elig = comb.eligibility(r, a)
        proj = comb.lexicographic_projection(elig, P)
        ineligible = [i for i, j in enumerate(prop) if j >= 0 and not elig[i, j]]
        out["projection"] = {
            "proposal": prop,
            "assignment": [int(x) for x in proj],
            "covered": int((proj >= 0).sum()),
            "kept_from_proposal": int(sum(1 for i, j in enumerate(prop)
                                          if j >= 0 and proj[i] == j)),
            "proposal_ineligible_agents": ineligible,
            "note": "lexicographic: max coverage first, then agreement with the "
                    "proposal (Hungarian on the rho_i <= alpha_j eligibility graph)",
        }
    return out


def lift(req: dict) -> dict:
    import numpy as np

    cert = _paperIII("certcmdp.certificate")
    e2 = _paperIII("e2_degradation")
    try:
        N = int(req.get("N"))
    except (TypeError, ValueError):
        raise BadRequest("N must be an integer")
    if not 1 <= N <= MAX_LIFT_N:
        raise BadRequest(f"N must lie in [1, {MAX_LIFT_N}]")
    alpha = _vector("alpha", req.get("alpha"), MAX_TASKS)
    q = _vector("q", req.get("q"), len(cert.ALERT_LIMITS) + 1)
    if len(q) != len(cert.ALERT_LIMITS) + 1:
        raise BadRequest(f"q must have {len(cert.ALERT_LIMITS) + 1} entries: one per "
                         f"alert-limit level {list(cert.ALERT_LIMITS)} plus 'above all'")
    if any(x < 0 for x in q) or abs(sum(q) - 1.0) > 1e-6:
        raise BadRequest(f"q must be non-negative and sum to 1 (sums to {sum(q):.6g})")
    p = float(e2.p_full_iid(N, np.asarray(alpha, float), np.asarray(q, float)))
    lv = list(cert.ALERT_LIMITS)
    labels = [f"rho <= {lv[0]:g}"] + [f"{lo:g} < rho <= {hi:g}" for lo, hi in zip(lv, lv[1:])] \
        + [f"rho > {lv[-1]:g}"]
    return {
        "N": N, "M": len(alpha), "alpha": alpha, "q": q, "q_levels": labels,
        "p_full": min(1.0, max(0.0, p)),
        "assumption": "agents fall in levels independently (the lift's evidence "
                      "obligation); spatially correlated jamming breaks it",
        "reference": _lift_reference(),
        "source": "paperIII/experiments/e2_degradation.py:p_full_iid",
    }


def marl() -> dict:
    base = REPO / "paperIII" / "results"
    tables, sources = {}, {}
    main_p = base / "e6_main.csv"
    if main_p.is_file():
        # e6_aggregate.py's default --dir is e5_marl; other run directories are
        # written as e6_main_<dir>.csv.
        tables["e5_marl"] = read_table(main_p)[1]
        sources["e5_marl"] = _rel(main_p)
    if base.is_dir():
        for p in sorted(base.glob("e6_main_*.csv")):
            key = p.stem[len("e6_main_"):]
            tables[key] = read_table(p)[1]
            sources[key] = _rel(p)
    if not tables:
        raise Unavailable("paperIII/results/e6_main.csv")
    return {"tables": tables, "dirs": list(tables), "sources": sources,
            "source": ", ".join(sources.values())}


# ================================================== Paper IV: the floor ===
#
# Paper IV's certified floor: with margin m, stealth budget delta_adv and the
# network tube net, the benign perturbations (GNSS error, benign fault, wind)
# must fit in what is left, s = m - delta_adv - net. Their marginals are known
# (e3_marginals.npz) but their coupling is not, so the paper bounds
# p(s) = Pr[gnss + fault + env > s] over every coupling and reports the floor
# 1 - p(s). Both bounds below are depbounds.py's own functions.

IV_MARGINALS = ("gnss", "fault", "env")   # the order pbar_union_cp unpacks


def _paperIV_depbounds():
    exp = REPO / "paperIV" / "experiments"
    src = exp / "depbounds.py"
    if not src.exists():
        raise Unavailable("paperIV/experiments/depbounds.py")
    name = "_robustuavs_paperIV_depbounds"
    if name in sys.modules:
        return sys.modules[name]
    # A private module name, as for Paper I: `depbounds` is the paper's name
    # for it, not ours to claim on sys.path.
    try:
        with _paper_imports(exp):
            spec = importlib.util.spec_from_file_location(name, src)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001
        sys.modules.pop(name, None)
        raise Unavailable("paperIV/experiments/depbounds.py",
                          f"Paper IV's depbounds.py could not be imported in this "
                          f"deployment ({type(exc).__name__}: {exc}).") from exc
    return mod


def _iv_marginals_path() -> tuple[Path, int, int]:
    p = REPO / "paperIV" / "results" / "e3_marginals.npz"
    if not p.is_file():
        raise Unavailable(_rel(p))
    st = p.stat()
    return p, st.st_mtime_ns, st.st_size


@functools.lru_cache(maxsize=4)
def _iv_marginals_load(path: str, mtime_ns: int, size: int) -> tuple:
    import numpy as np
    with np.load(path, allow_pickle=False) as z:
        missing = [k for k in IV_MARGINALS if k not in z.files]
        if missing:
            raise KeyError(f"arrays {missing} not in {Path(path).name}")
        return tuple(np.asarray(z[k], dtype=float) for k in IV_MARGINALS)


def _paperIV_marginals() -> tuple:
    p, mt, sz = _iv_marginals_path()
    try:
        return _iv_marginals_load(str(p), mt, sz)
    except (OSError, KeyError, ValueError) as exc:
        raise Unavailable(_rel(p), f"{_rel(p)} could not be read in this deployment "
                                   f"({type(exc).__name__}: {exc}).") from exc


@functools.lru_cache(maxsize=8)
def _iv_cp_tails(alpha: float, path: str, mtime_ns: int, size: int) -> tuple:
    # cp_tails is ~1500 beta quantiles; computed once per alpha and per
    # version of the marginals file, as the paper itself computes it once.
    db = _paperIV_depbounds()
    return tuple(db.cp_tails(list(_paperIV_marginals()), alpha=alpha))


def _scalar(name: str, v: Any, default: Optional[float] = None) -> float:
    if v is None:
        if default is None:
            raise BadRequest(f"{name} is required")
        return default
    x = _num(v)
    if x is None or not math.isfinite(x):
        raise BadRequest(f"{name} must be a finite number")
    return x


def _iv_rows(name: str) -> list[dict]:
    try:
        return read_table(REPO / "paperIV" / "results" / name)[1]
    except Unavailable:
        return []


def floor_defaults() -> dict:
    import inspect
    db = _paperIV_depbounds()
    X = _paperIV_marginals()
    r1 = _iv_rows("r1_delta_adv.csv")
    pilot = _iv_rows("e4_delta_adv.csv")
    presets = [{"label": f"R1 pooled, FPR {r['fpr']}", "fpr": r["fpr"],
                "delta_adv_m": r["delta_pooled_m"], "source": "paperIV/results/r1_delta_adv.csv",
                "provenance": r.get("provenance")} for r in r1] + \
              [{"label": f"pilot, FPR {r['fpr']}", "fpr": r["fpr"],
                "delta_adv_m": r["delta_adv_cal_m"], "source": "paperIV/results/e4_delta_adv.csv",
                "provenance": None} for r in pilot]
    nets = sorted({(r["theta_net"], r["net_tube"]) for r in _iv_rows("e4_soundness.csv")
                   if _num(r.get("net_tube")) is not None},
                  key=lambda tn: _num(tn[0]) or 0.0)
    reference = [{k: r.get(k) for k in ("fpr", "m", "theta_net", "delta_adv",
                                        "s_available_m", "floor_cp_sim")}
                 for r in _iv_rows("r5_floor_sensitivity.csv")]
    alpha = inspect.signature(db.cp_tails).parameters["alpha"].default
    return {
        "alpha_default": alpha,
        "delta_adv_presets": presets,
        "net_presets": [{"theta_net_s": tn, "net_m": net,
                         "source": "paperIV/results/e4_soundness.csv (net_tube)"}
                        for tn, net in nets],
        "marginals": [{"name": k, "n": int(len(x)), "max_m": float(x.max())}
                      for k, x in zip(IV_MARGINALS, X)],
        "marginal_summary": _iv_rows("e3_marginal_summary.csv"),
        "reference": reference,
        "limits": {"m_max": MAX_FLOOR_M, "cp_grid_step_m": db.STEP,
                   "cp_grid_max_m": db.S_MAX},
        "formula": "s = m - delta_adv - net;  floor = 1 - p(s),  "
                   "p(s) >= Pr[gnss + fault + env > s] over every coupling",
        "source": "paperIV/experiments/depbounds.py, paperIV/results/e3_marginals.npz, "
                  "r1_delta_adv.csv, e4_delta_adv.csv, e4_soundness.csv, "
                  "r5_floor_sensitivity.csv",
    }


def floor(req: dict) -> dict:
    """1 - p(s) at s = m - delta_adv - net, two ways, both depbounds.py's:

    union_bound     the standard (union) bound on the empirical marginals --
                    a point estimate of the worst-case tail
    pbar_union_cp   the same bound on simultaneous Clopper-Pearson upper tails
                    (cp_tails) -- valid with probability >= 1 - alpha

    The Rearrangement Algorithm bound (ra_bound) is not offered: it is a
    bisection over repeated rearrangements, seconds per call, and the paper
    itself reports the CP union bound as its finite-sample floor.
    """
    m = _scalar("m", req.get("m"))
    dadv = _scalar("delta_adv", req.get("delta_adv"))
    net = _scalar("net", req.get("net"), 0.0)
    alpha = _scalar("alpha", req.get("alpha"), 0.05)
    if not 0 < m <= MAX_FLOOR_M:
        raise BadRequest(f"m must lie in (0, {MAX_FLOOR_M:g}] metres")
    if dadv < 0 or net < 0:
        raise BadRequest("delta_adv and net must be >= 0")
    if not 0 < alpha < 1:
        raise BadRequest("alpha must lie in (0, 1)")

    db = _paperIV_depbounds()
    X = _paperIV_marginals()
    s = m - dadv - net
    if s <= 0:
        # No room left for any benign perturbation: the bound is 1, floor 0.
        p_u = p_cp = 1.0
    else:
        p_u = float(db.union_bound(list(X), s))
        p, mt, sz = _iv_marginals_path()
        p_cp = float(db.pbar_union_cp(list(_iv_cp_tails(alpha, str(p), mt, sz)), s))
    p_u, p_cp = min(1.0, max(0.0, p_u)), min(1.0, max(0.0, p_cp))
    notes = ["union_bound is evaluated on the empirical marginals: a point "
             "estimate of the worst-case tail, not a guarantee. pbar_union_cp "
             "replaces each marginal tail by its simultaneous Clopper-Pearson "
             f"upper bound, so it is a valid bound with probability >= {1 - alpha:g} "
             "-- the finite-sample floor."]
    if s > db.S_MAX:
        notes.append(f"s exceeds the CP split grid (S_MAX = {db.S_MAX:g} m), so "
                     f"pbar_union_cp is evaluated at {db.S_MAX:g} m: still valid, "
                     "conservative.")
    return {
        "inputs": {"m": m, "delta_adv": dadv, "net": net, "alpha": alpha},
        "s": s,
        "union_bound": p_u,
        "floor_union": 1.0 - p_u,
        "pbar_union_cp": p_cp,
        "floor_cp": 1.0 - p_cp,
        "confidence": 1.0 - alpha,
        "marginals": {k: int(len(x)) for k, x in zip(IV_MARGINALS, X)},
        "provenance": "sim",
        "note": " ".join(notes),
        "formula": "s = m - delta_adv - net;  floor = 1 - p(s)",
        "source": "paperIV/experiments/depbounds.py (union_bound, cp_tails, "
                  "pbar_union_cp), paperIV/results/e3_marginals.npz",
    }
