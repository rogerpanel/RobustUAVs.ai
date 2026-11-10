#!/usr/bin/env python3
"""Tables of the Paper IV PX4 SITL study, from results/px4/<exp>/missions.jsonl.

  calibrate  E0: thresholds (single detector at 1-f, stack at 1-f/4 as in the
             reduced-order model, anchor gate at 0.99), FPR by benign source,
             replay floor (benign mission flown twice with the same seed)
  smoke      injection, anchor fusion and replay diagnostics of the bring-up run
  e1         naive offsets: detection rate per detector at the operating points, ROC
  e2         cross-evaluated disguise matrix in PX4 and the pre-registered reading
  e3         PX4 stealth budget (best CEM attacker per family, fresh seeds)
  e4neg      negative control without the anchor
Every table carries provenance = px4_sitl. Nothing is filled in when an input is
missing: the table is skipped and the reason printed.
Usage: python3 p4_analyze.py [calibrate smoke e1 e2 e3 e4neg]
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE.parents[1] / "results"
PX = Path(__import__("os").environ.get("P4_PX4_RESULTS") or RES / "px4")
FPR_GRID = (0.01, 0.02, 0.05, 0.10, 0.20)
DETS = ("D1", "D2", "D3", "D4")
STACKS = {"D1": ("D1",), "D2": ("D2",), "D3": ("D3",), "D4": ("D4",), "ALL": DETS}
# reduced-order reference values (results/e2x_cross.csv, e2y_no_anchor_gate.csv; attackers 20-24, full stack, 5 %)
REF_GATE = {"step": (0.841, 2.108), "ramp": (0.872, 1.511), "fault_mimic": (0.790, 2.255),
            "gnss_mimic": (0.763, 2.406), "weather_mimic": (0.691, 2.880)}
REF_D2_NOGATE_MAX = 3.383          # largest undetected attack-only deviation under D2 alone, gate removed
REF_DELTA_ADV = {0.01: (4.371, 5.463)}   # pilot and pooled stealth budget (results/r1_delta_adv.csv)


EXCLUDED = {}       # (dir, exp) -> number of missions that were not flown (validity rule, PX4_PREREG.md deviation 1)


def flown(r):
    """Validity rule: the mission is valid iff PX4 was in mission mode (nav_state 3) inside the window.
    Missions that never flew went to Descend/Termination before the window started, at random
    (the same seed flies in another run), independently of the attack."""
    return 3 in (r.get("nav_states") or [])


def _all_rows(d):
    f = PX / d / "missions.jsonl"
    if not f.exists():
        return {}
    out = {}
    for line in f.read_text().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("status") == "ok":
            out[r["mid"]] = r
    return out


def rows(d, exp=None, valid_only=True):
    """ok missions of results directory d (one fleet run); exp filters on the spec's experiment tag;
    missions that were never flown are dropped and counted in EXCLUDED."""
    out = [r for r in _all_rows(d).values() if exp is None or r.get("exp") == exp]
    if not valid_only:
        return out
    bad = [r for r in out if not flown(r)]
    EXCLUDED[(d, exp)] = (len(bad), len(out))
    return [r for r in out if flown(r)]


def write(name, rs):
    if not rs:
        print(f"  {name}: nothing to write"); return
    keys = list(dict.fromkeys(k for r in rs for k in r))
    with open(PX / name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(rs)
    print(f"  wrote results/px4/{name} ({len(rs)} rows)")


def series(d, mid):
    f = PX / d / "series" / f"{mid}.npz"
    return np.load(f) if f.exists() else None


def twin_mid(r):
    return f"twin_{r['exp']}_a{r['anchor_s']}_s{r['seed']}"


_VALID = {}


def attack_only(r, d):
    """sup_t |e_attack(t) - e_twin(t)| after the attack onset (twin flown in the same run d), or None
    when the twin is missing or was not flown (validity rule)."""
    if d not in _VALID:
        _VALID[d] = {m for m, x in _all_rows(d).items() if flown(x)}
    if twin_mid(r) not in _VALID[d] or r["mid"] not in _VALID[d]:
        return None
    a = series(d, r["mid"]); b = series(d, twin_mid(r))
    if a is None or b is None:
        return None
    t = a["t"]; t0 = r.get("attack_t0") or 0.0
    m = t >= t0
    return float(np.max(np.abs(a["e"][m] - b["e"][m]))) if m.any() else 0.0


def qs(v):
    v = [x for x in v if x is not None]
    if not v:
        return {"q50": None, "q95": None, "max": 0.0}
    return {"q50": round(float(np.quantile(v, 0.5)), 3), "q95": round(float(np.quantile(v, 0.95)), 3),
            "max": round(float(np.max(v)), 3)}


def validity_report():
    out = [{"dir": d, "exp": e or "all", "n_ok": n, "n_not_flown": k, "rate": round(k / n, 4) if n else None,
            "provenance": "px4_sitl"} for (d, e), (k, n) in sorted(EXCLUDED.items(), key=str)]
    write("px4_validity.csv", out)


def cal_load():
    f = PX / "calibration.json"
    return json.loads(f.read_text()) if f.exists() else None


def alarm(r, cal, stack, fpr, gate=True):
    th = cal["stack"][str(fpr)] if stack == "ALL" else cal["single"][str(fpr)]
    a = any(r["S" + d[1]] > th[d] for d in STACKS[stack])
    if gate and r.get("anchor_s"):
        a |= r["SA"] > cal["anchor"]
    return a


# ---------------------------------------------------------------------- E0
def calibrate():
    R = rows("e0", "e0")
    if len(R) < 50:
        print(f"calibrate: only {len(R)} E0 missions; need >= 50"); return
    st = {d: np.array([r["S" + d[1]] for r in R]) for d in DETS}
    single = {str(f): {d: float(np.quantile(st[d], 1 - f)) for d in DETS} for f in FPR_GRID}
    stack = {str(f): {d: float(np.quantile(st[d], 1 - f / 4)) for d in DETS} for f in FPR_GRID}
    SA = np.array([r["SA"] for r in R]); stock = np.array([r["Sstk"] for r in R]); sat = np.array([r["Ssat"] for r in R])
    cal = {"n": len(R), "single": single, "stack": stack, "anchor": float(np.quantile(SA, 0.99)),
           "stock_fpr_any": float(np.mean(stock > 0)), "sat_any_fpr": float(np.mean(sat > 0)),
           "sat_q99_s": float(np.quantile(sat, 0.99)), "provenance": "px4_sitl"}
    (PX / "calibration.json").write_text(json.dumps(cal, indent=1))
    print(f"  calibration on {len(R)} benign PX4 missions -> results/px4/calibration.json")
    out = [{"fpr_target": f, "detector": d, "theta": round(single[str(f)][d], 5), "theta_stack": round(stack[str(f)][d], 5),
            "provenance": "px4_sitl"} for f in FPR_GRID for d in DETS]
    write("px4_e0_thresholds.csv", out)
    # FPR at 5 % by benign source present in the mission
    src = []
    for key in ("outage", "jam", "bias_step", "drift", "loe"):
        for present in (True, False):
            sub = [r for r in R if bool(r["benign_meta"][key]) == present]
            if not sub:
                continue
            row = {"source": key, "present": present, "n": len(sub)}
            for d in DETS:
                row[d] = round(float(np.mean([r["S" + d[1]] > single["0.05"][d] for r in sub])), 4)
            row["ALL+gate"] = round(float(np.mean([alarm(r, cal, "ALL", 0.05) for r in sub])), 4)
            row["provenance"] = "px4_sitl"
            src.append(row)
    write("px4_e0_fpr_by_source.csv", src)
    # benign envelope of the mission metric
    md = np.array([r["maxdev"] for r in R])
    write("px4_e0_benign_maxdev.csv", [{"q": q, "maxdev_m": round(float(np.quantile(md, q)), 3), "n": len(R),
                                         "provenance": "px4_sitl"} for q in (0.5, 0.9, 0.95, 0.99, 1.0)])
    replay()
    health("e0", R)


def replay():
    R = {r["mid"]: r for r in rows("e0", "e0")}
    P = {r["mid"]: r for r in rows("e0", "e0_replay")}
    out = []
    for mid, b in P.items():
        a = R.get(mid.replace("e0_replay_", "e0_"))
        if not a:            # one of the pair was not flown (validity rule)
            continue
        sa, sb = series("e0", a["mid"]), series("e0", mid)
        dev = float(np.max(np.abs(sa["e"] - sb["e"]))) if sa is not None and sb is not None else None
        row = {"seed": a["seed"], "sup_e_diff_m": None if dev is None else round(dev, 4),
               "maxdev_a": round(a["maxdev"], 3), "maxdev_b": round(b["maxdev"], 3)}
        for d in DETS + ("A",):
            k = "S" + (d[1] if d != "A" else "A")
            row[f"d{k}"] = round(abs(a[k] - b[k]), 4)
        row["provenance"] = "px4_sitl"
        out.append(row)
    write("px4_e0_replay.csv", out)
    if out:
        v = [r["sup_e_diff_m"] for r in out if r["sup_e_diff_m"] is not None]
        if not v:
            print("  replay floor: series not available"); return
        print(f"  replay floor: median {np.median(v):.3f} m, max {np.max(v):.3f} m over {len(v)} seed pairs")


def health(exp, R):
    n = len(R)
    if not n:
        return
    f = lambda k: int(sum(bool(r.get(k)) for r in R))
    print(f"  {exp}: {n} ok missions; failsafe {f('failsafe')}, disarmed in window {f('disarmed_in_window')}, "
          f"mission restarted after arming {f('mission_restarted_after_arm')}; anchors fused per mission "
          f"median {np.median([r['n_anchor_fused'] for r in R]):.0f} (published {np.median([r['n_anchor_pub'] for r in R]):.0f}); "
          f"cruise speed median {np.median([r.get('along_speed_mps', np.nan) for r in R]):.2f} m/s; "
          f"position resets in {sum(r.get('n_pos_reset', 0) > 0 for r in R)} missions")


def smoke():
    R = {r["mid"]: r for r in rows("smoke")}
    for mid, r in R.items():
        print(f"  {mid}: maxdev {r['maxdev']:.2f} m, offset applied max {r['dmax_applied']:.2f} m, "
              f"S1 {r['S1']:.2f} S2 {r['S2']:.2f} S3 {r['S3']:.1f} S4 {r['S4']:.3f} SA {r['SA']:.2f}, "
              f"anchors {r['n_anchor_fused']}/{r['n_anchor_pub']}, GNSS rejected {r['n_gnss_rejected']}, "
              f"resets {r.get('n_pos_reset')}, fusion stops {r.get('n_gnss_fusion_stops')}, "
              f"speed {r.get('along_speed_mps', float('nan')):.1f} m/s, nav {r['nav_states']}")
    a, b = series("smoke", "smoke_benign_a"), series("smoke", "smoke_benign_b")
    if a is not None and b is not None:
        print(f"  replay (same seed, benign): sup|e_a - e_b| = {np.max(np.abs(a['e'] - b['e'])):.4f} m")
    for mid in ("smoke_step5", "smoke_ramp05"):
        s = series("smoke", mid)
        if s is not None and a is not None:
            print(f"  {mid}: sup|e - e_benign| = {np.max(np.abs(s['e'] - a['e'])):.2f} m; offset at end {s['d'][-1]:.2f} m")


# ---------------------------------------------------------------------- E1
def e1():
    cal = cal_load()
    if not cal:
        print("e1: no calibration"); return
    R = rows("e1", "e1"); E0 = rows("e0", "e0")
    st0 = {d: np.array([r["S" + d[1]] for r in E0]) for d in DETS}
    out, roc = [], []
    for aid in ("step5", "ramp05"):
        sub = [r for r in R if r["attacker_id"] == aid]
        if not sub:
            continue
        for fpr in (0.01, 0.05, 0.10):
            row = {"attack": aid, "fpr": fpr, "n": len(sub)}
            for d in DETS:
                row[d] = round(float(np.mean([r["S" + d[1]] > cal["single"][str(fpr)][d] for r in sub])), 4)
            row["ALL"] = round(float(np.mean([alarm(r, cal, "ALL", fpr, gate=False) for r in sub])), 4)
            row["ALL+gate"] = round(float(np.mean([alarm(r, cal, "ALL", fpr) for r in sub])), 4)
            row["stock_any"] = round(float(np.mean([r["Sstk"] > 0 for r in sub])), 4)
            ao = [attack_only(r, "e1") for r in sub]
            ao = [x for x in ao if x is not None]
            row["attack_only_dev_median_m"] = round(float(np.median(ao)), 3) if ao else None
            row["provenance"] = "px4_sitl"
            out.append(row)
        for d in DETS:
            for q in np.linspace(0, 1, 41):
                th = float(np.quantile(st0[d], q))
                roc.append({"attack": aid, "detector": d, "fpr": round(1 - q, 4),
                            "tpr": round(float(np.mean([r["S" + d[1]] > th for r in sub])), 4), "provenance": "px4_sitl"})
    write("px4_e1_detection.csv", out); write("px4_e1_roc.csv", roc)


# ---------------------------------------------------------------------- E2
def e2():
    cal = cal_load()
    if not cal:
        print("e2: no calibration"); return
    R = rows("e2", "e2")
    by = {}
    for r in R:
        if r["family"] != "none":
            by.setdefault(r["attacker_id"], []).append(r)
    ref = {int(x["attacker_id"]): x for x in csv.DictReader(open(RES / "e2_attackers.csv"))}
    out = []
    for aid, sub in sorted(by.items()):
        fpr = float(ref[aid]["origin_fpr"])
        ao = {r["mid"]: attack_only(r, "e2") for r in sub}
        for stack in STACKS:
            for gate in (True, False):
                st = [r for r in sub if not alarm(r, cal, stack, fpr if stack == "ALL" else 0.05, gate)]
                aos = [ao[r["mid"]] for r in st if ao[r["mid"]] is not None]
                q = qs(aos)
                out.append({"attacker_id": aid, "family": ref[aid]["family"], "origin_stack": ref[aid]["origin_stack"],
                            "origin_fpr": fpr, "stack": stack, "anchor_gate": gate, "n": len(sub),
                            "evasion_rate": round(len(st) / len(sub), 4), "n_stealthy": len(st),
                            "n_with_twin": len(aos), "attack_only_dev_q50": q["q50"], "attack_only_dev_q95": q["q95"],
                            "attack_only_dev_max": round(max(aos), 3) if aos else 0.0,
                            "stealthy_dev_max": round(max(r["maxdev_after"] for r in st), 3) if st else 0.0,
                            "n_twins_missing": sum(v is None for v in ao.values()), "provenance": "px4_sitl"})
    write("px4_e2_cross.csv", out)
    reading(out)


def reading(out):
    """Pre-registered reading of E2 (PX4_PREREG.md, section E2)."""
    cell = lambda aid, stack, gate: next((r for r in out if r["attacker_id"] == aid and r["stack"] == stack
                                          and r["anchor_gate"] == gate), None)
    fams = ["step", "ramp", "fault_mimic", "gnss_mimic", "weather_mimic"]
    a_rows = []
    for k, fam in enumerate(fams):
        c = cell(20 + k, "ALL", True)
        if c is None:
            print("  E2 reading: primary attackers missing"); return
        ev_ok = c["evasion_rate"] >= 0.5
        dev_ok = c["attack_only_dev_max"] <= 2 * REF_GATE[fam][1]
        a_rows.append({"family": fam, "evasion_px4": c["evasion_rate"], "evasion_ro": REF_GATE[fam][0],
                       "dev_px4_m": c["attack_only_dev_max"], "dev_ro_m": REF_GATE[fam][1],
                       "evasion_ge_50pct": ev_ok, "dev_within_2x": dev_ok})
    a_holds = all(r["evasion_ge_50pct"] and r["dev_within_2x"] for r in a_rows)
    d2 = {fam: max((r["attack_only_dev_max"] for r in out if r["family"] == fam and r["stack"] == "D2"
                    and not r["anchor_gate"]), default=0.0) for fam in fams}
    d4 = {fam: max((r["attack_only_dev_max"] for r in out if r["family"] == fam and r["stack"] == "D4"
                    and not r["anchor_gate"]), default=0.0) for fam in fams}
    cap = 2 * REF_D2_NOGATE_MAX
    b1 = all(v <= cap for v in d2.values()); b2 = any(v > cap for v in d4.values())
    res = {"a": {"holds": a_holds, "cells": a_rows},
           "b": {"holds": b1 and b2, "cap_m": cap, "D2_caps_every_family": b1, "some_family_exceeds_cap_under_D4": b2,
                 "D2_max_by_family": d2, "D4_max_by_family": d4},
           "transfer_holds_qualitatively": a_holds and b1 and b2, "provenance": "px4_sitl"}
    (PX / "px4_e2_reading.json").write_text(json.dumps(res, indent=1))
    print(f"  E2 pre-registered reading: (a) {a_holds}, (b) {b1 and b2} "
          f"-> transfer holds qualitatively: {res['transfer_holds_qualitatively']}")


# ---------------------------------------------------------------------- E3
def e3():
    cal = cal_load()
    D3 = "e3eval2" if (PX / "e3eval2" / "missions.jsonl").exists() else "e3eval"
    R = [r for r in rows(D3, "e3eval") if r["family"] != "none"]
    if not cal or not R:
        print("e3: needs calibration and e3eval missions"); return
    out = []
    pooled = []
    for fpr in (0.01, 0.05, 0.10):
        for fam in sorted(set(r["family"] for r in R)):
            sub = [r for r in R if r["family"] == fam]
            st = [r for r in sub if not alarm(r, cal, "ALL", fpr)]
            aos = [attack_only(r, D3) for r in st]; aos = [x for x in aos if x is not None]
            q = qs(aos)
            out.append({"fpr": fpr, "family": fam, "n": len(sub), "evasion_rate": round(len(st) / len(sub), 4),
                        "n_with_twin": len(aos), "attack_only_dev_q50": q["q50"], "attack_only_dev_q95": q["q95"],
                        "attack_only_dev_max": q["max"], "source": D3, "provenance": "px4_sitl"})
        # pooled over the PX4-optimised attackers and the transferred ones (E2), as in the paper
        E2 = rows("e2", "e2")
        aos = [attack_only(r, D3) for r in R if not alarm(r, cal, "ALL", fpr)]
        aos += [attack_only(r, "e2") for r in E2 if r["family"] != "none" and not alarm(r, cal, "ALL", fpr)]
        aos = [x for x in aos if x is not None]
        ref = REF_DELTA_ADV.get(fpr)
        q = qs(aos)
        pooled.append({"fpr": fpr, "delta_adv_px4_m": round(max(aos), 3) if aos else 0.0, "n_stealthy": len(aos),
                       "attack_only_q50_m": q["q50"], "attack_only_q95_m": q["q95"],
                       "delta_adv_ro_pilot_m": ref[0] if ref else None, "delta_adv_ro_pooled_m": ref[1] if ref else None,
                       "provenance": "px4_sitl"})
    write("px4_e3_cem_eval.csv", out); write("px4_e3_delta_adv.csv", pooled)


def e4neg():
    cal = cal_load()
    R = [r for r in rows("e4neg", "e4neg") if r["family"] != "none"]
    if not cal or not R:
        print("e4neg: needs calibration and missions"); return
    aos = [attack_only(r, "e4neg") for r in R]
    st = [not alarm(r, cal, "ALL", 0.05, gate=False) for r in R]
    q = qs(aos)
    out = [{"control": "no anchor, ramp 0.5 m/s", "n": len(R), "evasion_rate": round(float(np.mean(st)), 4),
            "n_with_twin": sum(x is not None for x in aos), "attack_only_dev_median_m": q["q50"],
            "attack_only_dev_q95_m": q["q95"], "attack_only_dev_max_m": q["max"],
            "maxdev_after_median_m": round(float(np.median([r["maxdev_after"] for r in R])), 3),
            "provenance": "px4_sitl"}]
    write("px4_e4neg.csv", out)


def e3select():
    """Deviation 2 (PX4_PREREG.md): the CEM was steered by an objective that included missions that
    were never flown. Re-select, per family, the best of the candidates the CEM evaluated, with the
    objective recomputed on valid missions only and the clean calibration; write cem_state_clean.json."""
    cal = cal_load()
    R = {r["mid"]: r for r in rows("e3")}
    st = json.loads((PX / "e3" / "cem_state.json").read_text())
    clean, table = {}, []
    for fam, v in st.items():
        best = (-1.0, None, None)
        for h in v["hist"]:
            g = h["gen"]
            for c, u in enumerate(h["U"]):
                vals = [R[m]["maxdev_after"] * (not alarm(R[m], cal, "ALL", 0.05))
                        for m in (f"e3_{fam}_g{g}_c{c}_k{j}" for j in range(64)) if m in R]
                if len(vals) >= 8:
                    J = float(np.mean(vals))
                    table.append({"family": fam, "gen": g, "cand": c, "n_valid": len(vals), "J_clean": round(J, 4),
                                  "J_original": round(h["J"][c], 4), "provenance": "px4_sitl"})
                    if J > best[0]:
                        best = (J, u, (g, c))
        clean[fam] = {"best": [best[0], best[1]], "from": best[2], "best_original": v["best"]}
    (PX / "e3" / "cem_state_clean.json").write_text(json.dumps(clean, indent=1))
    write("px4_e3_reselect.csv", table)
    for fam, v in clean.items():
        print(f"  {fam}: clean best J {v['best'][0]:.3f} at gen/cand {v['from']} (original best J {v['best_original'][0]:.3f})")


def calib_from(R):
    st = {d: np.array([r["S" + d[1]] for r in R]) for d in DETS}
    return {"n": len(R),
            "single": {str(f): {d: float(np.quantile(st[d], 1 - f)) for d in DETS} for f in FPR_GRID},
            "stack": {str(f): {d: float(np.quantile(st[d], 1 - f / 4)) for d in DETS} for f in FPR_GRID},
            "anchor": float(np.quantile([r["SA"] for r in R], 0.99)), "provenance": "px4_sitl"}


BOUND_TA = {1.0: 10.24, 5.0: 31.90}     # proved worst case, linear loop, D1 + anchor gate + D_sat, 1 % (results/r8_*)


def ta1():
    """E5: re-anchoring every 1 s. Thresholds recalibrated on the 1 s benign missions; same tables as E2/E3,
    compared with the 5 s results and with the proved bound; pre-registered prediction (PX4_PREREG.md)."""
    D = "ta1"
    B = rows(D, "ta1_e0")
    if len(B) < 50:
        print(f"ta1: only {len(B)} benign missions"); return
    cal = calib_from(B)
    (PX / "calibration_ta1.json").write_text(json.dumps(cal, indent=1))
    md = [r["maxdev"] for r in B]
    print(f"  ta1 calibration on {len(B)} benign missions; anchor gate {cal['anchor']:.2f}; "
          f"benign maxdev q50 {np.median(md):.2f} q95 {np.quantile(md, 0.95):.2f} max {max(md):.2f} m")
    cal5 = cal_load()
    out = []
    for exp in ("ta1_e2", "ta1_e3", "ta1_e1"):
        R = [r for r in rows(D, exp) if r["family"] != "none"]
        for aid in sorted({str(r["attacker_id"]) for r in R}):
            sub = [r for r in R if str(r["attacker_id"]) == aid]
            ao = {r["mid"]: attack_only(r, D) for r in sub}
            for stack in STACKS:
                for gate in (True, False):
                    st = [r for r in sub if not alarm(r, cal, stack, 0.05, gate)]
                    q = qs([ao[r["mid"]] for r in st])
                    out.append({"exp": exp, "attacker_id": aid, "family": sub[0]["family"], "stack": stack,
                                "anchor_gate": gate, "n": len(sub), "evasion_rate": round(len(st) / len(sub), 4),
                                "n_with_twin": sum(ao[r["mid"]] is not None for r in st),
                                "attack_only_dev_q50": q["q50"], "attack_only_dev_q95": q["q95"],
                                "attack_only_dev_max": q["max"], "anchor_s": 1.0, "provenance": "px4_sitl"})
    write("px4_ta1_cross.csv", out)

    def worst(stack, gate, rowsx):
        c = [r for r in rowsx if r["stack"] == stack and r["anchor_gate"] == gate and r["exp"] != "ta1_e1"]
        return max((r["attack_only_dev_max"] for r in c), default=0.0)
    five = list(csv.DictReader(open(PX / "px4_e2_cross.csv"))) if (PX / "px4_e2_cross.csv").exists() else []
    w5 = lambda stack, gate: max((float(r["attack_only_dev_max"]) for r in five if r["stack"] == stack
                                  and r["anchor_gate"] == str(gate)), default=None)
    summ = {"bound_1s_m": BOUND_TA[1.0], "bound_5s_m": BOUND_TA[5.0]}
    for stack in ("D1", "ALL"):
        for gate in (True, False):
            summ[f"worst_{stack}_{'gate' if gate else 'nogate'}_1s_m"] = worst(stack, gate, out)
            summ[f"worst_{stack}_{'gate' if gate else 'nogate'}_5s_m"] = w5(stack, gate)
    summ["P1_D1gate_within_bound"] = summ["worst_D1_gate_1s_m"] <= BOUND_TA[1.0]
    summ["P2_D1gate_smaller_than_5s"] = (summ["worst_D1_gate_5s_m"] is not None
                                         and summ["worst_D1_gate_1s_m"] < summ["worst_D1_gate_5s_m"])
    summ["P2_ALLgate_smaller_than_5s"] = (summ["worst_ALL_gate_5s_m"] is not None
                                          and summ["worst_ALL_gate_1s_m"] < summ["worst_ALL_gate_5s_m"])
    rr = [r for r in out if r["exp"] == "ta1_e1" and r["stack"] == "ALL" and r["anchor_gate"]]
    summ["naive_ramp_1s"] = rr[0] if rr else None
    summ["provenance"] = "px4_sitl"
    (PX / "px4_ta1_summary.json").write_text(json.dumps(summ, indent=1))
    for k, v in summ.items():
        if k != "naive_ramp_1s":
            print(f"  {k}: {v}")


TASKS = {"calibrate": calibrate, "smoke": smoke, "e1": e1, "e2": e2, "e3": e3, "e4neg": e4neg, "e3select": e3select, "ta1": ta1}

if __name__ == "__main__":
    for t in (sys.argv[1:] or TASKS):
        print(f"[{t}]")
        TASKS[t]()
    validity_report()
