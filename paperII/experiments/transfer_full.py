#!/usr/bin/env python3
"""Amendment 5: the transfer table extended to the full study.

Rows
  - the pilot's 17 classes, with the states fixed in the pilot (results/class_states.csv);
  - the classes added in the full study (classes.csv, added = "full study";
    members in corpus/new_class_map.csv), with states derived from the
    full-study codes by the pilot's rule: modal (scope, modality), modal
    perturbation, intrinsic obligations of every lift used by at least half of
    the members, and the evidenced (SE/SEC) share -- here weighted by stratum
    (evidenced_share_full, given for every class with full-study members);
  - a "<class> (field)" variant for a pilot class whose weighted modal state in
    the full study differs from its pilot state and that has at least 5 coded
    full-study members.
Every class is checked: results/class_state_check.csv lists the pilot state
and the full-study modal state side by side.

Outputs  results/class_states_full.csv, results/transfer_table_full.csv,
         results/class_state_check.csv
Usage    python3 transfer_full.py
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from corpus_analysis import CLASS_PERT_OVERRIDE, TYPES
from quantifier import LIFT_OBLIGATIONS, STATISTICAL, transfer

HERE = Path(__file__).resolve().parent
C = HERE.parent / "corpus"
R = HERE.parent / "results"
MIN_VARIANT = 5


def lifts_of(r):
    s = r["lifts"].strip()
    return [] if s in ("", "none") else s.split(";")


def state(mem, w):
    """Pilot rule, weighted: modal state and perturbation, majority lifts, evidenced share."""
    sm, pt, lc = Counter(), Counter(), Counter()
    for r in mem:
        sm[((r["scope"] if r["scope"] != "pop" else "popd"), r["modality"])] += w(r)
        pt[r["perturbation"]] += w(r)
        for L in lifts_of(r):
            lc[L] += w(r)
    tot = sum(w(r) for r in mem)
    intr = list(dict.fromkeys(o for L, x in lc.items() if x >= tot / 2 for o in LIFT_OBLIGATIONS[L]))
    ev = sum(w(r) for r in mem if r["assumption"] in ("SE", "SEC")) / tot
    return sm.most_common(1)[0][0], pt.most_common(1)[0][0], intr, ev, sm


def main() -> int:
    csv.field_size_limit(10 ** 9)
    st = {r["metric"]: r["value"] for r in csv.DictReader((R / "screening_status.csv").open())}
    stratum = {r["cid"]: r["stratum"] for r in csv.DictReader((C / "coding_sample.csv").open())}
    allc = list(csv.DictReader((C / "codes_full_final.csv").open()))
    kc = sum(stratum[r["cid"]] == "core" for r in allc)
    N = {"core": int(st["core_included"]) / kc,
         "remainder": int(st["remainder_size"]) * int(st["sample_included"]) / int(st["sample_screened"]) / (len(allc) - kc)}
    w = lambda r: N[stratum[r["cid"]]]  # noqa: E731
    newmap = {r["cid"]: r["class"] for r in csv.DictReader((C / "new_class_map.csv").open())}
    codes = []
    for r in allc:
        if r["eligible"] == "1":
            codes.append({**r, "class": newmap.get(r["cid"], r["class"])})
    classes = list(csv.DictReader((C / "classes.csv").open()))
    pilot = {r["class"]: r for r in csv.DictReader((R / "class_states.csv").open())}
    objs = list(csv.DictReader((C / "objectives.csv").open()))

    rows_state, check, rows = [], [], []
    for c in classes:
        k = c["class"]
        mem = [r for r in codes if r["class"] == k]
        est = round(sum(w(r) for r in mem))
        full = state(mem, w) if mem else None
        if k in pilot:
            p = pilot[k]
            ps = (p["scope"], p["modality"])
            check.append({"class": k, "pilot_state": "/".join(ps), "pilot_n": p["n"], "full_coded": len(mem),
                          "full_est_papers": est, "full_state": "/".join(full[0]) if full else "",
                          "full_state_weights": "; ".join(f"{a}/{b} {round(x)}" for (a, b), x in full[4].most_common(3))
                          if full else "", "same": "" if not full else int(full[0] == ps)})
            rows_state.append({"class": k, "label": c["label"], "source": "pilot state", "scope": ps[0],
                               "modality": ps[1], "perturbation": p["perturbation"],
                               "intrinsic": p["intrinsic"], "evidenced_share": p["evidenced_share"],
                               "evidenced_share_full": round(full[3], 3) if full else "",
                               "n_coded_full": len(mem), "est_papers_full": est})
            if full and full[0] != ps and len(mem) >= MIN_VARIANT:
                pert = CLASS_PERT_OVERRIDE.get(k, (full[1],))[0]
                rows_state.append({"class": f"{k} (field)", "label": c["label"] + " -- full-study modal state",
                                   "source": "full study (variant)", "scope": full[0][0], "modality": full[0][1],
                                   "perturbation": pert, "intrinsic": ";".join(full[2]) or "none",
                                   "evidenced_share": round(full[3], 3), "evidenced_share_full": round(full[3], 3),
                                   "n_coded_full": len(mem), "est_papers_full": est})
        else:
            rows_state.append({"class": k, "label": c["label"], "source": "full study (added)", "scope": full[0][0],
                               "modality": full[0][1], "perturbation": full[1], "intrinsic": ";".join(full[2]) or "none",
                               "evidenced_share": round(full[3], 3), "evidenced_share_full": round(full[3], 3),
                               "n_coded_full": len(mem), "est_papers_full": est})
    for s in rows_state:
        sm = (s["scope"], s["modality"])
        intr = [] if s["intrinsic"] in ("", "none") else s["intrinsic"].split(";")
        for tid, tname, ost, hz, groups in TYPES:
            t = transfer(sm, s["perturbation"], ost, hz)
            nstat = len([o for o in t.obligations if o in STATISTICAL])
            nobj = sum(o["group"] in groups and ((o["scope"] if o["scope"] != "pop" else "popd"), o["modality"]) == ost
                       and o["hazard"] == hz for o in objs)
            rows.append({"class": s["class"], "source": s["source"], "type": tid, "type_label": tname,
                         "verdict": t.verdict, "k": t.k if t.verdict != "X" else "",
                         "k_stat": nstat if t.verdict != "X" else "", "lifts": "+".join(t.lifts),
                         "obligations": ";".join(t.obligations), "intrinsic": ";".join(intr),
                         "deficit": len(set(t.obligations) | set(intr)) if t.verdict != "X" else "",
                         "evidenced_share": s["evidenced_share"], "evidenced_share_full": s["evidenced_share_full"],
                         "est_papers_full": s["est_papers_full"],
                         "n_objectives": nobj})
    for name, data in (("class_states_full.csv", rows_state), ("transfer_table_full.csv", rows),
                       ("class_state_check.csv", check)):
        with (R / name).open("w", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(data[0]), lineterminator="\n"); wr.writeheader(); wr.writerows(data)
    cols = [t[0] for t in TYPES]
    print("class            " + "  ".join(f"{c:>5s}" for c in cols) + "   state      ~papers")
    for s in rows_state:
        cells = [next(f"{x['verdict']}{x['k']}" for x in rows if x["class"] == s["class"] and x["type"] == c) for c in cols]
        print(f"{s['class']:16s} " + "  ".join(f"{c:>5s}" for c in cells) +
              f"   {s['scope']}/{s['modality']:<3} {s['est_papers_full']:>5}  {s['source']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
