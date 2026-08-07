# Real-time simulation: what is corpus-backed and what is not

The Live Fleet Demo is the first piece of a real-time simulation architecture.
This records precisely which parts are drawn from measurement and which are
modelled, so the distinction survives being demonstrated on a stage.

## Instantiation — from the corpus

`platform/backend/app/corpus.py` draws every aircraft from the committed
results. Nothing about a fleet's initial state is invented.

| Source | Contributes | File |
|---|---|---|
| `uav_ew_bench_2026` | mission profile, defence configuration, J/S operating point, and the MCR that configuration actually achieved there | `results/ewbench_mcr_anchor.csv` |
| `datamut_sim` | per-hop residual delays for the peer mesh, sampled from 15,392 measured hops rather than from a distribution fitted to them | `results/hop_ledger.csv` |
| `uavids_2025` | mesh attack-class prior | `results/ingest_stats.csv` |
| `uav_attack_whelan` | the γ regime, from three real PX4 flights | `results/whelan_delta_calibration.csv` |
| `hcrl_uavcan` | intra-bus signature | `results/hcrl_type_signatures.csv` |
| `uav_cas` | **nothing** — its release file is not reachable in this deployment | `PENDING_ON_DATA.md` #1 |

UAV-CAS contributes nothing rather than having its weight silently
redistributed. The page shows the gap.

If the corpus cannot be read, the fleet still spawns but `corpus.backed` is
`false` and the reason is attached and rendered. A deployment with a broken
corpus must not demo identically to a working one.

## Mesh and clustering — emergent, not declared

Aircraft are linked by a peer mesh: a ring, which guarantees connectivity, plus
chords, which make clustering non-trivial. Each link starts at a measured benign
residual delay.

On every step a link takes the staleness of the worse endpoint, and its state
follows from that:

- `trust` — under the detector's θ
- `delayed` — over θ but under the 5 s contact-window slack
- `jammed` — either endpoint's link quality below 25%, or residual past 5 s

Clusters are the connected components over non-degraded links. So a jam that
splits the fleet produces a partition the simulation *arrives at*, rather than
one it announces. Measured: jamming two of eight aircraft for 30 s partitions a
9-link mesh into 4 clusters with 2 aircraft isolated.

That partition is the physical meaning of the theorem's slack term. Aircraft in
different groups cannot relay for each other, so a delayed frame has no
alternative path and misses its contact window — which costs a full 60 s TWiG
period and is flagged at any ε.

## What is still modelled

Stated plainly, because the page is labelled *illustrative* and should stay
honest about why:

- **Flight dynamics.** A circuit at 12 m/s with per-tick drift. Not a PX4 SITL
  run, and not derived from any recorded trajectory.
- **Attack damage rates.** The per-class link, GNSS and staleness rates in
  `ATTACKS` are chosen so the demo shows gradation over ~90 s. They are
  calibrated for legibility, not measured.
- **Detection rates.** `DEFENSE_CATCH` uses the campaign's coverage figures, but
  the per-step draw is a Bernoulli trial rather than a model inference.
- **Phase timings** on the GNSS spoof page.

## What is measured, and load-bearing

- **γ** — 1.195 m/s at the receiver, 1.365 m/s after the EKF, from three real
  PX4 flights. This converts undetected staleness into metres.
- **L = 1.181** — measured over operating-region trajectories, not by random
  power iteration.
- **Link residuals** — real hops from the DATAMUt ledger.
- **Campaign MCR per aircraft** — the actual EW-Bench outcome for that defence
  at that J/S.

So the deviation drawn on screen and the tube drawn around it are the same
quantity the certificate bounds. That is the property worth protecting as this
grows.

## Where this goes next

In rough order of value:

1. **Trajectories from recorded flights.** EW-Bench has per-flight outcomes but
   not tracks; the Whelan ULOGs do have tracks, and `ingest_whelan.py` already
   parses them. Three flights is a small pool, but replaying a real track under
   a simulated attack would move flight dynamics from modelled to measured.
2. **Routing over the mesh.** Links exist and partition, but nothing routes
   across them yet. AODV/OLSR over this graph would let the missed-contact-window
   penalty be computed rather than asserted.
3. **Per-step detector inference.** Replace the Bernoulli draw with the real
   `PaperExactDetector` over the link residuals. The residuals are already real,
   so this is the shortest path from illustrative to measured.
4. **Attack rate calibration.** Once (1) and (3) land, the damage rates can be
   fitted to observed outcomes instead of chosen for legibility.

Each step moves one row from the modelled list to the measured list. The page's
`illustrative` badge should only become `measured` when the list above is empty.
