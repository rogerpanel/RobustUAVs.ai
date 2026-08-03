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

### Primary recommendation — **create as CPX32, rescale to CPX42 on demand**

Create the server as **CPX32** (4 vCPU / 8 GB / 160 GB, $41.99/mo) and rescale
it up to **CPX42** (8 vCPU / 16 GB, $81.99/mo) using the **"CPU and RAM only"**
option whenever a heavy week demands it — then rescale back down.

This gives CPX42 capability when it is needed and CPX32 cost the rest of the
time. The reason to create at the *smaller* tier is Rule 1 in §2b: a server
created as CPX42 has a 320 GB disk and can never be downgraded, because disks
cannot shrink. Creating at CPX32 keeps the 160 GB disk and therefore keeps the
downgrade path open permanently.

Rationale, tied to the measurements in §1:
- **16 GB clears the binding constraint when it matters.** Measured peak ingest
  RSS is 0.73 GB; the realistic concurrent load (web + dashboard + an ingest +
  PyTorch + Docker + TeX) lands around 6–8 GB. CPX32's 8 GB handles the current
  workload; CPX42's 16 GB gives comfort during full-corpus ingest and training,
  with the corpus held in page cache rather than re-read from disk.
- **160 GB is ~4.7x the 34 GB working set** (3.4 GB corpus + 10.6 GB staging +
  ~15 GB toolchain + snapshots) — ample, and the 320 GB of a natively-created
  CPX42 is headroom this project does not need.
- CPU is not the constraint, so paying for more cores buys nothing here; the
  extra vCPUs simply come bundled with the RAM tier.

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

---

## 2b. Cost control: rescaling up/down, and "pausing" the server

Two Hetzner behaviours govern this, and both are counter-intuitive enough to
cost money if assumed wrongly.

### Rule 1 — a disk can grow but never shrink

Rescaling offers two modes:
- **"CPU and RAM only"** — keeps the current disk. **Downgrading stays possible.**
- **CPU, RAM *and* disk** — grows the disk. **This is irreversible**, and it
  permanently blocks any downgrade to a plan with a smaller disk.

Consequence for the plan chosen above: a server *created* as CPX42 has a
320 GB disk, and **cannot** later be downgraded to CPX32 (160 GB), because that
would require shrinking the disk.

**Therefore, to keep the CPX32 ⇄ CPX42 flexibility you asked for, create the
server as CPX32 (160 GB) and, when you need more, rescale up choosing
"CPU and RAM only".** You then get CPX42's 8 vCPU / 16 GB while keeping the
160 GB disk, and you can drop back to CPX32 whenever the work is quiet.

Nothing is lost by this: the measured working set is ~34 GB, so a 160 GB disk
is still ~4.7x what the project needs — the 320 GB of a natively-created CPX42
was headroom we do not require.

### Rule 2 — powering off does **not** stop billing

Hetzner bills a cloud server for as long as it *exists*, regardless of power
state, because the resources stay reserved. Shutting the server down saves
nothing. To actually stop paying you must **delete** it.

The safe "pause" pattern is therefore:

1. **Snapshot** the server (this is what preserves the machine).
2. **Delete** the server.
3. Later, **create a new server from the snapshot** — same disk contents.

Keep the **Primary IP** when deleting (Hetzner lets you retain it for ~$0.60/mo)
so the Cloudflare DNS records keep pointing at the right address and nothing
needs re-pointing on resume.

Note that **Backups** (the 20% add-on) are tied to the server and go away with
it — they are *not* a pause mechanism. Convert a backup to a snapshot first if
you want to keep it past deletion. Snapshots are billed on the compressed disk
size at about €0.0143/GB/month.

### What this costs, for a ~40 GB disk

| State | Cost |
|---|---|
| CPX42 running | $81.99/mo |
| CPX32 running | $41.99/mo |
| **Paused** (snapshot + retained IPv4) | **≈ $1.22/mo** |

Annualised over realistic research rhythms:

| Pattern | Per year | Saving |
|---|---:|---:|
| Always-on CPX42 | $991 | — |
| Always-on CPX32 | $511 | 48% |
| 6 mo CPX42 + 6 mo CPX32 | $751 | 24% |
| 4 mo CPX42 + 4 mo CPX32 + 4 mo paused | $506 | 49% |
| 3 mo CPX42 + 9 mo paused | $259 | 74% |

Billing is **hourly with a monthly cap**, so partial months are pro-rata: a
CPX42 alive for ten days costs roughly $27, not $82. Short-lived experiment
servers are genuinely cheap, and you do not need to delete a server to benefit
from a partial month.

### Recommended operating rhythm for this project

- **Create as CPX32.** Run the website, artifact, and the detector campaign
  here permanently — this is the tier that must stay up, since it serves
  `robustuavs.ai`.
- **Rescale up to CPX42 ("CPU and RAM only") only for heavy weeks** — full
  corpus ingest, model training, large sweeps — then rescale back down.
- **Pause only if the site can go offline**: snapshot + delete, retain the
  Primary IP. Because the site is the public artifact for a submitted paper,
  full pausing is probably only appropriate before publication or between
  project phases.
- A cheaper always-on alternative if the site must stay up while compute
  pauses: keep a small CPX12/CPX22 serving the static artifact permanently, and
  create/delete a bigger machine per experiment campaign. The repo supports
  this: everything is reproducible from `experiments/run_real_corpus.sh`.

### Add-ons
- **Volume (block storage)** — not needed at 160 GB. Note a further advantage
  of Volumes for this workflow: a Volume **survives server deletion**, so
  putting `data/` on one lets you delete/recreate the compute node freely
  without re-downloading the corpus.
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

1. **Now:** the cloud server (CPX32, rescaled up as needed) is the permanent
   home for the website, the artifact, the schema/adapters, the detector
   campaign, and CPU experiments.
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
1. Create the server as **CPX32** in Helsinki with an SSH key + your
   cloud-init/firewall attached at creation time.
2. Point Cloudflare A/AAAA at it, proxied.
3. Install Origin CA cert, bring up the reverse proxy, verify `Full (strict)`.
4. `git clone` this repo, `pip install -r requirements.txt`, stage the corpus
   per `docs/data_staging_layout.md`, then run
   `experiments/run_real_corpus.sh` once to reproduce every number end to end.
5. Enable backups + snapshots; add the Volume only if `df` says you need it.

---

## 5. One-line summary for the supervisor

> **Create it as CPX32 (4 vCPU / 8 GB / 160 GB, $41.99/mo) in Helsinki, and
> rescale up to CPX42 with the "CPU and RAM only" option** whenever a heavy week
> needs 16 GB -- creating at the bigger tier would give a 320 GB disk that can
> never shrink, permanently blocking the downgrade path. 160 GB is still ~4.7x
> the working set. Skip the 32 GB tiers, whose only benefit costs ~$850/yr extra.
> Check the *Cost-Optimized* tab first in case a cheaper x86 option has stock.
> To truly pause, snapshot and **delete** the server (a powered-off server is
> still billed in full) and retain the Primary IP; an idle month then costs
> about $1.22 instead of $42-82.
> Note that a new server costs 2.5-5x the grandfathered price of the existing
> `robustidps.ai` box. A GPU is a **separate** Hetzner dedicated (GEX) machine
> added later and linked by vSwitch, because Hetzner Cloud has no GPU
> instances at all.
