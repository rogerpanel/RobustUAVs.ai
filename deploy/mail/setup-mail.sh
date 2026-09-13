#!/usr/bin/env bash
# One-shot bootstrap for the self-hosted mail stack on robustuavs.ai.
#
#   sudo bash deploy/mail/setup-mail.sh
#
# Idempotent: re-running skips accounts that already exist and reuses
# existing DKIM keys and certificates. Run from the repo root on the server.
#
# Flags:
#   --check       Run preconditions and Cloudflare token verification only,
#                 then stop. Changes nothing. Use it to diagnose credential
#                 problems without starting containers or contacting Let's
#                 Encrypt.
#   --set-token   Write deploy/mail/cloudflare.ini from a hidden prompt.
#                 Exists so operators never have to paste a secret into an
#                 editor inside the Hetzner web console, which silently
#                 rewrites bracket and quote characters.
#
# Adapted from the RobustIDPS mail package. The substantive differences are
# that robustuavs.ai has no application containers — Caddy runs on the host
# and the API is a systemd unit — so Roundcube is published on loopback and
# proxied by Caddy rather than joining an app network behind nginx.
set -euo pipefail

CHECK_ONLY=0
SET_TOKEN=0
case ${1:-} in
  --check)     CHECK_ONLY=1 ;;
  --set-token) SET_TOKEN=1; CHECK_ONLY=1 ;;
esac

cd "$(dirname "$0")/../.."
ENV_FILE=deploy/mail/.env.mail
COMPOSE_FILE=deploy/mail/docker-compose.mail.yml
COMPOSE="docker compose -f $COMPOSE_FILE --env-file $ENV_FILE"
DOMAIN=robustuavs.ai
CONTAINER=robustuavs-mail
ACCOUNTS=(roger admin support noreply)
ALIASES=("postmaster:admin" "abuse:admin" "hostmaster:admin" "webmaster:admin")

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
amber() { printf '\033[33m%s\033[0m\n' "$*"; }
bold()  { printf '\033[1m%s\033[0m\n' "$*"; }

# ── 0a. Write the Cloudflare token (--set-token) ─────────────────────────
if [[ $SET_TOKEN -eq 1 ]]; then
  bold "Set Cloudflare API token"
  # Check writability BEFORE prompting. cloudflare.ini is usually created by
  # an earlier root-run step and chmod'd 600, while SSH logins are the
  # unprivileged `deploy` user — so the write fails. Discovering that after
  # the operator has already pasted a secret wastes a rolled token.
  CF_INI=deploy/mail/cloudflare.ini
  if { [[ -e $CF_INI && ! -w $CF_INI ]]; } || { [[ ! -e $CF_INI && ! -w deploy/mail ]]; }; then
    red "  cannot write $CF_INI — you are $(id -un)"
    [[ -e $CF_INI ]] && ls -l "$CF_INI" | sed 's/^/      /'
    red "  The file belongs to another user (it was created by a root-run step)."
    red "  Re-run with sudo:"
    red "      sudo bash deploy/mail/setup-mail.sh --set-token"
    exit 1
  fi
  echo "  Paste the token, then press Enter. Input is hidden."
  read -rsp '  token: ' _TOK; echo
  _TOK=$(printf '%s' "$_TOK" | tr -d '[:space:]')
  [[ -n $_TOK ]] || { red "  nothing entered"; exit 1; }
  # Validate the character set, not the length. Cloudflare has shipped
  # tokens of differing lengths, so a hardcoded length only produces false
  # alarms. The character set is stable (base62 plus - and _), and it is
  # what actually catches a terminal that rewrites characters on paste:
  # the Hetzner web console maps '[' to '{', and '{' is not legal here.
  if [[ ! $_TOK =~ ^[A-Za-z0-9_-]+$ ]]; then
    red "  rejected: contains characters that never appear in a Cloudflare token."
    red "  Legal characters are A-Z a-z 0-9 _ -"
    red "  This is the signature of a terminal altering the text on paste."
    red "  Copy the token again in a terminal that pastes verbatim (not the"
    red "  Hetzner web console), or type it by hand."
    exit 1
  fi
  echo "  length: ${#_TOK} characters, character set valid"
  printf 'dns_cloudflare_api_token = %s\n' "$_TOK" > deploy/mail/cloudflare.ini
  chmod 600 deploy/mail/cloudflare.ini
  green "  wrote deploy/mail/cloudflare.ini (${#_TOK} characters)"
  unset _TOK
  echo
