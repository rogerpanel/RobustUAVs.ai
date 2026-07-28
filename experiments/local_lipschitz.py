#!/usr/bin/env python3
"""P1(b): is the Gronwall radius too tight because L_hat=1.01 is loose?

Three estimates on the TRAINED Phase-A checkpoint (run scripts/run_phase_a.sh
first; synthetic corpus, seeded):

  1. L_power   — the dissertation's estimator: power iteration on the drift
                 Jacobian wrt the hidden state at RANDOM (h, x). Global-ish;
                 reproduces ~1.01.
  2. L_local   — the same Jacobian probe, but along the DATA-DRIVEN hidden
                 trajectories the integrator actually visits on clean
                 operating-region inputs (h taken at several RK4 stages of
                 real forward passes). This is the local/empirical Lipschitz
                 constant over the operating region.
  3. S_in2out  — direct end-to-end input->logit sensitivity
                 ||g(x+d)-g(x)|| / ||d|| for small random d at clean inputs:
                 the empirically relevant input-robustness slope (the radius
                 the certificate guards is an input radius).

Output: results/local_lipschitz.csv + radius implications
R(L) = eps_out * exp(-L*T) with eps_out=0.5, T=1.

Provenance: trained on the synthetic Phase-A corpus (fixture-derived).
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "models"))

from uav_defense.models.ct_tgnn_gnss import CTTGNN, GNSSGraphSpec  # noqa: E402
from uav_defense.datasets.texbat import TEXBATConfig, make_synth   # noqa: E402

CKPT = REPO / "models" / "uav_defense" / "runs" / "phase_a_smoke" / "ckpt.pt"
EPS_OUT, T_HORIZON = 0.5, 1.0
SEED = 20260728


def load_model() -> CTTGNN:
    spec = GNSSGraphSpec(n_sats=8, feat_dim=8, hidden=32)
    model = CTTGNN(spec, t_span=(0.0, 1.0), method="rk4")
    state = torch.load(CKPT, map_location="cpu", weights_only=False)
    model.load_state_dict(state["model"])
    model.eval()
    return model


def jac_norm_at(model, h, adj, x, n_iter=30, eps=1e-3):
    """Power iteration for the drift Jacobian wrt h at a specific (h, x)."""
    v = torch.randn_like(h)
    v = v / v.flatten(1).norm(dim=1, keepdim=True).view(-1, 1, 1)
    L = 0.0
    with torch.no_grad():
        d0 = model.drift(0.0, h, adj=adj, x=x)
        for _ in range(n_iter):
            d1 = model.drift(0.0, h + eps * v, adj=adj, x=x)
            jv = (d1 - d0) / eps
            L = max(L, jv.flatten(1).norm(dim=1).max().item())
            v = jv / (jv.flatten(1).norm(dim=1, keepdim=True).view(-1, 1, 1) + 1e-8)
    return L


def data_driven_hidden_states(model, x, adj, stages=5):
    """Hidden states along the RK4 trajectory on real inputs."""
    hs = []
    with torch.no_grad():
        t0, t1 = model.t_span
        steps = 4
        dt = (t1 - t0) / steps
        h = torch.zeros(x.size(0), x.size(1), model.spec.hidden)
        hs.append(h.clone())
        t = torch.tensor(t0)
        for _ in range(steps):
            k1 = model.drift(t, h, adj=adj, x=x)
            k2 = model.drift(t + dt / 2, h + dt * k1 / 2, adj=adj, x=x)
            k3 = model.drift(t + dt / 2, h + dt * k2 / 2, adj=adj, x=x)
            k4 = model.drift(t + dt, h + dt * k3, adj=adj, x=x)
            h = h + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6
            t = t + dt
            hs.append(h.clone())
    return hs


def main() -> int:
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    model = load_model()

    ds = make_synth(n_clean=64, n_spoof=64, cfg=TEXBATConfig(), seed=SEED)
    feats, adjs = [], []
    for i in range(len(ds)):
        f, a, _ = ds[i]
        feats.append(f)
        adjs.append(a)
    x = torch.stack(feats)          # (128, 8, 8)
    adj = torch.stack(adjs)

    # 1. dissertation estimator (random h, random x)
    L_power = model.estimate_lipschitz(n_iter=50, batch_size=8)

    # 2. local: along data-driven trajectories, batched over the corpus
    L_locals = []
    for lo in range(0, x.size(0), 32):
        xb, ab = x[lo:lo + 32], adj[lo:lo + 32]
        for h in data_driven_hidden_states(model, xb, ab):
            L_locals.append(jac_norm_at(model, h, ab, xb))
    L_local_max = max(L_locals)
    L_local_med = float(np.median(L_locals))

    # 3. end-to-end input->logit sensitivity at clean inputs
    slopes = []
    with torch.no_grad():
        y0 = model(x, adj)
        for scale in (1e-3, 1e-2, 1e-1):
            for _ in range(8):
                d = torch.randn_like(x)
                d = d / d.flatten(1).norm(dim=1, keepdim=True).view(-1, 1, 1) * scale
                y1 = model(x + d, adj)
                s = ((y1 - y0).norm(dim=1) / scale)
                slopes.append(s.max().item())
    S_max = max(slopes)

    def radius(L):
        return EPS_OUT * math.exp(-L * T_HORIZON)

    rows = [
        {"estimator": "L_power_random (dissertation)", "value": round(L_power, 4),
         "gronwall_radius": round(radius(L_power), 4)},
        {"estimator": "L_local_max (data-driven trajectories)",
         "value": round(L_local_max, 4),
         "gronwall_radius": round(radius(L_local_max), 4)},
        {"estimator": "L_local_median", "value": round(L_local_med, 4),
         "gronwall_radius": round(radius(L_local_med), 4)},
        {"estimator": "S_in2out_max (input->logit slope, small-ball)",
         "value": round(S_max, 4),
         "gronwall_radius": None},
    ]
    out = REPO / "results" / "local_lipschitz.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["estimator", "value", "gronwall_radius"])
        w.writeheader()
        w.writerows(rows)
    print(f"[local-lipschitz] ckpt={CKPT.name} seed={SEED} -> {out}")
    for r in rows:
        print(f"  {r['estimator']:<45} {r['value']:>8}   R={r['gronwall_radius']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
