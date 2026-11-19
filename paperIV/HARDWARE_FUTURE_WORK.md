# Paper IV, future work: a real GNSS receiver in the loop

Status: **plan only, not part of the USENIX Security '27 submission.** Nothing below has been bought,
built or run. Prices are rough 2026 street prices, so check them before ordering.

## Why a receiver, not a full hardware-in-the-loop rig

The paper's attack acts on the GNSS solution. The largest part of the realism gap is therefore
whether a real receiver passes the disguised offsets through unchanged, and what its own spoofing
monitors flag. Its tracking loops, position filter and spoofing/jamming flags are what matter here.

Hardware-in-the-loop on a flight controller alone (a Pixhawk running PX4) runs the same EKF2 code on
simulated sensors. It mainly adds real-time and processor effects, so it is optional below.

## Bill of materials

| # | Item | Purpose | Approx. cost |
|---|---|---|---|
| 1 | SDR transmitter with an external clock input, e.g. HackRF One plus a TCXO clock module, or a bladeRF 2.0 micro | generates the GPS L1 C/A signal | EUR 300-600 |
| 2 | 10 MHz reference or TCXO (if not included in 1) | GNSS needs a stable carrier; the HackRF crystal alone drifts | EUR 30-150 |
| 3 | Multi-band receiver with spoofing and jamming indicators, e.g. u-blox ZED-F9P board (UBX-SEC-SIG, UBX-MON-RF); a cheaper single-band NEO-M9N as a second receiver model | device under test | EUR 60-250 each |
| 4 | Conducted RF path: SMA cables, DC block, fixed attenuators totalling about 60-70 dB, a splitter for two receivers | the signal stays in the cable at receiver-level power (about -130 dBm) | EUR 80-150 |
| 5 | RF shield box (recommended) | a second barrier against any radiation | EUR 150-400 |
| 6 | Optional: Pixhawk 6C or 6X flight controller and USB-serial adapters | PX4 hardware-in-the-loop with the receiver's output | EUR 200-400 |
| 7 | Host PC | existing server or a laptop with USB 3 | - |

Software (open source):
- gps-sdr-sim, which generates GPS L1 C/A from a RINEX navigation file and a user motion file;
- u-center or pyubx2 for UBX logging;
- the existing Paper IV harness, detectors and analysis.

Total, without the flight controller: about EUR 600-1,300.

## Protocol sketch (to pre-register before any run)

1. **Trajectories.** Take the true trajectory and the applied offset of PX4 missions that were
   already flown: naive step and ramp, the five transferred attackers and the PX4-optimised
   attackers, each with its benign twin. Write true position plus offset as a gps-sdr-sim motion
   file, one per mission.
2. **Replay through the receiver.** This is open loop: the vehicle does not react to the receiver's
   output in real time. Log NAV-PVT, SEC-SIG and MON-RF at 10 Hz.
3. **Measurements.**
   - (a) How the receiver transfers the commanded offset to the reported position (lag, smoothing,
     rejection).
   - (b) How often its spoofing and jamming flags fire on disguised versus naive offsets, used as an
     extra detector D5 with its own false-alarm rate from the benign twins.
   - (c) A measured GNSS noise marginal from the real receiver.
4. **Back into the evaluation.** Feed the receiver's reported positions into the offline detectors
   and into PX4 SITL as recorded GNSS input. Report the stealth budget and the detection rates with
   the receiver in place of the simulated GNSS module.
5. **Optional hardware-in-the-loop.** Run the same flights with PX4 on the Pixhawk, using the
   receiver output.

## Limits of this design

- **Open loop.** The attack trajectories are replayed, not adapted live. A closed-loop adaptive
  spoofer would need real-time signal generation, which is a larger engineering effort.
- **Narrow coverage.** It covers GPS L1 C/A only (gps-sdr-sim), and one or two receiver models.
- **Still a simulation.** There are no airframe dynamics, no real wind and no antenna effects.

## Legal and ethical constraints

- **Conducted or shielded only.** Never connect an antenna to the SDR, and never radiate. Over-the-air
  GNSS transmission is illegal in most jurisdictions without a licence, and it can endanger aviation
  and other users.
- **Approvals.** Confirm the national regulator's rules and the institution's approval before the
  first transmission. Update the Ethics appendix to describe the setup.
- **No real flight with spoofing.** Outdoor spoofing tests belong in licensed test ranges and are
  outside this project's scope.

## Effort

About 1 week of procurement, 1-2 weeks to set up and validate (receiver lock, power level, logging),
and 1-2 weeks of runs and analysis. That is roughly 4-5 weeks for one person once the parts arrive.
