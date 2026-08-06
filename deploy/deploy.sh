#!/usr/bin/env bash
# Pull the current branch and refresh the deployed artifact on the server.
#
# Idempotent and safe to re-run. Run it as the `deploy` user:
#     ssh deploy@robustuavs.ai '/srv/robustuavs/repo/deploy/deploy.sh'
# or, once checked out, simply:
#     cd /srv/robustuavs/repo && ./deploy/deploy.sh
#
# It deliberately does NOT touch data/raw or data/staging: the corpus is
# staged independently (docs/data_staging_layout.md) and must survive deploys.
set -euo pipefail

REPO="${REPO:-/srv/robustuavs/repo}"
# Default to whatever the checkout is already on, NOT a hardcoded `main`.
# Hardcoding it means an innocent-looking deploy silently switches branches and
# can delete the very files it is running from.
BRANCH="${BRANCH:-$(git -C "${REPO:-/srv/robustuavs/repo}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)}"
VENV="${VENV:-/srv/robustuavs/venv}"
ARTIFACT="${ARTIFACT:-/srv/robustuavs/artifact}"
# The client is served from the domain root; there is no separate static site.
APP_DIR="${APP_DIR:-/srv/robustuavs/app}"

log() { printf '\033[1;36m[deploy]\033[0m %s\n' "$*"; }

cd "$REPO"

log "fetching origin/$BRANCH"
git fetch --prune origin "$BRANCH"

before=$(git rev-parse HEAD)
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

# Remove untracked files that would collide with a future checkout. A file
# written by a build step and later committed upstream blocks the checkout with
# "untracked working tree files would be overwritten", and `reset --hard` alone
# does not clear it. `-d` without `-x` leaves ignored paths untouched, so
# node_modules, dist/, data/raw and data/staging all survive.
git clean -fd

after=$(git rev-parse HEAD)

if [ "$before" = "$after" ]; then
	log "already at $after — nothing new"
else
	log "$before -> $after"
	git --no-pager log --oneline "$before..$after" | sed 's/^/         /'
fi

# Python environment. Recreate only if missing; upgrade deps every run since
# requirements.txt is pinned and pip is a no-op when nothing changed.
if [ ! -d "$VENV" ]; then
	log "creating venv at $VENV"
	python3 -m venv "$VENV"
fi
log "installing requirements"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r requirements.txt

# Schema gate: never publish an artifact whose staged output does not validate.
if [ -d data/staging ] && compgen -G "data/staging/*/events.jsonl" >/dev/null; then
	log "validating staged output against the schema"
	for f in data/staging/*/events.jsonl data/staging/*/windows.jsonl; do
		[ -e "$f" ] || continue
		"$VENV/bin/python" ingest/validate.py "$f"
	done
else
	log "no staged corpus on this host — skipping schema gate"
fi

# Publish the artifact tree. rsync --delete keeps it an exact mirror of the
# committed results, so a removed file disappears from the site too.
log "publishing artifact -> $ARTIFACT"
mkdir -p "$ARTIFACT"
for d in schema ingest certificates experiments results paper docs; do
	[ -d "$d" ] || continue
	rsync -a --delete "$d" "$ARTIFACT/"
done
cp -f README.md CLAUDE.md PENDING_ON_DATA.md requirements.txt "$ARTIFACT/" 2>/dev/null || true

# Reverse proxy: reload rather than restart, so the site never drops.
if [ -f deploy/Caddyfile ] && command -v caddy >/dev/null; then
	if ! diff -q deploy/Caddyfile /etc/caddy/Caddyfile >/dev/null 2>&1; then
		log "Caddyfile changed — installing and reloading"
		sudo install -m 0644 deploy/Caddyfile /etc/caddy/Caddyfile
		sudo caddy validate --config /etc/caddy/Caddyfile
		sudo systemctl reload caddy
	fi
fi

