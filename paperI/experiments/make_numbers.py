#!/usr/bin/env python3
"""Write paperI/manuscript/numbers.tex: one LaTeX macro per number quoted in
the manuscript, read from the result CSVs. When Claude Code re-runs an
experiment (e.g. replaces a literature cycle count with an STM32H7
measurement), re-running this script updates every sentence that quotes it.
"""
from __future__ import annotations

import csv
import math

from constants import E, OUT

MS = OUT.parent / "manuscript"


def rd(name):
    with (OUT / name).open() as fh:
        return list(csv.DictReader(fh))


def pick(rows, **kw):
    for r in rows:
        if all(str(r[k]) == str(v) for k, v in kw.items()):
            return r
    raise KeyError(kw)


def f(x, nd=3):
    x = float(x)
    return f"{x:.{nd}f}"


def main():
    m = {}
    m["Emult"] = f(E, 3)
    g = rd("gamma_ratio.csv")
    sup = pick(g, quantile="1.0")
    p95 = pick(g, quantile="0.95")
    m["GammaU"] = f(sup["gamma_u"], 3)
    m["GammaA"] = f(sup["gamma_a"], 3)
    m["GammaRatio"] = f(sup["ratio"], 2)
    m["GammaRatioP"] = f(p95["ratio"], 2)
    m["GammaRatioPlo"] = f(p95["ratio_lo95"], 2)
    m["GammaRatioPhi"] = f(p95["ratio_hi95"], 2)
    c = rd("crossover.csv")
    for sc, nm in (("headline", "Head"), ("conservative", "Cons"), ("secant", "Sec")):
        r = pick(c, gamma_scenario=sc, theta="0.25", transport="can", scheme="mav2")
        m[f"Ratio{nm}"] = f(r["ratio"], 2)
        m[f"Cop{nm}"] = f(float(r["C_s"]) * 1e3, 0)
        r2 = pick(c, gamma_scenario=sc, theta="0.178", transport="can", scheme="mav2")
        m[f"Cbn{nm}"] = f(float(r2["C_s"]) * 1e3, 0)
    for sk, nm in (("mldsa44", "ML"), ("ed25519", "Ed"), ("mav2", "Mac")):
        r = pick(c, gamma_scenario="conservative", theta="0.25", transport="can", scheme=sk)
        m[f"ThetaCrossCons{nm}"] = f(r["theta_cross_s"], 3)
        r = pick(c, gamma_scenario="headline", theta="0.25", transport="can", scheme=sk)
        m[f"ThetaCrossHead{nm}"] = f(r["theta_cross_s"], 3)
        m[f"RhoA{nm}"] = f(r["rho_a_m"], 2)
    m["RhoU"] = f(pick(c, gamma_scenario="headline", theta="0.25", transport="can",
                       scheme="mav2")["rho_u_m"], 2)
    rc = pick(c, gamma_scenario="conservative", theta="0.25", transport="can", scheme="mldsa44")
    m["RhoAMLCons"] = f(rc["rho_a_m"], 2)

    fr = rd("transport_frames.csv")
    for sk, nm in (("mav2", "Mac"), ("ed25519", "Ed"), ("fndsa512", "Fal"),
                   ("mldsa44", "ML"), ("slhdsa128f", "SLHf"), ("slhdsa128s", "SLHs")):
        r = pick(fr, transport="can", scheme=sk)
        m[f"Rstar{nm}"] = f(r["r_star_u0"], 1)
        m[f"RstarZero{nm}"] = f(r["r_star_u0_0"], 1)
        m[f"Frames{nm}"] = r["extra_frames"]
        m[f"Tx{nm}"] = f(r["tx_ms"], 2)
        r = pick(fr, transport="canfd", scheme=sk)
        m[f"RstarFD{nm}"] = f(r["r_star_u0"], 1)
        m[f"FramesFD{nm}"] = r["extra_frames"]
    m["RstarTesla"] = f(pick(fr, transport="can", scheme="tesla")["r_star_u0"], 1)
    m["UzeroMax"] = f(pick(fr, transport="can", scheme="mav2")["u0"], 3)

    da = rd("dauth.csv")
    for sk, nm in (("mav2", "Mac"), ("ed25519", "Ed"), ("fndsa512", "Fal"), ("mldsa44", "ML"),
                   ("tesla@0.05", "TeslaA"), ("tesla@0.1", "TeslaB"), ("tesla@0.5", "TeslaC")):
        r = pick(da, transport="can", scheme=sk)
        m[f"Dauth{nm}"] = f(r["dauth_ms"], 1)
        m[f"DauthCert{nm}"] = f(r["dauth_cert_ms"], 1)
        m[f"Rtx{nm}"] = f(r["R_tx_ms"], 1)
        r = pick(da, transport="canfd", scheme=sk)
        m[f"DauthCertFD{nm}"] = f(r["dauth_cert_ms"], 1)

    iv = rd("iv_amplification.csv")
    for tr, tn in (("can", ""), ("canfd", "FD")):
        for sk, nm in (("mav2", "Mac"), ("ed25519", "Ed"), ("fndsa512", "Fal"),
                       ("mldsa44", "ML"), ("slhdsa128s", "SLHs")):
            r = pick(iv, transport=tr, scheme=sk, beta="0.2")
            m[f"Rhoiv{tn}{nm}"] = f(r["rho_iv"], 3)
            m[f"Asat{tn}{nm}"] = f(r["bus_share_to_saturate_cpu"], 3)
            am_ = float(r["attacker_bus_max"])
            m[f"Amax{tn}{nm}"] = f(am_, 3) if am_ > 0 else "n/a"

    hz = rd("horizon_crossover.csv")
    for sk, nm in (("mav2", "Mac"), ("ed25519", "Ed"), ("fndsa512", "Fal"), ("mldsa44", "ML"),
                   ("tesla@0.1", "TeslaB"), ("tesla@0.5", "TeslaC"), ("tesla@1", "TeslaD")):
        r = pick(hz, transport="can", scheme=sk, theta="0.25")
        m[f"HzCross{nm}"] = f(r["theta_cross_s"], 3)
        m[f"HzGainOp{nm}"] = f(float(r["benefit_tube_m"]) * 100, 1)  # cm
        m[f"HzLossOp{nm}"] = f(-float(r["benefit_tube_m"]) * 100, 1)  # cm, positive = harm
        r = pick(hz, transport="can", scheme=sk, theta="0.5")
        m[f"HzGainHalf{nm}"] = f(r["benefit_tube_m"], 2)
    r = pick(hz, transport="can", scheme="mav2", theta="0.25")
    m["HzDu"] = f(r["delta_u_m"], 2)
    r = pick(hz, transport="can", scheme="mav2", theta="0.5")
    m["HzDuHalf"] = f(r["delta_u_m"], 2)
    m["HzDaHalfML"] = f(pick(hz, transport="can", scheme="mldsa44", theta="0.5")["delta_a_m"], 2)

    he = rd("horizon_envelopes.csv")
    def env_at(col, d):
        pts = [(float(r["delta"]), float(r[col])) for r in he]
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            if x0 <= d <= x1:
                return y0 + (y1 - y0) * (d - x0) / (x1 - x0)
    m["HzDiffOpCm"] = f(abs(float(pick(hz, transport="can", scheme="mav2", theta="0.25")["delta_a_m"])
                          - float(pick(hz, transport="can", scheme="mav2", theta="0.25")["delta_u_m"])) * 100, 0)
    dr = rd("dead_reckoning_fit.csv")[0]
    m["DRvzero"] = f(dr["v0_m_s"], 3)
    m["DRb"] = f(dr["b_m_s2"], 3)
    m["DRrmse"] = f(dr["rmse_m"], 2)
    m["DRn"] = dr["n"]

    pt = rd("parent_table.csv")
    m["MminU"] = f(pick(pt, m="m_min_unauth")["theta_star_s"], 2)
    m["GammaReq"] = f(pick(pt, m="gamma_req@10")["theta_star_s"], 2)

    from constants import SCHEME
    for sk, nm in (("ed25519", "Ed"), ("fndsa512", "Fal"), ("mldsa44", "ML"),
                   ("slhdsa128f", "SLHf"), ("slhdsa128s", "SLHs"), ("mav2", "Mac")):
        s = SCHEME[sk]
        m[f"Tsign{nm}"] = f(s.t_sign * 1e3, 2)
        m[f"Tver{nm}"] = f(s.t_verify * 1e3, 3)
    m["MLtail"] = f(SCHEME["mldsa44"].sign_tail_factor, 1)

    am = rd("amortisation.csv")
    r = pick(am, transport="can", scheme="mldsa44", k="8")
    m["AmBusMLk"] = f(float(r["bus_util"]) * 100, 1)
    m["AmDauthMLk"] = f(r["dauth_cert_ms"], 0)
    r = pick(am, transport="can", scheme="mldsa44", k="1")
    m["AmBusMLone"] = f(float(r["bus_util"]) * 100, 1)

    sel = rd("selection.csv")
    tot = len(sel)
    inf = sum(1 for r in sel if r["choice"] == "INFEASIBLE")
    m["SelCells"] = str(tot)
    m["SelInfeasible"] = str(inf)

    des = rd("transport_des.csv")
    m["DESn"] = f"{sum(int(r['n']) for r in des):,}".replace(",", "{,}")
    m["DESok"] = "all" if all(r["bound_holds"] == "True" for r in des) else "NOT all"
    m["DESmaxEd"] = f(max(float(r["max_ms"]) for r in des if r["scheme"] == "ed25519"), 2)
    m["RTAEd"] = f(max(float(r["rta_ms"]) for r in des if r["scheme"] == "ed25519"), 2)
    m["DESmaxML"] = f(max(float(r["max_ms"]) for r in des if r["scheme"] == "mldsa44"), 2)
    m["RTAML"] = f(max(float(r["rta_ms"]) for r in des if r["scheme"] == "mldsa44"), 2)
    cl = [r for r in rd("transport_cliff.csv") if r["scheme"] == "mldsa44"]
    cth = float(pick(c, gamma_scenario="headline", theta="0.25", transport="can", scheme="mav2")["C_s"]) * 1e3
    prev = None
    for r in cl:
        if float(r["md1_ms"]) > cth:
            x0, y0 = float(prev["rate_frac"]), float(prev["md1_ms"])
            x1, y1 = float(r["rate_frac"]), float(r["md1_ms"])
            m["MDcross"] = f(x0 + (cth - y0) * (x1 - x0) / (y1 - y0), 2)
            break
        prev = r
    tp = rd("time_push.csv")
    m["PushOne"] = f(float(pick(tp, nu="0.001", tau_fresh_s="60.0")["time_to_denial_s"]) / 3600, 1)
    m["PushTen"] = f(pick(tp, nu="0.01", tau_fresh_s="60.0")["time_to_denial_s"], 0)
    m["PushHundred"] = f(pick(tp, nu="0.1", tau_fresh_s="60.0")["time_to_denial_s"], 0)
    hd = [r for r in sel if r["gamma"] == "headline" and r["regime"] == "delay"]
    rescue = [r for r in hd if r["choice"] not in ("none", "INFEASIBLE")
              and float(r["rho_unauth_m"]) > float(r["m"])]
    m["SelRescue"] = str(len(rescue))
    m["SelHeadDelay"] = str(len(hd))
    m["SelHeadDelayNone"] = str(sum(1 for r in hd if r["choice"] == "none"))
    m["SelHeadDelayInf"] = str(sum(1 for r in hd if r["choice"] == "INFEASIBLE"))
    dn = [r for r in sel if r["gamma"] == "headline" and r["regime"] == "denial"]
    m["SelHeadDenial"] = str(len(dn))
    m["SelHeadDenialInf"] = str(sum(1 for r in dn if r["choice"] == "INFEASIBLE"))
    cd = [r for r in sel if r["gamma"] == "conservative" and r["regime"] == "denial"]
    m["SelConsDenialInf"] = str(sum(1 for r in cd if r["choice"] == "INFEASIBLE"))
    m["SelConsDenial"] = str(len(cd))

    with (MS / "numbers.tex").open("w") as fh:
        fh.write("% AUTO-GENERATED by paperI/experiments/make_numbers.py -- do not edit\n")
        for k, v in sorted(m.items()):
            fh.write(f"\\newcommand{{\\n{k}}}{{{v}}}\n")
    print(f"-> {MS / 'numbers.tex'} ({len(m)} macros)")


if __name__ == "__main__":
    main()
