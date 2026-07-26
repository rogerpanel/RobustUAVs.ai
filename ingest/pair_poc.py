#!/usr/bin/env python3
"""Proof-of-concept cross-layer pairing (schema demo, NOT the theorem).

For each DATAMUt network attack window, compute the worst-case *residual*
budget of an attacker that evades the detector at operating point theta
(per-hop injected delay <= theta), map it to a state-staleness perturbation
delta via the placeholder mapping `staleness_v0`, and pair it with the
UAV-EW-Bench autonomy window whose defense is 'ours_m1m4m6m7' at a chosen
J/S level. Emits CrossLayerPairing records conforming to the schema.

The delta mapping and the certified_mcr here are PLACEHOLDERS to exercise the
schema end-to-end; Week 3-4 replaces them with the empirically grounded
mapping (UAV Attack Dataset) and the Lipschitz-Gronwall certificate output.

Usage:
  python3 pair_poc.py <datamut_windows.jsonl> <ewbench_windows.jsonl> <out.jsonl> \
      [--theta 0.25] [--vmax 15.0] [--js 20.0] [--defense ours_m1m4m6m7]
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from certificates.engine import REGISTRY, Perturbation


def _certify(delta_m: float) -> dict:
    """Call the real Grönwall certificate. delta_m is in metres (pos error);
    the W3 unit bridge (certificates/unit_bridge.py, caf_shift_v1) converts it
    to feature-space l2 inside certify(). Metre-scale deltas sit far beyond
    the carrier-decorrelation plateau, so expect inside_radius=False there —
    the certified floor engages only for sub-wavelength perturbations.
    """
    cert = REGISTRY["lipschitz_gronwall"]
    return cert.certify(Perturbation("pos_error_m", delta_m,
                                     "staleness_v0")).to_schema()


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("net_windows"); ap.add_argument("auto_windows"); ap.add_argument("out")
    ap.add_argument("--theta", type=float, default=0.25)
    ap.add_argument("--vmax", type=float, default=15.0, help="UAV max speed m/s for staleness_v0")
    ap.add_argument("--js", type=float, default=20.0)
    ap.add_argument("--defense", default="ours_m1m4m6m7")
    a = ap.parse_args()

    net = load(a.net_windows)
    autos = [w for w in load(a.auto_windows) if w["scenario_id"] == a.defense]
    if not autos:
        print("no autonomy windows for defense", a.defense); return 1
    # nearest J/S level to the requested one
    target = min(autos, key=lambda w: abs(w["intensity"]["js_db"] - a.js))

    pairings = []
    for w in net:
        n_hops = max(1, len(w.get("event_ids", [])))  # malicious-origin hops in window
        cum = a.theta * n_hops                        # worst-case evading cumulative delay
        delta = a.vmax * cum                          # staleness_v0: metres of state drift
        pairings.append({
            "pairing_id": f"poc:{w['window_id']}<->{target['window_id']}",
            "network_window_id": w["window_id"],
            "autonomy_window_id": target["window_id"],
            "pairing_basis": "synthetic_alignment",
            "theta": a.theta,
            "detector_name": "datamut_paper_exact",
            "detector_verdict": "evaded",
            "residual_budget": {
                "undetected_delay_per_hop_s": a.theta,
                "n_malicious_hops": n_hops,
                "cumulative_delay_s": cum,
            },
            "delta": {
                "kind": "pos_error_m",
                "value": round(delta, 3),
                "mapping": f"staleness_v0: delta = v_max({a.vmax} m/s) * cumulative_delay_s "
                           "(PLACEHOLDER - to be grounded on UAV Attack Dataset, W3)",
            },
            "certificate": _certify(delta),
            "empirical": {
                "mcr": target.get("empirical_mcr"),
                "n_flights": target.get("n_flights"),
            },
        })

    Path(a.out).write_text("\n".join(json.dumps(p) for p in pairings) + "\n")
    print(f"[pair] {len(pairings)} pairings (theta={a.theta}s -> delta~"
          f"{pairings[0]['delta']['value']}m vs autonomy window js={target['intensity']['js_db']:.1f} dB,"
          f" empirical MCR={target.get('empirical_mcr'):.3f}) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
