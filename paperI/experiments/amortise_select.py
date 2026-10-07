#!/usr/bin/env python3
"""Amortisation (batch signing) and the certified selection rule.

Batching. The sender closes a batch of k navigation messages, signs the root
of a Merkle tree over them, and sends one signature plus a log2(k)-hash
authentication path with each message. Then, for message rate r,
  Delta_auth(k) = (k-1)/r + t_sign + R_tx(sig) + t_verify   (worst message)
  bus load      = U0 + (r/k) n_sig C + r n_path C
Batching trades bus occupancy (the cliff) for latency (the slope). A
MAC-plus-periodic-signature hybrid has the same latency form with k = P.

Selection. For every (theta, m, transport, adversary, PQ requirement,
regime) the rule enumerates (scheme, k, mitigation) and returns the feasible
configuration of least resource cost (bus + CPU utilisation). Feasibility:
  certified    (Delta(theta) + Delta_auth_cert) gamma_a E <= m
  rate         total bus utilisation < 1
  insider      scheme provides source authentication
  pq           scheme is post-quantum
  iv-safe      a forged-signature flood cannot saturate the verifier, either
               because the bus runs out first or because slot budgeting is on
  denial       unauthenticated configurations are vacuous (Prop. 4)
The space is finite, so enumeration is exact; the file also records how many
configurations were feasible, so the reader can see how tight each cell is.

Outputs: amortisation.csv, selection.csv
"""
from __future__ import annotations

import csv
import math

from constants import (BETA_CPU, E, GAMMA_SCENARIOS, MARGINS, OUT, SCHEME,
                       THETA_BENIGN, THETA_OP, delta_theta)
from transport import TRANSPORT, background, rta_bound, tag_bytes, u0_from_hcrl

HASH = 16           # truncated Merkle hash, bytes                   [assumption]
R_MSG = 10.0
KS = (1, 2, 4, 8, 16, 32)
SC_KEYS = ("mav2", "ed25519", "fndsa512", "mldsa44", "slhdsa128f", "slhdsa128s")
HEADLINE = [g for g in GAMMA_SCENARIOS if g.name == "headline"][0]
CONSERV = [g for g in GAMMA_SCENARIOS if g.name == "conservative"][0]


def write(name, rows):
    with (OUT / name).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f"-> paperI/results/{name} ({len(rows)} rows)")


def config_cost(sk, tr_key, k, r=R_MSG):
    """Return dict with Delta_auth (cert), bus utilisation, cpu utilisation."""
    tr = TRANSPORT[tr_key]
    sc = SCHEME[sk]
    u0 = u0_from_hcrl(TRANSPORT["can"])[2]
    n_sig = tr.extra_frames(tag_bytes(sk))
    path_bytes = HASH * math.ceil(math.log2(k)) if k > 1 else 0
    n_path = tr.extra_frames(path_bytes) if path_bytes else 0
    bus = u0 + (r / k) * n_sig * tr.frame_time + r * n_path * tr.frame_time
    # signer and verifier run on different nodes; each may spend BETA_CPU
    cpu = max((r / k) * sc.t_sign, (r / k) * sc.t_verify) / BETA_CPU
    if bus >= 1.0:
        return dict(dauth=math.inf, dauth_cert=math.inf, bus=bus, cpu=cpu)
    bg = background(u0, tr.frame_time)
    if n_path:
        # per-message authentication-path frames interfere at the full rate r
        bg = bg + [(1.0 / r, n_path * tr.frame_time)]
    R = rta_bound(n_sig, tr.frame_time, r / k, bg)
    wait = (k - 1) / r
    base = wait + R + sc.t_verify
    return dict(dauth=base + sc.t_sign, dauth_cert=base + sc.t_sign * sc.sign_tail_factor,
                bus=bus, cpu=cpu)


def iv_safe(sk, tr_key, mitigation):
    if mitigation == "slot_k":
        return True
    tr = TRANSPORT[tr_key]
    sc = SCHEME[sk]
    u0 = u0_from_hcrl(TRANSPORT["can"])[2]
    n = tr.extra_frames(tag_bytes(sk))
    rho = sc.t_verify / (n * tr.frame_time)
    a_max = 1.0 - u0 - R_MSG * n * tr.frame_time
    return a_max * rho + R_MSG * sc.t_verify < BETA_CPU


def main():
    am = []
    for tr_key in ("can", "canfd"):
        for sk in SC_KEYS:
            for k in KS:
                c = config_cost(sk, tr_key, k)
                am.append(dict(transport=tr_key, scheme=sk, k=k,
                               dauth_ms=round(c["dauth"] * 1e3, 2) if math.isfinite(c["dauth"]) else "inf",
                               dauth_cert_ms=round(c["dauth_cert"] * 1e3, 2) if math.isfinite(c["dauth_cert"]) else "inf",
                               bus_util=round(c["bus"], 4), cpu_budget_util=round(c["cpu"], 4),
                               feasible=c["bus"] < 1 and c["cpu"] < 1))
    write("amortisation.csv", am)

    sel = []
    for gsc in (HEADLINE, CONSERV):
        for regime in ("delay", "denial"):
            for adv in ("outsider", "insider"):
                for pq in (False, True):
                    for tr_key in ("can", "canfd"):
                        for th in (THETA_BENIGN, THETA_OP, 0.5, 1.0):
                            d = delta_theta(th)
                            for m in MARGINS:
                                cands = []
                                # option 0: no authentication
                                rho_u = d * gsc.gamma_u * E
                                if regime == "delay" and rho_u <= m and adv == "outsider" and not pq:
                                    cands.append((0.0, "none", 1, "-", 0.0, rho_u))
                                elif regime == "delay" and rho_u <= m:
                                    cands.append((0.0, "none", 1, "-", 0.0, rho_u))
                                for sk in SC_KEYS:
                                    sc = SCHEME[sk]
                                    if adv == "insider" and not sc.source_auth:
                                        continue
                                    if pq and not sc.pq:
                                        continue
                                    for k in KS:
                                        c = config_cost(sk, tr_key, k)
                                        if not (c["bus"] < 1 and c["cpu"] < 1):
                                            continue
                                        rho_a = (d + c["dauth_cert"]) * gsc.gamma_a * E
                                        if rho_a > m:
                                            continue
                                        for mit in ("none", "slot_k"):
                                            if not iv_safe(sk, tr_key, mit):
                                                continue
                                            cost = (c["bus"] - u0_from_hcrl(TRANSPORT["can"])[2]) \
                                                + c["cpu"] * BETA_CPU + (0.001 if mit == "slot_k" else 0)
                                            cands.append((cost, sk, k, mit, c["dauth_cert"], rho_a))
                                cands.sort(key=lambda x: (x[0], x[5]))
                                best = cands[0] if cands else None
                                sel.append(dict(gamma=gsc.name, regime=regime, adversary=adv,
                                                pq_required=pq, transport=tr_key, theta=th, m=m,
                                                n_feasible=len(cands),
                                                choice=best[1] if best else "INFEASIBLE",
                                                k=best[2] if best else "",
                                                mitigation=best[3] if best else "",
                                                dauth_ms=round(best[4] * 1e3, 2) if best else "",
                                                rho_m=round(best[5], 3) if best else "",
                                                rho_unauth_m=round(rho_u, 3)))
    write("selection.csv", sel)


if __name__ == "__main__":
    main()
