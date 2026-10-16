"""Budget levels b_tot over Paper IV quantities (runbook P1.1).

    b_tot(eps, theta, fpr) = e^{L T_c} delta_net(theta) + delta_adv(fpr) + s*(eps)

delta_adv comes from Paper IV R1 (5.463 m at FPR 1% and 5%, 5.038 m at 10%; the pilot
4.371 m only as a sensitivity row). net_tube(theta) = e^{L T_c} gamma_sup H min(theta, SLACK_S)
is re-implemented (Paper IV's module cannot be imported: constants.py collision). s*(eps)
inverts the dependence-sharp union bound (or the RA bound) over Paper IV's committed marginals,
with Paper IV's depbounds.py loaded under a private module name.

Levels: b0 = 0, b1 = delta_adv, b2 = b1 + net_tube(0.1 s), b3 = b2 + s*(0.05).

    python3 budget.py --levels      -> results/budget_levels.csv
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
from functools import lru_cache

import numpy as np

try:
    from . import constants as C
    from .admissible import Tightening
except ImportError:
    import constants as C
    from admissible import Tightening


@lru_cache(maxsize=None)
def _depbounds():
    spec = importlib.util.spec_from_file_location("p4_depbounds", C.REPO / "paperIV/experiments/depbounds.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def delta_adv(fpr=C.FPR_HEADLINE, source="r1"):
    if source == "pilot":
        return C.DELTA_ADV_PILOT
    return C.DELTA_ADV_R1[round(float(fpr), 2)]


def net_tube(theta, gamma=C.GAMMA_SUP, L=C.L_LOC):
    return float(np.exp(L * C.T_C) * gamma * C.H_HOPS * min(theta, C.SLACK_S))


@lru_cache(maxsize=None)
def s_star(eps, method="union"):
    db = _depbounds()
    d = np.load(C.REPO / "paperIV/results/e3_marginals.npz")
    X = [d["gnss"], d["fault"], d["env"]]
    f = (lambda s: db.union_bound(X, s)) if method == "union" else (lambda s: db.ra_bound(X, s, N=1000))
    lo, hi = 0.0, 40.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if f(mid) <= eps:
            hi = mid
        else:
            lo = mid
    return hi


def b_tot(eps=None, theta=None, fpr=C.FPR_HEADLINE, source="r1", method="union"):
    b = delta_adv(fpr, source)
    if theta is not None:
        b += net_tube(theta)
    if eps is not None:
        b += s_star(eps, method)
    return b


def level_values(source="r1"):
    return {"b0": 0.0,
            "b1": b_tot(source=source),
            "b2": b_tot(theta=C.THETA_NET, source=source),
            "b3": b_tot(eps=C.EPS_B3, theta=C.THETA_NET, source=source)}


LEVEL_TEXT = {"b0": "rho_i only", "b1": "delta_adv (Paper IV R1, FPR 5%)",
              "b2": "delta_adv + e^{LT_c} delta_net(0.1 s)", "b3": "b2 + s*(0.05) (union bound)"}


def levels(w_bar=None, delta_bar=C.DELTA_BAR_S, gamma=C.GAMMA_SUP, source="r1"):
    """Rows of results/budget_levels.csv: one per (level, m), with the tightened half-widths.

    half_width_runbook = m - rho_0 - b (the runbook's rule, rho_0 = rho_floor);
    half_width_terminal = m - beta_inf = m - rho_bar - eps_inf - b (what the filter needs at t0);
    dispatchable = half_width_terminal > 0."""
    w_bar = C.load_wbar() if w_bar is None else w_bar
    rows = []
    for lev, b in level_values(source).items():
        for m in C.CORRIDOR_M:
            t = Tightening(w_bar=w_bar, b_tot=b, m=m, delta_bar=delta_bar, gamma=gamma)
            hw_rb = m - t.rho_floor - b
            hw = float(t.half_width()[0])
            rows.append(dict(level=lev, b_tot_m=round(b, 4), m=m, gamma=gamma, delta_bar_s=delta_bar,
                             w_bar=round(w_bar, 4), rho_floor_m=round(t.rho_floor, 4), rho_bar_m=round(t.rho_bar, 4),
                             eps_inf_m=round(t.eps_inf, 4), u_nom=round(t.u_nom, 4),
                             half_width_runbook_m=round(hw_rb, 4), half_width_terminal_m=round(hw, 4),
                             dispatchable_runbook=int(hw_rb > 0), dispatchable=int(hw > 0 and t.u_nom > 0),
                             composition=LEVEL_TEXT[lev], delta_adv_source=source, provenance="derived"))
    return rows


def write_levels(path=None, **kw):
    path = path or C.RESULTS / "budget_levels.csv"
    rows = levels(**kw)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return path, rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", action="store_true")
    a = ap.parse_args()
    if a.levels:
        p, rows = write_levels()
        print("wrote", p)
        for r in rows:
            print(f"{r['level']} b={r['b_tot_m']:7.3f} m={r['m']:4.0f}  runbook hw={r['half_width_runbook_m']:7.3f} "
                  f"terminal hw={r['half_width_terminal_m']:7.3f}  dispatchable={r['dispatchable']}")
