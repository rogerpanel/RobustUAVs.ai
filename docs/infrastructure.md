# RobustUAVs.ai — server sizing and deployment plan

Target: host the project the way `robustidps.ai` is hosted (Hetzner Cloud +
Cloudflare DNS), but sized for *this* project's measured footprint, with a
GPU path that can be added later.

Everything below that is a **measurement** was taken on the development box on
2026-08-01 and is reproducible from the repo; everything that is a **price** is
what Hetzner advertised in mid-2026 and must be re-checked in the console,
because Hetzner raised cloud prices twice in 2026 (April, then 15 June, the
latter hitting the CPX/CCX dedicated-vCPU lines by up to ~2x).

---

## 1. What the project actually needs (measured, not guessed)

| Resource | Measurement | Where it comes from |
|---|---|---|
| Raw corpus on disk | **156 MB** staged today; **~3.4 GB** when the two large sets land (UAV-CAS ts ~2.5 GB, full Whelan ~700 MB) | `du -sh data/raw` |
| Staged (schema-valid) output | **490 MB** today; expansion factor **3.16x** over raw → **~10.6 GB** at full corpus | `du -sh data/staging` |
| Peak RAM, largest ingest run so far | **0.73 GB** for 122,171 UAVIDS flows | `ingest_uavids.py`, RSS measured |
| Peak RAM, projected worst case | **~10–25 GB** for `UAV-CAS_ts.csv` (2.5 GB of stringified per-packet arrays) if `native` lists are retained; **~1 GB** with `--drop-native-lists` | `ingest_uavcas.py` design |
| CPU, detector campaign | **0.01 s** per operating point (8 seeds x 4 policies); the full 78-point campaign is dominated by process launch, not compute | `build/datamut_demo` timed |
| CPU, model training | ~5 min for the Phase-A smoke test on 4 cores; real training is the GPU case | `scripts/run_phase_a.sh` |
| Repo + results + toolchain | 655 MB repo; PyTorch + TeX Live + Docker images add ~10–15 GB | `du -sh .` |

**Conclusion: RAM is the only binding constraint, not CPU.** The published
campaign is I/O- and startup-bound; the one workload that can genuinely exhaust
a small machine is parsing the 2.5 GB UAV-CAS time-series file at full fidelity.

Traffic is not a constraint either: at Hetzner's 20 TB included allowance, a
3.4 GB full-corpus download could be served ~5,800 times a month before any
overage.

---

## 2. Recommended server

### Primary recommendation — **CX52** (Helsinki, `eu-central`)

| | |
|---|---|
| vCPU / RAM / disk | 16 vCPU (shared, x86) / **32 GB** / 320 GB NVMe |
| Advertised price | ~**€32.40/mo** (verify in console; your account bills in USD) |
| Why | 32 GB is the number that removes the *only* measured hard limit — it lets the UAV-CAS time-series file be ingested at full fidelity with `native` packet arrays retained, instead of forcing `--drop-native-lists`. 320 GB holds the full corpus (3.4 GB) + staging (10.6 GB) + PyTorch/Docker/TeX (~15 GB) + model checkpoints + snapshots with roughly 10x headroom for future datasets. |

This is a real upgrade over the `robustidps.ai` box (CPX32: 4 vCPU / 8 GB /
160 GB): **4x the RAM, 4x the cores, 2x the disk**, for roughly twice the price.

### Budget alternative — **CX42**
8 vCPU / 16 GB / 160 GB, ~€16.40/mo — i.e. the same price class as the existing
CPX32 but with double its cores and RAM. Perfectly adequate **provided** the
UAV-CAS ts ingest is run with `--drop-native-lists` (which the adapter already
supports precisely for this reason). Choose this if budget is tight; you can
rescale up to CX52 later without rebuilding (Hetzner rescale keeps the disk).

### Not recommended right now — **CCX (dedicated vCPU)**
The usual argument for dedicated vCPU is timing reproducibility, and this
project *does* publish per-policy execution times. But the measurement in
question takes **0.01 s**, so noisy-neighbour variance is irrelevant to it,
while the June 2026 price adjustment made CCX dramatically more expensive.
Dedicated vCPU is not worth the premium for this workload.

### Not recommended as primary — **CAX (ARM/Ampere)**
CAX31 (8 vCPU / 16 GB / 160 GB) is the cheapest way to get these specs and the
whole stack (Python, PyTorch, the C++ replay) builds on ARM. The reason to
avoid it *as the main node* is scientific, not technical: the paper reports
execution timings and reviewers will reproduce on x86, so keeping the
publication host on x86 preserves parity. CAX is an excellent choice for a
secondary CI/build node later.

