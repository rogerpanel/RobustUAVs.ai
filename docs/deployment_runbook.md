# Deployment runbook — Hetzner CPX32 + Cloudflare + GitHub

Companion to `docs/infrastructure.md` (which decides *what* to buy and *why*).
This file is the *how*: the create-server form field by field, then domain →
TLS → repository → deploy, end to end.

Everything below assumes the sizing decision already made: **CPX32 created at
160 GB, rescaled up to CPX42 with "CPU and RAM only" when a heavy week needs
it** (`docs/infrastructure.md` §2b).

---

## 1. The Hetzner create-server form, field by field

The order below follows the console page top to bottom. The column that
matters most is the last one — a few of these choices cannot be undone, and
those are the only ones worth slowing down for.

| # | Field | Set it to | Changeable later? |
|---|---|---|---|
| 1 | **Location** | **Helsinki** (`eu-central`) | **No** — a move means snapshot → new server. Volumes and Primary IPs are location-bound too. |
| 2 | **Image** | **Ubuntu 26.04 LTS** (Resolute Raccoon) or 24.04 LTS | Only by *Rebuild*, which **wipes the disk**. |
| 3 | **Type** | Shared vCPU → **x86** tab → **CPX32** | Yes (see §2b of infrastructure.md — but only ever with "CPU and RAM only"). |
| 4 | **Networking** | Public IPv4 ✅ · Public IPv6 ✅ | Yes. |
| 5 | **SSH keys** | **Add your public key here** | ⚠️ **No — not via the Console.** |
| 6 | **Volumes** | none | Yes, attach anytime. |
| 7 | **Firewall** | attach one (see below) | Yes. |
| 8 | **Backups** | your call (+20%) | Yes, toggled anytime. |
| 9 | **Placement groups** | none | Yes. |
| 10 | **Labels** | `project=robustuavs` | Yes. |
| 11 | **Cloud config** | paste `deploy/cloud-init.yaml` | **No** — first boot only. |
| 12 | **Name** | `robustuavs.ai` | Yes, cosmetic. |
| 13 | **Quantity** | **1** | — |

### The four fields actually worth care

**(5) SSH keys — the one genuine trap.** Select your public key *on this form*.
After the server exists, **the Hetzner Console offers no way to add an SSH
key** — you would be left with the root password Hetzner emails you, i.e.
password authentication on a public host, and recovering from it means going
through the browser VNC console. Everything else on this page is recoverable;
this one costs you an afternoon.

If you have no key yet, on your laptop:

```bash
ssh-keygen -t ed25519 -C "roger@robustuavs.ai" -f ~/.ssh/robustuavs
cat ~/.ssh/robustuavs.pub          # paste this into Hetzner
```

Paste the `.pub` line — never the file without `.pub`.

**Reusing an existing key is fine**, and if you already have keys in the
project (e.g. one from another server), simply tick them here. Because keys
cannot be added through the Console afterwards, **tick every key whose private
half you still control** — selecting several costs nothing, all of them land in
`/root/.ssh/authorized_keys`, and it is cheap insurance against discovering
later that one private key is gone. Do not tick a key you no longer trust:
revoking it means editing `authorized_keys` on the server, not the Console.

**(11) Cloud config — free now, tedious later.** Cloud-init runs *once*, at
first boot; there is no way to attach it to a running server. Paste
`deploy/cloud-init.yaml` (replace `<YOUR_SSH_PUBLIC_KEY>` first). It installs
Docker, Caddy, `ufw`, `fail2ban`, unattended security upgrades, and creates the
non-root `deploy` user the rest of this runbook uses. Skipping it is not fatal —
§2.3 does the same work by hand — but it is the cheapest ten seconds on the page.

**(7) Firewall — do not lock yourself out.** Attach one at creation with:

- `22/tcp` — inbound **from your admin IP only**.
- `80,443/tcp` — inbound **from Cloudflare's published IP ranges only**
  (`https://www.cloudflare.com/ips-v4` and `/ips-v6`), so nobody can reach the
  origin directly and bypass the proxy.
- Everything else denied inbound; all outbound allowed.

If your home IP is dynamic, restricting `22/tcp` to it *will* eventually lock
you out. Two things make that survivable: the Hetzner **web Console (VNC)** is
out-of-band and always works, and the cloud firewall is editable from the
Console without touching the server. If that still feels tight, open `22/tcp`
to `0.0.0.0/0` at first — the cloud-init sets key-only auth plus `fail2ban`, so
it is defensible — and narrow it once the machine is up.

Because §2.4 uses a **Cloudflare Origin CA** certificate rather than Let's
Encrypt, port 80 never needs to be open to the whole internet for an ACME
challenge. That is the main practical reason to prefer Origin CA here.

