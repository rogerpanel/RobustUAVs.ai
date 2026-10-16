"""Every constant is tagged; copied values match their sources (runbook P1.3)."""
import csv
import subprocess
import sys

import numpy as np

import constants as C


def test_every_constant_tagged():
    rows = list(csv.DictReader(open(C.RESULTS / "constants_paperV.csv")))
    assert rows
    tags = {"parent", "paperIII", "paperIV", "platform", "model", "assumption", "derived"}
    for r in rows:
        assert r["provenance"] in tags, r
        assert r["value"] not in ("", "nan"), r


def test_l_rho_matches_paper_iii():
    sys.path.insert(0, str(C.REPO / "paperIII" / "experiments"))
    from certcmdp.certificate import KAPPA
    assert abs(C.L_RHO - 5.2958) < 1e-4
    assert abs(C.L_RHO - KAPPA) < 1e-12


def test_copied_values_match_paper_iv():
    src = (C.REPO / "paperIV" / "experiments" / "constants.py").read_text()
    for name, val in (("GAMMA_SUP", C.GAMMA_SUP), ("SLACK_S", C.SLACK_S), ("H_HOPS", C.H_HOPS),
                      ("L_LOC", C.L_LOC), ("U_MAX", C.U_MAX), ("C_DRAG", C.C_DRAG), ("KP, KD", None)):
        assert name in src
    ns = {}
    exec(compile(src, "p4_constants", "exec"), ns)
    assert ns["GAMMA_SUP"] == C.GAMMA_SUP and ns["SLACK_S"] == C.SLACK_S and ns["H_HOPS"] == C.H_HOPS
    assert ns["L_LOC"] == C.L_LOC and ns["U_MAX"] == C.U_MAX and ns["C_DRAG"] == C.C_DRAG
    assert (ns["KP"], ns["KD"]) == (C.KP, C.KD)
    assert tuple(ns["CORRIDOR_M"]) == C.CORRIDOR_M
    for w in (15.0, 30.0):
        assert np.allclose(ns["dryden_lateral"](w), C.dryden_sigma(w))


def test_delta_adv_matches_paper_iv_files():
    rows = {float(r["fpr"]): r for r in csv.DictReader(open(C.REPO / "paperIV/results/r1_delta_adv.csv"))}
    for fpr, v in C.DELTA_ADV_R1.items():
        assert float(rows[fpr]["delta_pooled_m"]) == v
    e4 = list(csv.DictReader(open(C.REPO / "paperIV/results/e4_delta_adv.csv")))
    assert {float(r["delta_adv_cal_m"]) for r in e4} == {C.DELTA_ADV_PILOT}


def test_platform_values():
    src = (C.REPO / "platform/backend/app/uav.py").read_text()
    assert "MAX_FLEET = 12" in src and "NOMINAL_MISSION_S = 70.0" in src and "KAPPA = 0.25" in src
    ns = {}
    start = src.index("ATTACKS: dict")
    # nine attack classes plus nominal
    import ast
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "ATTACKS":
            keys = [k.value for k in node.value.keys]
            assert "none" in keys and len(keys) - 1 == C.NUM_ATTACK_CLASSES
            break
    else:
        raise AssertionError("ATTACKS not found")


def test_engine_tube_and_self_check():
    sys.path.insert(0, str(C.REPO / "certificates"))
    import engine
    r = engine.StalenessGronwallCertificate(L=1.1814).certify_staleness(0.25, 2, 10.0, "campaign_sup")
    assert abs(r.params["tube_m"] - 2.65) <= 0.01
    out = subprocess.run([sys.executable, str(C.REPO / "certificates" / "engine.py")], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-2000:]


def test_dt_satisfies_paper_iii_thm3():
    assert C.DT <= (2.0 - 0.94) / C.L_RHO + 1e-9 or C.DT <= 0.200
