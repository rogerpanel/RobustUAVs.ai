# PENDING_ON_DATA — the complete, minimal set of items that need external access

Everything here is blocked ONLY by data/network access, not by engineering.
Each item says exactly what unblocks it. Nothing else in the project is
data-gated: the certificate radius, mission margins, HCRL map, PAC-Bayes form,
and both papers' reconciliation are all done on real or stated data (see the
provenance ledger `results/paper_figures/README.md`).

Last updated: 2026-07-29.

## 1. UAV-CAS stat CSV — the only missing real ingest ❌
- **Needs:** `data/raw/uav_cas/UAV-CAS_stat.csv` (+ `UAV-CAS_stat_cfg.csv`),
  99,492 flows / 59 cols. Described as committed but **absent from every
  source available in this session** (uploads + the six-datasets repo). From
  IEEE DataPort DOI 10.21227/zgrg-z865 or the authors' pipeline
  (github.com/Sripathm2/Collaborative-UAV-Dataset — code only, no CSV).
- **Unblocks:** the 6th real ingest. Adapter is fixture-verified and ready;
  `run_real_corpus.sh` picks it up automatically. Replace the fixture-derived
  UAV-CAS row in the ledger with real class counts once staged.
- The 2.5 GB `UAV-CAS_ts.csv` is explicitly OUT OF SCOPE (user); ts-dependent
  sequence work stays out until it lands.

## 2. Whelan attack-interval timestamps ⚠️ (calibration works without them)
- **Needs:** the per-flight attack-on/off times from the Whelan dataset docs
  (NOT in the CSVs). Fill `ingest/whelan_manifest.json` `attack_start`/
  `attack_end` and remove the `"calibration": true` flags.
- **Unblocks:** windowed (not self-referenced) pos_error for paper-final
  numbers. The δ calibration already ran self-referenced (γ≈1.2–1.4 m/s); the
  adapter refuses fabricated intervals, so this is a real gate for the
  windowed figure only, not for the headline γ.

## 3. TEXBAT re-calibration of the caf_shift_v2 bridge ⚠️
- **Needs:** real TEXBAT IQ (UT-RNL registration). Pass real clean windows to
  `certificates/unit_bridge._calibrate_v2` (same API).
- **Unblocks:** replacing the synthetic-corpus bridge crossings (0.45 m
  Grönwall / 1.15 m RS) with real-IQ values. The v1→v2 correction (carrier
  nuisance) is structural and holds regardless; only the numeric crossing
  moves. Bridge numbers stay tagged fixture-derived until then.

## 4. Whelan δ mapping: cruise regime + more flights ⚠️
- **Needs:** more than 3 flights, and non-hover (cruise) flights, to turn the
  γ calibration into a distribution and test whether γ rises toward the
  kinematic bound at speed.
- **Unblocks:** promoting γ_emp from "3-flight hover calibration" to a
  defensible distribution. Current verdict (θ=0.25 s inside the window) holds
  unless cruise γ exceeds 7.28 m/s (m=10 m) — a >5× rise; worth confirming.
  This is the one open question that could flip Paper A's framing back to
  narrow, so it is the highest-value real-data follow-up.

## 5. PAC-Bayes numeric KL constant ⚠️
- **Needs:** the prior/posterior KL from the dissertation **methods chapter**
  (NOT in the ported code — confirmed by grep). 
- **Unblocks:** a single PAC-Bayes number. The McAllester bound is already
  wired to the trained checkpoint's real empirical risk
  (`PACBayesCertificate.bound(r_emp, m, kl)`); it returns a real certified
  accuracy floor the moment a KL is supplied. Until then it reports
  `kl_pending` honestly.

## 6. HCRL attack-map confirmation ⚠️
- **Needs:** the scenario table in arXiv:2212.09268 (403 from this
  environment) to confirm the **data-derived** per-type map
  (`results/hcrl_type_signatures.csv`: type1 flooding, type2 replay,
  type3–6/8 fuzzing, type7/9/10 collaborative replay+fuzzing).
- **Unblocks:** upgrading the map from "measured from frames, plausible" to
  "confirmed against the source table". The ingests already run and validate
  with the derived classes; this is a verification, not a blocker.

---

### NOT pending (done on real/stated data — do not wait on these)
- Local Lipschitz radius 0.153 (measured on the trained checkpoint) — locked,
  propagated as the default certificate regime.
- Mission-corridor margins — read from `uavbench/corpus.py` (waypoint 2–12 km);
  the corridor half-width is deliberately a stated family {2,5,10,20} m because
  the DO-326A deviation bound is read from the M7 certificate at run time, not
  fixed in the release (`results/ewbench_margins.csv`).
- Real MCR anchor — computed from the 93,600-row per_flight.csv (matches the
  drafted values; now tagged real-corpus, and 93,600 confirmed canonical vs
  the plan doc's "108k").
- Operating curve, composition, dominance stats — real DATAMUt simulation.