fi

# ── 0. Preconditions ─────────────────────────────────────────────────────
# The install path needs root: ufw rule changes and the compose stack both
# require it. Say so up front rather than failing partway through with a
# bare "Permission denied". --check and --set-token do not need root.
if [[ $CHECK_ONLY -eq 0 && ${EUID:-$(id -u)} -ne 0 ]]; then
  red "This script must run as root to install (ufw rules, containers)."
  red "  sudo bash deploy/mail/setup-mail.sh"
  red "Read-only modes do not need root: --check, --set-token"
  exit 1
fi
command -v docker >/dev/null || {
  red "docker not found. deploy/cloud-init.yaml installs it; on a server built"
  red "without the cloud config, follow docs/deployment_runbook.md §2.3."
  exit 1
}
docker compose version >/dev/null 2>&1 || {
  red "The docker compose plugin is missing (docker-compose-plugin package)."
  exit 1
}
[[ -f $ENV_FILE ]] || { red "Missing $ENV_FILE — copy deploy/mail/.env.mail.example and fill it in."; exit 1; }
[[ -f deploy/mail/cloudflare.ini ]] || {
  red "Missing deploy/mail/cloudflare.ini."
  red "  sudo bash deploy/mail/setup-mail.sh --set-token"
  exit 1
}
for f in deploy/mail/cloudflare.ini "$ENV_FILE"; do
  [[ -r $f ]] && continue
  red "Cannot read $f — you are $(id -un)"
  ls -l "$f" 2>/dev/null | sed 's/^/  /'
  red "These files are mode 600 and owned by the user that created them."
  red "Re-run with sudo, e.g.:  sudo bash deploy/mail/setup-mail.sh ${1:-}"
  exit 1
done
grep -q PASTE_TOKEN_HERE deploy/mail/cloudflare.ini && { red "deploy/mail/cloudflare.ini still has the placeholder token."; exit 1; }
# Non-owners cannot chmod; not fatal, the readability check above already
# established we can use the files.
chmod 600 deploy/mail/cloudflare.ini "$ENV_FILE" 2>/dev/null || true
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a
MAIL_HOSTNAME=${MAIL_HOSTNAME:-mail.$DOMAIN}
mkdir -p deploy/mail/config

# ── 0b. Outbound port 25 ─────────────────────────────────────────────────
# Hetzner blocks outbound 25 on new projects until support lifts it. Test it
# rather than assuming: the unblock is granted per project, so whether the
# RobustIDPS server has it says nothing about this one. Not fatal — inbound
# mail and webmail work regardless, and a relay covers outbound — but
# finding out now beats finding out from a queue of deferred messages.
bold "[0/6] Outbound port 25"
if timeout 6 bash -c '</dev/tcp/gmail-smtp-in.l.google.com/25' 2>/dev/null; then
  green "  open — this server can deliver mail directly"
else
  amber "  BLOCKED. Nothing this server sends will reach another mail server."
  amber "  Two options, both fine:"
  amber "    1. Hetzner Cloud Console -> Support -> request the port 25 unblock"
  amber "       (state the use: transactional and staff mail for robustuavs.ai)."
  amber "    2. Set RELAY_HOST / RELAY_USER / RELAY_PASSWORD in $ENV_FILE and"
  amber "       re-run. Inbound mail and storage stay on this server either way."
  amber "  Continuing — everything else installs normally."
fi

