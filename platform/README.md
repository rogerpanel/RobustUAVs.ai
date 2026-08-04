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
`/api/certify/staleness`, `/api/copilot/{tools,tool/{name},ask}`.

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
npm run build:web  # static bundle -> dist/, deployable to /app on the origin
```

Four tabs today: Overview, Composition, Registry, Copilot.

The **Composition** tab is the one built for a live demonstration. The paper's
central claim is that the certified verdict is parametric in the θ↦δ mapping, so
the mapping is a control rather than a footnote: at θ = 0.25 s, flipping
Kinematic → EKF turns *outside the certified window* into *inside* — same
theorem, same detector setting, opposite verdicts, decided by a measurement.
That is precisely what a static PDF cannot show.

## Not built yet

Job plane (background θ-sweeps and ingest with a WebSocket progress stream),
Postgres/Redis persistence, and auth. The artifact is public and read-mostly, so
these are deferred; §4 of the architecture doc gives the build order.
