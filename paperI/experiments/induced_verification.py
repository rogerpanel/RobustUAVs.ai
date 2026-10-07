#!/usr/bin/env python3
"""RQ5: the induced-verification attack, its mission-level bound, and three
mitigations.

An adversary on the bus injects transfers that are syntactically valid but
carry invalid signatures. Each one occupies the bus for n frames and then
costs the receiver t_verify of CPU before it is rejected. Legitimate signed
navigation messages share both resources, so the attack adds delay to them;
that added delay enters Delta_eff exactly as adversarial staleness does.

Key quantity (new):  rho_iv = t_verify / (n * C)
  CPU-seconds the defender spends per bus-second the attacker spends.
  With a verification CPU share beta, an attacker holding a fraction a of
  the bus saturates the verifier iff  a * rho_iv + r_leg * t_verify >= beta.

Model (discrete-event):
  * bus   : one server; legitimate transfers (periodic, rate r_leg) have
            priority over attacker transfers (Poisson); the measured HCRL base
            load U0 is modelled as a reduced service rate (C / (1 - U0)).
  * CPU   : FIFO verification queue served at share beta of the core.
  * mitigations:
      none        every completed transfer is fully verified
      prefilter   a 4-byte group-key MAC is checked first (t_pre); an OUTSIDER
                  attacker fails it, an INSIDER (key-holding relay) passes it
      slot_k      schedule-aware budget: per expected legitimate slot, at most
                  k candidates claiming that source are verified; the rest are
                  dropped unverified (an insider can still win k-1 slots)

Outputs: induced_verification.csv  (DES)  and  iv_amplification.csv (analytic)
"""
from __future__ import annotations

import csv
import heapq
import math
import random

from constants import BETA_CPU, OUT, SCHEME, F_CPU
from transport import TRANSPORT, tag_bytes, u0_from_hcrl

T_PRE = 27_337 / F_CPU / 4      # truncated-MAC pre-check on a short tag [physics_model]
R_LEG = 10.0


def write(name, rows):
    with (OUT / name).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f"-> paperI/results/{name} ({len(rows)} rows)")


def simulate(scheme, transport, a_bus, beta, mitigation, attacker="insider",
             horizon=60.0, seed=0, k_slot=2):
    """Return list of legitimate end-to-end auth latencies (bus + CPU), s."""
    rng = random.Random(seed)
    tr = TRANSPORT[transport]
    u0 = u0_from_hcrl(TRANSPORT["can"])[2]
    n = tr.extra_frames(tag_bytes(scheme))
    c_eff = tr.frame_time / (1.0 - u0)
    s_bus = n * c_eff
    t_v = SCHEME[scheme].t_verify / beta
    t_p = T_PRE / beta
    r_adv = a_bus / s_bus if a_bus > 0 else 0.0

    arrivals = []
    t = rng.random() / R_LEG
    while t < horizon:
        arrivals.append((t, 0)); t += 1.0 / R_LEG
    t = 0.0
    while r_adv > 0:
        t += rng.expovariate(r_adv)
        if t >= horizon:
            break
        arrivals.append((t, 1))
    arrivals.sort()

    # ---- bus: CAN arbitrates per FRAME, so a legitimate transfer (higher
    # priority) waits at most one attacker frame; attacker transfers progress
    # only while no legitimate transfer is on the bus (preemptive-resume at
    # frame granularity). Attacker frames above the legitimate priority would
    # be plain bus flooding, which the parent's HCRL-class IDS addresses.
    done = []                  # (completion_time, kind, release)
    legit_busy = []
    for rel, kind in arrivals:
        if kind == 0:
            start = rel + (c_eff if r_adv > 0 else 0.0)   # one-frame blocking
            end = start + s_bus
            legit_busy.append((rel, end))
            done.append((end, 0, rel))
    legit_busy.sort()
    j = 0
    free = 0.0
    for rel, kind in arrivals:
        if kind != 1:
            continue
        t0 = max(rel, free)
        work = s_bus
        while work > 1e-15:
            while j < len(legit_busy) and legit_busy[j][1] <= t0:
                j += 1
            if j < len(legit_busy) and legit_busy[j][0] <= t0 < legit_busy[j][1]:
                t0 = legit_busy[j][1]; continue
            nxt = legit_busy[j][0] if j < len(legit_busy) else math.inf
            step = min(work, nxt - t0)
            t0 += step; work -= step
        free = t0
        done.append((t0, 1, rel))
    done.sort()

    # ---- CPU: FIFO verification
    lat = []
    cpu_free = 0.0
    slot_count = {}
    for comp, kind, rel in done:
        cost = t_v
        if kind == 1:
            if mitigation == "prefilter" and attacker == "outsider":
                cost = t_p
            elif mitigation == "slot_k":
                slot = math.floor(comp * R_LEG)
                c = slot_count.get(slot, 0)
                if c >= k_slot - 1:      # reserve one verification for legit
                    continue
                slot_count[slot] = c + 1
        if mitigation == "prefilter" and kind == 0:
            cost = t_v + t_p
        start = max(cpu_free, comp)
        cpu_free = start + cost
        if kind == 0:
            lat.append(cpu_free - rel)
    return lat, dict(n_frames=n, s_bus=s_bus, t_v=t_v, r_adv=r_adv)