# ── 0c. Verify the Cloudflare token BEFORE involving Let's Encrypt ───────
# Two cheap API calls that distinguish failure modes Cloudflare otherwise
# reports identically. Without this, a bad credential sends certbot into
# repeated failed lookups, trips Cloudflare's auth rate limiter (429), and
# burns ACME attempts for nothing.
bold "[0/6] Verifying Cloudflare API token"
CF_TOKEN=$(sed -n 's/^[[:space:]]*dns_cloudflare_api_token[[:space:]]*=[[:space:]]*//p' \
           deploy/mail/cloudflare.ini | tr -d '"'\''\r\n[:space:]')
[[ -n $CF_TOKEN ]] || { red "  no dns_cloudflare_api_token found in deploy/mail/cloudflare.ini"; exit 1; }
echo "      token length: ${#CF_TOKEN} chars"
# No length assertion: Cloudflare token length has varied, and a hardcoded
# value only produces false alarms. The API call below is the arbiter.
if [[ ! $CF_TOKEN =~ ^[A-Za-z0-9_-]+$ ]]; then
  red "  token contains illegal characters (legal: A-Z a-z 0-9 _ -)"
  red "  Almost certainly altered on paste. Re-set it with:"
  red "      sudo bash deploy/mail/setup-mail.sh --set-token"
  exit 1
fi

CF_CODE=$(curl -s -o /tmp/cf_verify.$$ -w '%{http_code}' \
  https://api.cloudflare.com/client/v4/user/tokens/verify \
  -H "Authorization: Bearer $CF_TOKEN") || true
case "$CF_CODE" in
  200) green "  [1/2] token string is valid" ;;
  429) red "  Cloudflare is rate-limiting this IP: 'too many authentication failures'."
       red "  This clears on its own — wait 30-60 min and re-run. Do NOT retry in a loop."
       rm -f /tmp/cf_verify.$$; exit 1 ;;
  *)   red "  [1/2] token REJECTED by Cloudflare (HTTP $CF_CODE)"
       sed 's/^/      /' /tmp/cf_verify.$$ 2>/dev/null | head -5
       red "  The token string itself is wrong — permissions are not the issue here."
       red "  Re-copy it from Cloudflare -> My Profile -> API Tokens (it is shown once;"
       red "  use 'Roll' to generate a fresh value), then:"
       red "      sudo bash deploy/mail/setup-mail.sh --set-token"
       rm -f /tmp/cf_verify.$$; exit 1 ;;
esac
rm -f /tmp/cf_verify.$$

# The token can be valid yet unable to resolve the zone by name, which is
# precisely the call certbot makes first. Test that exact capability.
CF_ZONES=$(curl -s "https://api.cloudflare.com/client/v4/zones?name=$DOMAIN" \
  -H "Authorization: Bearer $CF_TOKEN") || true
if grep -q '"id"' <<<"$CF_ZONES" && grep -q '"success":true' <<<"$CF_ZONES"; then
  green "  [2/2] token can resolve zone $DOMAIN"
else
  red "  [2/2] token is valid but CANNOT look up zone '$DOMAIN'"
  sed 's/^/      /' <<<"$CF_ZONES" | head -5
  red "  certbot resolves the zone by name before writing the challenge record."
  red "  Add 'Zone / Zone / Read' to the token (keep 'Zone / DNS / Edit'), or confirm"
  red "  the token's Zone Resources include $DOMAIN. Then re-run this script."
  exit 1
fi

# ── 0d. Confirm every image reference resolves ───────────────────────────
# A bad tag otherwise surfaces at step 3, after the certificate has already
# been issued — the expensive place to find out. Non-fatal: a registry
# hiccup or rate limit must not block an otherwise valid install, so this
# warns rather than exits and lets the pull be the final authority.
bold "[0/6] Checking image references"
for _img in $(awk '/^[[:space:]]+image:[[:space:]]*/{print $2}' "$COMPOSE_FILE"); do
  if docker manifest inspect "$_img" >/dev/null 2>&1; then
    green "  ok  $_img"
  else
    red   "  !!  $_img — not resolvable (bad tag, or registry unreachable)"
  fi
done

# ── 0e. Is Caddy ready to serve webmail? ─────────────────────────────────
# Reported, never repaired: this script does not edit /etc/caddy/Caddyfile.
# A mail install has no business rewriting the config that serves the
# platform, and a failed edit there takes robustuavs.ai down with it.
bold "[0/6] Checking host Caddy for the webmail vhost"
if [[ -f /etc/caddy/Caddyfile ]] && grep -q "webmail.$DOMAIN" /etc/caddy/Caddyfile; then
  green "  webmail.$DOMAIN block present"
else
  amber "  webmail.$DOMAIN is not in /etc/caddy/Caddyfile — webmail will not be"
  amber "  reachable until it is. Install it after this script finishes:"
  amber "      sudo bash deploy/mail/install-caddy-vhost.sh"
  amber "  Mail itself (SMTP/IMAP, clients, DKIM) does not depend on this."
fi

if [[ $CHECK_ONLY -eq 1 ]]; then
  echo
  green "All preconditions pass. Re-run without --check to install."
  exit 0
