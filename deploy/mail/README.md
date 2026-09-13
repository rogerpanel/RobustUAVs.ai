# Self-hosted mail for robustuavs.ai

Four mailboxes — `roger@`, `admin@`, `support@`, `noreply@` — on the same
Hetzner box that serves the platform, fully under our own control: Postfix +
Dovecot + Rspamd (docker-mailserver) with Roundcube webmail at
`https://webmail.robustuavs.ai`. No third party holds the mail, and no
forwarding service sits in the path.

```
Internet ──────25────▶ mail.robustuavs.ai (grey, DNS-only) ┐
Mail clients ─465/587/993─▶                                ├─ robustuavs-mail
Roundcube ────────────────▶                                ┘
Browser ─443─▶ webmail.robustuavs.ai (orange, Cloudflare) ─▶ host Caddy
                                                            └─▶ 127.0.0.1:8081
                                                                robustuavs-webmail
certbot (DNS-01 via Cloudflare API) ─▶ Let's Encrypt cert for mail.robustuavs.ai
```

Adapted from the mail package built for RobustIDPS. The one structural
difference: robustuavs.ai has no application containers — the API is a
systemd unit behind **host Caddy** — so there is no app network for
Roundcube to join. It is published on loopback and Caddy proxies it.
Everything else (docker-mailserver, rspamd DKIM, the provisioning
sequence, the operator scripts) carries across unchanged.

---

## What the grey record costs

`docs/deployment_runbook.md` §2.2 is emphatic that every DNS record stays
**Proxied** and that publishing one grey is a one-way door: the origin
IPv4 is scraped into passive-DNS archives within hours and stays publicly
associated with the domain forever, even after the proxy is turned back
on. That is correct, and self-hosted mail breaks it.

It is unavoidable. `mail.robustuavs.ai` is the MX target, and every
sending mail server on the internet must open a TCP connection to it on
port 25. Cloudflare's proxy carries HTTP(S) only — it has nothing to
forward SMTP to. An orange cloud on `mail` returns a Cloudflare anycast
address and mail silently stops arriving.

So the trade, stated plainly:

- **Lost.** Origin-IP concealment. Anyone can now map `robustuavs.ai` to
  this server. The Cloudflare-IPs-only firewall rule on 80/443 still
  blocks direct web requests, but it no longer *also* hides which machine
  to aim at.
- **Kept.** The firewall rule itself. Keep `80,443/tcp` restricted to
  Cloudflare ranges. Only `25, 465, 587, 993` open to `0.0.0.0/0`, and
  those four are answered by the mail container, not the platform.
- **Alternative if that is unacceptable.** Put mail on a second, cheap
  VPS with its own IP and its own rDNS. The DNS records and this package
  work identically there; only `MAIL_HOSTNAME` and the A record change.
  That keeps the platform's origin hidden at the cost of another host to
  patch.

Decide this before running the setup script, not after the record is
published — because after is too late.

---

## Prerequisites (one-time, outside the server)

| # | Where | What |
|---|-------|------|
| 1 | Hetzner → server → Networking → Reverse DNS | Set PTR for the IPv4 to `mail.robustuavs.ai`. Without it Gmail and Outlook reject or spam-folder everything, regardless of SPF/DKIM/DMARC. |
| 2 | Hetzner → Support | Request the outbound port 25 unblock. It is blocked by default on new projects. `setup-mail.sh` tests it and tells you; a grant on another project does **not** carry over. |
| 3 | Cloudflare → My Profile → API Tokens | "Edit zone DNS" template scoped to `robustuavs.ai`, carrying **both** `Zone / Zone / Read` and `Zone / DNS / Edit`. certbot resolves the zone by name before writing the challenge, so DNS:Edit alone fails. |
| 4 | Cloudflare → SSL/TLS → Origin Server | Confirm the origin certificate installed at `/etc/caddy/certs/origin.pem` covers `*.robustuavs.ai`. That is the default when you create one; if yours lists only the apex and `www`, reissue it with the wildcard or webmail returns Cloudflare 526. |
| 5 | Hetzner → Firewalls (if one is attached) | Add inbound `25, 465, 587, 993/tcp` from `0.0.0.0/0`. The Cloud Firewall is separate from `ufw` and `setup-mail.sh` cannot touch it. |

---

## Install (on the server, ~10 min)

```bash
ssh deploy@<server-ipv4>
cd /srv/robustuavs/repo
git fetch origin && git checkout dev/whelan-uavcas-ingest && git pull

cp deploy/mail/.env.mail.example deploy/mail/.env.mail
sudo nano deploy/mail/.env.mail            # relay credentials only if port 25 is blocked

sudo bash deploy/mail/setup-mail.sh --set-token    # paste the Cloudflare token, hidden
sudo bash deploy/mail/setup-mail.sh --check        # verify everything, change nothing
sudo bash deploy/mail/setup-mail.sh                # install
sudo bash deploy/mail/install-caddy-vhost.sh       # serve webmail.robustuavs.ai
```

