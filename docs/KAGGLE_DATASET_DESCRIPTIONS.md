# Kaggle page copy — "UAVs Network & Navigation End-to-End Security Data"

Paste-ready Markdown for the aggregated Kaggle dataset. Section **0** is the
top-of-page overview; sections **1–6** are the six component datasets. Each
component carries its own source attribution, DOI, and licence note — keep
these intact, since four of the six are third-party benchmarks redistributed
under their original terms.

---

## 0. Overview (top of the Kaggle page)

**The first end-to-end UAV-security corpus spanning both the network layer and the autonomy/navigation layer.**

Intrusion-detection research for drones has historically stopped at the wire: it
detects the malicious packet but never asks what that packet does to the aircraft's
flight. This aggregate closes that gap. It brings together **six datasets** that,
together, cover the full attack surface of an autonomous UAV — from the swarm mesh,
the ground-control C2 link, and the on-board UAVCAN bus (the **network layer**), all
the way to the GNSS receiver, the controller, and the completed mission (the
**autonomy layer**).

Two of the six are released by this project; the other four are established,
independently-published benchmarks reused under their original open licences so
that network-layer attacks can, for the first time, be studied against
autonomy-layer degradation in one place.

| # | Dataset | Real / Sim | Layer · surface | Scale |
|---|---------|-----------|-----------------|-------|
| 1 | **UAV-EW-Bench-2026** *(this project)* | Sim (physics-informed) | Autonomy · GNSS + controller | 5,000 base flights · 32 J/S levels (0–40 dB) · 4 defences |
| 2 | **DATAMUt traces** *(this project)* | Sim (event replay) | Network · multi-hop mesh (DTN/TWiG) | Time-delay / jamming / DoS forwarding traces, sweepable detector threshold |
| 3 | **UAV Attack Dataset** *(Whelan et al., 2020)* | Real testbed + SITL/HITL | C2 link · MAVLink / PX4 | Benign + GPS-spoof / GPS-jam / ping-DoS flights (ULOG + CSV) |
| 4 | **UAVIDS-2025** *(Zeng et al., 2025)* | Sim (NS-3.24) | Network · 802.11ac swarm mesh | 122,171 flows · 22 features · 5 classes |
| 5 | **UAVCAN Intrusion Dataset** *(Kim et al., 2025)* | Real testbed | Intra-UAV bus · UAVCAN v0 / DroneCAN | 10 scenarios · Flooding / Fuzzy / Replay · CAN frames |
| 6 | **UAV-CAS** *(Mishra et al., 2026)* | Sim (AERPAW-calibrated digital twin) | Network · swarm mesh | 99,492 flows · 1,024 configs · 5 attack families + 9 collaborative |

**Why together?** Each row of the network sets is an attack *on the wire*; each row
of the autonomy set is a mission *outcome*. Aligning them lets a model — or a
formal guarantee — reason across the whole causal chain: *a jammed link or a
delayed forwarder → a degraded navigation input → a mission that does or doesn't
complete.* The four third-party sets supply real and calibrated network-layer
ground truth; the two project-released sets supply the autonomy-layer anchor and
the mesh-forwarding detector traces that bridge to it.

**Layers covered:** swarm mesh · C2/MAVLink link · UAVCAN/DroneCAN bus · GNSS
receiver · flight controller · mission outcome.
**Attack families across the corpus:** GPS spoofing, GPS/RF jamming, time-delay
forwarding, DoS/DDoS/flooding, ping-DoS, blackhole, wormhole, Sybil, fuzzing,
replay, and nine collaborative compositions.

> **Licensing.** Component datasets retain their original licences and citation
> requirements (listed per section below). If you use any component, cite its
> original authors as well as this aggregate. This page bundles integration
> convenience only; it does not relicense the underlying data.

---

## 1. UAV-EW-Bench-2026 — the autonomy-layer anchor *(released by this project)*

A reproducible benchmark measuring **autonomous-UAV mission completion under
electronic-warfare jamming**. It reports the DO-326A / ED-202A safe-mission-completion
fraction as a function of the **jamming-to-signal ratio J/S (0–40 dB)** under a
combined adversarial contour (GNSS spoofing + PGD visual perturbation + BIM
DRL-policy attack), and is the only set in this corpus that provides
**navigation-layer ground truth** — i.e. what actually happens to the flight.

**Design.** 5,000 base flights spanning **3 mission profiles**
(`search_and_rescue`, `perimeter_patrol`, `cargo_mixed_terrain`) × **3 simulated
GNSS receiver models** (`ublox_f9p_sim`, `novatel_oem7_sim`, `gp_software_receiver`);
a **32-point J/S sweep** from 0 to 40 dB; **4 defence configurations** — `no_def`
(undefended PX4 baseline), `caf_cnn`, `seq2seq_tr`, and `ours_m1m4m6m7` (the
Phase-A method stack); 200 flights per point × **3 seeds (42, 7, 13)**; Wilson 95 %
score intervals throughout.

