#!/usr/bin/env python3
"""RQ4: does a freshness window bound the hidden delay, and what does the
GNSS-coupled clock do to it?

Three analyses:
  1. Natural holdover drift  eps(t) = |y0| t + D t^2 / 2  for three oscillator
     classes (physics_model, datasheet-class parameters).
  2. Binding condition: freshness reduces the hidden delay only when
     tau_fresh + eps_clk(t) < Delta(theta) = H min(theta, s). Deployed windows
     (MAVLink 2 signing: 60 s; Galileo OSNMA: 30-165 s) are compared with the
     largest delay the detector already admits (H s = 10 s).
  3. Forward time push. MAVLink 2 updates its signing clock as
     max(GPS time, stored time) and rejects any signed packet more than one
     minute behind it (mavlink.io, Message Signing). A GNSS spoofer that
     advances the verifier's clock by more than the window therefore makes
     every *legitimate* signed packet fail freshness: the delay adversary is
     converted into a persistent-denial adversary.

Outputs: clock_holdover.csv, freshness_binding.csv, time_push.csv
"""
from __future__ import annotations

import csv

from constants import (H, OUT, S_SLACK, TAU_FRESH_MAVLINK, TAU_FRESH_OSNMA,
                       TAU_FRESH_OSNMA_MAX, THETA_BENIGN, THETA_OP, delta_theta)

# fractional frequency offset y0 and ageing D (1/s) -- physics_model
OSCILLATORS = [
    ("XO (+-20 ppm)", 20e-6, 1e-12),
    ("TCXO (+-2 ppm)", 2e-6, 1e-13),
    ("OCXO (+-0.05 ppm)", 5e-8, 1e-15),
]


def eps(t, y0, d):
    return abs(y0) * t + 0.5 * d * t * t


def write(name, rows):
    with (OUT / name).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f"-> paperI/results/{name} ({len(rows)} rows)")


def main():
    rows = []
    for t in (1, 10, 60, 600, 3600, 6 * 3600, 24 * 3600):
        row = dict(holdover_s=t)
        for name, y0, d in OSCILLATORS:
            row[name] = round(eps(t, y0, d) * 1e3, 4)   # ms
        rows.append(row)
    write("clock_holdover.csv", rows)

    bind = []
    for th in (THETA_BENIGN, THETA_OP, 1.0, S_SLACK):
        dl = delta_theta(th)
        for tau_name, tau in (("MAVLink 2 (60 s)", TAU_FRESH_MAVLINK),
                              ("OSNMA T_L (30 s)", TAU_FRESH_OSNMA),
                              ("OSNMA max (165 s)", TAU_FRESH_OSNMA_MAX),
                              ("tight (theta)", th)):
            margin = dl - tau
            row = dict(theta=th, delta_theta_s=dl, window=tau_name, tau_fresh_s=tau,
                       binding=margin > 0, margin_s=round(margin, 4))
            # holdover time before an XO clock erodes the margin
            for name, y0, d in OSCILLATORS:
                if margin <= 0:
                    row[f"holdover_to_loss_{name.split()[0]}_s"] = 0
                else:
                    # solve |y0| t + d t^2/2 = margin
                    import math
                    tt = (-abs(y0) + math.sqrt(y0 * y0 + 2 * d * margin)) / d
                    row[f"holdover_to_loss_{name.split()[0]}_s"] = round(tt, 1)
            bind.append(row)
    write("freshness_binding.csv", bind)

    push = []
    # nu: rate at which a spoofer can advance GPS time without tripping a
    # receiver/autopilot plausibility check (s of time per s of wall clock)
    for nu_name, nu in (("1 ms/s (1000 ppm)", 1e-3), ("10 ms/s", 1e-2),
                        ("100 ms/s", 0.1), ("1 s/s", 1.0), ("step", float("inf"))):
        for tau in (TAU_FRESH_MAVLINK, 5.0, 1.0, 0.25):
            t_denial = 0.0 if nu == float("inf") else tau / nu
            push.append(dict(push_rate=nu_name, nu=nu, tau_fresh_s=tau,
                             time_to_denial_s=round(t_denial, 2),
                             time_to_denial_min=round(t_denial / 60, 2)))
    write("time_push.csv", push)
    print(f"Hs = {H * S_SLACK} s is the largest delay the detector admits; "
          f"MAVLink window {TAU_FRESH_MAVLINK} s is {TAU_FRESH_MAVLINK / (H * S_SLACK):.0f}x larger.")


if __name__ == "__main__":
    main()
