# platform/ — the RobustUAVs.ai web platform

Design authority: [`docs/platform_architecture.md`](../docs/platform_architecture.md),
which traces the structure of RobustIDPS.ai v5 and explains what transfers,
what is re-targeted, and what is deliberately dropped.

```
platform/
  backend/    FastAPI control plane — registry, results, certificates, copilot
  mobile/     Expo / React Native client (iOS, Android, and web from one source)
```

## Backend

```bash
cd platform/backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# interactive docs at http://localhost:8000/docs
```

Endpoints: `/api/health`, `/api/models[/{id}]`, `/api/results[/{name}]`,
`/api/certify/staleness`, `/api/copilot/{tools,tool/{name},ask}`, and the
`/api/papers/...` surface described under [Papers I–IV](#papers-iiv).

Two conventions worth knowing:

- **503 means "not produced", not "broken".** A result endpoint returns 503 when
  its file has not been generated in this deployment (a data-gated item). The
  client distinguishes the two, because a reviewer must not read a pending
  measurement as a failure.
- **Nothing is hard-coded.** Every number served traces to a file under
  `results/` or to a live call into `certificates/engine.py`.

Tests:

```bash
python3 tests_smoke.py
```

`test_copilot_symmetry` is the load-bearing one — a tool advertised to the model
but absent from the dispatcher is a lie told to the model, and RobustIDPS
enforces the same invariant in CI.

## Papers I–IV

`app/papers.py` serves the follow-on papers (`paperI/`, `paperII/`,
`paperIII/`, `paperIV/`); the client shows them under **Papers**, one page each. Paths are
derived from the repository root, and paper code is imported lazily from the
paper's own `experiments/` (no bytecode written into it), so an import failure
is a 503 naming the file rather than a 500.

    GET  /api/papers                              catalogue: id, title (from manuscript/main.tex), folder, CSVs + row counts
    GET  /api/papers/{I|II|III|IV}/results        every CSV under paper*/results/ (logs_r/, server_logs/, *.pt skipped):
                                                  name, rows, columns, distinct provenance values
    GET  /api/papers/{pid}/results/{name}?format=json|csv
                                                  one file as typed JSON rows, or the committed file itself;
                                                  only .csv, resolved and confined to that results/ (else 400)
    GET  /api/papers/I/budget                     Paper I defaults: constants.py values + provenance, dauth.csv schemes
    POST /api/papers/I/budget                     rho = (Delta + Delta_auth) * gamma * e^{L T_c} <= m; any input overridable
    GET  /api/papers/II/corpus?table=full_final&year_min=&year_max=&<codebook field>=<value>
                                                  filtered coded corpus, counts per category, PRISMA, search sensitivity;
                                                  tables: full_final (default) / full_C1 / full_C2, snow<k>_final|C1|C2,
                                                  and the pilot ADJ / C1 / C2; the full-study PRISMA is read from
                                                  results/screening_status.csv and snowball_iter*_status.csv
    GET  /api/papers/III/certify                  Paper III constants (KAPPA, THETA_BENIGN, ALERT_LIMITS), lift reference
    POST /api/papers/III/certify                  {rho | staleness_s, alpha, b?, proposal?} -> deficiency, coverage margin,
                                                  worst case, nested_greedy_fast, lexicographic_projection (N, M <= 2000)
    POST /api/papers/III/lift                     {N <= 200, alpha, q[5]} -> P(full coverage) via e2_degradation.p_full_iid
    GET  /api/papers/III/marl                     e6_main.csv and every e6_main_<dir>.csv, as {dir: rows}
    GET  /api/papers/IV/floor                     Paper IV defaults: delta_adv presets (r1_delta_adv.csv, e4_delta_adv.csv),
                                                  net-tube presets (e4_soundness.csv), r5_floor_sensitivity.csv reference
    POST /api/papers/IV/floor                     {m in (0, 40], delta_adv >= 0, net? >= 0, alpha? in (0, 1)} -> s = m - delta_adv - net,
                                                  depbounds.union_bound on e3_marginals.npz (point estimate) and
                                                  depbounds.pbar_union_cp on cp_tails(alpha) (valid w.p. >= 1 - alpha), floors 1 - each

Unknown paper -> 404; file or folder not present here -> 503; bad calculator
input or an unknown request key -> 422. `paperII/` lives on the
`paperII/full-study` branch, so a checkout without it reports Paper II as not
present and its endpoints answer 503.

## LLM providers

Four, in fallback order, with a deterministic synthetic responder last:

```
ANTHROPIC_API_KEY → OPENAI_API_KEY → GEMINI_API_KEY → DEEPSEEK_API_KEY → synthetic
```

The synthetic path is not a degraded mode to apologise for: it keeps CI
reproducible, lets the public artifact run without anyone's key, and means a
live demo cannot fail because a provider rate-limited. The active provider is
always surfaced to the client as a chip.

## Mobile client

```bash
cd platform/mobile
npm install
npm run web        # or: npm start, then scan the QR code
npm run build:web  # static bundle -> dist/, published to the origin's web root
```

Four tabs today: Overview, Composition, Registry, Copilot.

The **Composition** tab is the one built for a live demonstration. The paper's
central claim is that the certified verdict is parametric in the θ↦δ mapping, so
the mapping is a control rather than a footnote: at θ = 0.25 s, flipping
Kinematic → EKF turns *outside the certified window* into *inside* — same
theorem, same detector setting, opposite verdicts, decided by a measurement.
That is precisely what a static PDF cannot show.

## Job plane

Runs execute off the request thread on an in-process worker with DB-backed
state — structurally `backend/task_queue.py` from RobustIDPS.ai, chosen over
Celery for the same reason: no broker to deploy is one fewer thing that can
fail on the day of a talk.

Three runners, each declaring **two schemas**:

| | meaning | changing one means |
|---|---|---|
| `params` | what the experiment **is** | a different finding |
| `hyperparams` | how it was **computed** | a robustness claim |

The UI renders them as separate panels. Collapsing them into one form would
hide exactly the distinction a sceptical reviewer is listening for. Unknown
keys are rejected rather than ignored, so a demo cannot believe it varied
something it did not.

    certified_sweep    certified floor across a theta grid
    sensitivity        how steep gamma would have to get to lose the window
    mapping_compare    all three mappings at one operating point

## Persistence and auth

`DATABASE_URL` unset -> SQLite. Set -> Postgres. `REDIS_URL` unset -> in-process
cache. Set -> Redis, demoting back to memory permanently on first error rather
than flapping mid-demo. `platform/docker-compose.yml` brings up both, bound to
loopback; neither is required to run the artifact.

Auth is **bearer-token only, with no login or register surface**. With
`API_TOKENS` unset every endpoint is public, which is correct for a laptop demo
and for a reviewer running the artifact. Set it and run submission/cancellation
require `Authorization: Bearer <token>` while the read-only research surface
stays public — gating that would defeat the point of publishing it. The mode is
reported by `/api/health` so a deployment that believes it is protected and is
not can see so at a glance.

## Deploying to the domain root

`deploy/deploy.sh` builds the Expo web bundle and publishes it to
`/srv/robustuavs/app`; the Caddyfile serves that directory at the domain root
with an SPA fallback and reverse-proxies `/api` to the control plane on
loopback. Install the unit with:

```bash
sudo install -m644 deploy/robustuavs-api.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now robustuavs-api
```

Then `https://robustuavs.ai/` is the interactive client and `/artifact/` the
browsable research tree. `/app`, where the client used to live, is a permanent
redirect to `/`.

## Presenting

The **Home** tab is a cover page for the first slide. The theme toggle there
switches to the ivory *print* palette — a dark UI washes out badly on a
projector, and the print palette keeps every status colour distinguishable.
Both palettes are taken verbatim from robustidps.ai so the two platforms read
as one family.

## Not built yet

WebSocket progress streaming (polling is used instead), and ingest as a
background runner.