**Files.** `per_flight.csv` (per-flight completion outcomes across the sweep),
`per_point.csv` (aggregated completion per operating point with CIs),
`crossings.csv` (the J/S at which each defence crosses the 0.90 DO-326A floor),
plus the headline figure and its coordinates. A `sim-lite` analytical Monte-Carlo
backend regenerates the published curves anywhere in seconds; an `airsim` backend
drives full AirSim / PX4-SITL 3-D flights for full-fidelity regeneration.

**Note on fidelity.** The `sim-lite` completion probabilities are calibrated to
the plotted figure anchors and instantiated by Monte-Carlo replay — a transparent,
publishable analytical benchmark. If you use only `sim-lite`, describe results as a
*calibrated analytical Monte-Carlo benchmark*, not full 3-D renders.

**Attribution.** Roger Nick Anaedevha, *UAV-EW-Bench-2026*.
Source & docs: https://github.com/rogerpanel/UAV-EW-Bench-2026
**Licence:** data and generated artifacts under **CC BY 4.0**.

---

## 2. DATAMUt mesh-forwarding traces — the network↔autonomy bridge *(released by this project)*

Traces and detector outputs from **DATAMUt**, a time-window-graph (TWiG) detector
for **multi-hop forwarding misbehaviour** in UAV delay-tolerant mesh networks.
DATAMUt models periodic contact windows between UAVs and compares each hop's
observed forwarding time against a route-and-schedule oracle, flagging
**time-delay, jamming, and DoS** misbehaviour when a hop deviates beyond a
detector threshold ε (the detector's operating point).

**What it contributes.** This is the *bridge* set: it produces per-hop network-layer
observations — expected vs. observed send time, per-hop residual delay, path-match,
and the detector's suspicious/clean verdict — with a **sweepable detection threshold**,
so the same forwarding scenario can be replayed at any operating point. Two
malicious-delay regimes are provided (low, 1–7 s; medium, 1–10 s) against a 5-second
inter-UAV contact window, across grid, ring, and double-ring topologies with
AODV / OLSR / DSR / DSDV routing. Runs are deterministic per seed.

**Attribution.** Derived from the **DATAMUt** detector (Keiwan Soltani; SPRITZ
group, University of Padua — F. Turrin, M. Conti). *Cite the original DATAMUt
publication — fill in canonical reference/DOI here — in addition to this aggregate.*
**Licence / redistribution:** confirm terms with the original authors before reuse;
this project redistributes generated traces with permission for research use.

---

## 3. UAV Attack Dataset — real C2-link attacks on PX4 *(Whelan et al., 2020)*

Flight logs from **simulated and live UAV flights** under sensor and communication
attacks, on a real PX4 stack. Includes benign flights and flights under **GPS
spoofing**, **GPS jamming**, and **MAVLink ping-DoS**. In the live campaign, a
Keysight EXG N5172B signal generator supplies true coordinates while a HackRF SDR
with GPS-SDR-SIM broadcasts a false Shanghai fix (30.286502, 120.032669); jamming
uses white-Gaussian noise via the HackRF — all inside an RF-denied facility.
Simulated attacks add a Gazebo GPS-spoofing hook across multiple airframes
(quadcopter, plane) in SITL and HITL.

**What it contributes.** The **real-testbed C2 bridge**: attacks on the *same PX4 /
Pixhawk family* modelled by the autonomy anchor, coupling a concrete network/RF
event to measured navigation degradation — the empirical grounding for any
network→navigation mapping.

**Platform.** PX4 v1.11.3 on Pixhawk 4 (FMU-V5) + Pixhawk GPS, Holybro S500 frame,
QGroundControl 4.0.9. Full logs as ULOG; CSVs via `ulog2csv`.

**Attribution.** Whelan, Sangarapillai, Minawi, Almehmadi, El-Khatib (2020).
DOI **10.21227/00dg-0d12** · paper *Novelty-based Intrusion Detection of Sensor
Attacks on UAVs*, DOI 10.1145/3416013.3426446 · code https://github.com/jasonotu/MAVIDS
**Licence:** IEEE DataPort **Open Access (CC BY)**.

---

## 4. UAVIDS-2025 — swarm-mesh IDS benchmark at scale *(Zeng et al., 2025)*

A benchmark for **intrusion detection in UAV swarm networks**, generated in the
**NS-3.24** simulator with realistic UAV mobility from an extended BOID flocking
model. **122,171 labelled flow records** across five classes: **Normal, Blackhole,
Flooding, Sybil, Wormhole**. Each flow carries **22 features** grouped into
connection, traffic-volume, and performance metrics; the simulation uses IEEE
802.11ac, AODV routing, and a Nakagami channel model. Supports supervised and
unsupervised IDS, federated / decentralized security, and adversarial-robustness
research, including imbalanced-attack and swarm-mobility scenarios.

**What it contributes.** The **large-scale multi-hop mesh layer** — high-volume,
cleanly-labelled swarm-network flows covering four mesh attack types, the network
substrate the autonomy anchor pairs against.

**Attribution.** Zeng, Bashir, Nait-Abdesselam, *UAVIDS-2025*, IEEE CNS 2025.
DOI **10.21227/j5p4-zt27**. Please cite the CNS 2025 paper (and the FedGraph-ID
INFOCOM 2026 paper) as specified by the authors.
**Licence:** per IEEE DataPort dataset terms — retain author citation.

---

## 5. UAVCAN Intrusion Dataset — the on-board bus layer *(Kim et al., 2025)*

**UAVCAN (DroneCAN / UAVCAN v0)** communication logs from a real UAV testbed under
normal and attack conditions — the layer *below* the C2 link, inside the aircraft.
The testbed pairs a Pixhawk 4 flight controller with Holybro Kotleta20 ESCs, a
Raspberry-Pi CAN-Shield interface, and UAVCAN motor-control modules. **Flooding,
Fuzzy, and Replay** attacks were run across **10 scenarios** (takeoff, hover,
movement), each 180–280 s, capturing both normal and injected CAN frames.

**Format.** Per-frame records: **Label** (Normal / Attack), relative **Timestamp**
(s), **Interface**, 29-bit **CAN ID**, **DLC**, and **Data** bytes. Per-scenario
attack type, intervals, and frame counts are in the accompanying technical report.

**What it contributes.** The **intra-UAV bus attack surface** — a third network
layer beneath the mesh and the C2 link, letting the corpus reach from swarm-level
routing down to motor-control frames.

**Attribution.** D. Kim, Y. Song, S. Kwon, H. Kim, J. D. Yoo, H. K. Kim (Korea
University / HCRL). DOI **10.21227/fcyc-bb14** · report arXiv:2212.09268.
**Licence:** per IEEE DataPort dataset terms — **confirm redistribution with the
authors** before reuse; retain citation.

---

## 6. UAV-CAS — calibrated digital-twin swarm dataset *(Mishra et al., 2026)*

A large, **measurement-calibrated** flow dataset for UAV-swarm intrusion detection,
covering **single and collaborative attacks**. **99,492 flows** drawn from **1,024
configurations** of a 9-axis design space (attack composition, swarm size,
base-station count, payload, propagation model, modulation, mission, transmit power,
noise floor). Traffic comes from a Containernet swarm **digital twin** calibrated
against **AERPAW** testbed campaigns (AADM, AFAR), Maeng et al. RSRP, and
Gurses–Sichitiu channel soundings via a four-layer pipeline (path loss → mobility →
link chain → trace fidelity).

**Classes.** Six canonical — **Benign, DoS, DDoS, Blackhole, Wormhole, Replay** —
plus **nine collaborative compositions** (`+`-joined, e.g. `Blackhole+DoS`).
High-rate attacks separate strongly from benign; stealth attacks (Blackhole /
Wormhole / Replay) are designed to blend in. Two aligned representations:
**`UAV-CAS_stat.csv`** (47 aggregated per-flow features for classical models) and
**`UAV-CAS_ts.csv`** (per-packet timing/size/direction sequences for sequence
models; list columns are stringified — parse with `ast.literal_eval`).
Config-embedded variants (`*_cfg.csv`) carry the full scenario string after a `|`
separator. Recommended protocol: 70/10/20 splits with **cross-condition holdouts**
(hold out whole config-axis values) for robustness.

**What it contributes.** The **closest prior art and calibrated positioning** —
AERPAW-grounded swarm-mesh flows with explicit collaborative attacks; the authors
list GPS spoofing/jamming as future work, which is precisely the autonomy layer
this corpus supplies.

**Attribution.** Mishra, Bhargava, Liu, Islam (Purdue), *UAV-CAS*, 2026.
DOI **10.21227/zgrg-z865** · arXiv:2606.17845 · code
https://github.com/Sripathm2/Collaborative-UAV-Dataset
**Licence:** CSVs **CC BY 4.0**; calibration sources (AERPAW AADM/AFAR, Maeng RSRP,
Gurses–Sichitiu) retain their original licences — retain upstream attribution.

---

### Suggested Kaggle tags
`uav` · `drone` · `intrusion-detection` · `cybersecurity` · `gps-spoofing` ·
`gnss-jamming` · `electronic-warfare` · `uavcan` · `mavlink` · `swarm-networks` ·
`px4` · `network-security` · `anomaly-detection` · `benchmark`