**(3) Type — pick the x86 tab, not Arm.** `CPX32` is AMD x86. The Arm line
(`CAX`) is cheaper per core, but `third_party/datamut` is C++ built on the host
and the PyTorch/CUDA ecosystem is smoothest on x86; the saving is not worth the
wheel-availability risk for a paper artifact.

### On the image: 24.04 vs 26.04

Both are LTS. **26.04 (Resolute Raccoon)** has the longer support window and
Docker publishes a `resolute` pool, so `deploy/cloud-init.yaml` works on it.
The only rough edge on a four-month-old LTS is third-party apt repositories
that have not built for the new codename yet — if the Caddy step fails during
first boot, `apt install caddy` from the distro archive, or point the Cloudsmith
list at `noble` instead. Nothing else in the cloud config is version-sensitive.

### Skipping the firewall and backups on the first build

Both are safe to leave unchecked now — unlike SSH keys and cloud config,
**both can be added at any time from the Console**, to a running server, with
no rebuild and no downtime. Only two things follow from skipping them.

**Without a Cloud Firewall the host firewall is doing all the work.** That is
acceptable, but only if the machine is actually hardened: `deploy/cloud-init.yaml`
sets key-only SSH, `ufw` denying everything inbound except 22/80/443, and
`fail2ban`. If you skip the cloud config *as well*, the server is bare — in that
case run the hardening block in §2.3 immediately after first login, before
anything else.

The second consequence is that your origin IPv4 is directly reachable, so the
Cloudflare proxy can be bypassed by anyone who learns the address. Harmless
while the host serves nothing, but **add the Cloud Firewall (`80,443/tcp` from
Cloudflare ranges only) before the artifact URL goes into a submitted paper.**

**Without Backups you have no rollback.** For the first days that is fine —
there is nothing on the disk that is not in GitHub or on Kaggle. Turn the
20% option on (~$8.40/mo on CPX32) once the corpus is staged and campaign
output starts accumulating, i.e. once the disk holds something you cannot
cheaply regenerate. Two caveats worth knowing early: Backups are **deleted
with the server**, so they are not a pause mechanism (convert one to a snapshot
first), and they are not offsite — `restic` to a Hetzner Storage Box still
belongs on the list.

### Before you click *Create*

- **Quantity reads 1.** The field defaults to 1 but sits next to the type
  selector and is easy to bump.
- **The price line reads about $41.99/mo**, plus ~$0.60–0.70 for the IPv4 and
  ~$8.40 if you ticked backups. If it reads $81.99, you are still on CPX42 —
  go back, because creating at CPX42 permanently forecloses the downgrade path
  (`infrastructure.md` §2b, Rule 1).
- Displayed prices exclude VAT, and this account bills in **USD**.
- **Name:** the field wants a valid RFC 1123 hostname, unique within the
  project. `robustuavs.ai` should be accepted; if the form objects to the dot
  or the case, use `robustuavs-ai`. Either way this is a label plus the
  machine's hostname — **it has nothing to do with DNS.** Naming the server
  after the domain does not point the domain at it; §2.2 does that.

---

## 2. Domain → server → repository

### 2.1 "Registering" the domain — already done

Buying `RobustUAVs.ai` through **Cloudflare Registrar** already completed
registration *and* put the domain on Cloudflare's nameservers. There is no
separate registration step and no nameserver change to make: the zone is live
in your dashboard and you only need to add records.

(Had you bought it elsewhere, the extra step would be: add the site to
Cloudflare, then change the nameservers at the registrar to the two Cloudflare
gives you, and wait for propagation. Not applicable here.)

### 2.2 DNS records

Cloudflare dashboard → `robustuavs.ai` → **DNS** → *Add record*:

| Type | Name | Content | Proxy | TTL |
|---|---|---|---|---|
| A | `@` | server IPv4 | Proxied 🟠 | Auto |
| AAAA | `@` | server IPv6 — the `::1` host, **without** the `/64` | Proxied 🟠 | Auto |
| CNAME | `www` | `robustuavs.ai` | Proxied 🟠 | Auto |
| A | `artifact` *(optional)* | server IPv4 | Proxied 🟠 | Auto |

**The AAAA record needs a single address, not the `/64` Hetzner shows you.**
The console displays something like `2a01:4f9:c014:d5f2::/64` — that is a
*prefix*, naming the whole block of 2^64 addresses Hetzner routes to the
server, and Cloudflare rightly rejects it ("Enter a valid IPv6 address").
Strip the `/64` and give the host part, which Hetzner configures as `::1`:

```
console shows   2a01:4f9:c014:d5f2::/64      <- a subnet, not an address
paste into DNS  2a01:4f9:c014:d5f2::1        <- the server itself
```

Do not use the bare `…d5f2::` either: an all-zero host part is the
subnet-router anycast address, not the machine. Confirm what the interface
actually holds once you can log in:

