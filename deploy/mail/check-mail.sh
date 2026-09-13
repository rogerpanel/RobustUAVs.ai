#!/usr/bin/env bash
# Post-DNS sanity check for the mail stack. Read-only and safe to run any
# time, from the server or (for the DNS section) from anywhere.
#
#   bash deploy/mail/check-mail.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
DOMAIN=robustuavs.ai
HOST=mail.$DOMAIN
WEBMAIL=webmail.$DOMAIN
CONTAINER=robustuavs-mail
COMPOSE_FILE=deploy/mail/docker-compose.mail.yml
ENV_FILE=deploy/mail/.env.mail
ACCOUNTS=(roger admin support noreply)

command -v dig >/dev/null || { echo "dig not found — install it first:  apt-get install -y dnsutils"; exit 1; }
ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m✘\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
info() { printf '  \033[2m  %s\033[0m\n' "$*"; }

echo "DNS"
mx=$(dig +short MX "$DOMAIN" | sort -n | head -1)
[[ $mx == *"$HOST"* ]] && ok "MX → $mx" || bad "MX is '${mx:-none}' (expected 10 $HOST.)"
# A leftover Cloudflare Email Routing MX silently wins or ties on priority
# and swallows inbound mail, while every other check on this page passes.
dig +short MX "$DOMAIN" | grep -q 'mx.cloudflare.net' \
  && bad "Cloudflare Email Routing MX records are still published — inbound mail goes to them, not here" \
  || ok "no leftover Email Routing MX records"

a=$(dig +short A "$HOST"); [[ -n $a ]] && ok "A $HOST → $a" || bad "no A record for $HOST"
# A grey-clouded mail host is a requirement, not a preference: Cloudflare's
# proxy carries HTTP(S) only. An orange cloud here returns a Cloudflare
# anycast address and SMTP/IMAP fail with no error in the dashboard.
if [[ -n $a ]] && { [[ $a == 104.* ]] || [[ $a == 172.6[4-9].* ]] || [[ $a == 172.7[0-1].* ]] || [[ $a == 162.15[89].* ]]; }; then
  bad "$HOST resolves to a Cloudflare proxy address — turn the orange cloud OFF for 'mail'"
fi
ptr=$(dig +short -x "${a:-0.0.0.0}"); [[ $ptr == "$HOST." ]] && ok "PTR $a → $ptr" \
  || bad "PTR is '${ptr:-none}' (expected $HOST.) — set it in Hetzner → server → Networking → Reverse DNS"
spf=$(dig +short TXT "$DOMAIN" | grep v=spf1); [[ -n $spf ]] && ok "SPF $spf" || bad "no SPF record"
dkim=$(dig +short TXT "mail._domainkey.$DOMAIN" | grep -c v=DKIM1); [[ $dkim -gt 0 ]] && ok "DKIM mail._domainkey present" || bad "no DKIM record at mail._domainkey.$DOMAIN"
# Compare the published key against the one this server signs with. The
# record is ~400 base64 characters copied by hand into a web form, and a
# single altered character makes every signature fail verification while
# the record still *looks* correct. Presence alone proves nothing.
dkim_file=$(find deploy/mail/config -path '*dkim*' -name '*.public.dns.txt' 2>/dev/null | head -1)
if [[ -n $dkim_file && -r $dkim_file ]]; then
  pub=$(dig +short TXT "mail._domainkey.$DOMAIN" | tr -d '" ' | grep -oE 'p=[A-Za-z0-9+/=]+' | head -1 | cut -d= -f2-)
  loc=$(tr -d '\n\r" ' < "$dkim_file" | grep -oE 'p=[A-Za-z0-9+/=]+' | head -1 | cut -d= -f2-)
  if [[ -z $pub ]]; then
    bad "DKIM published record has no p= key"
  elif [[ "$pub" == "$loc" ]]; then
    ok "DKIM key in DNS matches this server (${#loc} chars)"
  else
    bad "DKIM key MISMATCH — signatures will fail verification"
    info "published: ${#pub} chars, server: ${#loc} chars"
    info "re-copy the value from $dkim_file into the mail._domainkey TXT record"
  fi
