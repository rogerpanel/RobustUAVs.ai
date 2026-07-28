#!/usr/bin/env python3
"""The W3 delta unit bridge: physical position error (metres) -> CAF-feature l2.

The Ch.6 certificates (Gronwall radius 0.18, RS radius 0.44) live in the
normalised CAF-feature l2 space of `uav_defense/datasets/texbat.py`
(N_SATS=8 satellites x 8 features per window, IQ normalised to int16
full-scale 1/32768). The network side of a CrossLayerPairing produces delta
in physical units — pos_error_m from the Whelan measurements or the
staleness mapping. This module converts the former into the latter by
*measuring the ported feature extractor itself*, not by fabricating a
constant:

  1. A GNSS position error of d metres corresponds, to first order, to a
     time-of-arrival shift tau = d/c on the affected signal, i.e.
       * a code-delay shift of tau * FS_HZ samples at the 25 MS/s baseband
         texbat.py ingests, and
       * a carrier-phase rotation of 2*pi*d/lambda_L1 (lambda ~ 0.1903 m).
  2. We apply exactly that perturbation (fractional-sample delay + phase
     rotation) to seeded clean IQ windows drawn from the same generator the
     Phase-A smoke pipeline uses, re-run texbat._caf_features, and record the
     l2 displacement of the (8 x 8) feature block.
  3. Because the carrier term wraps every lambda/2, the raw displacement
     oscillates in d; a certificate needs an UPPER bound, so the exported
     mapping is the running-max envelope over the calibration grid
     (sound: never understates the feature-space perturbation).

Consequences worth knowing before reading results:
  * The mapping saturates once d >> lambda (carrier fully decorrelated):
    every metre-scale spoof lands at the same plateau, comfortably OUTSIDE
    the 0.18 Gronwall radius. That is the physically honest answer — the
    certified floor applies to sub-wavelength perturbations; large measured
    Whelan deltas are certified as *outside* the safe tube, not silently
    passed.
  * Constants are derived at import-free calibration time from the ported
    code with a fixed seed; they are reproducible but SYNTHETIC-corpus
    quantities. Re-calibrate on real TEXBAT windows before quoting bridge
    numbers in the paper (same API, pass your own windows).

API:
    to_feature_l2(d_m)      -> float   (envelope l2 for pos error d_m)
    bridge_info()           -> dict    (version, grid, plateau, seed)
Usage as a script prints the calibration table.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "models"))

from uav_defense.datasets.texbat import (  # noqa: E402
    FS_HZ, GPS_L1_HZ, TEXBATConfig, _caf_features)

C_M_S = 299_792_458.0
L1_WAVELENGTH_M = C_M_S / GPS_L1_HZ          # ~0.1903 m

BRIDGE_VERSION = "caf_shift_v1"
_SEED = 20260726
_N_WINDOWS = 64
_N_SAMP = 512
# mm to 10 km, log-spaced; covers GPS noise floors up to the Whelan
# Shanghai-fix spoof distances.
_D_GRID_M = np.logspace(-3, 4, 36)

_CAL = None   # lazy: {"d": grid, "l2": envelope, "plateau": float}


def _clean_windows(rng: np.random.Generator, n: int, n_samp: int):
    """Clean GPS-like IQ windows; mirrors texbat.make_synth's clean class."""
    base_freq = np.linspace(0.0, np.pi, n_samp).astype(np.float64)
    out = []
    for _ in range(n):
        noise = (rng.standard_normal(n_samp)
                 + 1j * rng.standard_normal(n_samp)) * 0.4
        sig = np.exp(1j * (base_freq * (1.0 + 0.05 * rng.standard_normal())))
        out.append((sig + noise).astype(np.complex64))
    return out


def _apply_pos_error(iq: np.ndarray, d_m: float) -> np.ndarray:
    """First-order signal effect of a d_m position error: fractional-sample
    code delay (tau*FS) + carrier phase rotation (2*pi*d/lambda)."""
    n = iq.shape[0]
    shift = (d_m / C_M_S) * FS_HZ            # samples, usually fractional
    idx = np.arange(n) - shift
    i0 = np.floor(idx).astype(np.int64)
    frac = (idx - i0).astype(np.float64)
    i0 = np.clip(i0, 0, n - 1)
    i1 = np.clip(i0 + 1, 0, n - 1)
    delayed = iq[i0] * (1.0 - frac) + iq[i1] * frac
    phase = np.exp(1j * 2.0 * math.pi * d_m / L1_WAVELENGTH_M)
    return (delayed * phase).astype(np.complex64)


def _calibrate() -> dict:
    cfg = TEXBATConfig()
    rng = np.random.default_rng(_SEED)
    windows = _clean_windows(rng, _N_WINDOWS, _N_SAMP)
    base_feats = [_caf_features(w, cfg) for w in windows]

    med = []
    for d in _D_GRID_M:
        disp = [float(np.linalg.norm(_caf_features(_apply_pos_error(w, d), cfg)
                                     - f0))
                for w, f0 in zip(windows, base_feats)]
        med.append(float(np.median(disp)))
    env = np.maximum.accumulate(np.asarray(med))   # sound upper envelope
    return {"d": _D_GRID_M, "l2": env, "plateau": float(env[-1])}


