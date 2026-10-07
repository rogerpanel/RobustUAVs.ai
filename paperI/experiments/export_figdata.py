#!/usr/bin/env python3
"""Export whitespace-separated .dat tables that the manuscript's pgfplots
figures read directly, so every plotted point comes from a committed CSV."""
from __future__ import annotations

import csv
import math

from constants import OUT, PARENT_RES

FIG = OUT.parent / "manuscript" / "figdata"
FIG.mkdir(parents=True, exist_ok=True)


def read(p):
    with open(p) as fh:
        return list(csv.DictReader(fh))


def dat(name, header, rows):
    with (FIG / name).open("w") as fh:
        fh.write(" ".join(header) + "\n")
        for r in rows:
            fh.write(" ".join(str(x) for x in r) + "\n")
    print("->", FIG / name, len(rows))


def main():
    # gamma vs staleness: per-1-s-bin supremum for spoofing EKF and jamming EKF
    s = read(PARENT_RES / "gamma_campaign_samples.csv")
    for flight, name in (("gps_spoofing", "gamma_spoof.dat"), ("gps_jamming", "gamma_jam.dat")):
        pts = [(float(r["staleness_s"]), float(r["gamma_delta_m_s"])) for r in s
               if r["flight"] == flight and r["source"] == "ekf"]
        edges = [0.5, 1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 60]
        rows = []
        for a, b in zip(edges[:-1], edges[1:]):
            g = [x for t, x in pts if a <= t < b]
            if g:
                rows.append((round(math.sqrt(a * b), 3), round(max(g), 4),
                             round(sorted(g)[len(g) // 2], 4), len(g)))
        dat(name, ["tau", "gmax", "gmed", "n"], rows)

    # cliff
    c = read(OUT / "transport_cliff.csv")
    for sk in ("ed25519", "fndsa512", "mldsa44", "slhdsa128s"):
        rows = [(r["rate_frac"], r["R_ms"], r["tx_alone_ms"], r["md1_ms"]) for r in c if r["scheme"] == sk]
        dat(f"cliff_{sk}.dat", ["frac", "R", "tx", "md1"], rows)

    # crossover curves
    cc = read(OUT / "crossover_curves.csv")
    dat("crossover_curves.dat", ["theta", "Ccons", "Chead", "Csec", "Bhead"],
        [(r["theta"], r["C_conservative"], r["C_headline"], r["C_secant"], r["B10_headline"]) for r in cc])

    # induced verification (p99 vs attacker share fraction)
    iv = read(OUT / "induced_verification.csv")
    for tr, sk in (("can", "ed25519"), ("can", "mldsa44"), ("canfd", "ed25519"), ("canfd", "mldsa44")):
        for mit, att in (("none", "insider"), ("prefilter", "outsider"), ("slot_k", "insider")):
            rows = []
            for r in iv:
                if r["transport"] == tr and r["scheme"] == sk and r["mitigation"] == mit and r["attacker"] == att:
                    p99 = float(r["p99_ms"])
                    rows.append((r["attacker_bus_share"], min(p99, 1e5)))
            dat(f"iv_{tr}_{sk}_{mit}.dat", ["a", "p99"], rows)

    # horizon-matched envelopes
    he = read(OUT / "horizon_envelopes.csv")
    dat("horizon_env.dat", ["theta", "delta", "du", "da"],
        [(r["theta"], r["delta"], r["du"], r["da"]) for r in he])

    # amortisation (ML-DSA-44, classic CAN and CAN FD)
    am = read(OUT / "amortisation.csv")
    for tr in ("can", "canfd"):
        rows = [(r["k"], r["dauth_cert_ms"], r["bus_util"]) for r in am
                if r["transport"] == tr and r["scheme"] == "mldsa44"]
        dat(f"amort_{tr}_mldsa44.dat", ["k", "dauth", "bus"], rows)


if __name__ == "__main__":
    main()
