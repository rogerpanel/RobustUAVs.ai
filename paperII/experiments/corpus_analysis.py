#!/usr/bin/env python3
"""Corpus distribution, hypothesis tests H1-H4, the transfer table and the
research agenda (Paper II, Secs. VI-IX).

Inputs : ../corpus/codes_ADJ.csv, corpus_index.csv, classes.csv, objectives.csv
Outputs: ../results/distribution.csv, lift_usage.csv, assumption_by_period.csv,
         class_states.csv, transfer_objectives.csv, transfer_table.csv,
         agenda.csv, hypotheses.csv
Stdlib only.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from quantifier import (COVERS, LIFT_OBLIGATIONS, OBLIGATIONS, STATISTICAL,
                        transfer)

HERE = Path(__file__).resolve().parent
C = HERE.parent / "corpus"
R = HERE.parent / "results"
R.mkdir(exist_ok=True)

# Objective *types*: objectives with identical (scope, modality, hazard) form one column.
TYPES = [
    ("T1", "per flight hour", ("poph", "P"), "N", ["TLS", "CONT", "1309"]),
    ("T2", "ODD generalisation", ("popd", "P"), "N", ["GEN"]),
    ("T3", "average error", ("popd", "E"), "N", ["GEN"]),
    ("T4", "per operation", ("op", "A"), "N", ["CV", "NSF", "OOD", "RTA"]),
    ("T5", "security threat", ("op", "A"), "Adv", ["SEC"]),
    ("T6", "local robustness", ("in", "A"), "B", ["ROB"]),
]
# Class-level perturbation overrides (documented in the paper, Sec. IV-E)
CLASS_PERT_OVERRIDE = {"RTA": ("component_any",
                               "Simplex holds for arbitrary behaviour of the monitored component but not for attacks on the monitor inputs")}
COVERS["component_any"] = {"N"}   # arbitrary behaviour of the monitored component; not attacks on the monitor inputs


def wcsv(name, rows, keys=None):
    keys = keys or list(rows[0].keys())
    with open(R / name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})


def lifts_of(r):
    s = r["lifts"].strip()
    return [] if s in ("", "none") else s.split(";")


def main():
    idx = {r["gid"]: r for r in csv.DictReader(open(C / "corpus_index.csv"))}
    codes = {r["gid"]: r for r in csv.DictReader(open(C / "codes_ADJ.csv"))}
    for g, r in codes.items():
        r["year"] = int(idx[g]["year"])
    classes = list(csv.DictReader(open(C / "classes.csv")))
    g2c = {g: c["class"] for c in classes for g in c["gids"].split(";")}
    objs = list(csv.DictReader(open(C / "objectives.csv")))

    H = {}
    allg = list(codes.values())
    H["n_total"] = len(allg)
    H["n_tierA"] = sum(r["tier"] == "A" for r in allg)
    H["n_tierB"] = H["n_total"] - H["n_tierA"]
    H["n_objectives"] = len(objs)
    H["n_classes"] = len(classes)
    H["n_obj_primary"] = sum(o["source_check"] == "primary" for o in objs)

    # ---------------- distribution: tier x component x scope ----------------
    dist = []
    for tier in ("A", "AB"):
        sel = [r for r in allg if tier == "AB" or r["tier"] == "A"]
        for comp in ("perception", "estimation", "control", "planning", "end2end"):
            for sc in ("in", "tr", "op", "popd"):
                n = sum(r["component"] == comp and (r["scope"] if r["scope"] != "pop" else "popd") == sc for r in sel)
                dist.append({"tier": tier, "component": comp, "scope": sc, "n": n})
    wcsv("distribution.csv", dist)

    def share(sel, pred):
        return (sum(pred(r) for r in sel) / len(sel)) if sel else float("nan")

    for tier in ("A", "AB"):
        sel = [r for r in allg if tier == "AB" or r["tier"] == "A"]
        perc = [r for r in sel if r["component"] == "perception"]
        ctrl = [r for r in sel if r["component"] == "control"]
        H[f"h1_{tier}_n_perc"] = len(perc)
        H[f"h1_{tier}_n_ctrl"] = len(ctrl)
        H[f"h1_{tier}_perc_in"] = share(perc, lambda r: r["scope"] == "in")
        H[f"h1_{tier}_ctrl_in"] = share(ctrl, lambda r: r["scope"] == "in")
        H[f"h1_{tier}_ctrl_tr"] = share(ctrl, lambda r: r["scope"] == "tr")
        H[f"h1_{tier}_all_in"] = share(sel, lambda r: r["scope"] == "in")
        H[f"h1_{tier}_perc_pop"] = share(perc, lambda r: r["scope"] == "pop")
    # all perception papers across tiers, the claim H1 is about
    percAB = [r for r in allg if r["component"] == "perception"]
    H["h1_AB_perc_in_count"] = sum(r["scope"] == "in" for r in percAB)

    # ---------------- H2: lifts as obligations ----------------
    lifted = [r for r in allg if lifts_of(r)]
    H["h2_n_lifted"] = len(lifted)
    for s in ("U", "S", "SE", "SEC"):
        H[f"h2_share_{s}"] = share(lifted, lambda r, s=s: r["assumption"] == s)
    H["h2_share_accounted"] = share(lifted, lambda r: r["assumption"] in ("SE", "SEC"))
    H["h2_share_confidence"] = share(lifted, lambda r: r["assumption"] == "SEC")
    per = []
    for lab, lo, hi in (("2017-2021", 2017, 2021), ("2022-2026", 2022, 2026)):
        sel = [r for r in lifted if lo <= r["year"] <= hi]
        row = {"period": lab, "n": len(sel)}
        for s in ("U", "S", "SE", "SEC"):
            row[s] = sum(r["assumption"] == s for r in sel)
        row["accounted_share"] = round(share(sel, lambda r: r["assumption"] in ("SE", "SEC")), 4) if sel else ""
        per.append(row)
        H[f"h2_accounted_{lab[:4]}"] = row["accounted_share"]
        H[f"h2_n_{lab[:4]}"] = len(sel)
    wcsv("assumption_by_period.csv", per)
    lu = Counter(l for r in allg for l in lifts_of(r))
    wcsv("lift_usage.csv", [{"lift": k, "n": lu.get(k, 0)} for k in LIFT_OBLIGATIONS])
    # per-lift accounting: share of papers using lift L whose assumption is evidenced
    for L in LIFT_OBLIGATIONS:
        sel = [r for r in allg if L in lifts_of(r)]
        H[f"h2_{L}_n"] = len(sel)
        H[f"h2_{L}_acc"] = share(sel, lambda r: r["assumption"] in ("SE", "SEC")) if sel else ""

    # ---------------- H3: statistical guarantees ----------------
    for comp in ("perception", "control", "estimation", "end2end"):
        sel = [r for r in allg if r["component"] == comp]
        H[f"h3_{comp}_n_P"] = sum(r["modality"] == "P" for r in sel)
        H[f"h3_{comp}_share_P"] = share(sel, lambda r: r["modality"] == "P")
    H["h3_n_P"] = sum(r["modality"] == "P" for r in allg)
    H["h3_n_rate"] = sum("L_rate" in lifts_of(r) for r in allg)
    H["h3_perc_P_tierA"] = sum(r["modality"] == "P" and r["component"] == "perception" and r["tier"] == "A" for r in allg)

    # ---------------- class states ----------------
    cstates = {}
    crow = []
    for c in classes:
        mem = [codes[g] for g in c["gids"].split(";")]
        sm = Counter(((r["scope"] if r["scope"] != "pop" else "popd"), r["modality"]) for r in mem).most_common(1)[0][0]
        pert = Counter(r["perturbation"] for r in mem).most_common(1)[0][0]
        note = ""
        if c["class"] in CLASS_PERT_OVERRIDE:
            pert, note = CLASS_PERT_OVERRIDE[c["class"]]
        lifts_c = Counter(l for r in mem for l in lifts_of(r))
        intrinsic = []
        for L, n in lifts_c.items():
            if n >= len(mem) / 2:
                intrinsic += LIFT_OBLIGATIONS[L]
        intrinsic = list(dict.fromkeys(intrinsic))
        ev = share(mem, lambda r: r["assumption"] in ("SE", "SEC"))
        cstates[c["class"]] = (sm, pert, intrinsic, ev, len(mem))
        crow.append({"class": c["class"], "label": c["label"], "n": len(mem), "scope": sm[0],
                     "modality": sm[1], "perturbation": pert, "intrinsic": ";".join(intrinsic) or "none",
                     "evidenced_share": round(ev, 3), "note": note})
    wcsv("class_states.csv", crow)

    # ---------------- transfer per objective and per type ----------------
    trows = []
    for c in classes:
        sm, pert, intr, ev, n = cstates[c["class"]]
        for o in objs:
            t = transfer(sm, pert, (o["scope"] if o["scope"] != "pop" else "popd", o["modality"]), o["hazard"])
            trows.append({"class": c["class"], "oid": o["oid"], "group": o["group"], "verdict": t.verdict,
                          "lifts": ";".join(t.lifts), "obligations": ";".join(t.obligations), "k": t.k})
    wcsv("transfer_objectives.csv", trows)

    table = []
    for c in classes:
        sm, pert, intr, ev, n = cstates[c["class"]]
        for tid, tname, ost, hz, groups in TYPES:
            t = transfer(sm, pert, ost, hz)
            nstat = len([o for o in t.obligations if o in STATISTICAL])
            nobj = sum(o["group"] in groups and ((o["scope"] if o["scope"] != "pop" else "popd"), o["modality"]) == ost
                       and o["hazard"] == hz for o in objs)
            table.append({"class": c["class"], "type": tid, "type_label": tname, "verdict": t.verdict,
                          "k": t.k if t.verdict != "X" else "", "k_stat": nstat if t.verdict != "X" else "",
                          "lifts": "+".join(t.lifts), "obligations": ";".join(t.obligations),
                          "intrinsic": ";".join(intr), "deficit": (len(set(t.obligations) | set(intr))
                                                                     if t.verdict != "X" else ""),
                          "evidenced_share": round(ev, 3), "n_class": n, "n_objectives": nobj})
    wcsv("transfer_table.csv", table)
    V = Counter(r["verdict"] for r in table)
    H["tt_cells"] = len(table)
    H["tt_D"], H["tt_L"], H["tt_X"] = V["D"], V["L"], V["X"]
    H["tt_T1_reachable"] = sum(r["type"] == "T1" and r["verdict"] != "X" for r in table)
    H["tt_T1_min_k"] = min(r["k"] for r in table if r["type"] == "T1" and r["verdict"] != "X")
    H["tt_T4_D"] = sum(r["type"] == "T4" and r["verdict"] == "D" for r in table)
    H["tt_T6_D"] = sum(r["type"] == "T6" and r["verdict"] == "D" for r in table)
    # every T1 path spends at least one statistical obligation (Prop. 2 on data)
    H["tt_T1_all_stat"] = int(all(r["k_stat"] >= 1 for r in table if r["type"] == "T1" and r["verdict"] != "X"))
    # H4: how many per-operation (T4) discharges/lifts run through a monitor
    t4 = [r for r in table if r["type"] == "T4" and r["verdict"] != "X"]
    H["h4_T4_reachable"] = len(t4)
    H["h4_T4_via_mon"] = sum("L_mon" in r["lifts"] or r["class"] == "RTA" for r in t4)
    rta = [r for r in table if r["class"] == "RTA" and r["type"] == "T4"][0]
    H["h4_rta_T4_verdict"] = rta["verdict"]
    H["h4_rta_deficit"] = rta["deficit"]
    mon = [r for r in table if r["class"] == "MON" and r["type"] == "T4"][0]
    H["h4_mon_T4_k"] = mon["k"]

    # ---------------- agenda: what is missing, ranked ----------------
    ag = []
    for tid, tname, ost, hz, groups in TYPES:
        col = [r for r in table if r["type"] == tid]
        best = min((r for r in col if r["verdict"] != "X"), key=lambda r: (r["k"], -r["n_class"]), default=None)
        nobj = col[0]["n_objectives"]
        ag.append({"type": tid, "type_label": tname, "n_objectives": nobj,
                   "best_class": best["class"] if best else "none",
                   "best_k": best["k"] if best else "", "best_lifts": best["lifts"] if best else "",
                   "n_category_error": sum(r["verdict"] == "X" for r in col),
                   "n_discharge": sum(r["verdict"] == "D" for r in col)})
    ag.sort(key=lambda r: (-(r["best_k"] or 99) * r["n_objectives"]))
    wcsv("agenda.csv", ag)

    with open(R / "hypotheses.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["key", "value"])
        for k, v in H.items():
            w.writerow([k, round(v, 4) if isinstance(v, float) else v])
    return H, table


if __name__ == "__main__":
    H, table = main()
    for k, v in H.items():
        print(f"{k:28s} {v}")
    print()
    cols = [t[0] for t in TYPES]
    print("class   " + "  ".join(f"{c:>8s}" for c in cols))
    for cls in dict.fromkeys(r["class"] for r in table):
        cells = []
        for c in cols:
            r = [x for x in table if x["class"] == cls and x["type"] == c][0]
            cells.append(f"{r['verdict']}{r['k']}".rjust(8))
        print(f"{cls:7s} " + "  ".join(cells))
