"""The follow-on papers, shown working rather than only answered.

Each calculator in papers.py returns one verdict. This module returns the
steps in between, the same computation swept across an input, and the record
of how a published result was produced, so a reader can see where a number
comes from and probe it:

  Paper I    the budget written out step by step; rho swept over any input,
             with the exact point where the verdict flips; every signature
             scheme on a transport, each run through the same budget
  Paper II   one paper's path through the pipeline (search, two screeners,
             sampling, full text, two coders, adjudication); coder agreement
             recomputed live for any filtered selection with the paper's own
             reliability functions
  Paper III  the count profile behind the deficiency; the optimal attack
             replayed one collapse at a time; a Monte Carlo check of the
             i.i.d. lift against its exact value
  Paper IV   the split of the slack that attains the floor, term by term;
             the floor under independent and comonotone coupling beside the
             any-coupling bound; the floor swept over m, delta_adv or net,
             with the paper's own sensitivity rows; the three marginal tails

Everything calls the papers' own code (papers.py loads it) or reads their
committed files. Where a value is located by repeating a paper's
minimisation (the attaining split in Paper IV), the repeated minimum is
checked against the paper's function on every call and the request fails
rather than show a split that does not reproduce it.
"""
from __future__ import annotations

import csv
import functools
import importlib.util
import math
import re
import sys
from pathlib import Path
from typing import Any, Optional

from . import papers
from .papers import (BadRequest, Unavailable, REPO, _num, _finite, _rel, read_table,
                     _paper_imports, _scalar)

MAX_SWEEP = 61
MAX_TRIALS = 20000
MAX_GRID_SHOW = 40          # eligibility matrix is returned for N, M <= this


# ============================================================== Paper I ===

def budget_steps(out: dict) -> list[dict]:
    """The budget inequality written out with the values budget() used."""
    C = papers._paperI_constants()
    u = out["inputs"]
    theta, delta = u["theta_s"]["value"], u["delta_s"]["value"]
    dauth, gamma = u["delta_auth_s"]["value"], u["gamma_m_s"]["value"]
    L, Tc, m = u["L"]["value"], u["T_c_s"]["value"], u["alert_limit_m"]["value"]
    E, rho = out["amplification"], out["rho_m"]
    if u["delta_s"].get("provenance") == "user":
        d_expr = f"typed directly: Δ = {delta:g} s (θ = {theta:g} s is not used)"
    else:
        d_expr = (f"Δ = H · min(θ, S_SLACK) = {C.H} · min({theta:g}, {C.S_SLACK:g}) "
                  f"= {delta:g} s")
    steps = [
        {"step": "worst undetected delay (parent's Lemma 1)", "expr": d_expr,
         "value": delta, "unit": "s", "source": u["delta_s"].get("source")},
        {"step": "authentication delay", "expr": (u["delta_auth_s"].get("note")
                                                  or u["delta_auth_s"].get("source") or ""),
         "value": dauth, "unit": "s", "source": u["delta_auth_s"].get("source")},
        {"step": "total delay the certificate must absorb",
         "expr": f"Δ + Δ_auth = {delta:g} + {_g(dauth)}", "value": _finite(delta + dauth),
         "unit": "s"},
        {"step": "delay-to-position rate", "expr": u["gamma_m_s"].get("note") or "",
         "value": gamma, "unit": "m/s", "source": u["gamma_m_s"].get("source")},
        {"step": "error amplification over the horizon",
         "expr": f"e^(L·T_c) = e^({L:g}·{Tc:g})", "value": E, "unit": "×"},
        {"step": "certified tube radius",
         "expr": f"ρ = (Δ + Δ_auth) · γ · e^(L·T_c) = {_g(delta + dauth)} · {gamma:g} · {E:.4g}",
         "value": rho, "unit": "m"},
        {"step": "verdict",
         "expr": f"ρ {'≤' if out['pass'] else '>'} m = {m:g} m → "
                 f"{'certified' if out['pass'] else 'not certified'}",
         "value": out["margin_m"], "unit": "m margin"},
        {"step": "authentication budget left at this Δ, γ, m",
         "expr": f"m / (γ · e^(L·T_c)) − Δ = {m:g} / ({gamma:g} · {E:.4g}) − {delta:g}",
         "value": out["dauth_budget_s"], "unit": "s"},
    ]
    return steps


def _g(x: float) -> str:
    return "∞" if x is None or (isinstance(x, float) and math.isinf(x)) else f"{x:g}"


