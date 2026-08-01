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

> **Correction (2026-08-01).** An earlier draft of this document recommended a
> "CX52 at ~€32/mo" based on third-party pricing pages. That plan is **not what
> the console offers on this account**: the CX family sits under the
> *Cost-Optimized* tab and is marked *Limited availability*, and this account
> bills in **USD at the post-June-2026 rates**. Everything below is taken from
> the actual Helsinki create-server menu.

### The menu, as it actually appears (Helsinki, USD, incl. 20 TB traffic)

| Plan | vCPU | RAM | SSD | $/mo | Meets the 16 GB requirement? |
|---|---:|---:|---:|---:|---|
| CPX32 | 4 | 8 GB | 160 GB | 41.99 | no (tight) |
| **CPX42** | **8** | **16 GB** | **320 GB** | **81.99** | **yes** |
| CPX52 | 12 | 24 GB | 480 GB | 118.99 | yes (over-spec) |
| CPX62 | 16 | 32 GB | 640 GB | 152.99 | yes + full-fidelity ts |
| CCX23 (dedicated) | 4 | 16 GB | 160 GB | 101.49 | yes, but +$19 for fewer cores |
| CCX33 (dedicated) | 8 | 32 GB | 240 GB | 162.99 | yes, but +$81 |

Add ~$0.60/mo for the IPv4 address. Helsinki carries no location surcharge
(Singapore adds $16/mo).

### Primary recommendation — **CPX42** (8 vCPU / 16 GB / 320 GB, Helsinki), $81.99/mo

Rationale, tied to the measurements in §1:
- **16 GB clears the binding constraint.** Measured peak ingest RSS is 0.73 GB;
  the realistic concurrent load (web + dashboard + an ingest + PyTorch + Docker
  + TeX) lands around 6–8 GB, so 16 GB runs everything with the corpus
  comfortably in page cache rather than being re-read from disk.
- **320 GB is ~9x the 34 GB working set** (3.4 GB corpus + 10.6 GB staging +
  ~15 GB toolchain + snapshots), leaving room for several more datasets.
- CPU is not the constraint, so paying for more cores buys nothing here; 8
  vCPU comes bundled with the RAM tier anyway.

### Why *not* 32 GB (CPX62 / CCX33)

The only thing the extra 16 GB buys is ingesting `UAV-CAS_ts.csv` with the raw
per-packet arrays retained in `native`, instead of passing `--drop-native-lists`.
That is a weak justification for **+$71–81/mo ($850–970/yr)**, because: the ts
file is currently out of scope; the adapter retains every summary metric
(packets, bytes, duration, rate, fwd/bwd counts) either way; and the paper's
UAV-CAS analysis uses the *stat* file, not ts. Take CPX42 and pass the flag.

### Why *not* dedicated vCPU (CCX)

The usual argument is timing reproducibility, and this project does publish
per-policy execution times — but that measurement takes **0.01 s**, so
noisy-neighbour variance is irrelevant to it. CCX23 costs $19/mo more than
CPX42 for *half* the cores and *half* the disk. Not worth it here.

### Before ordering: check the **Cost-Optimized** tab

The console's *Cost-Optimized* tab (CX on x86, CAX on Arm64) is marked
*Limited availability* and is not shown in the screenshots. If a 16 GB option
has stock in Helsinki it will be materially cheaper than CPX42 — worth one
click before committing. Caveat: prefer **x86** for the publication host, since
the paper reports execution timings and reviewers will reproduce on x86; Arm64
(CAX) is a fine choice for a later CI/build node.

### A legitimate start-small option

**CPX32 (4/8/160, $41.99/mo)** — the same tier as `robustidps.ai` — runs
everything measured *today* (0.73 GB peak ingest, 0.01 s campaign points,
490 MB staging). 8 GB gets tight once PyTorch training, the web stack, and
Docker run concurrently, but Hetzner supports **rescaling up in place**, so
starting here and moving to CPX42 when the full corpus lands is a defensible,
reversible choice.

> **Budget warning:** the running `robustidps.ai` CPX32 shows **$16.49/mo** on
> its overview page, but the create page now quotes **$41.99/mo** for that same
> tier. The existing server is on grandfathered pre-increase pricing; any *new*
> server is billed at current rates. Expect the new machine to cost 2.5x
> (CPX32) to 5x (CPX42) what the current one does.

### Add-ons
- **Volume (block storage)** — not needed at CPX42's 320 GB. If the corpus later
  outgrows it, attach a Volume and mount it at `data/`, so the corpus can be
  snapshotted, detached, and resized without touching the OS disk.
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

1. **Now:** the CPX42 cloud server is the permanent home for the website, the
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

> Take **CPX42 (8 vCPU / 16 GB / 320 GB) in Helsinki, $81.99/mo** -- 16 GB is
> what the corpus parsing actually requires and 320 GB is ~9x the working set;
> skip the 32 GB tiers, whose only benefit costs an extra ~$850/yr. Check the
> *Cost-Optimized* tab first in case a cheaper 16 GB x86 option has stock.
> Note that a new server costs 2.5-5x the grandfathered price of the existing
> `robustidps.ai` box. A GPU is a **separate** Hetzner dedicated (GEX) machine
> added later and linked by vSwitch, because Hetzner Cloud has no GPU
> instances at all.
