"""Write pgfplots-ready .dat files (whitespace-separated, header row) into paperV/figdata/."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from admissible import TighteningConfig, tightened_area
from constants import RESULTS, FIGDATA, W_BAR_NOM, DELTA_ADV
from plant import make_geometry


def dat(name, df, fmt="%.6g"):
    with open(FIGDATA / name, "w") as fh:
        fh.write(" ".join(df.columns) + "\n")
        for _, r in df.iterrows():
            fh.write(" ".join((fmt % v) if isinstance(v, (float, np.floating, int, np.integer)) and not isinstance(v, bool)
                              else str(v) for v in r.values) + "\n")


def main():
    cells = pd.read_csv(RESULTS / "summary_cells.csv")
    # ---- violation filter ON/OFF bars (main stage)
    m = cells[cells.stage == "main"]
    rows = []
    for N in (4, 12):
        for pl in ("benign", "random", "stall", "oracle_violation", "oracle_denial"):
            on = m[(m.N == N) & (m.planner == pl) & (m.filter_on)]
            off = m[(m.N == N) & (m.planner == pl) & (~m.filter_on)]
            if len(on) and len(off):
                on, off = on.iloc[0], off.iloc[0]
                rows.append(dict(label=f"{pl}-N{N}", N=N, on=on.viol_ep_rate, on_lo=on.viol_ep_lo, on_hi=on.viol_ep_hi,
                                 off=off.viol_ep_rate, off_lo=off.viol_ep_lo, off_hi=off.viol_ep_hi,
                                 svr_on=on.svr, svr_on_cp95=on.svr_cp_upper95, svr_off=off.svr,
                                 eps_on=on.episodes, eps_off=off.episodes))
    dat("violation_onoff.dat", pd.DataFrame(rows))
    # ---- denial vs b_tot
    b = cells[(cells.stage == "budget") & (cells.tag == "budget")]
    geo4 = make_geometry(4)
    full = tightened_area(geo4, 0.0)
    for (N, pl), g in b.groupby(["N", "planner"]):
        g = g.sort_values("b_tot")
        area = [tightened_area(geo4 if N == 4 else make_geometry(12),
                               TighteningConfig(b_tot=x).summary()["beta_terminal"]) /
                tightened_area(geo4 if N == 4 else make_geometry(12), 0.0) for x in g.b_tot]
        out = pd.DataFrame(dict(btot=g.b_tot, denial=g.denial, lo=g.denial_lo, hi=g.denial_hi,
                                denial_filter=g.denial_filter, denial_envelope=g.denial_envelope,
                                fr=g.fr, fr_lo=g.fr_lo, fr_hi=g.fr_hi, ir=g.ir, mcr=g.mcr,
                                area_frac=area, eps=g.episodes))
        dat(f"denial_vs_btot_N{N}_{pl}.dat", out)
    # ---- analytic admissible-set shrinkage (terminal tightening) on a fine grid
    xs = np.linspace(0, 20, 81)
    ar = [tightened_area(geo4, TighteningConfig(b_tot=x).summary()["beta_terminal"]) / tightened_area(geo4, 0.0)
          for x in xs]
    sepreq = [5.0 + 2 * TighteningConfig(b_tot=x).summary()["beta_terminal"] for x in xs]
    dat("admissible_shrinkage.dat", pd.DataFrame(dict(btot=xs, area_frac=ar, sep_required_m=sepreq)))
    # ---- intervention / violation vs mismatch
    mm = cells[cells.stage == "mismatch"]
    for (N, pl), g in mm.groupby(["N", "planner"]):
        g = g.sort_values("w_true")
        dat(f"mismatch_N{N}_{pl}.dat", pd.DataFrame(dict(
            wmult=g.w_true / W_BAR_NOM, ir=g.ir, ir_lo=g.ir_lo, ir_hi=g.ir_hi, fr=g.fr, cont=g.cont_rate,
            viol_ep=g.viol_ep_rate, viol_lo=g.viol_ep_lo, viol_hi=g.viol_ep_hi, svr=g.svr,
            svr_cp95=g.svr_cp_upper95, min_margin=np.minimum(g.min_corridor_margin, g.min_sep_margin),
            eps=g.episodes)))
    # ---- solve-time CDFs
    from aggregate import solve_time_table
    _, allt = solve_time_table()
    for N, L in allt.items():
        if not L:
            continue
        t = np.sort(np.concatenate(L))
        q = np.linspace(0, 1, 201)
        dat(f"solvetime_cdf_N{N}.dat", pd.DataFrame(dict(ms=np.quantile(t, q), cdf=q)))
    # ---- nestedness
    p = RESULTS / "nestedness.csv"
    if p.exists():
        d = pd.read_csv(p)
        g = d.groupby("b_tot").agg(feasible=("feasible", "mean"), transparent=("transparent", "mean"),
                                   dev=("dev", "mean"), n=("instance", "count")).reset_index()
        dat("nestedness.dat", g.rename(columns={"b_tot": "btot"}))
    print("figdata written:", sorted(x.name for x in FIGDATA.iterdir()))


if __name__ == "__main__":
    main()