SWEEPABLE_I = {
    "theta_s": "θ, detector operating point (s)",
    "delta_auth_s": "Δ_auth, authentication delay (s)",
    "gamma_m_s": "γ, delay-to-position rate (m/s)",
    "L": "L, local Lipschitz constant (1/s)",
    "T_c_s": "T_c, certification horizon (s)",
    "alert_limit_m": "m, alert limit (m)",
}


def _grid(lo: float, hi: float, n: int) -> list[float]:
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


def _sweep_args(req: dict, allowed: dict) -> tuple[str, float, float, int]:
    vary = req.get("vary")
    if vary not in allowed:
        raise BadRequest(f"vary must be one of {sorted(allowed)}")
    lo, hi = _scalar("lo", req.get("lo")), _scalar("hi", req.get("hi"))
    n = int(_scalar("n", req.get("n"), 31))
    if not 2 <= n <= MAX_SWEEP:
        raise BadRequest(f"n must lie in [2, {MAX_SWEEP}]")
    if not hi > lo:
        raise BadRequest("hi must be greater than lo")
    return vary, lo, hi, n


def budget_sweep(req: dict) -> dict:
    """rho across one input, every other input as in the request.

    Each point is a full budget() call. Where the verdict changes between two
    grid points, the crossing is located by bisection on the same function,
    so the reported threshold is the budget's own, not an interpolation."""
    vary, lo, hi, n = _sweep_args(req, SWEEPABLE_I)
    base = {k: v for k, v in (req.get("base") or {}).items() if v is not None}
    notes = []
    if vary == "theta_s" and "delta_s" in base:
        base.pop("delta_s")
        notes.append("Δ typed directly was dropped so that θ drives Δ through Lemma 1.")
    if vary == "delta_auth_s" and base.get("scheme"):
        notes.append("Δ_auth is swept directly; the chosen scheme's γ_a still applies.")

    def run(x):
        return papers.budget({**base, vary: x})

    pts = []
    for x in _grid(lo, hi, n):
        r = run(x)
        pts.append({"x": x, "rho_m": r["rho_m"], "alert_limit_m": r["alert_limit_m"],
                    "margin_m": r["margin_m"], "pass": r["pass"]})
    flips = []
    for a, b in zip(pts, pts[1:]):
        if a["pass"] != b["pass"]:
            x0, x1 = a["x"], b["x"]
            p0 = a["pass"]
            for _ in range(60):
                mid = 0.5 * (x0 + x1)
                if run(mid)["pass"] == p0:
                    x0 = mid
                else:
                    x1 = mid
            flips.append({"x": 0.5 * (x0 + x1),
                          "from": "certified" if p0 else "not certified",
                          "to": "not certified" if p0 else "certified"})
    return {"vary": vary, "label": SWEEPABLE_I[vary], "points": pts, "flips": flips,
            "notes": notes, "sweepable": SWEEPABLE_I,
            "source": "paperI budget (papers.budget) evaluated at every point; "
                      "crossings by bisection on the same function"}


def budget_schemes(req: dict) -> dict:
    """Every signature scheme on a transport, each through the same budget."""
    base = {k: v for k, v in (req or {}).items()
            if v is not None and k not in ("scheme", "delta_auth_s")}
    transport = base.get("transport") or "can"
    rows_all = papers._dauth_rows()
    if not rows_all:
        raise Unavailable("paperI/results/dauth.csv")
    transports = sorted({r["transport"] for r in rows_all})
    if transport not in transports:
        raise BadRequest(f"transport must be one of {transports}")
    unauth = papers.budget({k: v for k, v in base.items() if k != "transport"})
    rows = [{"scheme": "none (unauthenticated)", "dauth_ms": 0.0, "rho_m": unauth["rho_m"],
             "pass": unauth["pass"], "margin_m": unauth["margin_m"], "benefit_m": None,
             "rate_feasible": None, "pq": None}]
    for r in rows_all:
        if r["transport"] != transport:
            continue
        out = papers.budget({**base, "scheme": r["scheme"], "transport": transport})
        un = out.get("unauthenticated") or {}
        rows.append({"scheme": r["scheme"], "dauth_ms": _finite(_num(r["dauth_cert_ms"])),
                     "rho_m": out["rho_m"], "pass": out["pass"], "margin_m": out["margin_m"],
                     "benefit_m": un.get("benefit_m"),
                     "rate_feasible": r.get("rate_feasible"), "pq": r.get("pq")})
    rows[1:] = sorted(rows[1:], key=lambda x: (_num(x["rho_m"]) is None,
                                                _num(x["rho_m"]) or 0.0))
    return {"transport": transport, "transports": transports, "rows": rows,
            "alert_limit_m": unauth["alert_limit_m"],
            "note": "benefit = ρ unauthenticated (γ_u) − ρ authenticated (γ_a, + Δ_auth): "
                    "positive means authentication pays at this margin",
            "source": "paperI/results/dauth.csv, each row through papers.budget"}


