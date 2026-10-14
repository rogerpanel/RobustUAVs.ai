#!/usr/bin/env python3
"""E6 -- aggregate the MARL runs (rliable-style statistics).

Per method: interquartile mean (IQM) over (train seed x eval seed) runs with a
95% stratified-bootstrap confidence interval (strata = train seeds), plus, for
methods that observed zero violations, the exact one-sided 95% Clopper-Pearson
upper bound on the per-agent-step violation rate given the total exposure in
agent-steps (training and evaluation reported separately).
Outputs: results/e6_main.csv, results/e6_curves.csv
(`--dir e5_marl_N48` aggregates another run directory into e6_main_e5_marl_N48.csv)
"""
from __future__ import annotations

import csv
import glob
import sys
from pathlib import Path

import numpy as np
from scipy.stats import beta

sys.path.insert(0, str(Path(__file__).resolve().parent))
from certcmdp.certificate import OUT  # noqa: E402
from certcmdp.env import EnvConfig  # noqa: E402

RES = OUT / "e5_marl"
METRICS = ("r_cert", "r_nom", "viol", "exposure", "switches", "cov_ratio")


def iqm(x):
    x = np.sort(np.asarray(x, float))
    n = x.size
    lo, hi = int(np.floor(0.25 * n)), int(np.ceil(0.75 * n))
    return float(x[lo:hi].mean()) if hi > lo else float(x.mean())


def strat_boot(groups, fn=iqm, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    keys = list(groups)
    stats = []
    for _ in range(n):
        s = []
        for k in keys:
            g = groups[k]
            s.extend(g[rng.integers(0, len(g), len(g))])
        stats.append(fn(s))
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def cp_upper(k, n, a=0.05):
    return float(beta.ppf(1 - a, k + 1, n - k)) if k < n else 1.0


def read(path):
    with open(path) as fh:
        return list(csv.DictReader(fh))


def main(sub="e5_marl"):
    cfg = EnvConfig()
    RES = OUT / sub
    suffix = "" if sub == "e5_marl" else f"_{sub}"
    rows = []
    by = {}
    for p in sorted(glob.glob(str(RES / "*_eval.csv"))):   # includes references_eval.csv
        for r in read(p):
            by.setdefault(r["method"], []).append(r)
    train_viol = {}
    for p in glob.glob(str(RES / "*_train.csv")):
        name = Path(p).name.rsplit("_s", 1)[0]
        tr = read(p)
        steps = int(tr[-1]["env_steps"]) * int(tr[-1].get("N") or cfg.N)
        train_viol.setdefault(name, [0, 0])
        train_viol[name][0] += int(tr[-1]["cum_violations"])
        train_viol[name][1] += steps
    for m, rs in sorted(by.items()):
        out = {"method": m, "n_runs": len(rs), "n_train_seeds": len({r["train_seed"] for r in rs})}
        for k in METRICS:
            vals = np.array([float(r[k]) for r in rs])
            groups = {}
            for r in rs:
                groups.setdefault(r["train_seed"], []).append(float(r[k]))
            groups = {g: np.asarray(v) for g, v in groups.items()}
            lo, hi = strat_boot(groups)
            out[f"{k}_iqm"] = iqm(vals)
            out[f"{k}_lo"] = lo
            out[f"{k}_hi"] = hi
        def per_run(r):     # agent-steps behind one evaluation row
            return int(r.get("eval_B") or 16) * cfg.horizon * int(r.get("N") or cfg.N)
        eval_steps = sum(per_run(r) for r in rs)
        k_eval = int(round(sum(float(r["viol"]) * per_run(r) for r in rs)))
        out["eval_agent_steps"] = eval_steps
        out["eval_violations"] = k_eval
        out["eval_viol_cp95"] = cp_upper(k_eval, eval_steps)
        base = m.replace("+proj", "")
        if base in train_viol and "+proj" not in m:
            k, n = train_viol[base]
            out["train_agent_steps"] = n
            out["train_violations"] = k
            out["train_viol_cp95"] = cp_upper(k, n)
        else:
            out["train_agent_steps"] = out["train_violations"] = out["train_viol_cp95"] = ""
        rows.append(out)
    with (OUT / f"e6_main{suffix}.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    # learning curves: mean and min/max across seeds, per update
    curves = []
    names = sorted({Path(p).name.rsplit("_s", 1)[0] for p in glob.glob(str(RES / "*_train.csv"))})
    for m in names:
        runs = [read(p) for p in sorted(glob.glob(str(RES / f"{m}_s*_train.csv")))]
        L = min(len(r) for r in runs)
        for u in range(L):
            rc = np.array([float(r[u]["r_cert"]) for r in runs])
            vi = np.array([float(r[u]["viol"]) for r in runs])
            cv = np.array([float(r[u]["cum_violations"]) for r in runs])
            curves.append({"method": m, "update": u + 1, "env_steps": int(runs[0][u]["env_steps"]),
                           "r_cert_mean": rc.mean(), "r_cert_lo": rc.min(), "r_cert_hi": rc.max(),
                           "viol_mean": vi.mean(), "cum_viol_mean": cv.mean(),
                           "n_seeds": len(runs)})
    if curves:
        with (OUT / f"e6_curves{suffix}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(curves[0]))
            w.writeheader(); w.writerows(curves)
    for r in rows:
        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()
               if k.endswith("_iqm") or k in ("method", "n_runs", "train_violations", "eval_violations")})


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="e5_marl")
    main(ap.parse_args().dir)
