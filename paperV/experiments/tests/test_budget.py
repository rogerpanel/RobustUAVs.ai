"""Budget levels against Paper IV (runbook P1.3)."""
import budget as B
import constants as C


def test_net_tube_matches_paper_iv_macro():
    tex = (C.REPO / "paperIV/manuscript/numbers.tex").read_text()
    line = [l for l in tex.splitlines() if "nNetTubeQuarter" in l][0]
    macro = float(line.split("{")[-1].rstrip("}"))
    assert abs(B.net_tube(0.25) - 2.65) <= 0.005
    assert abs(B.net_tube(0.25) - macro) <= 0.005


def test_delta_adv_sources():
    assert B.delta_adv(0.05, "r1") == 5.463
    assert B.delta_adv(0.05, "pilot") == 4.371
    assert B.delta_adv(0.10, "r1") == 5.038


def test_levels_ordered():
    lv = B.level_values()
    assert lv["b0"] == 0.0
    assert lv["b0"] <= lv["b1"] <= lv["b2"] <= lv["b3"]
    assert abs(lv["b1"] - 5.463) < 1e-12


def test_s_star_union_dominates_ra():
    # the union bound is looser than the sharp RA bound, so its s*(eps) is at least as large
    assert B.s_star(0.05, "union") >= B.s_star(0.05, "ra") - 1e-6