fi

# ── 1. Firewall ──────────────────────────────────────────────────────────
bold "[1/6] Opening mail ports"
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  for p in 25 465 587 993; do ufw allow "$p/tcp" >/dev/null; done
  ufw status | grep -E '^(25|465|587|993)/tcp' || true
  green "  ufw updated"
else
  amber "  ufw is not active on this host — skipping"
fi
amber "  The Hetzner Cloud Firewall is SEPARATE and is not touched by ufw."
amber "  If one is attached (deployment_runbook.md §1 recommends it), add"
amber "  inbound 25, 465, 587, 993/tcp from 0.0.0.0/0 in the Hetzner console."
amber "  Mail ports cannot be restricted to Cloudflare ranges: SMTP arrives"
amber "  directly from every sending mail server on the internet."

# ── 2. Certificate ───────────────────────────────────────────────────────
bold "[2/6] Issuing Let's Encrypt certificate for $MAIL_HOSTNAME (DNS-01 via Cloudflare)"
# A publicly trusted certificate is required here and the Cloudflare Origin
# CA pair used by Caddy cannot serve: Origin CA is trusted only by
# Cloudflare, and Thunderbird talking IMAPS to port 993 is not Cloudflare.
#
# Force-recreate rather than plain `up -d`. The container attempts issuance
# once at startup and then only loops on renewal, so a container left
# running by a failed attempt never retries — and `up -d` is a no-op when
# the config is unchanged, silently reusing it. That makes a re-run after
# fixing the credential appear to fail with the ORIGINAL error, which is
# only the old container's log. Recreating is idempotent: when a valid
# certificate already exists the container reports that and skips issuance.
$COMPOSE up -d --force-recreate certbot
for i in $(seq 1 30); do
  if $COMPOSE exec -T certbot test -s "/etc/letsencrypt/live/$MAIL_HOSTNAME/fullchain.pem" 2>/dev/null; then
    green "  certificate ready"; break
  fi
  [[ $i -eq 30 ]] && {
    red "  certificate not issued after 5 min — certbot output follows:"
    echo
    $COMPOSE logs --no-log-prefix --tail=40 certbot | sed 's/^/    /'
    echo
    red "  The token already passed verification in step [0/6], so the"
    red "  credential is not the problem. Read the error above and match it:"
    red "    'Too many authentication failures' (429) — Cloudflare rate limit."
    red "        Wait 30-60 min, then re-run. Do not retry in a loop."
    red "    'too many certificates' / 'rateLimited'  — Let's Encrypt limit."
    red "        5 failed validations per hostname per hour. Wait an hour."
    red "    anything else — capture it with:"
    red "        sudo $COMPOSE logs certbot"
    exit 1
  }
  sleep 10
done

# ── 3. Mail server + webmail ─────────────────────────────────────────────
bold "[3/6] Starting mailserver + roundcube"
$COMPOSE up -d mailserver roundcube
# docker-mailserver refuses to start Dovecot until at least one mailbox
# exists. It warns for 120 seconds, shuts down, and the restart policy
# brings it back to repeat the cycle indefinitely:
#
#   You need at least one mail account to start Dovecot (120s left ...)
#   Failed to start accounts provisioning because no accounts were
#   provided - Dovecot could not be started!
#
# So waiting for "healthy" before provisioning is a deadlock: healthy is
# unreachable until accounts exist, and accounts were only created after
# the wait. Provision first, then wait for health.
#
# Only the setup CLI is needed for provisioning, and that is available as
# soon as the container is running — no need for Dovecot to be up. The
# account file lives in the mounted config directory, so even if the
# container hits its 120s shutdown mid-provisioning, the next restart
# finds the accounts and boots cleanly.
printf '  waiting for the setup CLI'
CLI_OK=0
for i in $(seq 1 36); do
  state=$(docker inspect -f '{{ .State.Status }}' "$CONTAINER" 2>/dev/null || echo missing)
  # Probe only that the container runs commands and the CLI is on PATH.
  # `setup email list` is NOT usable here: it exits non-zero when no
  # accounts exist, which is exactly the state being waited on, so it can
  # never report ready no matter how long the wait.
  if [[ $state == running ]] && docker exec "$CONTAINER" sh -c 'command -v setup' >/dev/null 2>&1; then
    echo; green "  ready for provisioning"; CLI_OK=1; break
  fi
  printf '.'; sleep 5