def _cal() -> dict:
    global _CAL
    if _CAL is None:
        _CAL = _calibrate()
    return _CAL


def to_feature_l2(d_m: float) -> float:
    """Upper-envelope CAF-feature l2 displacement for a position error of
    d_m metres. Linear below the grid (small-angle regime), plateau above."""
    if d_m <= 0:
        return 0.0
    cal = _cal()
    d, l2 = cal["d"], cal["l2"]
    if d_m <= d[0]:
        return float(l2[0] * (d_m / d[0]))
    if d_m >= d[-1]:
        return cal["plateau"]
    return float(np.interp(math.log(d_m), np.log(d), l2))


# --------------------- caf_shift_v2: tracking-loop variant ------------------
# P1(a) finding (docs/certified_regime_analysis.md): v1 charges the full
# carrier rotation 2*pi*d/lambda to the adversary, but absolute carrier phase
# is a receiver nuisance parameter — tracking loops wipe it before any
# feature extraction, and in real IQ it is uniformly random per window (only
# the synthetic corpus has a deterministic initial phase). v2 models the
# perturbation a tracking-loop-fed extractor sees: code delay, then global
# phase re-aligned to the clean window by complex correlation. Measured
# effect: the Gronwall(0.18) crossing moves from ~2.1 mm to ~0.45 m and the
# RS(0.44) crossing to ~1.15 m; metre-scale spoofs still land outside the
# tube (that part is physics, not artifact).

BRIDGE_VERSION_V2 = "caf_shift_v2"
_CAL_V2 = None


def _apply_pos_error_tracked(iq: np.ndarray, d_m: float) -> np.ndarray:
    pert = _apply_pos_error(iq, d_m)
    z = np.vdot(iq, pert)
    if abs(z) > 0:
        pert = (pert * np.exp(-1j * np.angle(z))).astype(np.complex64)
    return pert


def _calibrate_v2() -> dict:
    cfg = TEXBATConfig()
    rng = np.random.default_rng(_SEED)
    windows = _clean_windows(rng, _N_WINDOWS, _N_SAMP)
    base = [_caf_features(w, cfg) for w in windows]
    med = []
    for d in _D_GRID_M:
        disp = [float(np.linalg.norm(
            _caf_features(_apply_pos_error_tracked(w, d), cfg) - f0))
            for w, f0 in zip(windows, base)]
        med.append(float(np.median(disp)))
    env = np.maximum.accumulate(np.asarray(med))
    return {"d": _D_GRID_M, "l2": env, "plateau": float(env[-1])}


def _cal_v2() -> dict:
    global _CAL_V2
    if _CAL_V2 is None:
        _CAL_V2 = _calibrate_v2()
    return _CAL_V2


def to_feature_l2_v2(d_m: float) -> float:
    """caf_shift_v2: tracking-loop-aligned upper envelope (the corrected
    RF-class bridge). Same envelope semantics as v1."""
    if d_m <= 0:
        return 0.0
    cal = _cal_v2()
    d, l2 = cal["d"], cal["l2"]
    if d_m <= d[0]:
        return float(l2[0] * (d_m / d[0]))
    if d_m >= d[-1]:
        return cal["plateau"]
    return float(np.interp(math.log(d_m), np.log(d), l2))


def bridge_info_v2() -> dict:
    cal = _cal_v2()
    return {"version": BRIDGE_VERSION_V2,
            "basis": "texbat._caf_features on seeded synthetic clean windows, "
                     "global carrier phase wiped by complex correlation "
                     "(tracking-loop model); re-calibrate on real TEXBAT "
                     "before quoting in-paper",
            "model": "code delay tau=d/c at FS=25MS/s; carrier phase treated "
                     "as receiver nuisance (P1(a), "
                     "docs/certified_regime_analysis.md); median over "
                     "windows; running-max envelope (upper bound)",
            "seed": _SEED, "n_windows": _N_WINDOWS,
            "plateau_l2": round(cal["plateau"], 4),
            "d_grid_m": [float(cal["d"][0]), float(cal["d"][-1])]}


def bridge_info() -> dict:
    cal = _cal()
    return {"version": BRIDGE_VERSION,
            "basis": "texbat._caf_features on seeded synthetic clean windows "
                     "(re-calibrate on real TEXBAT before quoting in-paper)",
            "model": "code delay tau=d/c at FS=25MS/s + carrier rotation "
                     "2*pi*d/lambda_L1; median over windows; running-max "
                     "envelope (upper bound)",
            "seed": _SEED, "n_windows": _N_WINDOWS,
            "plateau_l2": round(cal["plateau"], 4),
            "d_grid_m": [float(cal["d"][0]), float(cal["d"][-1])]}


if __name__ == "__main__":
    cal = _cal()
    print(f"{BRIDGE_VERSION}: CAF-feature l2 envelope vs position error "
          f"(seed={_SEED}, {_N_WINDOWS} windows)")
    for d, v in zip(cal["d"], cal["l2"]):
        print(f"  d={d:12.4f} m  ->  l2={v:.4f}")
    for probe in (0.001, 0.01, 0.05, 0.1, 1.0, 30.0, 89.0, 1.6e7):
        print(f"  to_feature_l2({probe:g} m) = {to_feature_l2(probe):.4f}")
