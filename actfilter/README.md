# actfilter — a predictive action filter for LLM agents (prototype)

`actfilter` sits between an LLM agent and the effects of its tool calls. It generalises
the predictive safety filter of Paper V from a UAV autopilot to any agent whose actions
have a usable state model. A proposed call is turned into a typed action and executed
only if a safe stop stays reachable afterwards; otherwise it is repaired to the nearest
admissible action, replaced by the safe-stop action, or denied.

It is a plug-in, not a framework: it runs as its own process, and existing hosts (Claude
Code / Claude Agent SDK, Hermes Agent, any MCP host such as OpenHands) reach it through
their pre-tool hooks or by launching MCP servers through its proxy. Nothing in the host
is forked.

```
 agent host (unchanged)         actfilter service (own process, own user, read-only policy)
 ┌──────────────────────┐ call  ┌────────────────────────────────────────────────────────┐
 │ Claude Code / SDK    │──────▶│ policy: tool -> state model           (default deny)    │
 │ Hermes Agent         │ hook  │ parse -> typed action                 (fail closed)     │
 │ MCP host (OpenHands) │◀──────│ admit iff safe now and safe stop reachable in N steps   │
 └──────────────────────┘ allow │ else nearest admissible repair -> safe stop -> deny     │
          │ MCP stdio    /proj/ │ hash-chained audit log of every decision                │
          ▼              fb/deny└────────────────────────────────────────────────────────┘
   actfilter.mcp_proxy ──▶ MCP server (only tools/call is intercepted)
```

## The decision rule

For a state model with state *x*, safe set *S*, terminal (safe-to-stop) set *T*, backup
action *b(x)* and horizon *N*, a proposed action *a* is

| decision | when | the host executes |
|---|---|---|
| `allow` | *x⁺ = f(x, a) ∈ S* and rolling *b* from *x⁺* reaches *T* within *N* steps inside *S* | the call as proposed |
| `project` | not the above, but a repair candidate *a′* (closest first) satisfies it | the call with repaired args |
| `fallback` | no candidate does, but *b(x)* does | nothing proposed; *b(x)* is returned |
| `deny` | the proposal cannot be parsed, its tool is not in the policy, or nothing is admissible | nothing |

If every admitted action keeps the backup path to *T* open, the state never leaves *S*
whatever the model proposes (the same recursive-feasibility argument as Paper V's
terminal set), provided the model's `predict` over-approximates what an action can do.
That proviso is the whole guarantee: it holds by construction for the UAV and budget
models and relative to the URL parser for the outbound-access model, and it does not
hold for free-form code or shell actions, which this prototype does not model.

## State models in this prototype

| model | state | safe set | terminal / backup | repair | guarantee |
|---|---|---|---|---|---|
| `uav` | fleet estimate from telemetry (`/v1/observe`) | tightened corridor (Paper V) | loiter set / latched tail, loiter | QP projection (Paper V's own `PredictiveSafetyFilter`, imported unchanged) | Paper V's theorem, under its bounded-disturbance assumptions |
| `budget` | spend, calls | spend ≤ max, calls ≤ max, nothing after stop | abort, costing a declared reserve | shrink adjustable units (e.g. `max_tokens`) to the largest admissible | exact (scalar integrator) |
| `egress` | requests made | allow-listed scheme/host/port/path/method, request budget | stop | http → https upgrade | relative to the strict URL parser (ambiguous URLs are denied) |

## Run it

```bash
pip install fastapi uvicorn numpy osqp clarabel scipy      # uav model needs the last four
ACTFILTER_POLICY=actfilter/examples/policy.json ACTFILTER_AUDIT=/var/lib/actfilter/audit.jsonl \
  uvicorn actfilter.service:app --host 127.0.0.1 --port 8765
python3 -m pytest actfilter/tests -q                       # 34 tests
```

`POST /v1/decide {"session","tool","args"}`, `POST /v1/observe {"session","model","observation"}`,
`GET /v1/health`, `GET /v1/stats`, `GET /v1/audit/verify`.

## Wire it into a host

**Claude Code / Claude Agent SDK** (`.claude/settings.json`; the hook may rewrite the input):
```json
{"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
  {"type": "command", "command": "python3 -m actfilter.hook --format claude --url http://127.0.0.1:8765"}]}]}}
```

**Hermes Agent** shell hook on `pre_tool_call` (set `fail_closed: true`; Hermes shell hooks
fail open by default):
`python3 -m actfilter.hook --format hermes --url http://127.0.0.1:8765`

**Any MCP host** (OpenHands, Hermes, Claude): launch each MCP server through the proxy,
e.g. in the host's MCP config
`"command": "python3", "args": ["-m", "actfilter.mcp_proxy", "--url", "http://127.0.0.1:8765", "--", "<server>", "<args>"]`.

## Deployment rules (from the 2025–2026 agent CVE record)

1. Run the service as a different user from the agent, and make the policy file and the
   hook/MCP configuration read-only to the agent. An agent that can edit its guard's
   configuration has no guard; most recent agent exploits did exactly that.
2. Route every effectful tool through the filter; list only side-effect-free tools as
   `passthrough`. Everything else is denied by default.
3. Bind the service to loopback or a unix socket.
4. Feed `/v1/observe` from trusted telemetry or ledgers only, never from the model.

## Measured here

In-process decision latency (p50 / p99): budget 0.016 / 0.056 ms, egress 0.017 / 0.057 ms,
UAV 4-aircraft observe + filter step 1.7 / 3.8 ms (one CPU core, this repository's server
class). The hook and proxy add one loopback HTTP round trip.

## Not yet done

- Filter-induced denial is counted (`/v1/stats`) but not yet split from attacker-induced
  denial as Paper V does.
- Further state models (infrastructure-as-code plans via `terraform plan`, database
  transactions) and a Pydantic AI / Google ADK adapter.
- An assurance case (GSN) and an adaptive red-team evaluation.