done
if [[ $CLI_OK -eq 0 ]]; then
  echo
  red "  mailserver never became usable. Last 40 log lines:"
  $COMPOSE logs --no-log-prefix --tail=40 mailserver 2>&1 | sed 's/^/    /'
  exit 1
fi

# ── 4. Accounts + aliases ────────────────────────────────────────────────
bold "[4/6] Creating mailboxes"

# Does this mailbox already exist?
#
# Primary source is the accounts file docker-mailserver itself reads,
# visible on the host through the mounted config directory. Its shape is
# "address|{SCHEME}hash", so an exact field comparison is authoritative and
# does not depend on any CLI presentation format.
account_exists() {
  local a=$1
  # Exact field comparison, not a substring match: grep -F "addr|" also
  # matches "oger@domain|" inside "roger@domain|", which would report a
  # non-existent account as present and silently skip creating it.
  if [[ -f deploy/mail/config/postfix-accounts.cf ]] \
     && awk -F'|' -v a="$a" '$1 == a { found = 1 } END { exit !found }' \
            deploy/mail/config/postfix-accounts.cf; then
    return 0
  fi
  # Fallback when the accounts file is not present on the host. Bound the
  # match so it cannot hit a longer address that contains this one.
  local esc
  esc=$(printf '%s' "$a" | sed 's/[][\.*^$+?(){}|/]/\\&/g')
  docker exec "$CONTAINER" setup email list 2>/dev/null \
    | grep -qE "(^|[^[:alnum:]._%+-])${esc}([^[:alnum:]._%+-]|$)"
}

# A plain counter alongside the map: ${#NEWPW[@]} on an *empty* associative
# array trips `set -u` with "unbound variable" — reproduced on bash 5.2, so
# this is not a legacy-version quirk. It fires on exactly the common path
# where every mailbox already exists and nothing was created.
declare -A NEWPW
NEWPW_COUNT=0
for u in "${ACCOUNTS[@]}"; do
  addr="$u@$DOMAIN"
  if account_exists "$addr"; then
    echo "  $addr exists — skipped (password unchanged)"
    continue
  fi
  pw=$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-24)
  # While accountless the container shuts down every 120s and restarts, so
  # an add can land in the gap. Retry rather than aborting; accounts persist
  # to the mounted config, so partial progress is kept.
  created=0
  add_out=""
  for attempt in 1 2 3 4; do
    if add_out=$(docker exec "$CONTAINER" setup email add "$addr" "$pw" 2>&1); then
      created=1; break
    fi
    # A failed add whose account now exists is success, not an error —
    # another run, or a partially completed earlier attempt, created it.
    if account_exists "$addr"; then
      echo "  $addr already present — keeping its existing password"
      created=2; break
    fi
    printf '  %s: attempt %s failed, container may be restarting — retrying\n' "$addr" "$attempt"
    sleep 10
  done
  case $created in
    1) NEWPW[$addr]=$pw; NEWPW_COUNT=$((NEWPW_COUNT + 1)); green "  created $addr" ;;
    2) ;;
    *) red "  could not create $addr after 4 attempts."
       red "  Last output from 'setup email add':"
       printf '%s\n' "$add_out" | sed 's/^/      /'
       red "  Container log:"
       docker logs --tail=20 "$CONTAINER" 2>&1 | sed 's/^/      /'
       exit 1 ;;
  esac
done
for pair in "${ALIASES[@]}"; do
  src="${pair%%:*}@$DOMAIN"; dst="${pair##*:}@$DOMAIN"
  docker exec "$CONTAINER" setup alias add "$src" "$dst" >/dev/null 2>&1 || true
done
echo "  aliases: postmaster@, abuse@, hostmaster@, webmaster@ → admin@"

# Print credentials here, not only in the closing summary. A failure in any
# later step would otherwise discard passwords that were already generated
# and applied to live accounts, leaving mailboxes nobody can log into.
if [[ $NEWPW_COUNT -gt 0 ]]; then
  echo
  bold "  ══ NEW MAILBOX PASSWORDS — shown once, store them now ══"
  for a in "${!NEWPW[@]}"; do printf '    %-32s %s\n' "$a" "${NEWPW[$a]}"; done
  bold "  ═══════════════════════════════════════════════════════"
  echo