# ============================================================= Paper II ===

FIELDS_II = ("tier", "component", "scope", "modality", "perturbation", "assumption",
             "evidence")


def _reliability():
    exp = REPO / "paperII" / "experiments"
    src = exp / "reliability.py"
    if not src.exists():
        raise Unavailable("paperII/experiments/reliability.py")
    name = "_robustuavs_paperII_reliability"
    if name in sys.modules:
        return sys.modules[name]
    try:
        with _paper_imports(exp):
            spec = importlib.util.spec_from_file_location(name, src)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001
        sys.modules.pop(name, None)
        raise Unavailable("paperII/experiments/reliability.py",
                          f"Paper II's reliability.py could not be imported "
                          f"({type(exc).__name__}: {exc}).") from exc
    return mod


def _study(table: str) -> dict:
    """Which files belong to the study a coded table comes from."""
    c = REPO / "paperII" / "corpus"
    m = re.fullmatch(r"snow(\d+)_\w+", table or "")
    if m:
        k = m.group(1)
        s = c / "snowball"
        return {"name": f"snowballing iteration {k}", "key": "cid",
                "C1": f"snow{k}_C1", "C2": f"snow{k}_C2", "final": f"snow{k}_final",
                "decisions": s / f"iter{k}_decisions.csv", "reasons": {},
                "sample": s / f"iter{k}_coding_sample.csv",
                "fulltext": s / f"iter{k}_fulltext_status.csv",
                "adj_glob": f"ADJ_S{k}ADJ*.csv"}
    if (table or "").startswith("full"):
        return {"name": "full study", "key": "cid",
                "C1": "full_C1", "C2": "full_C2", "final": "full_final",
                "decisions": c / "screening" / "decisions.csv",
                "reasons": {"L1": c / "screening" / "screen_L1.csv",
                            "L2": c / "screening" / "screen_L2.csv"},
                "sample": c / "coding_sample.csv", "fulltext": c / "fulltext_status.csv",
                "adj_glob": "ADJ_ADJ*.csv"}
    return {"name": "pilot", "key": "gid", "C1": "C1", "C2": "C2", "final": "ADJ",
            "decisions": None, "reasons": {}, "sample": None, "fulltext": None,
            "adj_glob": None}


@functools.lru_cache(maxsize=32)
def _index(path: str, mtime_ns: int, key: str) -> dict:
    _, rows = read_table(Path(path))
    return {str(r.get(key)): r for r in rows}


def _lookup(p: Optional[Path], key: str, ident: str) -> Optional[dict]:
    if p is None or not p.is_file():
        return None
    return _index(str(p), p.stat().st_mtime_ns, key).get(ident)


def _codes_table(name: str) -> dict:
    tables = papers._corpus_tables(REPO / "paperII" / "corpus")
    if name not in tables:
        return {}
    p = tables[name]
    _, rows = read_table(p)
    key = "gid" if rows and "gid" in rows[0] else "cid"
    return {str(r[key]): r for r in rows}


