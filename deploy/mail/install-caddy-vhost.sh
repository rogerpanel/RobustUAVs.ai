#!/usr/bin/env bash
# Append the webmail vhost to the live Caddy config, safely.
#
#   sudo bash deploy/mail/install-caddy-vhost.sh
#
# Backs up /etc/caddy/Caddyfile, appends deploy/mail/Caddyfile.webmail,
# validates the result, and restores the backup if validation fails. Only
# then does it reload Caddy.
#
# This is a separate script rather than a step inside setup-mail.sh on
# purpose. /etc/caddy/Caddyfile is what serves robustuavs.ai; editing it is
# a decision about the platform, not a detail of installing mail, and it
# should be something you run deliberately and can see the diff of.
set -euo pipefail

cd "$(dirname "$0")/../.."
SRC=deploy/mail/Caddyfile.webmail
DST=/etc/caddy/Caddyfile
DOMAIN=robustuavs.ai
MARKER="webmail.$DOMAIN"

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
amber() { printf '\033[33m%s\033[0m\n' "$*"; }
bold()  { printf '\033[1m%s\033[0m\n' "$*"; }

[[ ${EUID:-$(id -u)} -eq 0 ]] || { red "Run with sudo: sudo bash $0"; exit 1; }
[[ -f $SRC ]] || { red "Missing $SRC — run this from the repo root."; exit 1; }
[[ -f $DST ]] || {
  red "$DST does not exist. Caddy is not installed, or not configured yet."
  red "See docs/deployment_runbook.md §2.4."
  exit 1
}
command -v caddy >/dev/null || { red "caddy binary not found on PATH."; exit 1; }

# The vhost uses two snippets defined at the top of the platform's
# Caddyfile. Appending without them produces a config that parses but
# serves webmail with no certificate — a 526 from Cloudflare that looks
# like a certificate problem rather than a missing import.
for snip in origin_tls common; do
  grep -qE "^\($snip\)" "$DST" || {
    red "The snippet ($snip) is not defined in $DST."
    red "This vhost imports it. Install the repo's deploy/Caddyfile first, or"
    red "edit $SRC to inline the tls and header directives it needs."
    exit 1
  }
done

if grep -q "$MARKER" "$DST"; then
  green "$MARKER is already present in $DST — nothing to do."
  bold  "Validating the existing config anyway:"
  caddy validate --config "$DST" 2>&1 | sed 's/^/  /' | tail -3
  exit 0
fi

BACKUP="$DST.$(date +%Y%m%d-%H%M%S).bak"
cp -a "$DST" "$BACKUP"
green "Backed up $DST -> $BACKUP"

{
  printf '\n# ── Webmail (Roundcube) — deploy/mail/docker-compose.mail.yml ──\n'
  # Strip the file's own leading comment header: it documents the block for
  # a reader of the repo, and duplicating 30 lines of it into the live
  # server config just makes that file harder to read.
  sed -n "/^webmail\.$DOMAIN {/,\$p" "$SRC"
} >> "$DST"

if caddy validate --config "$DST" >/dev/null 2>&1; then
  green "Config validates."
else
  red "Appending produced a config that does NOT validate. Restoring the backup."
  caddy validate --config "$DST" 2>&1 | sed 's/^/  /' | head -10
  cp -a "$BACKUP" "$DST"
  red "Restored $DST from $BACKUP — Caddy was not reloaded, nothing changed."
  exit 1
fi

systemctl reload caddy
green "Caddy reloaded. webmail.$DOMAIN is now served."
echo
amber "Still required before it works from a browser:"
amber "  - an A record for webmail.$DOMAIN -> this server, Proxied (orange)"
amber "  - the Roundcube container running (docker ps | grep robustuavs-webmail)"
echo
echo "Check locally, bypassing DNS and Cloudflare:"
echo "  curl -sSI --resolve webmail.$DOMAIN:443:127.0.0.1 https://webmail.$DOMAIN/ -k | head -3"
