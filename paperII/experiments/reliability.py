#!/usr/bin/env python3
"""Inter-coder reliability for the Paper II coding study (Sec. IV-D).

For every nominal field: percent agreement, Cohen's kappa, Krippendorff's alpha
(nominal, two coders, no missing values), Gwet's AC1 and PABAK, each with a
percentile bootstrap interval over papers.  The set-valued `lifts` field is
scored per lift as a binary presence variable, plus mean Jaccard similarity.

Inputs : ../corpus/codes_<A>.csv, ../corpus/codes_<B>.csv  (same gid set)
Output : ../results/reliability_<A>_<B>.csv
Usage  : python3 reliability.py C1 C2       (default)
Stdlib only.  Includes self-tests against hand-computed values (run with --test).
"""
from __future__ import annotations

import csv
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent / "corpus"
RESULTS = HERE.parent / "results"
FIELDS = ["tier", "component", "scope", "modality", "perturbation", "assumption", "evidence"]
LIFTS = ["L_dyn", "L_hor", "L_gen", "L_op", "L_rate", "L_conc", "L_sup", "L_mon"]


def _cats(a, b):
    return sorted(set(a) | set(b))


def percent_agreement(a, b):
    return sum(x == y for x, y in zip(a, b)) / len(a)


def cohen_kappa(a, b):
    n = len(a)
    po = percent_agreement(a, b)
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in _cats(a, b)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def kripp_alpha_nominal(a, b):
    """Krippendorff's alpha, nominal metric, 2 coders, no missing data."""
    n = len(a)
    vals = list(a) + list(b)
    N = 2 * n
    nc = Counter(vals)
    Do_num = sum(1 for x, y in zip(a, b) if x != y) * 2      # coincidence off-diagonal mass
    Do = Do_num / N
    De = (N * N - sum(v * v for v in nc.values())) / (N * (N - 1))
    return 1.0 if De == 0 else 1 - Do / De


def gwet_ac1(a, b):
    n = len(a)
    cats = _cats(a, b)
    q = len(cats)
    po = percent_agreement(a, b)
    if q < 2:
        return 1.0
    ca, cb = Counter(a), Counter(b)
    pi = {k: (ca[k] + cb[k]) / (2 * n) for k in cats}
    pe = sum(p * (1 - p) for p in pi.values()) / (q - 1)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def pabak(a, b):
    q = max(2, len(_cats(a, b)))
    po = percent_agreement(a, b)
    return (q * po - 1) / (q - 1)


STATS = {"agree": percent_agreement, "kappa": cohen_kappa, "alpha": kripp_alpha_nominal,
         "ac1": gwet_ac1, "pabak": pabak}


def bootstrap(a, b, fn, B=2000, seed=7):
    rng = random.Random(seed)
    n = len(a)
    out = []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        aa, bb = [a[i] for i in idx], [b[i] for i in idx]
        try:
            out.append(fn(aa, bb))
        except ZeroDivisionError:
            continue
    out.sort()
    return out[int(0.025 * len(out))], out[int(0.975 * len(out)) - 1]


def load(coder):
    return {r["gid"]: r for r in csv.DictReader(open(CORPUS / f"codes_{coder}.csv"))}


def lifts_of(r):
    s = r["lifts"].strip()
    return set() if s in ("", "none") else set(s.split(";"))


def run(c1="C1", c2="C2"):
    A, Bc = load(c1), load(c2)
    gids = sorted(set(A) & set(Bc))
    rows = []
    for f in FIELDS + ["scope_x_modality"]:
        if f == "scope_x_modality":
            a = [A[g]["scope"] + "/" + A[g]["modality"] for g in gids]
            b = [Bc[g]["scope"] + "/" + Bc[g]["modality"] for g in gids]
        else:
            a = [A[g][f] for g in gids]
            b = [Bc[g][f] for g in gids]
        row = {"field": f, "n": len(gids)}
        for name, fn in STATS.items():
            row[name] = round(fn(a, b), 4)
            lo, hi = bootstrap(a, b, fn)
            row[name + "_lo"], row[name + "_hi"] = round(lo, 4), round(hi, 4)
        rows.append(row)
    for L in LIFTS:
        a = [int(L in lifts_of(A[g])) for g in gids]
        b = [int(L in lifts_of(Bc[g])) for g in gids]
        row = {"field": "lift:" + L, "n": len(gids)}
        for name, fn in STATS.items():
            row[name] = round(fn(a, b), 4)
            lo, hi = bootstrap(a, b, fn)
            row[name + "_lo"], row[name + "_hi"] = round(lo, 4), round(hi, 4)
        rows.append(row)
    jac = []
    for g in gids:
        x, y = lifts_of(A[g]), lifts_of(Bc[g])
        jac.append(1.0 if not (x | y) else len(x & y) / len(x | y))
    rows.append({"field": "lifts:jaccard_mean", "n": len(gids), "agree": round(sum(jac) / len(jac), 4)})
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"reliability_{c1}_{c2}.csv"
    keys = ["field", "n"] + [k for n in STATS for k in (n, n + "_lo", n + "_hi")]
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})
    # disagreement list for adjudication
    with open(RESULTS / f"disagreements_{c1}_{c2}.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["gid", "field", c1, c2])
        for g in gids:
            for f in FIELDS:
                if A[g][f] != Bc[g][f]:
                    w.writerow([g, f, A[g][f], Bc[g][f]])
            if lifts_of(A[g]) != lifts_of(Bc[g]):
                w.writerow([g, "lifts", A[g]["lifts"], Bc[g]["lifts"]])
    return rows


def _selftest():
    # Cohen's example (2 coders, 2 categories): po=0.7, pe=0.5 -> kappa=0.4
    a = list("YYYYYNNNNN"); b = list("YYYNNNNNYY")
    assert abs(percent_agreement(a, b) - 0.6) < 1e-9
    a = ["Y"] * 20 + ["N"] * 30 + ["Y"] * 5 + ["N"] * 45   # n=100
    b = ["Y"] * 20 + ["N"] * 30 + ["N"] * 5 + ["N"] * 45
    # 2x2: YY=20, YN=5, NY=0? recompute: a Y at 0..19 and 50..54; b Y at 0..19
    k = cohen_kappa(a, b)
    po = 0.95; pe = (0.25 * 0.20 + 0.75 * 0.80)
    assert abs(k - (po - pe) / (1 - pe)) < 1e-9
    # Krippendorff alpha ~ kappa for large n with similar marginals
    al = kripp_alpha_nominal(a, b)
    assert abs(al - k) < 0.02, (al, k)
    # perfect agreement
    assert cohen_kappa(a, a) == 1.0 and kripp_alpha_nominal(a, a) == 1.0 and gwet_ac1(a, a) == 1.0
    # kappa paradox: high agreement, skewed prevalence -> low kappa, high AC1
    a = ["in"] * 95 + ["tr"] * 5; b = ["in"] * 94 + ["tr"] + ["in"] * 4 + ["tr"]
    assert gwet_ac1(a, b) > cohen_kappa(a, b)
    print("reliability self-tests: OK")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _selftest()
        sys.exit(0)
    args = [x for x in sys.argv[1:] if not x.startswith("-")]
    rows = run(*(args or ["C1", "C2"]))
    for r in rows:
        print(f"{r['field']:22s} agree={r.get('agree')}  kappa={r.get('kappa','')}  alpha={r.get('alpha','')}  ac1={r.get('ac1','')}")
