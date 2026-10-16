"""Aggregate per-episode CSVs into per-cell metrics with CIs -> results/summary_cells.csv."""
from __future__ import annotations

import numpy as np
import pandas as pd

from constants import RESULTS
from stats import wilson, cp_upper, cp_interval, boot_mean

KEYS = ["tag", "N", "planner", "filter_on", "b_tot", "w_true", "w_assumed", "gamma", "delta_bar", "within",
        "lookahead", "continuation", "nature"]


def load(stages=("main", "hand", "budget", "mismatch", "negative")):
    dfs = []
    for s in stages:
        p = RESULTS / f"episodes_{s}.csv"
        if p.exists():
            d = pd.read_csv(p); d["stage"] = s; dfs.append(d)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def cell_metrics(g):
    ne = len(g)
    ast = int(g.aircraft_steps.sum()); vs = int(g.viol_steps.sum())
    ve = int(g.viol_episode.sum())
    comp = int(g.complete.sum())
    den = ne - comp
    d_f = int((g.denial_cause == "filter").sum()); d_e = int((g.denial_cause == "envelope").sum())
    d_v = int((g.denial_cause == "violation").sum())
    ir_ep = g.interventions / g.aircraft_ticks
    fr_ep = g.fallback_ticks / g.n_ticks
    cr_ep = g.continuation_ticks / g.n_ticks
    out = dict(episodes=ne, aircraft_steps=ast, viol_steps=vs,
               svr=vs / ast if ast else np.nan,
               svr_cp_lo=cp_interval(vs, ast)[0], svr_cp_hi=cp_interval(vs, ast)[1], svr_cp_upper95=cp_upper(vs, ast),
               viol_corridor_steps=int(g.viol_corridor_steps.sum()), viol_sep_steps=int(g.viol_sep_steps.sum()),
               viol_episodes=ve, viol_ep_rate=ve / ne, viol_ep_lo=wilson(ve, ne)[0], viol_ep_hi=wilson(ve, ne)[1],
               inside_assumptions_eps=int(g.inside_assumptions.sum()),
               viol_steps_inside=int(g.viol_steps[g.inside_assumptions == 1].sum()),
               aircraft_steps_inside=int(g.aircraft_steps[g.inside_assumptions == 1].sum()),
               min_corridor_margin=float(g.min_corridor_margin.min()), min_sep_margin=float(g.min_sep_margin.min()),
               ir=float(g.interventions.sum() / g.aircraft_ticks.sum()),
               ir_lo=boot_mean(ir_ep)[1], ir_hi=boot_mean(ir_ep)[2],
               fr=float(g.fallback_ticks.sum() / g.n_ticks.sum()), fr_lo=boot_mean(fr_ep)[1], fr_hi=boot_mean(fr_ep)[2],
               cont_rate=float(g.continuation_ticks.sum() / g.n_ticks.sum()),
               mcr=comp / ne, mcr_lo=wilson(comp, ne)[0], mcr_hi=wilson(comp, ne)[1],
               mcr_k025=float(g.complete_k025.mean()),
               denial=den / ne, denial_lo=wilson(den, ne)[0], denial_hi=wilson(den, ne)[1],
               denial_filter=d_f / ne, denial_filter_lo=wilson(d_f, ne)[0], denial_filter_hi=wilson(d_f, ne)[1],
               denial_envelope=d_e / ne, denial_envelope_lo=wilson(d_e, ne)[0], denial_envelope_hi=wilson(d_e, ne)[1],
               denial_violation=d_v / ne,
               aircraft_reached_frac=float(g.n_reached_dl.sum() / (g.aircraft_ticks / g.n_ticks).sum()),
               mean_dev=boot_mean(g.mean_dev)[0], mean_dev_lo=boot_mean(g.mean_dev)[1],
               mean_dev_hi=boot_mean(g.mean_dev)[2],
               infeasible_ticks=int(g.infeasible_ticks.sum()), verify_fail_ticks=int(g.verify_fail_ticks.sum()),
               fallback_ticks=int(g.fallback_ticks.sum()), uncertified_ticks=int(g.uncertified_ticks.sum()),
               sat_steps=int(g.sat_steps.sum()), rho_over_bar_steps=int(g.rho_over_bar_steps.sum()),
               t_fleet_done_mean=float(g.t_fleet_done.mean()),
               wall_s_mean=float(g.wall_s.mean()))
    return pd.Series(out)


def aggregate(df=None):
    df = load() if df is None else df
    df = df.copy()
    df["theta_key"] = df["theta"].fillna("")
    cells = df.groupby(KEYS + ["stage"], dropna=False).apply(cell_metrics, include_groups=False).reset_index()
    cells.to_csv(RESULTS / "summary_cells.csv", index=False)
    return cells


def time_overhead(df):
    """Benign mission-time overhead ON vs OFF, paired by seed (main stage)."""
    m = df[(df.stage == "main") & (df.planner == "benign")]
    rows = []
    for N in sorted(m.N.unique()):
        on = m[(m.N == N) & (m.filter_on)].set_index("seed").t_fleet_done
        off = m[(m.N == N) & (~m.filter_on)].set_index("seed").t_fleet_done
        j = on.to_frame("on").join(off.to_frame("off"), how="inner").dropna()
        d = (j.on - j.off).values
        mu, lo, hi = boot_mean(d)
        rows.append(dict(N=N, pairs=len(j), overhead_s=mu, lo=lo, hi=hi,
                         overhead_rel=float(np.mean(d / j.off.values)) if len(j) else np.nan,
                         t_off_mean=float(j.off.mean()) if len(j) else np.nan,
                         unpaired_on_incomplete=int(on.isna().sum())))
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "time_overhead.csv", index=False)
    return out


def solve_time_table():
    rows = []
    allt = {4: [], 12: []}
    for s in ("main", "hand", "budget", "mismatch", "negative"):
        p = RESULTS / f"solve_times_{s}.npz"
        if not p.exists():
            continue
        z = np.load(p)
        for k in z.files:
            t = z[k] * 1e3
            N = int(k.split("__")[1][1:])
            allt[N].append(t)
            rows.append(dict(stage=s, cell=k, N=N, n=len(t), p50_ms=np.percentile(t, 50), p95_ms=np.percentile(t, 95),
                             p99_ms=np.percentile(t, 99), max_ms=t.max()))
    for N, L in allt.items():
        if L:
            t = np.concatenate(L)
            rows.append(dict(stage="ALL", cell=f"ALL_N{N}", N=N, n=len(t), p50_ms=np.percentile(t, 50),
                             p95_ms=np.percentile(t, 95), p99_ms=np.percentile(t, 99), max_ms=t.max(),
                             frac_over_250ms=float(np.mean(t > 250)), frac_over_500ms=float(np.mean(t > 500))))
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "solve_times.csv", index=False)
    return out, allt


if __name__ == "__main__":
    df = load()
    c = aggregate(df)
    print(c.shape)
    print(time_overhead(df))
    print(solve_time_table()[0].tail(3))