# Interactive client: build the Expo web bundle and publish it to /app.
# Skipped when node is absent, so a server that only serves the static artifact
# does not need a JS toolchain installed.
if [ -d platform/mobile ] && command -v npm >/dev/null; then
	log "building the web client"

	# Metro is the largest memory consumer on this host. Left uncapped on a
	# machine with no swap it can take the box down hard enough that sshd
	# cannot get scheduled -- logins then fail with "Connection timed out
	# during banner exchange" and the only way back in is a panel reboot.
	# Two guards, because a build that fails is recoverable and a host that
	# is unreachable is not:
	#
	#   1. Refuse to start without enough headroom. Better a skipped build
	#      than an unreachable server.
	#   2. Cap V8's heap and run at low priority, so even a runaway bundle
	#      loses the scheduler fight with sshd rather than winning it.
	avail_mb=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 99999)
	swap_mb=$(awk '/SwapTotal/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)
	min_mb="${MIN_BUILD_MB:-1500}"
	if [ "$avail_mb" -lt "$min_mb" ] && [ "$swap_mb" -lt 1024 ]; then
		log "only ${avail_mb}MB available and ${swap_mb}MB swap — REFUSING to build"
		log "         the previous bundle stays published; add swap (deploy/bootstrap.sh)"
		log "         or set MIN_BUILD_MB to override once you know it fits"
		exit 1
	fi
	log "memory: ${avail_mb}MB available, ${swap_mb}MB swap"
	export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=2048}"
	NICE="nice -n 10"
	command -v ionice >/dev/null && NICE="$NICE ionice -c3"
	# CLEAN_NODE_MODULES=1 forces a fresh tree. Worth doing after any
	# package.json change: npm's incremental resolution can prune a package
	# that a previous tree had hoisted, leaving Expo unable to resolve a
	# transitive it expects at the project root.
	if [ "${CLEAN_NODE_MODULES:-0}" = "1" ]; then
		log "removing node_modules for a clean install"
		rm -rf platform/mobile/node_modules platform/mobile/package-lock.json
	fi
	# No --silent: a failed install or export must be readable in the log.
	if ! ( cd platform/mobile && { $NICE npm ci 2>/dev/null || $NICE npm install; } ); then
		log "npm install FAILED — see the output above"; exit 1
	fi
	if ! ( cd platform/mobile && $NICE npx expo export --platform web --output-dir dist ); then
		log "expo export FAILED — see the output above"; exit 1
	fi
	# Only publish once the bundle actually exists. Publishing an empty dist/
	# with --delete would wipe the whole site, which is now this bundle.
	if [ ! -f platform/mobile/dist/index.html ]; then
		log "export produced no index.html — refusing to publish"; exit 1
	fi
	mkdir -p "$APP_DIR"
	rsync -a --delete platform/mobile/dist/ "$APP_DIR/"
	log "client published -> $APP_DIR (served at /)"
else
	# The client IS the site now, so skipping the build leaves whatever was
	# published last time. That is the right behaviour -- never serve nothing --
	# but it must be loud, or a host without node silently freezes the site.
	log "npm not present or no client — SKIPPING the web build"
	log "         the site keeps serving the previously published bundle"
fi

# Control plane: install deps into the venv and restart the service if the
# unit is installed. Absent unit means this host serves the static artifact
# only, which is a valid deployment.
if systemctl list-unit-files 2>/dev/null | grep -q '^robustuavs-api.service'; then
	log "restarting the control plane"
	# Not --quiet: when a wheel is missing and pip falls back to a source
	# build, the reason is in the output and suppressing it turns a legible
	# error into a bare non-zero exit.
	if ! "$VENV/bin/pip" install -r platform/backend/requirements.txt; then
		log "backend dependency install FAILED — see the pip output above"
		exit 1
	fi
	sudo systemctl restart robustuavs-api
	sleep 2
	systemctl is-active --quiet robustuavs-api \
		|| { log "control plane FAILED — journalctl -u robustuavs-api -n 30"; exit 1; }
	# Prove it answers, not merely that systemd thinks it is up. A unit can be
	# "active" while the app is failing every request.
	if curl -fsS --max-time 10 http://127.0.0.1:8000/api/health >/dev/null; then
		log "control plane up and answering"
	else
		log "control plane is active but /api/health does not answer"; exit 1
	fi
fi

# Docker stack, only if this deployment defines one.
if [ -f docker-compose.yml ]; then
	log "bringing up the docker stack"
	docker compose up -d --build --remove-orphans
fi

# Final report. Each line is a fact about the deployment, not a guess.
#
# Checked against the LOCAL origin, not the public hostname. From the server,
# https://robustuavs.ai resolves to Cloudflare, and the origin generally cannot
# route back to itself through the proxy -- which returns 000 (no connection)
# and looks like an outage when the site is in fact fine. --resolve pins the
# name to loopback so TLS still matches the certificate, and -k accepts the
# Origin CA cert, which only Cloudflare is meant to trust.
log "verification (origin-local; the public path is Cloudflare's to serve)"
ok=1
for path in / /api/health /artifact/ /app; do
	code=$(curl -s -o /dev/null -w '%{http_code}' -k --max-time 10 \
		--resolve "robustuavs.ai:443:127.0.0.1" "https://robustuavs.ai${path}") || code=000
	case "$code" in 2*|3*) mark="ok" ;; *) mark="FAILED"; ok=0 ;; esac
	printf '         %-22s %s  %s\n' "$path" "$code" "$mark"
done
[ "$ok" = "1" ] || log "one or more endpoints did not answer locally"

log "deployed $after"
