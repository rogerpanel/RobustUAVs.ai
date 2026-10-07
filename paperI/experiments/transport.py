#!/usr/bin/env python3
"""RQ2 (transport term) and Proposition 3 (the cliff).

Frame-level models of three UAV transports, the maximum admissible signed
message rate r*, a busy-period response-time bound in the style of Davis,
Burns, Bril and Lukkien (Real-Time Systems 2007), and a discrete-event
simulation (DES) that validates the bound on a bus whose benign base load is
the one measured on the HCRL UAVCAN capture.

Outputs (paperI/results/):
  transport_frames.csv      frames, bus time and r* per scheme x transport
  transport_cliff.csv       worst-case response time vs signed-message rate
  transport_des.csv         DES latency quantiles vs the analytical bound
"""
from __future__ import annotations

import csv
import heapq
import math
import random
from dataclasses import dataclass

from constants import (CAN_BITRATE, CANFD_ARB_RATE, CANFD_DATA_RATE, OUT,
                       SCHEMES, TESLA_KEY_BYTES, TESLA_MAC_BYTES,
                       hcrl_benign_rates)

# --------------------------------------------------------------------------
# Frame models
# --------------------------------------------------------------------------


def can_ext_frame_bits(payload: int, worst_stuff: bool = True) -> int:
    """Classic CAN 2.0B extended frame (29-bit id), Davis et al. (2007):
    C = (54 + 8s + 13 + floor((54 + 8s - 1)/4)) bit times, the last term being
    worst-case bit stuffing. Without stuffing: 54 + 8s + 13."""
    base = 54 + 8 * payload + 13
    return base + ((54 + 8 * payload - 1) // 4 if worst_stuff else 0)


def canfd_ext_frame_time(payload: int, worst_stuff: bool = True) -> float:
    """CAN FD extended frame with bit-rate switch. Arbitration phase at the
    nominal rate, data phase at the data rate (ISO 11898-1:2015 field sizes).
    A stated engineering model, not a vendor timing."""
    arb = 1 + 11 + 1 + 1 + 18 + 1 + 1 + 1 + 1          # SOF..BRS
    arb_stuff = (arb - 1) // 4 if worst_stuff else 0
    tail = 1 + 2 + 7 + 3                               # CRC delim, ACK, EOF, IFS
    crc = 17 if payload <= 16 else 21
    data = 1 + 4 + 8 * payload + 4 + crc               # ESI, DLC, data, SC, CRC
    dyn = (1 + 4 + 8 * payload - 1) // 4 if worst_stuff else 0
    fixed = math.ceil((4 + crc) / 4)
    return (arb + arb_stuff + tail) / CANFD_ARB_RATE + (data + dyn + fixed) / CANFD_DATA_RATE


@dataclass(frozen=True)
class Transport:
    key: str
    label: str
    bytes_per_frame: int     # authenticated-payload bytes per frame/packet
    frame_time: float        # seconds per frame (worst case)
    frame_time_nominal: float
    crc_bytes: int           # per-transfer overhead bytes (multi-frame CRC)
    per_frame_overhead_bytes: int = 0

    def frames(self, extra_bytes: int, msg_bytes: int = 0) -> int:
        return math.ceil((msg_bytes + extra_bytes + self.crc_bytes)
                         / self.bytes_per_frame)

    def extra_frames(self, extra_bytes: int, msg_bytes: int = 0) -> int:
        """Frames needed to carry the authentication tag. With msg_bytes=0
        the tag is carried as a transfer of its own (one transfer CRC); with
        msg_bytes>0 it is the increment over the unsigned message."""
        if msg_bytes == 0:
            return math.ceil((extra_bytes + self.crc_bytes) / self.bytes_per_frame)
        return self.frames(extra_bytes, msg_bytes) - self.frames(0, msg_bytes)


def _serial(baud: int) -> tuple[float, float]:
    # MAVLink 2 packet: 10 B header + 2 B CRC; 8N1 framing = 10 bits/byte.
    # A tag larger than the 255 B payload limit is carried in additional
    # packets, each paying 12 B of overhead.
    byte_t = 10.0 / baud
    return byte_t, byte_t


TRANSPORTS = [
    # DroneCAN on classic CAN: 8 B frames, 1 tail byte -> 7 B payload/frame;
    # multi-frame transfers carry a 2 B transfer CRC.
    Transport("can", "Classic CAN (DroneCAN, 1\\,Mbit/s)", 7,
              can_ext_frame_bits(8) / CAN_BITRATE,
              can_ext_frame_bits(8, False) / CAN_BITRATE, 2),
    Transport("canfd", "CAN FD (DroneCAN, 1/5\\,Mbit/s)", 63,
              canfd_ext_frame_time(64), canfd_ext_frame_time(64, False), 2),
    # MAVLink 2 over serial; 'frame' = one 255 B payload packet + 12 B overhead
    Transport("mav57k", "MAVLink~2, 57.6\\,kbaud radio", 255,
              (255 + 12) * 10 / 57_600, (255 + 12) * 10 / 57_600, 0, 12),
    Transport("mav921k", "MAVLink~2, 921.6\\,kbaud link", 255,
              (255 + 12) * 10 / 921_600, (255 + 12) * 10 / 921_600, 0, 12),
]
TRANSPORT = {t.key: t for t in TRANSPORTS}


def tag_bytes(scheme_key: str) -> int:
    if scheme_key == "tesla":
        return TESLA_MAC_BYTES + TESLA_KEY_BYTES
    from constants import SCHEME
    return SCHEME[scheme_key].tag_bytes


def tx_time(transport: Transport, extra_bytes: int, msg_bytes: int = 0) -> float:
    """Worst-case bus time added by extra_bytes of authentication."""
    if transport.key.startswith("mav"):
        # byte-exact on a serial link
        byte_t = 10.0 / (57_600 if transport.key == "mav57k" else 921_600)
        extra_pkts = math.ceil(max(0, msg_bytes + extra_bytes - 255) / 255) \
            if extra_bytes > 13 else 0
        return byte_t * (extra_bytes + 12 * extra_pkts)
    return transport.extra_frames(extra_bytes, msg_bytes) * transport.frame_time


def u0_from_hcrl(transport: Transport, worst: bool = True) -> tuple[float, float, float]:
    """Base load implied by the HCRL benign frame rates (min, mean, max).
    Only meaningful for CAN; the frame payload in HCRL is taken as 8 B."""
    rates = hcrl_benign_rates()
    ft = transport.frame_time if worst else transport.frame_time_nominal
    us = [r * ft for r in rates]
    return min(us), sum(us) / len(us), max(us)


def r_star(transport: Transport, extra_bytes: int, u0: float,
           msg_bytes: int = 0) -> float:
    """Maximum admissible rate of authenticated messages (Prop. 3)."""
    t = tx_time(transport, extra_bytes, msg_bytes)
    return math.inf if t == 0 else (1.0 - u0) / t


# --------------------------------------------------------------------------
# Busy-period response-time bound (lowest-priority signed transfer)
# --------------------------------------------------------------------------


def rta_bound(n_frames: int, c: float, rate: float, bg_streams: list[tuple[float, float]],
              max_q: int = 100_000) -> float:
    """Worst-case response time of an n-frame signed transfer released
    periodically at `rate`, below periodic background streams (period, C).
    Level-i busy period with multiple instances (Davis et al. 2007, Sec. 3):
    returns math.inf when total utilisation >= 1."""
    u = rate * n_frames * c + sum(cb / tb for tb, cb in bg_streams)
    if u >= 1.0:
        return math.inf
    period = 1.0 / rate

    def interference(t):
        return sum(math.ceil(t / tb) * cb for tb, cb in bg_streams)

    # busy-period length
    t = n_frames * c
    while True:
        nt = math.ceil(t / period) * n_frames * c + interference(t)
        if abs(nt - t) < 1e-12:
            break
        t = nt
    q_max = min(max_q, math.ceil(t / period))
    worst = 0.0
    for q in range(q_max):
        f = (q + 1) * n_frames * c
        while True:
            nf = (q + 1) * n_frames * c + interference(f)
            if abs(nf - f) < 1e-12:
                break
            f = nf
        worst = max(worst, f - q * period)
    return worst


def background(u0: float, c: float, k: int = 24) -> list[tuple[float, float]]:
    """Represent the measured aggregate base load as k periodic streams of
    equal period (the RTA's assumption)."""
    rate_each = u0 / c / k
    return [(1.0 / rate_each, c)] * k


# --------------------------------------------------------------------------
# Discrete-event simulation of the same bus (validation)
# --------------------------------------------------------------------------


def des_latency(n_frames: int, c: float, rate: float, u0: float, k: int = 24,
                horizon: float = 30.0, seed: int = 0) -> list[float]:
    """Non-preemptive fixed-priority CAN arbitration. Background: k periodic
    streams with random phase (higher priority). Signed transfers: periodic,
    lowest priority, frames queued FIFO within the transfer."""
    rng = random.Random(seed)
    events = []  # (time, kind, payload)
    rate_each = u0 / c / k
    for i in range(k):
        ph = rng.random() / rate_each
        t = ph
        while t < horizon:
            heapq.heappush(events, (t, 0, i))   # priority 0 = background
            t += 1.0 / rate_each
    t, idx = rng.random() / rate, 0
    while t < horizon:
        heapq.heappush(events, (t, 1, idx))
        t += 1.0 / rate
        idx += 1
    bg_q = 0
    sig_q: list[list] = []  # [release, frames_left]
    now = 0.0
    lat = []
    while events or bg_q or sig_q:
        # admit all arrivals up to now
        while events and events[0][0] <= now + 1e-15:
            tt, kind, _ = heapq.heappop(events)
            if kind == 0:
                bg_q += 1
            else:
                sig_q.append([tt, n_frames])
        if bg_q:
            bg_q -= 1
            now += c
        elif sig_q:
            sig_q[0][1] -= 1
            now += c
            if sig_q[0][1] == 0:
                lat.append(now - sig_q[0][0])
                sig_q.pop(0)
        elif events:
            now = events[0][0]
        if now > horizon * 3:
            break
    return lat


def main() -> None:
    can = TRANSPORT["can"]
    u0_min, u0_mean, u0_max = u0_from_hcrl(can)
    u0n = u0_from_hcrl(can, worst=False)
    print(f"HCRL-derived U0 on classic CAN: worst-stuffing {u0_min:.3f}-{u0_max:.3f} "
          f"(mean {u0_mean:.3f}); nominal {u0n[0]:.3f}-{u0n[2]:.3f}")

    keys = [s.key for s in SCHEMES] + ["tesla"]
    rows = []
    for tr in TRANSPORTS:
        # same measured utilisation assumed on CAN FD; serial base load unknown
        u0 = u0_max if tr.key in ("can", "canfd") else 0.0
        for k in keys:
            b = tag_bytes(k)
            ef = tr.extra_frames(b) if not tr.key.startswith("mav") else math.ceil(b / 255)
            t = tx_time(tr, b)
            rows.append(dict(transport=tr.key, scheme=k, tag_bytes=b,
                             extra_frames=ef, tx_ms=round(t * 1e3, 4),
                             u0=round(u0, 4),
                             r_star_u0_0=round(r_star(tr, b, 0.0), 2),
                             r_star_u0=round(r_star(tr, b, u0), 2)))
    with (OUT / "transport_frames.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    for r in rows:
        if r["transport"] in ("can", "canfd"):
            print(r)

    # The cliff: response time vs signed rate, classic CAN, measured U0
    cliff = []
    bg = background(u0_max, can.frame_time)
    for k in ["ed25519", "fndsa512", "mldsa44", "slhdsa128s"]:
        n = can.extra_frames(tag_bytes(k))
        rmax = (1 - u0_max) / (n * can.frame_time)
        for frac in [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9,
                     0.93, 0.95, 0.97, 0.98, 0.99]:
            r = frac * rmax
            R = rta_bound(n, can.frame_time, r, bg)
            # contrast: sporadic (Poisson) releases, M/D/1 mean response with
            # service n*C/(1-U0) -- latency grows as a slope, not a cliff
            S = n * can.frame_time / (1 - u0_max)
            rho_q = r * S
            md1 = S + rho_q * S / (2 * (1 - rho_q))
            cliff.append(dict(scheme=k, n_frames=n, rate=round(r, 4),
                              rate_frac=frac, r_star=round(rmax, 3),
                              R_ms=round(R * 1e3, 3),
                              md1_ms=round(md1 * 1e3, 3),
                              tx_alone_ms=round(n * can.frame_time * 1e3, 3)))
    with (OUT / "transport_cliff.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cliff[0]))
        w.writeheader(); w.writerows(cliff)

    # DES validation of the RTA bound (Ed25519 and ML-DSA-44)
    des = []
    for k in ["ed25519", "mldsa44"]:
        n = can.extra_frames(tag_bytes(k))
        rmax = (1 - u0_max) / (n * can.frame_time)
        for frac in [0.2, 0.5, 0.8, 0.9]:
            r = frac * rmax
            bound = rta_bound(n, can.frame_time, r, bg)
            lats = []
            for seed in range(8):
                lats += des_latency(n, can.frame_time, r, u0_max, seed=seed,
                                    horizon=20.0 if k == "ed25519" else 120.0)
            lats.sort()
            q = lambda p: lats[min(len(lats) - 1, int(p * len(lats)))]
            des.append(dict(scheme=k, rate_frac=frac, rate=round(r, 3),
                            n=len(lats), p50_ms=round(q(0.5) * 1e3, 3),
                            p99_ms=round(q(0.99) * 1e3, 3),
                            max_ms=round(lats[-1] * 1e3, 3),
                            rta_ms=round(bound * 1e3, 3),
                            bound_holds=lats[-1] <= bound + 1e-9))
            print(des[-1])
    with (OUT / "transport_des.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(des[0]))
        w.writeheader(); w.writerows(des)


if __name__ == "__main__":
    main()