fi

# With at least one mailbox present, Dovecot can finally start. The
# container may still be inside a 120s shutdown countdown from a previous
# accountless cycle, so restart it to begin a clean boot rather than
# waiting out a timer that is already doomed.
bold "      starting Dovecot now that mailboxes exist"
$COMPOSE restart mailserver >/dev/null
printf '      waiting for mailserver to become healthy'
MAIL_OK=0
for i in $(seq 1 72); do
  state=$(docker inspect -f '{{ .State.Status }}' "$CONTAINER" 2>/dev/null || echo missing)
  health=$(docker inspect -f '{{ if .State.Health }}{{ .State.Health.Status }}{{ else }}none{{ end }}' \
           "$CONTAINER" 2>/dev/null || echo none)
  if [[ $health == healthy ]] \
     || { [[ $state == running ]] && docker exec "$CONTAINER" ss -ltn 2>/dev/null | grep -qE ':993[[:space:]]'; }; then
    echo; green "      mailserver healthy (Dovecot listening)"; MAIL_OK=1; break
  fi
  printf '.'; sleep 5
done
if [[ $MAIL_OK -eq 0 ]]; then
  echo
  red "      Dovecot did not start even though mailboxes exist. Last 40 lines:"
  $COMPOSE logs --no-log-prefix --tail=40 mailserver 2>&1 | sed 's/^/        /'
  exit 1
fi

# ── 5. DKIM ──────────────────────────────────────────────────────────────
bold "[5/6] DKIM key (rspamd, selector 'mail', 2048-bit)"
# Locate the generated record by searching rather than assuming a filename:
# the layout differs between docker-mailserver versions and between the
# rspamd and opendkim backends, and a stale hardcoded path would fail the
# run at the last step after everything else had already been created.
find_dkim() { find deploy/mail/config -path '*dkim*' -name '*.public.dns.txt' 2>/dev/null | head -1; }
DKIM_DNS=$(find_dkim)
if [[ -z $DKIM_DNS ]]; then
  docker exec "$CONTAINER" setup config dkim keytype rsa keysize 2048 selector mail domain "$DOMAIN" >/dev/null
  $COMPOSE restart mailserver >/dev/null
  DKIM_DNS=$(find_dkim)
fi
if [[ -z $DKIM_DNS ]]; then
  red "  DKIM key generated but no *.public.dns.txt found under deploy/mail/config."
  red "  Everything else is installed. Inspect with:"
  red "      find deploy/mail/config -path '*dkim*'"
  red "  then add the TXT record for mail._domainkey.$DOMAIN by hand."
  exit 1
fi
echo "      record file: $DKIM_DNS"
# The container writes this file asynchronously after the restart, so it
# can exist while still empty — `find` sees it before it has content.
for _i in $(seq 1 12); do
  [[ -s $DKIM_DNS ]] && break
  sleep 5
done
# Two layouts exist and both must parse.
#
#   rspamd (what this install produces) writes the bare value:
#       v=DKIM1; k=rsa; p=MIIBIjANBgkq...
#
#   opendkim / BIND style wraps it in a zone record, split across quoted
#   chunks because a TXT string caps at 255 bytes:
#       mail._domainkey IN TXT ( "v=DKIM1; k=rsa; "
#               "p=MIIBIjANBgkq..." ) ;
#
# Normalise rather than matching one shape: flatten to one line, join
# adjacent quoted chunks, drop quotes, take everything from v=DKIM1 onward,
# then trim any zone-file tail. Extracting only quoted chunks finds nothing
# in the bare layout and reports a valid key as unparseable.
#
# `|| true` is load-bearing: under `set -o pipefail` a non-matching grep
# makes the substitution non-zero and `set -e` would exit with no message.
DKIM_VALUE=$(
  tr -d '\n\r' < "$DKIM_DNS" 2>/dev/null \
  | sed -E 's/"[[:space:]]*"//g' \
  | tr -d '"' \
  | grep -oE 'v=DKIM1.*' \
  | sed -E 's/[[:space:]]*\)[[:space:]]*;?[[:space:]]*$//' \
  | sed -E 's/[[:space:]]+/ /g; s/[[:space:]]+$//' \
  || true
)
if [[ $DKIM_VALUE != v=DKIM1*p=?* ]]; then
  red "  could not parse a complete DKIM record from:"
  red "      $DKIM_DNS"
  red "  File contents were:"
  sed 's/^/      /' "$DKIM_DNS" 2>/dev/null | head -10 || echo "      (empty or unreadable)"
  red "  Everything else is installed. Retrieve the record with:"
  red "      sudo docker exec $CONTAINER setup config dkim help"
  red "  and add it as the mail._domainkey TXT record by hand."
  exit 1
