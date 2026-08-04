#!/usr/bin/env bash
# Bring a bare Ubuntu server to the state deploy/cloud-init.yaml would have
# produced. Use this when the cloud config did not run (see the runbook, §2.3
# "cloud-init reports done but nothing was configured") and rebuilding the
# server is not worth it.
#
# Run as root on the server:
#     bash bootstrap.sh 'ssh-ed25519 AAAA... you@laptop'
#
# The argument is optional: if the key is already in /root/.ssh/authorized_keys
# it is copied to the deploy user automatically. Safe to re-run.
set -euo pipefail

PUBKEY="${1:-}"
DEPLOY_USER=deploy

log() { printf '\033[1;36m[bootstrap]\033[0m %s\n' "$*"; }
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }

# `--lock-ssh` is the separate second pass; it must not fall through to the
# provisioning below, nor be mistaken for a public key.
if [ "$PUBKEY" = "--lock-ssh" ]; then
	log "disabling password authentication"
	sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' \
		/etc/ssh/sshd_config
	rm -f /etc/ssh/sshd_config.d/*cloud-init*
	systemctl reload ssh
	sshd -T | grep -i passwordauthentication
	exit 0
fi

# ---------------------------------------------------------------- packages --
log "installing base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
	git curl ca-certificates gnupg ufw fail2ban unattended-upgrades \
	python3-venv python3-pip build-essential rsync htop \
	debian-keyring debian-archive-keyring apt-transport-https

# ------------------------------------------------------------- deploy user --
if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
	log "creating $DEPLOY_USER"
	adduser --disabled-password --gecos "" "$DEPLOY_USER"
	usermod -aG sudo "$DEPLOY_USER"
	printf '%s ALL=(ALL) NOPASSWD:ALL\n' "$DEPLOY_USER" \
		> "/etc/sudoers.d/90-$DEPLOY_USER"
	chmod 440 "/etc/sudoers.d/90-$DEPLOY_USER"
fi

# Authorised keys: prefer an explicitly supplied key, else inherit root's.
install -d -m700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh"
if [ -n "$PUBKEY" ]; then
	log "installing the supplied public key"
	printf '%s\n' "$PUBKEY" >> "/home/$DEPLOY_USER/.ssh/authorized_keys"
	printf '%s\n' "$PUBKEY" >> /root/.ssh/authorized_keys
elif [ -s /root/.ssh/authorized_keys ]; then
	log "copying root's authorized_keys to $DEPLOY_USER"
	cat /root/.ssh/authorized_keys >> "/home/$DEPLOY_USER/.ssh/authorized_keys"
else
	echo "no public key available — pass one as \$1" >&2
	exit 1
fi
# de-duplicate, then lock the file down
for f in /root/.ssh/authorized_keys "/home/$DEPLOY_USER/.ssh/authorized_keys"; do
	sort -u "$f" -o "$f"
done
chown "$DEPLOY_USER:$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh/authorized_keys"
chmod 600 "/home/$DEPLOY_USER/.ssh/authorized_keys"

# ------------------------------------------------------------------ docker --
if ! command -v docker >/dev/null; then
	log "installing Docker from the official repository"
	install -m 0755 -d /etc/apt/keyrings
	curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
		-o /etc/apt/keyrings/docker.asc
	chmod a+r /etc/apt/keyrings/docker.asc
	. /etc/os-release
	echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
		> /etc/apt/sources.list.d/docker.list
	apt-get update -qq
	apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
		docker-buildx-plugin docker-compose-plugin
fi
usermod -aG docker "$DEPLOY_USER"

# ------------------------------------------------------------------- caddy --
if ! command -v caddy >/dev/null; then
	log "installing Caddy"
	curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
		| gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
	curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
		> /etc/apt/sources.list.d/caddy-stable.list
	apt-get update -qq
	# A young Ubuntu release may have no Cloudsmith pool yet; fall back to the
	# distro package rather than leaving the box without a reverse proxy.
	apt-get install -y -qq caddy || {
		log "Cloudsmith has no pool for this release — using the distro caddy"
		rm -f /etc/apt/sources.list.d/caddy-stable.list
		apt-get update -qq && apt-get install -y -qq caddy
	}
fi

# ---------------------------------------------------------------- firewall --
log "configuring ufw and fail2ban"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# The sshd jail is DISABLED by default here, deliberately.
#
# Password authentication is off on this host, so a brute-force attempt
# cannot succeed no matter how many times it runs — the jail buys quieter
# logs, not security. Against that it carries a real cost: it bans the
# operator. Aborted connections and wrong-key attempts all count as
# failures, and if your ISP hands out rotating addresses (CGNAT, mobile
# tethering, a VPN egress pool) an `ignoreip` whitelist cannot keep up —
# you get banned on an address you did not have five minutes ago, and the
# Hetzner VNC console becomes the only way back in.
#
# Set FAIL2BAN_SSHD=1 to enable it, e.g. once password auth is confirmed off
# AND you have a static admin address to whitelist:
#     FAIL2BAN_SSHD=1 ADMIN_IP=203.0.113.7 bash bootstrap.sh
if [ "${FAIL2BAN_SSHD:-0}" = "1" ]; then
	ADMIN_IP="${ADMIN_IP:-$(echo "${SSH_CLIENT:-}" | awk '{print $1}')}"
	log "enabling the fail2ban sshd jail (ignoreip: ${ADMIN_IP:-none})"
	{
		printf '[sshd]\nenabled = true\nmaxretry = 10\nfindtime = 10m\nbantime = 15m\n'
		printf 'ignoreip = 127.0.0.1/8 ::1%s\n' "${ADMIN_IP:+ $ADMIN_IP}"
	} > /etc/fail2ban/jail.d/sshd.local
else
	log "leaving the fail2ban sshd jail disabled (SSH is key-only)"
	printf '[sshd]\nenabled = false\n' > /etc/fail2ban/jail.d/sshd.local
fi
systemctl enable --now fail2ban
fail2ban-client reload >/dev/null 2>&1 || true

# Keepalives. A rotating or NAT-ed client address silently kills idle
# sessions: the mapping expires, the peer never learns, and the session
# hangs rather than closing. Probing every 30s keeps the mapping warm and
# turns an unrecoverable hang into a clean disconnect after ~3 minutes.
printf 'ClientAliveInterval 30\nClientAliveCountMax 6\nTCPKeepAlive yes\n' \
	> /etc/ssh/sshd_config.d/10-keepalive.conf
systemctl reload ssh 2>/dev/null || systemctl restart ssh.socket 2>/dev/null || true

# ------------------------------------------------------- unattended upgrades
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
cat > /etc/apt/apt.conf.d/51unattended-upgrades-local <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
EOF

# ------------------------------------------------------------ directories ---
install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" /srv/robustuavs /srv/data
install -d -m755 /etc/caddy/certs

# The Caddyfile logs to /var/log/caddy/access.log. `caddy validate` accepts
# the config regardless, then the service exits 1 at startup if the directory
# is not writable by the caddy user — so create it here, not after the fact.
if id caddy >/dev/null 2>&1; then
	install -d -m755 -o caddy -g caddy /var/log/caddy
fi

log "done. Verify key login works BEFORE closing password auth:"
cat <<EOF

    ssh $DEPLOY_USER@\$(hostname -I | awk '{print \$1}')

Once that logs in with no password prompt, run:

    bash $(readlink -f "$0") --lock-ssh

EOF