def paper_trace(ident: str, table: Optional[str] = None) -> dict:
    """One paper's record at every stage the study put it through."""
    if not ident or not re.fullmatch(r"[A-Za-z0-9_]+", ident):
        raise BadRequest("id must be a cid (O…) or a pilot gid (G…)")
    if table in (None, ""):
        table = "ADJ" if ident.startswith("G") else "full_final"
    st = _study(table)
    c = REPO / "paperII" / "corpus"
    stages: list[dict] = []
    sources: list[str] = []

    if st["key"] == "gid":
        meta = _lookup(c / "corpus_index.csv", "gid", ident)
        if meta is None:
            raise BadRequest(f"no pilot paper {ident!r}")
        stages.append({"stage": "selected for the pilot", "outcome": "included",
                       "detail": {k: meta.get(k) for k in ("bibkey", "year", "venue", "title")}})
        sources.append("paperII/corpus/corpus_index.csv")
        title, year, venue, doi = meta.get("title"), meta.get("year"), meta.get("venue"), None
    else:
        meta = papers._cid_metadata(c).get(ident)
        if meta is None:
            raise BadRequest(f"no candidate {ident!r} in the search or snowballing files")
        title, year, venue, doi = meta.get("title"), meta.get("year"), meta.get("venue"), meta.get("doi")
        found = meta.get("found_by") or "search"
        detail = {"found_by": found, "records merged": meta.get("n_records"),
                  "openalex": meta.get("openalex")}
        if meta.get("direction"):
            detail["snowballing direction"] = meta.get("direction")
        stages.append({"stage": "identified", "outcome": "candidate", "detail": detail})
        dec = _lookup(st["decisions"], "cid", ident)
        if dec is not None:
            detail = {"screener L1": _yn(dec.get("L1")), "screener L2": _yn(dec.get("L2")),
                      "batch": dec.get("batch")}
            if dec.get("stratum"):
                detail["stratum"] = dec.get("stratum")
            for who, p in st["reasons"].items():
                rr = _lookup(p, "cid", ident)
                if rr and rr.get("reason"):
                    detail[f"{who} reason"] = rr.get("reason")
            stages.append({"stage": "title and abstract screening",
                           "outcome": "included" if _yn(dec.get("include")) == "include"
                           else "excluded",
                           "detail": detail})
            sources.append(_rel(st["decisions"]))
        else:
            stages.append({"stage": "title and abstract screening",
                           "outcome": "not in the screened set",
                           "detail": {"note": "the long tail was screened by sample; this record "
                                              "was not drawn"}})
        smp = _lookup(st["sample"], "cid", ident)
        if smp is not None:
            stages.append({"stage": "drawn for full-text coding", "outcome": "sampled",
                           "detail": {"stratum": smp.get("stratum"), "draw order": smp.get("order"),
                                      "sampling weight": smp.get("weight")}})
            sources.append(_rel(st["sample"]))
        ft = _lookup(st["fulltext"], "cid", ident)
        if ft is not None:
            stages.append({"stage": "full text", "outcome": ft.get("status"),
                           "detail": {"source": ft.get("source"), "characters": ft.get("chars")}})
            sources.append(_rel(st["fulltext"]))

    c1, c2, fin = (_codes_table(st["C1"]).get(ident), _codes_table(st["C2"]).get(ident),
                   _codes_table(st["final"]).get(ident))
    fields = ["eligible", "elig_reason", "class", *FIELDS_II[:5], "lifts", *FIELDS_II[5:], "note"]
    if c1 or c2 or fin:
        rows = []
        for f in fields:
            a = (c1 or {}).get(f)
            b = (c2 or {}).get(f)
            v = (fin or {}).get(f)
            if a in (None, "") and b in (None, "") and v in (None, ""):
                continue
            rows.append({"field": f, "C1": a, "C2": b, "final": v,
                         "agree": None if f in ("elig_reason", "note") else _same(f, a, b)})
        stages.append({"stage": "coded by two coders independently", "outcome":
                       f"{sum(1 for r in rows if r['agree'] is False)} field(s) disagree",
                       "codes": rows})
        sources += [f"codes_{st['C1']}", f"codes_{st['C2']}"]
        adj = []
        if st["adj_glob"]:
            for p in sorted((c / "coding").glob(st["adj_glob"])):
                for r in read_table(p)[1]:
                    if str(r.get("cid")) == ident:
                        adj.append({"field": r.get("field"), "value": r.get("value"),
                                    "rationale": r.get("rationale"), "file": _rel(p)})
        elif st["key"] == "gid":
            p = c / "adjudication.csv"
            if p.is_file():
                adj = [{"field": r.get("field"), "value": r.get("value"),
                        "rationale": r.get("rationale"), "file": _rel(p)}
                       for r in read_table(p)[1] if str(r.get("gid")) == ident]
        stages.append({"stage": "adjudication", "outcome":
                       (fin or {}).get("resolved_by") or ("adjudicated" if adj else
                                                          "no disagreement to resolve"),
                       "adjudications": adj})
    else:
        stages.append({"stage": "full-text coding", "outcome": "not coded",
                       "detail": {"note": "not in this study's coded tables"}})
    return {"id": ident, "table": table, "study": st["name"], "title": title, "year": year,
            "venue": venue, "doi": doi, "stages": stages,
            "source": ", ".join(dict.fromkeys(sources))}


