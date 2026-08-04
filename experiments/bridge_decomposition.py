#!/usr/bin/env python3
"""P1(a): decompose caf_shift_v1 — is the ~5.1 plateau physics or artifact?

caf_shift_v1 maps a d-metre position error to a CAF-feature l2 displacement by
applying BOTH first-order signal effects to clean IQ:
    (1) code-delay shift   tau = d/c  ->  d * 0.0834 samples/m at 25 MS/s
    (2) carrier rotation   phi = 2*pi*d/lambda_L1  ->  wraps every 19 cm

Hypothesis (a) of the certified-regime question: the plateau is driven by (2),
a global carrier-phase rotation that a real receiver's tracking loop wipes off
before any feature extraction, and that carries no position information at the
feature level (absolute carrier phase is a receiver nuisance parameter; in
real IQ it is uniformly random per window — only the SYNTHETIC clean corpus
has a deterministic initial phase, which makes the features look
phase-sensitive).

This script measures four variants on the same seeded windows:
    full      : delay + carrier rotation          (== caf_shift_v1)
    carrier   : carrier rotation only
    delay     : code-delay shift only
    tracked   : delay, then global phase re-aligned to the clean window by
                a complex inner product (a one-tap PLL / wipeoff model) —
                the perturbation a tracking-loop-fed feature extractor sees.

Output: results/bridge_decomposition.csv (per-d medians per variant) and the
radius crossings for the Gronwall (0.18) and RS (0.44) radii.

Provenance: synthetic clean corpus (texbat.make_synth-style, seeded);
fixture-derived — re-calibrate on real TEXBAT before quoting in-paper.
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "models"))
sys.path.insert(0, str(REPO))

from uav_defense.datasets.texbat import TEXBATConfig, _caf_features  # noqa: E402
from certificates.unit_bridge import (  # noqa: E402
    C_M_S, FS_HZ, L1_WAVELENGTH_M, _SEED, _N_WINDOWS, _N_SAMP, _clean_windows)

GRONWALL_R = 0.18
RS_R = 0.44


def frac_delay(iq: np.ndarray, d_m: float) -> np.ndarray:
    n = iq.shape[0]
    shift = (d_m / C_M_S) * FS_HZ
    idx = np.arange(n) - shift
    i0 = np.floor(idx).astype(np.int64)
    frac = (idx - i0).astype(np.float64)
    i0c = np.clip(i0, 0, n - 1)
    i1c = np.clip(i0 + 1, 0, n - 1)
    return (iq[i0c] * (1.0 - frac) + iq[i1c] * frac).astype(np.complex64)


def carrier(iq: np.ndarray, d_m: float) -> np.ndarray:
    return (iq * np.exp(1j * 2.0 * math.pi * d_m / L1_WAVELENGTH_M)).astype(
        np.complex64)


def tracked(iq_clean: np.ndarray, d_m: float) -> np.ndarray:
    """Delay + carrier, then wipe the global phase like a tracking loop:
    align by the phase of <perturbed, clean>."""
    pert = carrier(frac_delay(iq_clean, d_m), d_m)
    z = np.vdot(iq_clean, pert)          # complex correlation
    if abs(z) > 0:
        pert = pert * np.exp(-1j * np.angle(z))
    return pert.astype(np.complex64)


VARIANTS = {
    "full": lambda iq, d: carrier(frac_delay(iq, d), d),
    "carrier": carrier,
    "delay": frac_delay,
    "tracked": tracked,
}


def crossing(ds, l2s, radius):
    """First d whose envelope l2 exceeds radius (linear interp in log d)."""
    env = np.maximum.accumulate(l2s)
    for i, v in enumerate(env):
        if v > radius:
            if i == 0:
                return ds[0] * radius / v if v > 0 else float("nan")
            # log-linear interp between i-1 and i
            x0, x1 = math.log(ds[i - 1]), math.log(ds[i])
            y0, y1 = env[i - 1], env[i]
            t = (radius - y0) / (y1 - y0) if y1 > y0 else 0.0
            return math.exp(x0 + t * (x1 - x0))
    return float("inf")


def main() -> int:
    cfg = TEXBATConfig()
    rng = np.random.default_rng(_SEED)
    windows = _clean_windows(rng, _N_WINDOWS, _N_SAMP)
    base = [_caf_features(w, cfg) for w in windows]

    ds = np.logspace(-3, 4, 36)
    rows = []
    med = {k: [] for k in VARIANTS}
    for d in ds:
        row = {"d_m": round(float(d), 6)}
        for name, fn in VARIANTS.items():
            disp = [float(np.linalg.norm(_caf_features(fn(w, float(d)), cfg) - f0))
                    for w, f0 in zip(windows, base)]
            m = float(np.median(disp))
            med[name].append(m)
            row[f"l2_{name}"] = round(m, 5)
        rows.append(row)

    out = REPO / "results" / "bridge_decomposition.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"[bridge-decomp] seed={_SEED} windows={_N_WINDOWS} -> {out}")
    print(f"{'variant':<9} {'plateau_l2':>10} {'d@R=0.18 (m)':>14} {'d@R=0.44 (m)':>14}")
    summary = {}
    for name in VARIANTS:
        arr = np.maximum.accumulate(np.asarray(med[name]))
        cg = crossing(ds, med[name], GRONWALL_R)
        cr = crossing(ds, med[name], RS_R)
        summary[name] = {"plateau": float(arr[-1]), "cross_gronwall_m": cg,
                         "cross_rs_m": cr}
        print(f"{name:<9} {arr[-1]:>10.4f} {cg:>14.4g} {cr:>14.4g}")

    # carrier share of the full displacement at the plateau
    share = (np.asarray(med['carrier'])[-1] / np.asarray(med['full'])[-1]
             if med['full'][-1] > 0 else float('nan'))
    print(f"\ncarrier-only / full displacement at d=10km: {share:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