```bash
ip -6 addr show scope global      # expect …:d5f2::1/64 on eth0
```

**Leave the proxy ON (orange 🟠) from the very first save.** The moment a
record is published grey, the origin IPv4 is scraped into passive-DNS archives
and stays publicly associated with the domain **forever**, even after you turn
the proxy on — which quietly defeats the point of the Cloudflare-IPs-only
firewall rule. Publishing grey "just while building" is a one-way door.

The only thing you give up is direct `curl` diagnostics, and the SSH tunnel
covers that without exposing anything:

```bash
ssh -L 8080:127.0.0.1:80 deploy@<SERVER_IPv4>   # then curl http://127.0.0.1:8080/
```

**Expect Cloudflare error 521 ("web server is down") between saving the record
and finishing §2.4.** That is correct behaviour, not a misconfiguration: the
proxy is live but no web server is listening on the origin yet. It clears the
moment Caddy comes up with the Origin CA certificate.

Before saving, confirm the IPv4 you paste is the **new** server's — Hetzner
Console → Servers → the CPX32 → *Networking* → Public IPv4. It is easy to
paste the address of an existing box out of muscle memory, and the resulting
failure looks like a TLS problem rather than a wrong-host problem.

Then **SSL/TLS → Overview → Full (strict)**, and under *Edge Certificates*
enable **Always Use HTTPS** and **HSTS**.

> Do not leave the mode on *Flexible*. Flexible means Cloudflare talks plain
> HTTP to your origin — the padlock in the browser would be a lie.

### 2.3 First login and hardening

```bash
ssh root@<SERVER_IPv4>              # first login uses the key from form field 5
cloud-init status --wait            # wait for the cloud config to finish
ssh deploy@<SERVER_IPv4>            # from here on, work as `deploy`
```

If you skipped the cloud config, do the equivalent by hand:

```bash
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy/
apt update && apt -y upgrade
apt -y install git python3-venv python3-pip build-essential rsync ufw fail2ban \
               unattended-upgrades
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl reload ssh
ufw default deny incoming && ufw default allow outgoing
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
```

Confirm password login is off before you close the session:
`sshd -T | grep -i passwordauth` must print `passwordauthentication no`.

### 2.4 TLS with a Cloudflare Origin CA certificate

Cloudflare dashboard → **SSL/TLS → Origin Server → Create Certificate**.
Accept the defaults (RSA, hostnames `robustuavs.ai` and `*.robustuavs.ai`,
15-year validity). Cloudflare shows the certificate and the key **once** — copy
both now.

On the server:

```bash
sudo mkdir -p /etc/caddy/certs
sudo nano /etc/caddy/certs/origin.pem     # paste the certificate
sudo nano /etc/caddy/certs/origin.key     # paste the private key
sudo chown -R caddy:caddy /etc/caddy/certs
sudo chmod 600 /etc/caddy/certs/origin.key

sudo install -m 0644 /srv/robustuavs/repo/deploy/Caddyfile /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Verify, then flip the DNS records to Proxied:

```bash
curl -sSI https://robustuavs.ai/ | head -1        # expect HTTP/2 200
curl -sSI https://robustuavs.ai/ | grep -i cf-    # cf-ray => proxy is on
```

A 15-year Origin CA certificate never renews, so nothing can silently expire
mid-review. It is only trusted by Cloudflare, which is exactly the point:
combined with the Cloudflare-IPs-only firewall rule, the origin is unreachable
except through the proxy.

### 2.5 Connecting the GitHub repository — use a deploy key

The server needs to **read** the repository forever and should never be able to
**write** to it. That is precisely a GitHub *deploy key*: a keypair scoped to
one repository, read-only unless you tick write access.

Do not copy your personal SSH key onto the server, and do not use a personal
access token. Both give a machine that is exposed to the internet the ability
to push to every repository you own; a deploy key compromised on the server
leaks read access to one repo and nothing else.

**On the server, as `deploy`:**

```bash
ssh-keygen -t ed25519 -f ~/.ssh/gh_robustuavs -N "" \
           -C "robustuavs.ai deploy key"
cat ~/.ssh/gh_robustuavs.pub
```

**On GitHub:** repository → **Settings → Deploy keys → Add deploy key**.
Title `robustuavs.ai server`, paste the public key, and **leave "Allow write
access" unchecked**.

**Back on the server**, pin the key to GitHub via an SSH alias so `git` picks
it up without any environment fiddling:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github-robustuavs
    HostName github.com
    User git
    IdentityFile ~/.ssh/gh_robustuavs
    IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config

ssh -T github-robustuavs        # expect: "Hi rogerpanel/RobustUAVs.ai! ..."
```

Clone through the alias:

