# Bringing the full stack up on robustuavs.ai

Wires the GitHub repo onto the Hetzner server so `https://robustuavs.ai` serves
the interactive client at the domain root, `/artifact/` the research tree, and
`/api` the control plane. There is no separate static landing page: the client
*is* the site, and `/app` is a permanent redirect to `/` for old links.

Assumes the server is already reachable and the repo cloned per
`docs/deployment_runbook.md` (deploy key, `/srv/robustuavs/repo`, Caddy running
with the Origin CA certificate). Every command runs as `deploy` over SSH from
PowerShell:

```powershell
ssh deploy@62.238.48.164
```

Run the blocks in order and read each result before continuing.

---

## 1. Pull the platform

```bash
cd /srv/robustuavs/repo
git fetch origin
git checkout claude/whelan-uavcas-ingest-u00isn
git pull
ls platform/           # expect: backend  mobile  docker-compose.yml  README.md
```

## 2. Node, for the client build

Expo's web export needs Node 20+. Ubuntu's archive lags, so use NodeSource:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
node --version && npm --version      # expect v20.x
```

## 3. Backend dependencies

```bash
/srv/robustuavs/venv/bin/pip install -r platform/backend/requirements.txt
/srv/robustuavs/venv/bin/python -c "import fastapi, sqlalchemy; print('backend deps ok')"
```

The Postgres and Redis drivers are **not** in that file. They live in
`requirements-optional.txt` and are installed only in section 4, because a
driver with no wheel for the host's Python must never be able to abort the core
install — pinning one there once left the API unable to start at all.

## 4. Postgres and Redis (optional)

Skip this section entirely for a first bring-up — the API falls back to SQLite
and an in-process cache, and everything works. Add it when you want run history
to survive across processes.

```bash
cd /srv/robustuavs/repo/platform
printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -base64 24)" > .env
chmod 600 .env
docker compose up -d
docker compose ps                    # both should read healthy

# Only now install the drivers.
/srv/robustuavs/venv/bin/pip install -r ../platform/backend/requirements-optional.txt
```

Both bind to `127.0.0.1` only, so neither is reachable from outside the host.

## 5. Environment file

```bash
sudo install -d -m 0750 -o deploy -g deploy /etc/robustuavs

# Start from the safe default: no tokens (open), no DB, no Redis.
sudo tee /etc/robustuavs/api.env >/dev/null <<'EOF'
# Leave API_TOKENS unset for an open demo. Set it to require a bearer token
# for run submission; reads stay public either way.
# API_TOKENS=paste-a-long-random-token-here

# Uncomment only if section 4 was run. Password must match platform/.env.
# DATABASE_URL=postgresql+psycopg://robustuavs:PASSWORD@127.0.0.1/robustuavs
# REDIS_URL=redis://127.0.0.1:6379/0

# Optional: any one of these enables narrated copilot answers. With none set
# the copilot still works, answering from the local result cache.
# ANTHROPIC_API_KEY=
# OPENAI_API_KEY=
# GEMINI_API_KEY=
# DEEPSEEK_API_KEY=
EOF
sudo chown deploy:deploy /etc/robustuavs/api.env
sudo chmod 600 /etc/robustuavs/api.env
```

> The file holds API keys and a DB password, so it is `0600` and owned by
> `deploy`. It is read by systemd, never committed, and never served.

## 6. Install and start the control plane

```bash
sudo install -m644 deploy/robustuavs-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now robustuavs-api
systemctl status robustuavs-api --no-pager | head -6
```

Confirm it answers on loopback before exposing it:

```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool
```

Read `auth.mode` in that output. `open` means run submission is public — fine
for a demo, deliberate rather than accidental. If it should be protected, set
`API_TOKENS` in step 5 and `sudo systemctl restart robustuavs-api`.

## 7. Publish the routes

```bash
sudo install -m 0644 deploy/Caddyfile /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## 8. Build and deploy everything

```bash
cd /srv/robustuavs/repo
./deploy/deploy.sh
```