### Add-ons
- **Volume (block storage)** — optional at CX52's 320 GB. If the corpus grows
  past that, attach a 100 GB Volume (~€0.057/GB/mo ≈ €5.70/mo) and mount it at
  `data/`, so the corpus can be snapshotted, detached, and resized without
  touching the OS disk.
- **Backups** — enable (20% surcharge). Cheap insurance for a machine that will
  hold months of experiment output.
- **Location** — **Helsinki (`eu-central`)**: same location as `robustidps.ai`,
  lowest prices, full instance-type availability, largest traffic allowance,
  EU data residency, and lowest latency to the Padova collaborator.

---

## 3. The GPU path (important caveat)

**Hetzner Cloud does not offer GPU instances.** A GPU cannot be added to a CX/
CPX/CCX cloud server. GPUs are only on Hetzner's **dedicated-server** line
(GEX series — e.g. the GEX131 with an NVIDIA RTX PRO 6000 Blackwell, announced
April 2026).

The right architecture is therefore two machines, added in sequence:

1. **Now:** the CX52 cloud server is the permanent home for the website, the
   artifact, the schema/adapters, the detector campaign, and CPU experiments.
2. **When GPU training is needed:** order a GEX dedicated server, and link it to
   the cloud server's private network. Hetzner supports connecting Cloud
   networks to dedicated servers via **vSwitch** (confirm the current procedure
   in Hetzner docs at the time of ordering). The GPU box then mounts or syncs
   the corpus from the cloud node and pushes checkpoints back.

This also means GPU cost is *deferred*, not designed-in — you pay for it only
in the months you actually train.

---

## 4. Cloudflare + Hetzner wiring (mirrors robustidps.ai)

**DNS (Cloudflare, domain `robustuavs.ai`)**

| Type | Name | Value | Proxy |
|---|---|---|---|
| A | `@` | server IPv4 | Proxied (orange) |
| AAAA | `@` | server IPv6 (Hetzner gives a `/64`) | Proxied |
| CNAME | `www` | `robustuavs.ai` | Proxied |
| A/AAAA | `artifact` (optional) | same IPs | Proxied |

- SSL/TLS mode: **Full (strict)** — install a Cloudflare **Origin CA**
  certificate on the server (15-year validity, free) rather than Let's Encrypt,
  so renewal never breaks behind the proxy.
- Enable: Always Use HTTPS, HSTS, Brotli, and caching rules for the static
  artifact paths (large downloads benefit most).

**Hetzner Cloud Firewall** (attach at creation, not after):
- `22/tcp` — inbound **only from your admin IP**, not `0.0.0.0/0`.
- `80,443/tcp` — inbound **only from Cloudflare's published IP ranges**, so the
  origin cannot be reached directly and the proxy cannot be bypassed.
- Everything else denied inbound; all outbound allowed.

**On the server**
- Ubuntu LTS, unattended-upgrades, SSH key-only (`PasswordAuthentication no`),
  `fail2ban`.
- Reverse proxy: Caddy (simplest with Origin CA) or nginx.
- Application stack in Docker Compose, mirroring `robustidps.ai`: the dashboard,
  a static artifact/download endpoint, and the docs site.
- `data/` on its own path (Volume mount point if a Volume is added) so corpus
  and application lifecycles are independent.
- Backups: Hetzner automatic snapshots **plus** `restic` to a Hetzner **Storage
  Box** for the corpus and results — snapshots alone are not an offsite backup.

**Provisioning order** (each step is reversible):
1. Create the CX52 in Helsinki with an SSH key + your cloud-init/firewall
   attached at creation time.
2. Point Cloudflare A/AAAA at it, proxied.
3. Install Origin CA cert, bring up the reverse proxy, verify `Full (strict)`.
4. `git clone` this repo, `pip install -r requirements.txt`, stage the corpus
   per `docs/data_staging_layout.md`, then run
   `experiments/run_real_corpus.sh` once to reproduce every number end to end.
5. Enable backups + snapshots; add the Volume only if `df` says you need it.

---

## 5. One-line summary for the supervisor

> Take **CX52 (16 vCPU / 32 GB / 320 GB) in Helsinki**, roughly €32/mo — the
> 32 GB is what the corpus parsing actually requires, the rest is headroom;
> a GPU is a *separate* Hetzner dedicated (GEX) machine added later and linked
> by vSwitch, because Hetzner Cloud has no GPU instances at all.