`setup-mail.sh` opens the `ufw` ports, issues the certificate, starts the
containers, creates the four mailboxes (printing their passwords **once**),
adds the RFC-2142 aliases, generates the DKIM key, reloads Caddy, and
prints the exact DNS records to add.

`--check` is worth the extra minute. It verifies the Cloudflare token
against the live API and confirms the zone is resolvable *before* anything
contacts Let's Encrypt — a bad credential otherwise burns ACME attempts
and trips Cloudflare's auth rate limiter, and you wait an hour.

## DNS cut-over (Cloudflare → robustuavs.ai → DNS → Records)

1. **Remove Cloudflare Email Routing if it is on.** Its
   `route1/2/3.mx.cloudflare.net` MX records will otherwise keep winning
   inbound mail. A lock icon on those rows opens the Email Routing page;
   disable routing there, then delete the three MX rows. Any forwarding it
   was doing stops at that moment.
2. Add the records the setup script printed:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `mail` | server IPv4 | **DNS only** 🟤 |
| A | `webmail` | server IPv4 | Proxied 🟠 |
| MX | `@` | `mail.robustuavs.ai` · priority 10 | — |
| TXT | `@` | `v=spf1 mx -all` | — |
| TXT | `mail._domainkey` | `v=DKIM1; k=rsa; p=…` (from script output) | — |
| TXT | `_dmarc` | `v=DMARC1; p=quarantine; rua=mailto:admin@robustuavs.ai; adkim=s; aspf=s; pct=100` | — |

3. Wait ~5 min, then `bash deploy/mail/check-mail.sh` — everything ✔.
4. Send a test from Roundcube to a Gmail address and open **Show original**:
   SPF, DKIM and DMARC must all read `PASS`. Nothing in `check-mail.sh`
   proves that; only a delivered message does.

### Why SPF says `mx` and not `a`

`v=spf1 mx -all` authorises whatever the MX records point at — here, the
one grey `mail` host. `v=spf1 a -all` would authorise the **apex** A
record instead, which is Proxied, so it would authorise Cloudflare's
entire proxy range to send mail as `@robustuavs.ai`. That is a large
shared pool and not something to vouch for.

### Why the mail certificate is Let's Encrypt, not the Origin CA

The platform uses a Cloudflare Origin CA certificate, which is trusted
*only by Cloudflare* — that is precisely the point of it, paired with the
Cloudflare-IPs-only firewall rule. But Thunderbird speaking IMAPS to port
993 is not Cloudflare, and neither is a sending mail server doing STARTTLS
on 25. Those need a publicly trusted certificate, which is why the stack
runs its own certbot with a DNS-01 challenge. `check-mail.sh` fails loudly
if the Origin CA certificate ever ends up on port 993.

---

## Everything on this page needs sudo

`deploy/mail/.env.mail` and `cloudflare.ini` are mode 600 and root-owned,
because they hold an API token and possibly relay credentials. SSH logins
are the unprivileged `deploy` user, so any `docker compose` command
carrying `--env-file deploy/mail/.env.mail` fails with "permission denied"
without sudo. Commands that address a container by name do not need the
env file:

```bash
docker logs --tail=40 robustuavs-mail          # no sudo needed
sudo docker compose -f deploy/mail/docker-compose.mail.yml \
     --env-file deploy/mail/.env.mail ps
```

## Day-to-day: managing mailboxes

Use the helper — no docker commands to remember, and it refuses unsafe
operations rather than silently doing the wrong thing:

```bash
sudo bash deploy/mail/mailuser.sh list
sudo bash deploy/mail/mailuser.sh add     sarah          # prompts for a password
sudo bash deploy/mail/mailuser.sh passwd  sarah          # reset a forgotten password
sudo bash deploy/mail/mailuser.sh quota   sarah 2G
sudo bash deploy/mail/mailuser.sh alias   sales sarah    # sales@ delivers to sarah@
sudo bash deploy/mail/mailuser.sh aliases
sudo bash deploy/mail/mailuser.sh delete  sarah          # asks you to type the address
```

A bare name gets `@robustuavs.ai` appended; a full address is used as
given, so aliases can forward off-domain.

### There is no self-service password reset

Nobody can reset their own password from webmail, and there is no "forgot
password" link. A password-reset link needs a trusted second channel to
send it to, and for a mailbox the mailbox *is* that channel — so the only
safe reset path is an administrator:

```bash
sudo bash deploy/mail/mailuser.sh passwd sarah
```