elif [[ -n $dkim_file ]]; then
  info "DKIM key file not readable as $(id -un); re-run with sudo to compare it against DNS"
fi
dmarc=$(dig +short TXT "_dmarc.$DOMAIN" | grep v=DMARC1); [[ -n $dmarc ]] && ok "DMARC $dmarc" || bad "no DMARC record"
wm=$(dig +short A "$WEBMAIL"); [[ -n $wm ]] && ok "A $WEBMAIL → $wm" || warn "no A record for $WEBMAIL (webmail unreachable until added)"

echo "Ports (from this host)"
for p in 25 465 587 993; do
  timeout 5 bash -c "</dev/tcp/$HOST/$p" 2>/dev/null && ok "$HOST:$p open" || bad "$HOST:$p closed"
done

echo "TLS"
exp=$(echo | timeout 8 openssl s_client -connect "$HOST:993" -servername "$HOST" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
[[ -n $exp ]] && ok "IMAPS cert valid until $exp" || bad "could not read IMAPS certificate"
cn=$(echo | timeout 8 openssl s_client -connect "$HOST:993" -servername "$HOST" 2>/dev/null | openssl x509 -noout -subject 2>/dev/null)
[[ $cn == *"$HOST"* ]] && ok "cert subject matches $HOST" || bad "cert subject: ${cn:-none}"
# The mail certificate must be publicly trusted. A Cloudflare Origin CA cert
# here would satisfy every check above and still be rejected by every mail
# client on earth, because only Cloudflare trusts that CA.
iss=$(echo | timeout 8 openssl s_client -connect "$HOST:993" -servername "$HOST" 2>/dev/null | openssl x509 -noout -issuer 2>/dev/null)
case "$iss" in
  *Cloudflare*) bad "IMAPS is serving a Cloudflare Origin CA certificate — mail clients will reject it" ;;
  *)            [[ -n $iss ]] && ok "issuer: ${iss#issuer=}" ;;
esac

echo "Mailboxes"
if docker inspect "$CONTAINER" >/dev/null 2>&1; then
  listing=$(docker exec "$CONTAINER" setup email list 2>/dev/null)
  for u in "${ACCOUNTS[@]}"; do
    grep -q "$u@$DOMAIN" <<<"$listing" && ok "$u@$DOMAIN" || bad "$u@$DOMAIN missing"
  done
else
  info "container $CONTAINER not present on this host — skipping"
fi

echo "Webmail"
# Resolve to loopback so this tests the origin, not Cloudflare's cache, and
# works before the DNS record exists. -k because the origin presents the
# Cloudflare Origin CA certificate, which this host does not trust and is
# not supposed to.
code=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 \
       --resolve "$WEBMAIL:443:127.0.0.1" "https://$WEBMAIL/" 2>/dev/null)
case "$code" in
  200|302) ok "origin serves $WEBMAIL (HTTP $code)" ;;
  000)     bad "no response from the origin — is Caddy running with the webmail vhost?" ;;
  502|503) bad "Caddy answered $code — the vhost exists but Roundcube is not reachable on 127.0.0.1:8081" ;;
  *)       warn "origin returned HTTP $code" ;;
esac

echo "Outbound"
if timeout 5 bash -c '</dev/tcp/gmail-smtp-in.l.google.com/25' 2>/dev/null; then
  ok "port 25 outbound open — direct delivery possible"
else
  bad "port 25 outbound blocked by Hetzner — ask support to lift it, or set RELAY_* in $ENV_FILE"
fi

echo "Containers"
if [[ -r $ENV_FILE ]]; then
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps \
    --format 'table {{.Name}}\t{{.Status}}' 2>/dev/null | sed 's/^/  /'
else
  # .env.mail is mode 600 and root-owned, so compose cannot read it as the
  # deploy user. Fall back to a name filter, which needs no env file.
  docker ps --filter name=robustuavs- --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null | sed 's/^/  /'
  info "run with sudo for the full compose view"
fi

echo
info "Then send a real test: from Roundcube to a Gmail address, open 'Show original',"
info "and confirm SPF=pass, DKIM=pass, DMARC=pass. Nothing above proves that."
info "Or mail check-auth@verifier.port25.com and read the automated report."