fi
green "  DKIM record parsed (${#DKIM_VALUE} chars)"

# ── 6. Webmail behind Caddy ──────────────────────────────────────────────
bold "[6/6] Reloading Caddy so webmail.$DOMAIN is served"
# Validate before reload. `caddy reload` on a broken file leaves the old
# process serving the previous config, which looks like success from the
# outside — the platform keeps working and webmail silently does not.
if [[ -f /etc/caddy/Caddyfile ]] && grep -q "webmail.$DOMAIN" /etc/caddy/Caddyfile; then
  if caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
    systemctl reload caddy && green "  Caddy reloaded"
  else
    red "  /etc/caddy/Caddyfile does NOT validate — not reloading."
    caddy validate --config /etc/caddy/Caddyfile 2>&1 | sed 's/^/      /' | head -10
  fi
else
  amber "  no webmail.$DOMAIN block in /etc/caddy/Caddyfile — skipping reload."
  amber "  Add it with:  sudo bash deploy/mail/install-caddy-vhost.sh"
fi

# ── Summary ──────────────────────────────────────────────────────────────
SPF_INCLUDE=""
case "${RELAY_HOST:-}" in
  *smtp2go*)   SPF_INCLUDE=" include:spf.smtp2go.com" ;;
  *brevo*)     SPF_INCLUDE=" include:spf.brevo.com" ;;
  *amazonaws*) SPF_INCLUDE=" include:amazonses.com" ;;
esac
# Print a placeholder rather than a guess when detection fails. A wrong IP
# in a DNS table is worse than an obvious blank: it gets pasted.
SERVER_IP=$(curl -4 -s --max-time 8 https://ifconfig.me || true)
[[ -n $SERVER_IP ]] || SERVER_IP='<this server IPv4>'

echo
bold "════════════ DNS RECORDS — add these in Cloudflare → $DOMAIN → DNS ════════════"
cat <<EOF

  Type   Name              Content                                          Proxy
  ----   ----              -------                                          -----
  A      mail              $SERVER_IP                                DNS only (grey)
  A      webmail           $SERVER_IP                                Proxied (orange)
  MX     @                 mail.$DOMAIN   (priority 10)              —
  TXT    @                 v=spf1 mx${SPF_INCLUDE} -all
  TXT    mail._domainkey   $DKIM_VALUE
  TXT    _dmarc            v=DMARC1; p=quarantine; rua=mailto:admin@$DOMAIN; adkim=s; aspf=s; pct=100

  'mail' MUST be grey. Cloudflare's proxy carries HTTP(S) only, so an
  orange-clouded MX target breaks SMTP and IMAP with no error anywhere.

  READ docs/deployment_runbook.md §2.2 BEFORE saving the grey record: it
  publishes this server's origin IPv4 permanently, which that section warns
  against. That trade is unavoidable for self-hosted mail — see
  deploy/mail/README.md, "What the grey record costs".

  If Cloudflare Email Routing is on, delete the three route*.mx.cloudflare.net
  MX records first (the lock icon opens the Email Routing page; disable it
  there). Any forwarding it was doing stops at that moment.
EOF

if [[ $NEWPW_COUNT -gt 0 ]]; then
  echo
  bold "════════════ NEW MAILBOX PASSWORDS — shown once, store them now ════════════"
  for a in "${!NEWPW[@]}"; do printf '  %-32s %s\n' "$a" "${NEWPW[$a]}"; done
  echo
  echo "  Reset later with:  sudo bash deploy/mail/mailuser.sh passwd <user>"
fi

echo
bold "Webmail:  https://webmail.$DOMAIN   (once the webmail A record resolves)"
bold "Clients:  IMAP $MAIL_HOSTNAME:993 (SSL)   SMTP $MAIL_HOSTNAME:587 (STARTTLS)   user = full address"
echo
echo "Verify once DNS has propagated:  bash deploy/mail/check-mail.sh"
