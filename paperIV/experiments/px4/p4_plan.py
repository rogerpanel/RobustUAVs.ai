#!/usr/bin/env python3
"""Mission plans of the pre-registered PX4 experiments (PX4_PREREG.md).

  smoke  2 benign missions with the same seed (replay check), 1 step 5 m, 1 ramp 0.5 m/s
  e0     500 benign calibration missions, seeds 1000-1499, anchor 5 s; 20 replays (seeds 1000-1019)
  e1     naive offsets: step 5 m and ramp 0.5 m/s at t0 = 25 s, 300 each (seeds 5000-5299, 5300-5599)
         plus their benign twins
  e2     transfer of the reduced-order disguise matrix: the 35 optimised attackers of
         results/e2_attackers.csv, NOT re-optimised; primary = attackers 20-24 (full stack, 5 %)
         on 100 missions each, secondary = the other 30 on 50 missions each; seeds 4000-4099
         shared by every attacker, plus their 100 benign twins
  e4neg  negative control: no anchor (C2' broken), ramp 0.5 m/s, 100 missions (seeds 3900-3999) + twins
Writes plans/<name>.jsonl (one mission spec per line).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p4_spec as S  # noqa: E402

RES = HERE.parents[1] / "results"
STEP5 = {"amp": 5.0, "t0": 25.0}
RAMP05 = {"rate": 0.5, "t0": 25.0, "cap": 40.0}


def smoke():
    return [S.mission("smoke_benign_a", "smoke", 1000), S.mission("smoke_benign_b", "smoke", 1000),
            S.mission("smoke_step5", "smoke", 1000, family="step", phys=STEP5),
            S.mission("smoke_ramp05", "smoke", 1000, family="ramp", phys=RAMP05)]


def e0(n=500, n_replay=20):
    specs = [S.mission(f"e0_s{1000 + j}", "e0", 1000 + j) for j in range(n)]
    specs += [S.mission(f"e0_replay_s{1000 + j}", "e0_replay", 1000 + j) for j in range(n_replay)]
    return specs


def e1(n=300):
    specs = []
    for j in range(n):
        a = S.mission(f"e1_step5_s{5000 + j}", "e1", 5000 + j, family="step", phys=STEP5, attacker_id="step5")
        b = S.mission(f"e1_ramp05_s{5300 + j}", "e1", 5300 + j, family="ramp", phys=RAMP05, attacker_id="ramp05")
        specs += [a, b, S.twin(a), S.twin(b)]
    return specs


def e2(n_primary=100, n_secondary=50):
    rows = list(csv.DictReader(open(RES / "e2_attackers.csv")))
    specs = []
    for r in rows:
        aid = int(r["attacker_id"]); fam = r["family"]; u = json.loads(r["params"])
        n = n_primary if 20 <= aid <= 24 else n_secondary
        for j in range(n):
            specs.append(S.mission(f"e2_a{aid}_s{4000 + j}", "e2", 4000 + j, family=fam, u=u, attacker_id=aid))
    tw = {}
    for s in specs:
        t = S.twin(s); tw[t["mid"]] = t
    return specs + list(tw.values())


def e4neg(n=100):
    specs = []
    for j in range(n):
        a = S.mission(f"e4neg_ramp05_s{3900 + j}", "e4neg", 3900 + j, anchor=None, family="ramp", phys=RAMP05,
                      attacker_id="ramp05_noanchor")
        specs += [a, S.twin(a)]
    return specs


def e3eval(n=50, out_dir=None):
    """Best PX4-optimised attacker per family (from the E3 CEM state), on fresh seeds 25000-25049, with twins."""
    out_dir = Path(out_dir or RES / "px4" / "e3")
    f = out_dir / "cem_state_clean.json"
    st = json.loads((f if f.exists() else out_dir / "cem_state.json").read_text())
    specs = []
    for fam, v in st.items():
        u = v["best"][1]
        for j in range(n):
            specs.append(S.mission(f"e3eval_{fam}_s{25000 + j}", "e3eval", 25000 + j, family=fam, u=u,
                                   attacker_id=f"px4cem_{fam}"))
    tw = {}
    for s_ in specs:
        t = S.twin(s_); tw[t["mid"]] = t
    return specs + list(tw.values())


def ta1(anchor=1.0):
    """E5 (PX4_PREREG.md): the design rule at a 1 s re-anchoring interval. Same seeds as the 5 s runs.
      benign calibration     200 missions, seeds 1000-1199
      E2 primary (20-24)     100 missions each, seeds 4000-4099, plus 100 twins
      worst gate-removed     attackers 7, 12, 14, 29 (largest 5 s deviations without the anchor gate),
                             50 missions each, seeds 4000-4049 (twins shared with E2)
      E3 clean attackers     step, ramp, fault mimic, 50 missions each, seeds 25000-25049, plus 50 twins
      naive ramp 0.5 m/s     50 missions, seeds 5300-5349, plus twins"""
    specs = [S.mission(f"ta1_e0_s{1000 + j}", "ta1_e0", 1000 + j, anchor=anchor) for j in range(200)]
    att = {int(r["attacker_id"]): r for r in csv.DictReader(open(RES / "e2_attackers.csv"))}
    for aid, n in [(a, 100) for a in range(20, 25)] + [(a, 50) for a in (7, 12, 14, 29)]:
        for j in range(n):
            specs.append(S.mission(f"ta1_e2_a{aid}_s{4000 + j}", "ta1_e2", 4000 + j, anchor=anchor,
                                   family=att[aid]["family"], u=json.loads(att[aid]["params"]), attacker_id=aid))
    clean = json.loads((RES / "px4" / "e3" / "cem_state_clean.json").read_text())
    for fam in ("step", "ramp", "fault_mimic"):
        for j in range(50):
            specs.append(S.mission(f"ta1_e3_{fam}_s{25000 + j}", "ta1_e3", 25000 + j, anchor=anchor, family=fam,
                                   u=clean[fam]["best"][1], attacker_id=f"px4cem_{fam}"))
    for j in range(50):
        specs.append(S.mission(f"ta1_e1_ramp05_s{5300 + j}", "ta1_e1", 5300 + j, anchor=anchor, family="ramp",
                               phys=RAMP05, attacker_id="ramp05"))
    tw = {}
    for s_ in specs:
        if s_["family"] != "none":
            t = S.twin(s_); tw[t["mid"]] = t
    return specs + list(tw.values())


PLANS = {"smoke": smoke, "e0": e0, "e1": e1, "e2": e2, "e4neg": e4neg, "e3eval": e3eval, "ta1": ta1}

if __name__ == "__main__":
    out = HERE / "plans"; out.mkdir(exist_ok=True)
    for name in (sys.argv[1:] or [k for k in PLANS if k not in ("e3eval", "ta1")]):
        specs = PLANS[name]()
        mids = [s["mid"] for s in specs]
        assert len(mids) == len(set(mids)), f"duplicate mission ids in {name}"
        (out / f"{name}.jsonl").write_text("".join(json.dumps(s) + "\n" for s in specs))
        print(f"{name}: {len(specs)} missions -> plans/{name}.jsonl")