Roundcube's `password` plugin is deliberately not enabled: every driver it
ships writes to an account store it can reach, and docker-mailserver keeps
accounts in another container with no password-change API. Enabling it
yields a Settings tab that fails on submit, which users read as broken mail
rather than an unsupported feature.

### Mail client settings

| | Server | Port | Security | Username |
|---|---|---|---|---|
| Incoming IMAP | `mail.robustuavs.ai` | 993 | SSL/TLS | full address |
| Outgoing SMTP | `mail.robustuavs.ai` | 587 | STARTTLS | full address |

---

## The four mailboxes

| Address | Intended use |
|---|---|
| `roger@robustuavs.ai` | Correspondence author on the papers. This is the address that goes on a submission, so it is the one that most needs DKIM/DMARC to pass — reviewers' institutional mail servers are strict. |
| `admin@robustuavs.ai` | Operations. Receives the RFC-2142 aliases (`postmaster@`, `abuse@`, `hostmaster@`, `webmaster@`) and the DMARC aggregate reports. Also the ACME registration address. |
| `support@robustuavs.ai` | The public contact address for the platform and the artifact. |
| `noreply@robustuavs.ai` | Outbound-only, for anything the platform sends itself. **Nothing uses it yet** — the platform has no login or registration flow, deliberately, until the paper clears review. The mailbox exists so that the address is reserved and DKIM-signed from day one rather than being introduced under deadline later. |

When there is something for `noreply@` to send, these are the settings —
a note for later, not wiring to add now:

```
SMTP_HOST=mail.robustuavs.ai
SMTP_PORT=587
SMTP_STARTTLS=1
SMTP_USER=noreply@robustuavs.ai
SMTP_PASSWORD=<from the setup output>
SMTP_FROM="RobustUAVs <noreply@robustuavs.ai>"
```

The API runs on the host, not in a container, so it reaches the mail
server over the published port on `mail.robustuavs.ai` like any other
client. Put `SMTP_PASSWORD` in the systemd unit's environment file, never
in the repo.

---

## Deliverability: this IP has no sending history

Authentication is necessary, not sufficient. SPF, DKIM, DMARC and rDNS all
passing gets a message *considered*; whether it lands in the inbox depends
on a reputation this address does not have yet. Expect some providers to
greylist or spam-folder the first messages. Reputation accrues over days
of low, steady volume — a burst of a hundred messages on day one is the
one thing that reliably makes it worse.

If deliverability needs a shortcut, set `RELAY_HOST` / `RELAY_PORT` /
`RELAY_USER` / `RELAY_PASSWORD` in `.env.mail` to route outbound through
SMTP2GO, Brevo or SES, and add that provider's `include:` to the SPF
record at the same time (the setup script prints the right SPF string for
whichever relay it finds configured). Inbound mail and storage stay on
this server either way.

---

## Backups

Everything lives in three named volumes — `robustuavs-mail_dms-data`
(the mail itself), `robustuavs-mail_dms-state` (rspamd and fail2ban
state), `robustuavs-mail_roundcube-db` (webmail settings and contacts) —
plus `deploy/mail/config/`, which holds the accounts file, the aliases and
the **DKIM private key**. Back that directory up; it is `.gitignore`d and
must never be committed.

```bash
sudo docker run --rm -v robustuavs-mail_dms-data:/data -v "$PWD/backups":/out alpine \
  tar czf /out/mail-$(date +%F).tgz -C /data .
sudo tar czf backups/mail-config-$(date +%F).tgz deploy/mail/config
```

Losing `deploy/mail/config/` means losing the DKIM key, which means
regenerating it and re-publishing the TXT record — recoverable, but every
message signed with the old key fails verification in the meantime.

---

## Later (optional hardening)

- **MTA-STS + TLS-RPT** — forces TLS on inbound mail. Needs a small static
  site at `mta-sts.robustuavs.ai`; Caddy can serve it from the same host in
  a few lines. Add once the basics are stable.
- **ClamAV** — `ENABLE_CLAMAV=1` in the compose file. Costs ~1.5 GB RAM,
  which matters on a CPX32 that is also running campaign jobs.
- **IPv6** — assign an address from the `/64`, set its PTR in Hetzner, add
  an AAAA for `mail`, then set `POSTFIX_INET_PROTOCOLS=all` and
  `DOVECOT_INET_PROTOCOLS=all`. Do all four or none: an AAAA without a PTR
  makes Gmail reject mail it currently accepts over IPv4.
- **Tighten DMARC** — start at `p=quarantine`, read the `rua` reports in
  `admin@` for a few weeks, move to `p=reject` once nothing legitimate is
  failing.
- **Backup MX** — a second cheap VPS or a relay's inbound queue, so mail is
  held rather than bounced while this box is down for a rescale.