def _cell(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _yn(v: Any) -> Optional[str]:
    x = _num(v)
    return None if x is None else ("include" if x >= 1 else "exclude")


def _lifts(v: Any) -> frozenset:
    s = str(v or "").strip()
    return frozenset() if s in ("", "none") else frozenset(x.strip() for x in s.split(";") if x.strip())


def _same(f: str, a: Any, b: Any) -> Optional[bool]:
    if a is None or b is None:
        return None
    if f == "lifts":
        return _lifts(a) == _lifts(b)
    if f == "eligible":
        return _num(a) == _num(b)
    return str(a).strip() == str(b).strip()


def agreement(table: Optional[str] = None, filters: Optional[dict] = None,
              year_min: Optional[int] = None, year_max: Optional[int] = None) -> dict:
    """Coder agreement recomputed for exactly the papers the filters select.

    Same rules as paperII/experiments/reliability.py:run -- eligibility over
    every selected paper, the coded fields over papers both coders found
    eligible -- and the same functions (percent_agreement, cohen_kappa). With
    no filter on the full study the result reproduces the committed
    reliability_full_C1_full_C2.csv, which is returned beside it."""
    R = _reliability()
    sel = papers.corpus(table=table, filters=filters, year_min=year_min, year_max=year_max)
    st = _study(sel["table"])
    A, B = _codes_table(st["C1"]), _codes_table(st["C2"])
    if not A or not B:
        raise Unavailable(f"paperII/corpus/codes_{st['C1']}.csv")
    key = sel["key"]
    ids = [str(r[key]) for r in sel["rows"] if str(r[key]) in A and str(r[key]) in B]
    rows = []
    full = "eligible" in next(iter(A.values()))
    fin = _codes_table(st["final"])

    def stat(field, a, b, n):
        if n == 0:
            return {"field": field, "n": 0, "agree": None, "kappa": None, "disagree": 0}
        return {"field": field, "n": n, "agree": round(R.percent_agreement(a, b), 4),
                "kappa": round(R.cohen_kappa(a, b), 4),
                "disagree": sum(1 for x, y in zip(a, b) if x != y)}

    coded = ids
    if full:
        a = [A[g]["eligible"] for g in ids]
        b = [B[g]["eligible"] for g in ids]
        rows.append(stat("eligible", a, b, len(ids)))
        coded = [g for g in ids if _num(A[g]["eligible"]) == 1 and _num(B[g]["eligible"]) == 1]
    for f in (["class"] if full else []) + list(R.FIELDS):
        a = [_cell(A[g].get(f)) for g in coded]
        b = [_cell(B[g].get(f)) for g in coded]
        rows.append(stat(f, a, b, len(coded)))
    a = [sorted(_lifts(A[g].get("lifts"))) for g in coded]
    b = [sorted(_lifts(B[g].get("lifts"))) for g in coded]
    rows.append(stat("lifts (as a set)", [";".join(x) for x in a], [";".join(x) for x in b],
                     len(coded)))

    dis = []
    for g in ids:
        for f in (["eligible"] if full else []) + (["class"] if full else []) + list(R.FIELDS) + ["lifts"]:
            if f != "eligible" and full and g not in coded:
                continue
            x, y = A[g].get(f), B[g].get(f)
            if not _same(f, x, y):
                dis.append({key: g, "field": f, "C1": x, "C2": y,
                            "final": (fin.get(g) or {}).get(f)})
    committed = None
    p = REPO / "paperII" / "results" / f"reliability_{st['C1']}_{st['C2']}.csv"
    if p.is_file():
        committed = [{k: r.get(k) for k in ("field", "n", "agree", "kappa")}
                     for r in read_table(p)[1]]
    return {"table": sel["table"], "study": st["name"], "coders": [st["C1"], st["C2"]],
            "n_selected": len(ids), "n_coded_both_eligible": len(coded), "rows": rows,
            "disagreements": dis[:300], "n_disagreements": len(dis),
            "committed": committed, "committed_source": _rel(p) if committed else None,
            "filters": sel["filters"],
            "source": "paperII/experiments/reliability.py (percent_agreement, cohen_kappa) on "
                      f"codes_{st['C1']}.csv and codes_{st['C2']}.csv"}


# ============================================================ Paper III ===

def certify_working(req: dict) -> dict:
    """The deficiency's count profile, and the optimal attack replayed.

    Lemma 1: sort tasks by alpha; n_k counts agents with rho <= alpha_(k);
    d = max_k (k - n_k)^+. Proposition 3: the adversary's best b collapses are
    the b smallest-rho agents. The replay removes those agents one at a time,
    recomputes the deficiency on what is left with the paper's deficiency(),
    checks it equals worst_case_deficiency(b), and reassigns with
    nested_greedy_fast."""
    import numpy as np
    out = papers.certify(req)
    comb = papers._paperIII("certcmdp.combinatorics")
    r = np.asarray(out["rho"], float)
    a = np.asarray(out["alpha"], float)
    N, M = len(r), len(a)
    prof = out["count_profile"]
    a_sorted = out["alpha_sorted"]
    gaps = [k + 1 - n for k, n in enumerate(prof)]
    kstar = int(np.argmax(gaps)) + 1 if gaps else None
    profile = [{"k": k + 1, "alpha_k": a_sorted[k], "n_k": prof[k], "k_minus_n_k": gaps[k]}
               for k in range(M)]

    order = np.argsort(r, kind="stable")
    replay = []
    for b in range(0, min(N, 20) + 1):
        gone = order[:b]
        keep = np.setdiff1d(np.arange(N), gone)
        d_left = int(comb.deficiency(r[keep], a)) if keep.size else M
        d_wc = int(comb.worst_case_deficiency(r, a, b))
        if d_left != d_wc:
            raise RuntimeError(f"replay mismatch at b={b}: deficiency of the remaining "
                               f"agents {d_left} != worst_case_deficiency {d_wc}")
        assign = np.full(N, -1, dtype=int)
        if keep.size:
            assign[keep] = comb.nested_greedy_fast(r[keep], a)
        replay.append({"b": b, "collapsed": [int(i) for i in gone],
                       "deficiency": d_left, "covered": M - d_left,
                       "assignment": [int(x) for x in assign]})
    elig = None
    if N <= MAX_GRID_SHOW and M <= MAX_GRID_SHOW:
        elig = [[bool(r[i] <= a[j]) for j in range(M)] for i in range(N)]
    out.update({
        "profile": profile, "k_star": kstar,
        "profile_note": "tasks sorted by alert limit; n_k agents can serve the k tightest; "
                        "if k > n_k the k tightest tasks cannot all be held (Hall), so "
                        "d = max_k (k − n_k)⁺",
        "replay": replay,
        "replay_note": "Proposition 3: the optimal attack collapses the b smallest-ρ agents "
                       "(the only ones that can serve the tightest tasks); each row's "
                       "deficiency is recomputed on the remaining agents and checked against "
                       "worst_case_deficiency(b)",
        "eligibility_matrix": elig,
    })
    return out


def lift_simulate(req: dict) -> dict:
    """Monte Carlo check of the lift: draw fleets with i.i.d. certificate levels
    and count how often every task can be covered (batch_deficiency == 0)."""
    import numpy as np
    from scipy.stats import beta as _beta
    exact = papers.lift(req)
    cert = papers._paperIII("certcmdp.certificate")
    comb = papers._paperIII("certcmdp.combinatorics")
    N, a, q = exact["N"], np.asarray(exact["alpha"], float), np.asarray(exact["q"], float)
    trials = int(_scalar("trials", req.get("trials"), 4000))
    seed = int(_scalar("seed", req.get("seed"), 7))
    if not 100 <= trials <= MAX_TRIALS:
        raise BadRequest(f"trials must lie in [100, {MAX_TRIALS}]")
    levels = np.asarray(list(cert.ALERT_LIMITS) + [math.inf], float)
    rng = np.random.default_rng(seed)
    lv = rng.choice(len(levels), size=(trials, N), p=q / q.sum())
    rho = levels[lv]
    d = comb.batch_deficiency(rho, a)
    full = (d == 0)
    k = int(full.sum())
    lo = 0.0 if k == 0 else float(_beta.ppf(0.025, k, trials - k + 1))
    hi = 1.0 if k == trials else float(_beta.ppf(0.975, k + 1, trials - k))
    checkpoints = sorted({int(round(x)) for x in np.geomspace(20, trials, 30)})
    cum = np.cumsum(full)
    running = [{"trials": t, "p_hat": float(cum[t - 1] / t)} for t in checkpoints]
    examples = [{"levels_m": [None if math.isinf(x) else float(x) for x in rho[i]],
                 "deficiency": int(d[i])} for i in range(min(5, trials))]
    return {"N": N, "alpha": exact["alpha"], "q": exact["q"], "q_levels": exact["q_levels"],
            "trials": trials, "seed": seed, "covered_fleets": k,
            "p_hat": k / trials, "ci95": [lo, hi], "p_exact": exact["p_full"],
            "inside_ci": bool(lo <= exact["p_full"] <= hi),
            "running": running, "examples": examples,
            "deficiency_histogram": {str(int(v)): int((d == v).sum()) for v in np.unique(d)},
            "note": "each agent's certificate level is drawn independently with the "
                    "probabilities q (ρ at that alert limit; 'above all' = no task); a fleet "
                    "is fully covered when batch_deficiency is 0. The interval is "
                    "Clopper–Pearson 95 %.",
            "source": "paperIII/experiments/certcmdp/combinatorics.py:batch_deficiency, "
                      "e2_degradation.py:p_full_iid"}


# ============================================================= Paper IV ===

def _tails_at(x, t: float) -> float:
    return float((x > t).mean())


def _cp_argmin(U, s: float, db) -> tuple[float, tuple[int, int, int]]:
    """The split pbar_union_cp minimises over, located by the same loop."""
    import numpy as np
    G = min(int(np.floor(s / db.STEP + 1e-9)) + 1, db.G_GRID)
    Ug, Uf, Ue = U
    best, arg = math.inf, (0, 0, 0)
    for i in range(G):
        j = np.arange(G - i)
        tot = Ug[i] + Uf[j] + Ue[G - 1 - i - j]
        jj = int(tot.argmin())
        if float(tot[jj]) < best:
            best, arg = float(tot[jj]), (i, jj, G - 1 - i - jj)
    return min(1.0, best), arg


def _union_argmin(X, s: float, grid: int = 200) -> tuple[float, tuple[float, float, float]]:
    """The split union_bound minimises over, located by the same loop."""
    import numpy as np
    srt = [np.sort(x) for x in X]
    surv = lambda i, t: 1.0 - np.searchsorted(srt[i], t, side="right") / len(srt[i])  # noqa: E731
    ts = np.linspace(0, s, grid + 1)
    best, arg = math.inf, (0.0, 0.0, s)
    for t1 in ts:
        t2 = ts[ts <= s - t1]
        val = surv(0, t1) + surv(1, t2) + surv(2, s - t1 - t2)
        k = int(val.argmin())
        if float(val[k]) < best:
            best, arg = float(val[k]), (float(t1), float(t2[k]), float(s - t1 - t2[k]))
    return min(1.0, best), arg


def floor_working(req: dict) -> dict:
    """The floor with its attaining split and the coupling comparison."""
    out = papers.floor(req)
    db = papers._paperIV_depbounds()
    X = papers._paperIV_marginals()
    s, alpha = out["s"], out["inputs"]["alpha"]
    names = papers.IV_MARGINALS
    res: dict[str, Any] = {**out}
    if s > 0:
        pu, split_u = _union_argmin(X, s)
        if abs(pu - out["union_bound"]) > 1e-12:
            raise RuntimeError(f"union split does not reproduce union_bound ({pu} vs "
                               f"{out['union_bound']})")
        p, mt, sz = papers._iv_marginals_path()
        U = list(papers._iv_cp_tails(alpha, str(p), mt, sz))
        pc, (i, j, k) = _cp_argmin(U, s, db)
        if abs(pc - out["pbar_union_cp"]) > 1e-12:
            raise RuntimeError(f"CP split does not reproduce pbar_union_cp ({pc} vs "
                               f"{out['pbar_union_cp']})")
        idx = (i, j, k)
        res["split_cp"] = [{"source": n, "s_i_m": idx[q] * db.STEP,
                            "empirical_tail": _tails_at(X[q], idx[q] * db.STEP),
                            "cp_upper_tail": float(U[q][idx[q]])}
                           for q, n in enumerate(names)]
        res["split_union"] = [{"source": n, "s_i_m": split_u[q],
                               "empirical_tail": _tails_at(X[q], split_u[q])}
                              for q, n in enumerate(names)]
        p_ind = float(db.indep_tail(list(X), s))
        p_com = float(db.comon_tail(list(X), s))
    else:
        res["split_cp"] = res["split_union"] = []
        p_ind = p_com = 1.0
    res["couplings"] = [
        {"coupling": "independent", "p_exceed": p_ind, "floor": 1 - p_ind,
         "how": "depbounds.indep_tail: Monte Carlo, 400,000 draws, seed 1"},
        {"coupling": "comonotone (all move together)", "p_exceed": p_com, "floor": 1 - p_com,
         "how": "depbounds.comon_tail: quantile sum"},
        {"coupling": "any coupling, empirical marginals", "p_exceed": out["union_bound"],
         "floor": out["floor_union"], "how": "depbounds.union_bound"},
        {"coupling": f"any coupling, valid w.p. ≥ {1 - alpha:g}", "p_exceed": out["pbar_union_cp"],
         "floor": out["floor_cp"], "how": "depbounds.pbar_union_cp on cp_tails"},
    ]
    res["split_note"] = ("the bound splits the slack s into one share per source and adds "
                         "the three tail probabilities Pr[X_i > s_i]; the floor uses the "
                         "split that makes the sum smallest. Located by repeating the "
                         "paper's minimisation, checked against its value on this call.")
    return res


SWEEPABLE_IV = {"m": "m, alert limit (m)", "delta_adv": "δ_adv, stealth budget (m)",
                "net": "net, network tube (m)"}


def floor_sweep(req: dict) -> dict:
    vary, lo, hi, n = _sweep_args(req, SWEEPABLE_IV)
    n = min(n, 41)
    base = {k: v for k, v in (req.get("base") or {}).items() if v is not None}
    pts = []
    for x in _grid(lo, hi, n):
        r = papers.floor({**base, vary: x})
        pts.append({"x": x, "s": r["s"], "floor_union": r["floor_union"],
                    "floor_cp": r["floor_cp"]})
    ref = []
    if vary == "m" and base.get("delta_adv") is not None:
        # r5 rows name the network tube by theta_net; e4_soundness.csv maps it to metres.
        net_of = {0.0: 0.0, **{_num(r["theta_net"]): _num(r["net_tube"])
                               for r in papers._iv_rows("e4_soundness.csv")
                               if _num(r.get("theta_net")) is not None
                               and _num(r.get("net_tube")) is not None}}
        want_net = float(base.get("net") or 0.0)
        for row in papers._iv_rows("r5_floor_sensitivity.csv"):
            row_net = net_of.get(_num(row.get("theta_net")))
            if (_num(row.get("delta_adv")) is not None and row_net is not None
                    and abs(row_net - want_net) < 1e-6
                    and abs(_num(row["delta_adv"]) - float(base["delta_adv"])) < 1e-6):
                ref.append({"x": _num(row.get("m")), "floor_cp": _num(row.get("floor_cp_sim")),
                            "theta_net": row.get("theta_net"), "fpr": row.get("fpr")})
    return {"vary": vary, "label": SWEEPABLE_IV[vary], "points": pts, "reference": ref,
            "reference_source": "paperIV/results/r5_floor_sensitivity.csv (rows at this δ_adv)"
            if ref else None,
            "source": "papers.floor at every point (depbounds.union_bound, pbar_union_cp)"}


def marginal_tails(alpha: Optional[float] = None) -> dict:
    """Pr[X > t] for each benign source, empirical and CP upper, on the CP grid."""
    import numpy as np
    db = papers._paperIV_depbounds()
    X = papers._paperIV_marginals()
    a = 0.05 if alpha is None else _scalar("alpha", alpha)
    p, mt, sz = papers._iv_marginals_path()
    U = papers._iv_cp_tails(a, str(p), mt, sz)
    tmax = float(min(db.S_MAX, max(float(np.quantile(x, 0.999)) for x in X) * 1.2))
    idx = np.arange(0, int(tmax / db.STEP) + 1, max(1, int(tmax / db.STEP / 80)))
    out = []
    for name, x, u in zip(papers.IV_MARGINALS, X, U):
        out.append({"source": name, "n": int(len(x)),
                    "quantiles_m": {q: float(np.quantile(x, float(q))) for q in
                                    ("0.5", "0.9", "0.99", "0.999")},
                    "max_m": float(x.max()),
                    "points": [{"t": float(i * db.STEP), "empirical": _tails_at(x, i * db.STEP),
                                "cp_upper": float(u[i])} for i in idx]})
    return {"alpha": a, "marginals": out,
            "source": "paperIV/results/e3_marginals.npz; depbounds.cp_tails"}