```bash
mkdir -p /srv/robustuavs
git clone git@github-robustuavs:rogerpanel/RobustUAVs.ai.git \
          /srv/robustuavs/repo
cd /srv/robustuavs/repo
```

From now on `git pull`, `git fetch`, and `git checkout <branch>` work normally
in that directory — including the working branches, e.g.
`git checkout claude/whelan-uavcas-ingest-u00isn`.

### 2.6 Python environment and the first full reproduction

```bash
cd /srv/robustuavs/repo
python3 -m venv /srv/robustuavs/venv
/srv/robustuavs/venv/bin/pip install -r requirements.txt

# Stage the corpus per docs/data_staging_layout.md, then reproduce end to end:
/srv/robustuavs/venv/bin/python -m pip install kagglehub
./experiments/run_real_corpus.sh
```

`data/raw/` and `data/staging/` are gitignored, so the corpus lives on the
server independently of the repository and survives every deploy.

### 2.7 Deploying — three routes, in increasing automation

**(a) Manual, from your laptop.** The everyday case:

```bash
ssh deploy@robustuavs.ai '/srv/robustuavs/repo/deploy/deploy.sh'
```

`deploy/deploy.sh` fetches, hard-resets to `origin/$BRANCH`, refreshes the
venv, runs `ingest/validate.py` over any staged output as a gate, mirrors the
artifact tree into `/srv/robustuavs/artifact`, reloads Caddy only if the
`Caddyfile` changed, and brings up the Docker stack if one is defined. It never
touches `data/`.

Make it a one-word command by adding to your laptop's `~/.ssh/config`:

```
Host robustuavs
    HostName robustuavs.ai
    User deploy
    IdentityFile ~/.ssh/robustuavs
```

then `ssh robustuavs /srv/robustuavs/repo/deploy/deploy.sh`.

**(b) Directly on the server.** For experiment work you are iterating on live:

```bash
ssh robustuavs
cd /srv/robustuavs/repo && ./deploy/deploy.sh
```

Note `deploy.sh` does `git reset --hard`, so **do not keep uncommitted edits in
`/srv/robustuavs/repo`** — they will be discarded. Treat the server checkout as
a read-only mirror of GitHub and do editing on your laptop. If you must
experiment on the server, work in a scratch clone elsewhere.

**(c) Push-to-deploy via GitHub Actions.** Copy
`deploy/github-actions-deploy.yml.example` to `.github/workflows/deploy.yml`
and add the four repository secrets it documents. Every push to `main` then
runs `deploy.sh` on the server and smoke-tests `https://robustuavs.ai/`.

Note the direction of trust: Actions only supplies the *trigger*. The server
still pulls from GitHub with its own read-only deploy key, so a compromised
Actions runner cannot write to the server's filesystem beyond running that one
script. Gate it behind a `production` environment with required reviewers if
you want a manual approval step.

---

## 3. Ordered checklist

```
[ ]  1. Laptop: ssh-keygen; copy the .pub
[ ]  2. Hetzner: create CPX32 / Helsinki / Ubuntu 26.04 LTS / x86
         - SSH key(s) selected         <- cannot be added later
         - cloud-init pasted           <- first boot only
         - firewall + backups optional <- both attachable any time
         - quantity 1, price ~$42.59 with the IPv4
[ ]  3. Cloudflare DNS: A + AAAA + CNAME, Proxied from the first save
         (expect error 521 until step 5 — that is normal)
[ ]  4. ssh root@IP; cloud-init status --wait; verify the deploy user
[ ]  5. Origin CA cert -> /etc/caddy/certs; install Caddyfile; reload
[ ]  6. SSL/TLS = Full (strict); curl https://robustuavs.ai/ -> 200
[ ]  7. Server: generate the deploy key; add it read-only on GitHub
[ ]  8. git clone via the github-robustuavs alias into /srv/robustuavs/repo
[ ]  9. venv + requirements; stage the corpus; run_real_corpus.sh
[ ] 10. ./deploy/deploy.sh; confirm https://robustuavs.ai/ serves
[ ] 11. Enable Hetzner backups; add restic -> Storage Box for offsite
[ ] 12. Optional: enable the Actions workflow for push-to-deploy
```

---

## 4. Afterwards

- **Rescaling up for a heavy week:** Console → Rescale → **"CPU and RAM
  only"** → CPX42. Never the option that also grows the disk — see
  `infrastructure.md` §2b, Rule 1.
- **Pausing:** snapshot → delete the server → **retain the Primary IP**, so the
  Cloudflare records stay valid and nothing needs re-pointing on resume
  (`infrastructure.md` §2b, Rule 2). A powered-off server is still billed in
  full.
- **Adding the GPU box later:** a separate Hetzner *dedicated* GEX machine
  linked by vSwitch — Hetzner Cloud has no GPU instances at all
  (`infrastructure.md` §3).