def main():
    can = TRANSPORT["can"]
    u0 = u0_from_hcrl(can)[2]
    amp = []
    for tr_key in ("can", "canfd"):
        tr = TRANSPORT[tr_key]
        for sk in ("mav2", "ed25519", "fndsa512", "mldsa44", "slhdsa128s"):
            sc = SCHEME[sk]
            n = tr.extra_frames(tag_bytes(sk))
            rho = sc.t_verify / (n * tr.frame_time)
            a_max = 1.0 - u0 - R_LEG * n * tr.frame_time
            for beta in (0.05, 0.2, 1.0):
                a_sat = (beta - R_LEG * sc.t_verify) / rho   # bus share that saturates CPU
                amp.append(dict(transport=tr_key, scheme=sk, n_frames=n,
                                t_verify_ms=round(sc.t_verify * 1e3, 3),
                                bus_ms=round(n * tr.frame_time * 1e3, 3),
                                rho_iv=round(rho, 4), beta=beta,
                                attacker_bus_max=round(a_max, 4),
                                bus_share_to_saturate_cpu=round(a_sat, 4),
                                cpu_bound=a_sat < a_max))
    write("iv_amplification.csv", amp)
    for r in amp:
        if r["beta"] == BETA_CPU:
            print(r)

    rows = []
    for tr_key, sk in (("can", "ed25519"), ("can", "mldsa44"),
                       ("canfd", "ed25519"), ("canfd", "mldsa44")):
        tr = TRANSPORT[tr_key]
        n = tr.extra_frames(tag_bytes(sk))
        a_max = 1.0 - u0 - R_LEG * n * tr.frame_time
        for frac in (0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
            a = frac * a_max
            for mit, att in (("none", "insider"), ("prefilter", "outsider"),
                             ("prefilter", "insider"), ("slot_k", "insider")):
                lats = []
                for seed in range(4):
                    l, info = simulate(sk, tr_key, a, BETA_CPU, mit, att,
                                       horizon=60.0, seed=seed)
                    lats += l
                lats.sort()
                p99 = lats[int(0.99 * (len(lats) - 1))]
                mx = lats[-1]
                diverged = p99 > 10.0
                rows.append(dict(transport=tr_key, scheme=sk, beta=BETA_CPU,
                                 attacker_bus_share=round(a, 4),
                                 frac_of_max=frac, mitigation=mit,
                                 attacker=att, n=len(lats),
                                 p50_ms=round(lats[len(lats) // 2] * 1e3, 3),
                                 p99_ms=round(p99 * 1e3, 3),
                                 max_ms=round(mx * 1e3, 3),
                                 diverged=diverged))
    write("induced_verification.csv", rows)


if __name__ == "__main__":
    main()