This pulls, refreshes the venv, runs the schema gate over any staged corpus,
publishes `site/` and the artifact tree, builds the Expo web bundle into
`/srv/robustuavs/app` (served at `/`), and restarts the API. First run takes a
few minutes —
`npm install` dominates.

## 9. Verify from the outside

```bash
curl -sSI https://robustuavs.ai/            | head -1   # 200
curl -sSI https://robustuavs.ai/app         | head -1   # 301 -> /
curl -s   https://robustuavs.ai/api/health  | python3 -m json.tool
curl -sSI https://robustuavs.ai/artifact/   | head -1   # 200
```

Then in a browser:

| URL | What it is |
|---|---|
| `https://robustuavs.ai` | interactive client — cover page, live runner, copilot |
| `https://robustuavs.ai/app` | permanent redirect to `/` (kept for old links) |
| `https://robustuavs.ai/artifact/` | browsable research tree |
| `https://robustuavs.ai/api/health` | deployment status |

---

## Updating later — the one-liner

Same shape as the robustidps.ai one-liner. `deploy.sh` already fetches and
hard-resets to the tracked branch, so the `git pull` is belt-and-braces rather
than required:

**On the server** — one command, detached so a dropped SSH session cannot
kill a build in progress:

```bash
/srv/robustuavs/repo/deploy/redeploy.sh
```

Add `--watch` to follow the log immediately. `Ctrl-C` while watching stops the
*watching*, never the deploy.

If you would rather run it in the foreground and watch it directly:

```bash
cd /srv/robustuavs/repo && git pull && ./deploy/deploy.sh
```

**From your laptop, without logging in:**

```powershell
ssh deploy@62.238.48.164 "cd /srv/robustuavs/repo && git pull && ./deploy/deploy.sh"
```

Make it a single word by adding this to `~/.bashrc` on the server:

```bash
echo "alias redeploy='cd /srv/robustuavs/repo && git pull && ./deploy/deploy.sh'" >> ~/.bashrc
source ~/.bashrc
```

Then it is just `redeploy`.

Why there is no `docker compose up --build` in it, unlike robustidps.ai: the
control plane runs under systemd rather than in a container, so `deploy.sh`
restarts the unit instead. Postgres and Redis are the only containerised
pieces, and they are optional and long-lived — rebuilding them on every deploy
would drop the run history for no benefit.

The script ends by printing the HTTP status of `/`, `/api/health`, `/artifact/`
and the `/app` redirect,
so a deploy that half-succeeded is visible immediately rather than on the next
page load.

## Before the conference

```bash
# 1. Warm the caches so the first click in front of an audience is not the
#    slow one (the certificate engine's first import dominates).
curl -s https://robustuavs.ai/api/health > /dev/null
curl -s -X POST https://robustuavs.ai/api/runs \
     -H 'Content-Type: application/json' \
     -d '{"kind":"mapping_compare","params":{"theta_s":0.25}}'

# 2. Confirm a run completes end to end.
curl -s 'https://robustuavs.ai/api/runs?limit=3' | python3 -m json.tool

# 3. Snapshot the server from the Hetzner console, so a mid-demo mistake is
#    a rollback rather than a rebuild.
```

On the day: open `https://robustuavs.ai`, and on the **Home** tab switch to the
**print theme**.
The dark palette washes out on most projectors; the ivory one keeps every
status colour distinguishable.

## If something fails

| Symptom | Cause and fix |
|---|---|
| `/api/health` 502 | API not running: `journalctl -u robustuavs-api -n 40` |
| `/` 404 or blank | bundle not built: rerun `./deploy/deploy.sh`, check the npm step |
| site loads, API calls fail | Caddy answering `/api` from the SPA — reinstall the Caddyfile; `handle /api/*` must precede the root `handle` block |
| `caddy validate` passes, service dead | validate never opens files or binds ports; the real reason is in `journalctl -u caddy -n 40 \| grep -i error` |
| runs stay `queued` | worker thread dead: restart the API; check `jobs.worker_alive` in `/api/health` |
| `503` from a result endpoint | not an error — that result has not been produced in this deployment (see `PENDING_ON_DATA.md`) |
