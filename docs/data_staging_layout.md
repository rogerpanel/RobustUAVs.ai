# Data staging layout — exact paths every adapter expects

This is the authoritative map from raw dataset files to the `data/raw/<source>/`
paths the six ingest adapters read. Stage files to match this and the whole
pipeline (fetch → ingest → validate → compose → figures) runs with no path
guessing. `data/raw/` and `data/staging/` are gitignored — raw corpora never
get committed.

Any of the three access routes lands here identically:
1. **allowlist** `api.kaggle.com` + `ieee-dataport.org`, then `python3
   data/fetch_kaggle.py` stages automatically via its MAPPING table;
2. **local drop** — copy the files to the paths below by hand;
3. **permissive-session fetch** — run `data/fetch_kaggle.py` elsewhere and copy
   the resulting `data/raw/` tree over (it holds symlinks by default; use
   `--copy` to materialise real files first).

`experiments/run_real_corpus.sh` consumes exactly this layout.

Status legend: ✅ staged & ingested on real data this session · ⚠️ staged,
partial · ❌ not yet on disk.

---

## 1. `data/raw/uav_ew_bench_2026/` — autonomy anchor ✅

```
data/raw/uav_ew_bench_2026/UAV-EW-Bench-2026/
  data/per_flight.csv        <- 93,600 rows (defense,js_db,seed,flight_id,mission,receiver,completed)
  data/per_point.csv
  data/crossings.csv
  config/benchmark.yaml       <- mission profiles + J/S sweep + margins basis
  uavbench/corpus.py          <- waypoint_km range (corridor grounding)
```
Adapter: `ingest/ingest_ewbench.py data/raw/.../data/per_flight.csv OUT`.
Anchor + margins: `experiments/ewbench_anchor.py` (reads per_flight.csv).
Note: the release ships **93,600** per_flight rows (not the plan doc's "108k");
93,600 = 4 defenses × 39 J/S levels × 200 flights × 3 seeds. **93,600 is
canonical.**

## 2. `data/raw/uav_attack_whelan/` — the measured bridge ✅ (3-flight sample)

Staged-corpus convention (adapter accepts a plain `gps.csv` per flight dir):
```
data/raw/uav_attack_whelan/
  benign/       gps.csv  local.csv     <- reference flight
  gps_jamming/  gps.csv  local.csv
  gps_spoofing/ gps.csv  local.csv
  README.md
```
`gps.csv` = vehicle_gps_position export (lat/lon as 1e-7-deg ints, fix_type,
satellites_used, jamming_indicator, noise_per_ms). `local.csv` =
vehicle_local_position (x/y/z the EKF output). If instead you have the full
ULOG/ulog2csv release, the adapter also accepts a directory of
`*vehicle_gps_position*.csv` files, or a raw `.ulg` via `--ulog`.
Adapter/manifest: `ingest/ingest_whelan.py OUT --manifest ingest/whelan_manifest.json`.
Calibration: `experiments/whelan_delta_calibration.py`.
**The attack-on/off timestamps are NOT in these CSVs** — `whelan_manifest.json`
carries `"calibration": true` + `self_ref_frac` for interval-free pos_error
calibration; set the real `attack_start`/`attack_end` (from the dataset docs)
and drop the calibration flag for paper-final windowed numbers. The adapter
**refuses** to run an attack flight with unset/TODO intervals unless it is
flagged calibration (no fabricated windows).

## 3. `data/raw/uavids_2025/` — swarm mesh at scale ✅

```
data/raw/uavids_2025/UAVIDS-2025_0.csv     <- 122,171 flow rows, 22 features, 5 classes
   (add _1.csv, _2.csv … shards if present)
```
Adapter: `ingest/ingest_uavids.py data/raw/uavids_2025/UAVIDS-2025_0.csv OUT --part 0`
(one invocation per shard; `--part` tags the shard).

## 4. `data/raw/hcrl_uavcan/` — on-board bus ✅

```
data/raw/hcrl_uavcan/type1_label.bin … type10_label.bin
```
candump-style text: `Label (ts) iface CANID [dlc] BB BB …`.
Attack-class map is **data-derived** (`experiments/hcrl_type_signatures.py` →
`results/hcrl_type_signatures.csv`); `ingest/ingest_hcrl.py` reads it
automatically (`--attack-class` overrides). Confirm against arXiv:2212.09268
before camera-ready (PENDING_ON_DATA.md).
Adapter: `ingest/ingest_hcrl.py data/raw/hcrl_uavcan/type1_label.bin OUT --scenario type1`.

## 5. `data/raw/datamut_sim/` — forwarding detector ✅ (built from source)

```
data/raw/datamut_sim/datamut_paper_exact_demo.cc
data/raw/datamut_sim/datamut_analysis.h
```
These are identical to `third_party/datamut/`. The sweep builds the patched
binary into `build/` (see CLAUDE.md Build & run); the raw copy here is only for
provenance. Campaign: `experiments/sweep_full.py`.

## 6. `data/raw/uav_cas/` — calibrated swarm digital twin ❌ STAT PRESENT? / TS PENDING

```
data/raw/uav_cas/UAV-CAS_stat.csv        <- 99,492 flows, 59 cols, 15 classes  [EXPECTED]
data/raw/uav_cas/UAV-CAS_stat_cfg.csv    <- Label = "<canonical>|<config_string>"  [EXPECTED]
data/raw/uav_cas/UAV-CAS_ts.csv          <- per-packet lists; 2.5 GB  [OUT OF SCOPE this session]
data/raw/uav_cas/UAV-CAS_ts_cfg.csv      <- [OUT OF SCOPE]
```
Adapter (auto-detects stat vs ts from the header):
`ingest/ingest_uavcas.py data/raw/uav_cas/UAV-CAS_stat.csv OUT` and the `_cfg`
variant. **As of this session the stat CSV is NOT on disk** — it was described
as committed but is absent from every source available here (uploads, the
six-datasets repo). Drop `UAV-CAS_stat.csv` + `UAV-CAS_stat_cfg.csv` into
`data/raw/uav_cas/` and re-run; the adapter is fixture-verified against the
authors' own generator output and ready.

Column layout the stat adapter expects (verified against the authors'
`build_stat_csv.py`): 11 meta (`config_idx,num_drones,num_bs,payload,pathloss,
modulation,mission,tx_power,noise,src_ip,dst_ip`) + 47 features + `Label`. The
ts adapter expects `packet_time,packet_size,[packet_flag,]packet_dir,Label`
with the first columns as stringified Python lists.

---

## `data/fetch_kaggle.py` MAPPING (for route 1/3)

Filename-substring → staging subdir, already covers all six:
`per_flight`/`per_point`/`crossings`→ew_bench; `uavids`→uavids_2025;
`_label.bin`→hcrl_uavcan; `uav-cas_ts`/`uav-cas_stat`→uav_cas;
`ulg`/`ulog`/`gps_spoof`/`jamming`→uav_attack_whelan; `datamut`→datamut_sim.
Extend the table only if the Kaggle layout adds new filenames.
