# RobustUAVs.ai codebase map for Paper V (Predictive Safety Filtering for Language-Model UAV Agents under Adaptive Attack)

Scope: local read-only inspection of `the repository` (shallow clone, branch `claude/whelan-uavcas-ingest-u00isn`, tip `982a41c`, 1,281 files, 56 MB excluding .git). Sources below are local file paths (`file://` links) with line numbers. Timings were measured in this container (Python 3.13.16, 2 vCPU, 7 GB RAM, no GPU), running only offline repository code (certificate engine, Paper III combinatorics). Nothing was modified, installed or pushed.

## Q1. Certificate engine: how R_i(t), gamma = 1.625 m/s, Lipschitz L, margins and admissible sets are computed; API; runtime

### Takeaway
`certificates/engine.py` is a small set of scalar, closed-form certificate classes. It has no per-aircraft time-varying radius R_i(t) and no admissible-set object. The only thing close to "R_i(t) with an admissible set" is in Paper III: `CertificateProcess.rho()` gives a per-agent radius, and `eligibility()` gives the discrete admissible (agent, task) pairs, with rho_i <= alpha_j as the rule. Paper V therefore has to build the continuous admissible set A_adm(x_t) itself. Every primitive it needs (gamma, L, e^{LT}, slack, margins) already exists, and each call costs microseconds.

### Cited Findings
- **Engine file.** `certificates/engine.py` is 401 lines. Its classes are `Perturbation` (L121), `CertificateResult` (L129, with `.to_schema()`), `LipschitzGronwallCertificate` (L140), `RandomizedSmoothingCertificate` (L190), `StalenessGronwallCertificate` (L210), `MWURegretCertificate` (L289) and `PACBayesCertificate` (L304). `REGISTRY` is at L339 and a self-check `__main__` at L348–401. — [engine.py](file://certificates/engine.py)
- **Constants (`PHASE_A`, L94–118).** L_g = 1.01 (global), L_g_local = 1.181, T = 1.0, eps_out = 0.5, rs_sigma = 0.25, rs_radius = 0.44, mwu_num_policies = 4 ({aggressive, loiter, RTH, INS-only}), mcr_certified_target = 0.80, mcr_do326a_floor = 0.90. The Gronwall feature-space radii are 0.182 (global) and 0.153 (local). — [engine.py L94-118](file://certificates/engine.py)
- **gamma.** `StalenessGronwallCertificate.GAMMA` (L247–257) is {kinematic 15.0, receiver 1.20, ekf 1.37, campaign_sup 1.625}. The comment says 1.625 is the "supremum of the baseline-corrected per-sample rate over all 674 post-onset samples (experiments/gamma_campaign.py)". — [engine.py L247-257](file://certificates/engine.py)
- **State-space certificate.** `certify_staleness(theta_s, n_malicious_hops, margin_m, mapping="kinematic")` (L259–286) computes Δ = H·min(θ, s), δ_pos = γ·Δ and ρ = δ_pos·e^{L·T}, and certifies iff ρ ≤ margin_m. The returned params dict contains delta_staleness_s, gamma_m_s, delta_pos_m, tube_m, margin_m and inside_tube. Defaults are v_max = 15, slack_s = 5.0, L = PHASE_A["L_g"] = 1.01. — [engine.py L236-286](file://certificates/engine.py)
- **Inconsistent L.** `StalenessGronwallCertificate` defaults to the global L = 1.01. Elsewhere the local value is used: the fleet snapshot uses L = 1.181 (uav.py L831), Paper III uses `L_LOC = 1.1814` (certificate.py L38) and Paper IV uses `L_LOC = 1.1814` (constants.py L16). A live call `certify_staleness(0.25, 2, 10.0, 'campaign_sup')` returned `'L': 1.01, 'tube_m': 2.231`. — [engine.py L237](file://certificates/engine.py); [uav.py L831](file://platform/backend/app/uav.py); [certificate.py L38](file://paperIII/experiments/certcmdp/certificate.py)
- **Margins.** Corridor half-widths are a stated family {2, 5, 10, 20} m (`ALERT_LIMITS` in Paper III certificate.py L43, and `CORRIDOR_M` in Paper IV constants.py L75). The fleet simulator's default corridor_m is 10.0. — [certificate.py](file://paperIII/experiments/certcmdp/certificate.py); [paperIV constants.py](file://paperIV/experiments/constants.py)
- **Closest analogue to R_i(t).** Paper III `certcmdp/certificate.py`:
  - `KAPPA = exp(L_LOC*T_C)*GAMMA_SUP` (L44) equals 5.2958 m of certified error per second of staleness (measured here).
  - `rho_of_staleness()` is at L47.
  - `CertificateProcess` (L97) is a vectorised (B fleets × N agents) generator with `rho()` = KAPPA·(benign + dead-reckoning + relay) and `step(dt, jam_mask)`. It draws from measured residual pools in `results/hop_ledger.csv` (`residual_pools()`, L53).
  - `ThreatProfile` (L80) holds the jam/relay/fault rates, all tagged [assumption].
  — [certificate.py L44-162](file://paperIII/experiments/certcmdp/certificate.py)
- **Closest analogue to the admissible set.** `paperIII/experiments/certcmdp/combinatorics.py`:
  - `eligibility(rho, alpha, holder_of, h, lookahead, eta, keep_lookahead)` (L162) returns an (N, M) boolean admissibility matrix. Its acquire and keep rules include hysteresis and predictive lookahead.
  - `lexicographic_projection(elig, proposal, value, prev, eps_prev)` (L114) is the projection layer. It runs Hungarian matching via `scipy.optimize.linear_sum_assignment` and maximises coverage, then value, then agreement with the proposal.
  — [combinatorics.py](file://paperIII/experiments/certcmdp/combinatorics.py)
- **Runtime, measured here.**
  - Engine import: 0.099 s.
  - `certify_staleness`: 2.32 µs per call.
  - `LipschitzGronwallCertificate.certify`: 1.27 µs per call.
  - Paper III `CertificateProcess.step` (B = 1, N = 12): 65.8 µs.
  - `lexicographic_projection` (N = 12, M = 6): 46.2 µs.
  - Paper III's committed `e3_latency.csv` reports lexicographic_hungarian p50 0.018 ms and p99 0.040 ms at N = 12, M = 6 on an AMD EPYC-Genoa with 4 threads.
  — [paperIII/results/e3_latency.csv](file://paperIII/results/e3_latency.csv)
- **Unit bridge unavailable here.** In this container the engine ran with `HAVE_BRIDGE=False`. `certificates/unit_bridge.py` imports `uav_defense.datasets.texbat`, which needs torch, and torch is not installed. As a result the pos_error_m → feature-l2 bridge (caf_shift_v2) refuses with `unit_bridge_missing`. The staleness path does not need the bridge. — [unit_bridge.py L50-54](file://certificates/unit_bridge.py)
- **Existing callers.** The platform reaches the engine through `copilot.t_certify_staleness` (copilot.py L113–130), `/api/certify/staleness` (main.py L180) and `runners._run_certified_sweep` (runners.py L39). — [copilot.py](file://platform/backend/app/copilot.py); [runners.py](file://platform/backend/app/runners.py)

### Inferences
- The proposal's statement "Certificate engine producing A_adm (parent; γ = 1.625 m/s supremum)" overstates what exists. The engine produces a scalar tube and a yes/no verdict for one (θ, H, m). A_adm(x_t) over a continuous action space has to be built as a new module.
- A natural construction: the per-aircraft radius R_i(t) = KAPPA·staleness_i(t) (Paper III), optionally plus Paper IV's δ_tot terms, tightens the corridor. A_adm(x_t) is then the set of waypoint or velocity commands whose H-step predicted tube, inflated by R_i, stays inside the corridor and ends in a loiter-invariant set.
- Paper V should pin L explicitly to the local value 1.1814, or pass `L=` to `StalenessGronwallCertificate`, to avoid the 1.01/1.181 mismatch.
- Certificate evaluation is negligible next to any MPC solve or LLM call. Per-step filter cost will be dominated by the QP and the LLM.

### Gaps
- No R_i(t) symbol or admissible-set API exists anywhere in `certificates/`. I found no "admissible" identifier in the engine.
- There is no measured or certified closed-loop dynamics model F(x, u) with the Lipschitz constant over the operating region of the fleet simulator. L = 1.181 is the CT-TGNN navigation model's local Lipschitz constant, not the simulator's plant. The model-plant mismatch margin that the proposal's "honestly" box demands has no implementation yet.

## Q2. Fleet simulator: dynamics, time step, state/action, attack injection, the "ten" attack classes, seeds, logging, provenance, export

### Takeaway
The live fleet simulator is `platform/backend/app/uav.py` (1,086 lines). Its dynamics are illustrative, open-loop and kinematic: a fixed 12 m/s circular track with a lateral offset driven by attack-state variables. It has no control or action input that a planner could set (no waypoints, velocity or mode commands) and no MPC-usable model. Its per-step RNG is seeded from wall-clock time, so runs are not reproducible. Paper V needs either a new controllable, seeded simulator core, or reuse of Paper IV's vectorised closed-loop lateral simulator, which has real control.

### Cited Findings
- **Constants.** `MAX_FLEET = 12` (L519), `NOMINAL_MISSION_S = 70.0` (L520), `KAPPA = 0.25` (L521; schedule overrun, deadline = 87.5 s). The local `GAMMA` table is {kinematic 15.0, receiver 1.195, ekf 1.365} (L517). This table does **not** include the 1.625 campaign supremum, so the fleet tube uses 1.365 by default. — [uav.py L516-521](file://platform/backend/app/uav.py)
- **State.** The `UAVState` dataclass (L536–582) holds:
  - mission_progress_pct, battery_pct, link_quality_pct, gnss_spoof_confidence, staleness_s
  - autopilot_mode ∈ {nominal, gnss_degraded, rtl}, rtl_steps
  - x, y, z, heading_deg, nom_x, nom_y, deviation_m
  - completed, t_arr_s, on_time
  - history (capped at `HISTORY_CAP = 400`, L599)
  - provenance fields (mission, receiver, campaign_js_db, campaign_mcr, uplink_residual_s, bus_signature)

  `Fleet` (L585) holds uavs, links, t_s, corridor_m = 10, mapping = "ekf", js_db = 10 and n_steps. Sessions are kept in the in-memory `_STORE`, capped at 64 sessions (L597–598). — [uav.py L536-599](file://platform/backend/app/uav.py)
- **Dynamics in `fleet_step`.** `fleet_step(session, attacks, js_db, dt_s=1.0, corridor_m, mapping)` is at L686–819. Default dt = 1 s. Nominal motion is speed 12 m/s with heading increasing 4°/s, i.e. a fixed circle (L748–752). The actual position is the nominal position offset laterally by δ = γ·staleness + 3·gnss_spoof_confidence + U(−0.6, 0.6) (L754–759).
- **Modes and termination.** The mode switches to rtl when gnss_conf > 0.85 or link < 10, and to gnss_degraded when gnss_conf > 0.7 or link < 25 (L733–737). Termination: failure if deviation_m > corridor_m; success when progress ≥ 100; failure on battery < 5 or rtl_steps ≥ 12. on_time is checked against 70·(1 + 0.25) (L768–782). — [uav.py L686-819](file://platform/backend/app/uav.py)
- **Attack injection.** A per-step dict maps uav_id to an attack key (the `FleetStep` pydantic model in main.py L321–327, posted to `/api/uav/fleet/step`). Each class in `ATTACKS` (L474–513) carries link, gnss, stale_s, battery, stealth and progress coefficients. Detection is a Bernoulli draw with probability DEFENSE_CATCH[defense]·(1 − 0.6·stealth) (L516, L711–713). — [uav.py](file://platform/backend/app/uav.py); [main.py L321-353](file://platform/backend/app/main.py)
- **Attack class count.** `ATTACKS` has 10 keys: none, fgsm, pgd, cw, deepfool, gaussian, gnss_spoof, jam_link, delay_relay, label_flip. That is 9 attack classes plus nominal. The module comment says "The nine attack classes" (L462), while the README and the Paper V proposal say "ten attack classes". A separate `ATTACK_CATALOG` (L429) lists 7 perception attacks and is marked `executable: False`. — [uav.py L429-513](file://platform/backend/app/uav.py); [README.md](file://README.md)
- **Seeds.** `_spawn(n, seed=42)` (L602) draws initial states from the corpus through `corpus.sample_fleet(n, seed)`. `fleet_reset` always uses the default seed 42 and does not expose it (L670–677). The per-step RNG is `random.Random(int(time.time()*1000) % 2_000_000_000)` (L700), which makes steps non-deterministic. — [uav.py L602-700](file://platform/backend/app/uav.py)
- **Spatial and temporal certificates in the snapshot.** `snapshot()` (L821–890) reports spatial_mcr, temporal_mcr and composed_mcr. Its certificate block has tube = γ·worst_staleness·e^{1.181·1} against the corridor, plus a temporal budget κT = 17.5 s. The payload is tagged `"provenance": "synthetic_alignment"` with the note "Flight dynamics are illustrative." — [uav.py L821-890](file://platform/backend/app/uav.py)
- **Documented as modelled, not measured.** The docs list flight dynamics, attack damage rates, detection draws and GNSS phase timings as modelled ("A circuit at 12 m/s with per-tick drift. Not a PX4 SITL run"). Only γ, L, link residuals and campaign MCR are listed as measured. — [docs/simulation_architecture.md L51-97](file://docs/simulation_architecture.md)
- **Corpus-backed initialisation.** `platform/backend/app/corpus.py` (`sample_fleet` L186, `sample_mesh` L237, `clusters` L275) reads only committed `results/*.csv` files (ewbench_mcr_anchor, hop_ledger, ingest_stats, whelan_delta_calibration, hcrl_type_signatures). — [corpus.py](file://platform/backend/app/corpus.py)
- **Paper IV's simulator.** `paperIV/experiments/sim.py` has `simulate(N, seed, ...)` at L119. It is a vectorised lateral closed loop: a drag-damped double integrator under PD control on the estimated state, a 3-state KF, DT = 0.05 s (20 Hz), GNSS at 10 Hz, T_MISSION = 60 s, U_MAX = 4 m/s², C_DRAG = 0.35 s⁻¹. It includes Dryden wind and seeded common random numbers (`_CRN`), and reports a per-rollout maxdev. — [sim.py](file://paperIV/experiments/sim.py); [paperIV constants.py L21-29](file://paperIV/experiments/constants.py)
- **Paper III's environment.** `paperIII/experiments/certcmdp/env.py` `CertSwarm` is a vectorised 2-D task-allocation environment: agents fly toward assigned task sites at 15 m/s with a 0.5 s decision epoch, with spatial jammers. It has a proposal → `allocate(mode=projection|masking|first-claimant|fixed-margin)` pipeline. — [env.py](file://paperIII/experiments/certcmdp/env.py)
- **Export and provenance machinery.**
  - Front-end `ExportMenu` component, wired in `screens/uav/parts.js` (ScreenHeader, L16–29) and `screens/papers/parts.js` (`ResultsBrowser`, L173–248, with provenance chips).
  - Backend papers results API: `/api/papers/{pid}/results[/{name}]` (main.py L602–608, papers.py `results_index` L249 and `result_file` L287).
  - Experiment CSVs carry `provenance` columns, e.g. `paperIII/results/constants_paperIII.csv` has name,value,provenance,source.
  — [papers parts.js](file://platform/mobile/src/screens/papers/parts.js); [papers.py](file://platform/backend/app/papers.py)

### Inferences
- The proposal's plan to "put a language-model planner on the mission-planning task of the fleet simulator" cannot be done against `uav.py` as written, because there is no action channel. Paper V needs a controllable plant. Options:
  - (a) A new 2-D or 3-D point-mass or double-integrator fleet core with waypoint, velocity and mode actions, a fixed seed and dt of 0.1–0.5 s, reusing `UAVState` field names and the snapshot schema so the platform page can render it.
  - (b) Paper III's `CertSwarm` for task-level actions, combined with Paper IV's `sim.py` lateral dynamics for continuous safety.

  Option (a), with the plant made linear so the filter is a QP, is the cleanest route to Prop. 1. A linear plant makes recursive feasibility checkable exactly.
- RQ1 (zero violations) requires deterministic seeding. The wall-clock RNG at uav.py L700 must not be used in experiment code.
- The "ten attack classes" claim should be stated as "nine attack classes + nominal". Alternatively, adding a tenth class (e.g. `prompt_injection` on the textual channel) would make "ten" literally true.

### Gaps
- No logging to disk exists in the fleet simulator. History is in-memory only (HISTORY_CAP = 400). Paper V needs its own per-step JSONL or CSV intervention log.
- No routing, real detector inference or trajectory replay. These are listed as "where this goes next" in simulation_architecture.md.

## Q3. LLM provider integration (anthropic / openai / gemini / deepseek)

### Takeaway
`platform/backend/app/llm.py` (167 lines) is a minimal, single-turn, async text-completion router over raw HTTP (httpx). It covers four providers and falls back to a deterministic synthetic responder. It has no tool use, structured or JSON output, temperature or seed control, multi-turn agent loop, token or cost accounting, response caching or retries. Per-session rate limiting exists only at the FastAPI layer. The only "agent" is the copilot, which does keyword retrieval followed by a single completion. There is no planner agent.

### Cited Findings
- **Providers (llm.py L33–42).** Fallback order, first key wins:
  - anthropic: `ANTHROPIC_API_KEY`, model `"claude-sonnet-5"`, https://api.anthropic.com/v1/messages
  - openai: `OPENAI_API_KEY`, `"gpt-4o"`
  - gemini: `GEMINI_API_KEY`, `"gemini-2.0-flash"`
  - deepseek: `DEEPSEEK_API_KEY`, `"deepseek-chat"`

  `DEFAULT_PROVIDER = "anthropic"` (L57). — [llm.py](file://platform/backend/app/llm.py)
- **Call interface.** `async def complete(system, prompt, max_tokens=900, provider=None, api_key=None) -> Completion(text, provider, model, synthetic)` (L96–115). Any exception degrades to `_synthetic()` with a prefix note. It never raises. — [llm.py L96-115](file://platform/backend/app/llm.py)
- **`_dispatch` (L118–149).** Anthropic Messages API (anthropic-version 2023-06-01) with a single user message. Gemini `generateContent` puts the key in the URL query string. OpenAI and DeepSeek share chat-completions. Only `max_tokens` is set: no temperature, top_p, seed, tools or response_format. Timeout is 30 s (connect 10 s). There are no retries. — [llm.py L118-149](file://platform/backend/app/llm.py)
- **Key handling.** Keys come from environment variables or from a per-call user-supplied `api_key`, which is "never written to the environment, never persisted, and never included in a response" (L101–103, L120–122). On the server they come from `EnvironmentFile=-/etc/robustuavs/api.env` (deploy/robustuavs-api.service L25). — [llm.py](file://platform/backend/app/llm.py); [robustuavs-api.service](file://deploy/robustuavs-api.service)
- **Synthetic fallback.** `_synthetic` (L152–167) returns fixed text plus a sha256 digest. It does not produce actions.
- **Rate limiting.** `platform/backend/app/sessions.py` sets `LIMITS = {"llm": (30, 3600), "upload": (20, 3600)}` per session per hour (L65–68), enforced in process by `check_rate` (L71–92). The source notes it is "per-worker". — [sessions.py L53-100](file://platform/backend/app/sessions.py)
- **Caching.** `platform/backend/app/cache.py` is a Redis cache with an in-memory TTL fallback (DEFAULT_TTL 300 s, 512 entries). It is a generic cache, and I found no usage that caches LLM completions. — [cache.py](file://platform/backend/app/cache.py)
- **Cost tracking.** A grep for cost, usage and token accounting found no cost or token tracking in the platform's LLM path. The only "tokens" hits are auth tokens (auth.py). — [platform/backend/app/](file://platform/backend/app/)
- **Copilot.** `platform/backend/app/copilot.py` has a symmetric `TOOLS`/`DISPATCH` registry (14 tools, L141–212). `retrieve()` does keyword routing (L232–254), not model-driven tool calls. `answer()` makes one `complete()` call (L257–273). Its system prompt is at L20–34. — [copilot.py](file://platform/backend/app/copilot.py)
- **Mission plan review.** `review_mission_plan(text)` (uav.py L404–427) is a deterministic regex rule set (geofence, RTL, altitude, deadline, SORA) over free text. It is not a model. — [uav.py L386-427](file://platform/backend/app/uav.py)
- **Dependencies.** `httpx>=0.28.1` is a backend requirement. The `anthropic` and `openai` SDKs are not required anywhere. In this container fastapi, httpx, anthropic and openai are **not installed**. — [platform/backend/requirements.txt](file://platform/backend/requirements.txt)

### Inferences
- Paper V needs a new agent layer with these pieces:
  - a situation-to-text prompt builder (telemetry, operator note, map, peer reports), with explicitly delimited, attacker-controllable fields
  - structured action output: a JSON schema for {waypoint, task, mode}, with a parser that rejects malformed output and maps it to a "no-op/hold" proposal
  - temperature = 0 or a seed where the provider supports it
  - retries and backoff
  - per-call token and cost logging read from the provider usage fields
  - an on-disk response cache keyed by sha256(provider, model, system, prompt) so experiments can be replayed offline
  - a deterministic offline "scripted/mock agent" so CI and RQ1 can run without keys

  `llm.complete()` can be wrapped, but it discards usage metadata and swallows errors into synthetic text. Experiment code should call a variant that surfaces failures and usage.
- The configured model strings, especially "claude-sonnet-5" and "gpt-4o", must be verified against current provider catalogues before running. The paper must record the exact model IDs and dates. I did not verify availability (no network use).
- The 30/hour/session platform limit is irrelevant for offline experiments, but it matters for the live Safety Filter page. Each page step that calls an LLM consumes the "llm" bucket.

### Gaps
- No existing agent loop, no tool or function calling, no structured outputs, and no prompt-injection test fixtures anywhere in the repository.
- Provider pricing and quotas are not recorded in the repository.

## Q4. Paper III projection/feasibility code and Paper IV budget δ_tot code

### Takeaway
Both exist and are reusable:
- **Paper III** has a discrete projection layer. It is exact Hungarian matching under eligibility with hysteresis and lookahead.
- **Paper IV** composes the perturbation budget: the network tube, an adversarial stealth budget δ_adv, and empirical gnss/fault/env marginals combined by union or Rearrangement-Algorithm bounds.

Neither is continuous MPC. Paper V lifts Paper III's projection to a continuous QP and takes δ_tot from Paper IV as a margin tightening.

### Cited Findings
- **Paper III layout.** `paperIII/experiments/`:
  - `certcmdp/{certificate.py, combinatorics.py, env.py, trace_process.py}`
  - e1–e6 scripts, r3–r6 robustness scripts
  - `run_all.sh` (~10 min on 2 cores for E1–E4)
  - `run_marl.sh` (~1 h on 2 cores, trains 25 policies)

  `paperIII/results/` holds e5_marl_N{24,48,96} runs and r9 checkpoints (`*_actor.pt`), 843 files in total. — [paperIII/experiments/run_all.sh](file://paperIII/experiments/run_all.sh)
- **Projection layer.** `lexicographic_projection` (combinatorics.py L114) is lexicographic: max coverage, then max value, then max agreement with the proposal, with an optional keep-previous bonus. `eligibility` (L162) implements acquire (ρ + lookahead ≤ (1 − η)α − h) and keep (ρ + keep_lookahead ≤ α) with Thm 2/3 hysteresis and lookahead. `resolve_conflicts` is at L184 and `brute_max_matching` (oracle) at L196. — [combinatorics.py](file://paperIII/experiments/certcmdp/combinatorics.py)
- **Paper IV constants (paperIV/experiments/constants.py).**
  - GAMMA_SUP = 1.625, SLACK_S = 4.84, H_HOPS = 2, L_LOC = 1.1814, T_C = 1.0, AMP = e^{L·T} (L13–18)
  - DT = 0.05, T_MISSION = 60 (L21–23)
  - CORRIDOR_M = (2, 5, 10, 20) (L75)

  — [paperIV constants.py](file://paperIV/experiments/constants.py)
- **δ_tot composition.** The manuscript defines δ_tot = δ_net(θ) ⊕ δ_adv(θ) ⊕ δ_gnss ⊕ δ_fault ⊕ δ_env (paperIV/manuscript/main.tex L45, L189). In code (`paperIV/experiments/run_pilot.py`):
  - `net_tube(theta_net) = AMP*GAMMA_SUP*H_HOPS*min(theta_net, SLACK_S)` (L269–270)
  - `pbar(marg, s, method="ra"|"union"|"indep")` gives the tail probability of the gnss + fault + env sum (L273–279)
  - `e3_budget(N)` builds the marginals (L232–267)
  - `e4` computes δ_adv as the supremum of stealthy maxdev (L282–)

  `depbounds.py` provides `union_bound` (L30), `ra_bound` (L82, Rearrangement Algorithm), `indep_tail` (L107) and `comon_tail` (L113). The certified floor is f = 1 − p̄(m − δ_adv − net_tube). — [run_pilot.py](file://paperIV/experiments/run_pilot.py); [depbounds.py](file://paperIV/experiments/depbounds.py)
- **Committed numbers.** `paperIV/results/e4_delta_adv.csv` gives δ_adv_cal = 4.371 m (argmax family fault_mimic) at FPR 0.01, 0.05 and 0.1. `e3_marginals.npz` (610 KB) stores the empirical gnss/fault/env/joint marginals. The pilot ran 1,839,600 missions in 1,637 s wall time (`run_meta.json`). — [e4_delta_adv.csv](file://paperIV/results/e4_delta_adv.csv); [run_meta.json](file://paperIV/results/run_meta.json)
- **Paper IV attacker search.** `r1_attackers.py` uses CMA-ES (`cma`) and optuna TPE. Neither is installed here. — [r1_attackers.py L7-110](file://paperIV/experiments/r1_attackers.py)
- **Platform exposure.** `/api/papers/III/certify`, `/III/lift`, `/III/marl` and `/IV/floor` (main.py L565–598) call this code through papers.py (`certify` L685, `_paperIV_depbounds` L832). — [main.py](file://platform/backend/app/main.py)

### Inferences
- For Prop. 3, the simplest sound coupling is to tighten the corridor: m_eff(t) = m − R_i(t) − q_{1−α}(δ_tot), where the quantile comes from Paper IV's RA or union bound, or from δ_adv + net_tube as a deterministic shift. The denial rate is then measured as a function of the δ_tot quantile or θ. All of these can be read from committed Paper IV results without re-running Paper IV.
- Paper IV's CMA-ES/TPE black-box attacker harness (seed blocks, held-out evaluation, Clopper–Pearson, Holm) is a ready template for Paper V's adaptive-attack protocol. It can be reused with a cheaper surrogate (mock LLM) for the search, then re-evaluated with real LLMs.

### Gaps
- There is no `delta_tot()` function. δ_tot exists as a composition across `run_pilot.py` helpers, not as one importable API. Paper V should add a thin wrapper.

## Q5. Data: data/, ingest/, the "whelan uavcas ingest", PENDING_ON_DATA.md

### Takeaway
`data/` holds only `fetch_kaggle.py`; `data/raw/` and `data/staging/` are gitignored and absent. There are no Git LFS pointers in the clone. The branch name refers to two ingest adapters:
- `ingest_whelan.py`: the Whelan "UAV Attack Dataset", IEEE DataPort 10.21227/00dg-0d12, real and SITL/HITL PX4 flights under GPS spoof, GPS jam and MAVLink ping-DoS.
- `ingest_uavcas.py`: UAV-CAS, whose release file is unreachable.

Paper V needs no raw data. It consumes only committed `results/*.csv` (γ samples, hop ledger, local Lipschitz) and Paper IV marginals.

### Cited Findings
- **`data/` contents.** `data/` contains only `fetch_kaggle.py`, which uses kagglehub and needs Kaggle credentials for the dataset `rogernickanaedevha/uavs-network-and-navigation-end-to-end-security-data` (DOI 10.34740/kaggle/dsv/18346203). `.gitignore` excludes `data/raw/` and `data/staging/`. A grep for `git-lfs.github.com` pointers found none. — [fetch_kaggle.py](file://data/fetch_kaggle.py); [.gitignore](file://.gitignore)
- **Corpus sizes (README).**
  - UAV Attack Dataset (Whelan): ~700 MB
  - UAV-CAS: ~2.5 GB, not committed
  - Ingested events: HCRL 200,000; UAVIDS-2025 122,171; EW-Bench 93,600; DATAMUt 15,392; Whelan 610; UAV-CAS 0
  - Total 431,773 events, of which 200,610 (46.5%) are real hardware

  — [README.md](file://README.md)
- **Whelan adapter.** `ingest/ingest_whelan.py` docstring: "real + SITL/HITL PX4 flights (Pixhawk 4, Holybro S500, PX4 v1.11.3) under GPS spoofing, GPS jamming, and MAVLink ping-DoS". It parses ULOG or ulog2csv input. The manifest `ingest/whelan_manifest.json` lists 3 flights (benign_live_01, jam_live_01, spoof_live_01), with attack_start and attack_end left as "TODO". — [ingest_whelan.py](file://ingest/ingest_whelan.py); [whelan_manifest.json](file://ingest/whelan_manifest.json)
- **PENDING_ON_DATA.md (last updated 2026-08-13).**
  - §0: anonymised artifact is a pre-submission blocker. It also asks for manual deletion of the stale branch `claude/whelan-uavcas-ingest-u00isn` (the branch of this clone).
  - §1: UAV-CAS stat CSV missing.
  - §2: Whelan attack intervals.
  - §3: TEXBAT IQ for caf_shift_v2 re-calibration.
  - §4: interface campaign done (γ_sup = 1.625 from 674 samples, 6.1× variation); platform diversity and cruise regime still blocked.
  - §4b: cruise-regime γ.
  - §5: PAC-Bayes KL.
  - §6: HCRL map confirmation.

  — [PENDING_ON_DATA.md](file://PENDING_ON_DATA.md)
- **Hover-only γ.** γ is from hover only: "Hover only; p90 of |v_xy| is under 0.65 m/s". — [PENDING_ON_DATA.md §4](file://PENDING_ON_DATA.md)

### Inferences
- Paper V's sim runs at cruise speeds (12–15 m/s in the existing sims), while γ = 1.625 is a hover-regime supremum. This must be stated as an assumption, or Paper V must also report the kinematic γ = 15 m/s as a conservative bound. It is the same open risk Paper I and the parent flag.
- The runbooks say to branch from `claude/whelan-uavcas-ingest-u00isn` or `dev/whelan-uavcas-ingest`, but PENDING §0 says this branch is to be deleted. Paper V work should go on `dev/whelan-uavcas-ingest` or `main`.

### Gaps
- The 3 Whelan flights are not present locally, so I could not verify the "~700 MB" size from data. That figure is from the README only.

## Q6. Platform (web app): framework, adding pages, deploy

### Takeaway
- **Backend:** FastAPI (one `main.py`, 615 lines, with routes grouped by tag).
- **Front end:** Expo 52 / React Native 0.76 / react-native-web.
- **Adding a page:** write a screen component, register it in two files (`layout/nav.js` LEFT_GROUPS and `layout/Shell.js`), add an API client function and add backend routes.
- **Deploy:** Caddy + systemd uvicorn via `deploy/` scripts.

A Safety Filter page fits the existing "Papers" group pattern (Paper I–IV screens) or the "UAV" group next to FleetDemo.

### Cited Findings
- **Backend modules.** `platform/backend/app/` contains main.py, uav.py, llm.py, copilot.py, papers.py, runners.py, jobs.py, sessions.py, cache.py, db.py (SQLite by default), auth.py, upload.py, evaluation.py, registry.py, results.py and corpus.py (5,678 lines in total). Requirements: fastapi ≥0.115.6, uvicorn, pydantic ≥2.11, httpx, python-multipart, sqlalchemy. Postgres and Redis are optional. — [platform/backend/requirements.txt](file://platform/backend/requirements.txt)
- **Paper routes.** `PAPERS = {"I": "paperI", "II": "paperII", "III": "paperIII", "IV": "paperIV"}` (papers.py L48). Generic routes `/api/papers/{pid}/results` exist (main.py L602–608). Paper-specific calculators are explicit routes (main.py L540–598). Adding "V": "paperV" to `PAPERS` would give the results browser for free. — [papers.py L48](file://platform/backend/app/papers.py)
- **Runner registry.** `jobs.register(Runner(...))` (jobs.py L77). Runners are defined in runners.py, e.g. `_run_certified_sweep` (L39), registered at L89. The `AgentStudioScreen` auto-renders any registered runner "without a frontend change". — [jobs.py](file://platform/backend/app/jobs.py); [AgentStudioScreen.js](file://platform/mobile/src/screens/eval/AgentStudioScreen.js)
- **Front end.** `platform/mobile/package.json`: expo ~52.0.0, react 18.3.1, react-native 0.76.5, react-native-svg 15.8.0, react-native-web ~0.19.13. The web build is `expo export --platform web`.
  - Navigation registry: `src/layout/nav.js`, where `LEFT_GROUPS` entries have {key, glyph, title, grounded, blurb, steps, tip}. The Papers group is at L163–208.
  - Screen map: `src/layout/Shell.js` (imports L13–44, key→component map L47+).
  - API clients: `src/api/{client,uav,papers,evaluation}.js`.
  - Existing paper screens: `src/screens/papers/PaperI–IVScreen.js` (235–340 lines each), with shared `parts.js` (usePaper, Field, Pills, DataTable, ResultsBrowser, ExportMenu).
  - Fleet page: `src/screens/uav/FleetDemoScreen.js`.

  — [nav.js](file://platform/mobile/src/layout/nav.js); [Shell.js](file://platform/mobile/src/layout/Shell.js); [package.json](file://platform/mobile/package.json)
- **Planned Safety Filter page.** Documentation_v2.tex L1131–1133 already lists it as planned, not built: "a language-model agent in the mission-planning loop, behind a predictive safety filter; shows the agent's proposal, the filtered action, and the fallback rate under adaptive evaluation". It states that every page "reuses the existing export menu, provenance badge and certificate engine". — [Documentation_v2.tex L1108-1133](file://docs/Documentation_v2.tex)
- **Deploy files.** `deploy/`: Caddyfile, robustuavs-api.service (systemd, EnvironmentFile /etc/robustuavs/api.env), deploy.sh, redeploy.sh, bootstrap.sh, cloud-init.yaml, BRINGUP.md and github-actions-deploy.yml.example. The runbook is in docs/deployment_runbook.md. — [deploy/](file://deploy/)
- **503 convention.** The platform convention is that "A 503 from the API means 'not produced in this deployment'", and pages carry a `grounded` or `illustrative` badge. — [README.md](file://README.md)

### Inferences
- The live page should default to a mock or scripted agent plus replay of committed Paper V results, with an optional user-supplied key (llm.complete supports `api_key`) for live LLM steps. This keeps it inside the shared 30/h budget and makes it render on deployments without keys.
- The page should be badged "illustrative" for dynamics, consistent with simulation_architecture.md.

### Gaps
- I did not build or run the front end (no npm install was allowed), so page rendering is unverified.

## Q7. Experiment harness conventions; proposals files for Paper V and bib keys

### Takeaway
Each paper lives in a folder `paperX/{experiments, results, manuscript}`. Scripts are plain Python with `argparse`. Each paper has a `constants.py` whose values are tagged [measured]/[parent]/[model]/[assumption]. Results are CSVs with provenance columns. A `run_all.sh` drives everything, `make_numbers.py` writes `manuscript/numbers.tex` macros and `export_figdata.py` writes `manuscript/figdata/*.dat`. The rule is "never type a number into main.tex". The repository does **not** contain `proposal_preamble3.tex` or `proposals3.bib`: the uploaded proposal references both, while the repository copy references `proposal_preamble` and `proposals`. All 10 keys cited by Paper V exist in `paper/proposals/proposals.bib`.

### Cited Findings
- **Harness pattern.**
  - `paperIII/experiments/run_all.sh` runs certificate.py, e1–e6, export_figdata.py and make_numbers.py.
  - `paperIV/results/run_meta.json` records N, budgets, wall time and seed blocks.
  - Constants CSVs carry name,value,provenance,source (e.g. `paperIII/results/constants_paperIII.csv`).
  - Top-level `experiments/` holds the parent's scripts (compose_certified.py, gamma_campaign.py, make_paper_figures.py, provenance_ledger.py, run_real_corpus.sh).

  — [paperIII run_all.sh](file://paperIII/experiments/run_all.sh); [run_meta.json](file://paperIV/results/run_meta.json); [experiments/](file://experiments/)
- **Project runbooks.** The project runbooks confirm: "Every experiment writes a CSV to `paperIV/results/`. `make_numbers.py` turns those CSVs into LaTeX macros in `manuscript/numbers.tex` … Never type a number into `main.tex`." They also note the sandbox constraint "2 cores, 7 GB RAM, no GPU, no flight simulator". — Project doc `PaperIV/RUNBOOK_CLAUDE_CODE.md` (Projects tool)
- **Proposal location.** The Paper V proposal in the repository is `paper/proposals/PaperV_safety_filter_llm_agent.tex` (with a compiled PDF). It differs from the upload in three lines: `\input{proposal_preamble}` vs `{proposal_preamble3}`, `\bibliography{proposals}` vs `{proposals3}`, and a date "2026-10-01" on the author line. — [PaperV_safety_filter_llm_agent.tex](file://paper/proposals/PaperV_safety_filter_llm_agent.tex)
- **Preamble.** `paper/proposals/proposal_preamble.tex` defines `\code`, `\proposalheader`, the `honestly` environment, and the `proposition`, `definition` and `claim` theorem types that Paper V uses. — [proposal_preamble.tex](file://paper/proposals/proposal_preamble.tex)
- **Bib keys.** In `paper/proposals/proposals.bib` (62 entries) I found parentpaper, openai2024agents, greshake2023injection, seto1998simplex, sha2001simplex, wabersich2021psf, hewing2020mpclearning, rawlings2017mpc, carlini2017towards and tramer2020adaptive. `parentpaper` is `@misc` (L277): Anonymous, "From Wire to Flight: A Conditional Mission-Completion Guarantee for UAVs", under submission, 2026. — [proposals.bib](file://paper/proposals/proposals.bib)
- **README note.** paper/proposals/README.md says Paper V is "Paper III's projection layer lifted to continuous MPC" and that SUPERVISOR_BRIEF.tex "currently covers I–IV". — [paper/proposals/README.md](file://paper/proposals/README.md)

### Inferences
- To compile the uploaded version, either copy `proposal_preamble.tex` → `proposal_preamble3.tex` and `proposals.bib` → `proposals3.bib`, or revert the two `\input`/`\bibliography` lines. The "3" files are presumably from a separate Overleaf bundle that I did not find on disk.
- Paper V should follow the convention `paperV/{experiments/{constants.py, run_all.sh, make_numbers.py, export_figdata.py, ...}, results/, manuscript/}`.

### Gaps
- `proposal_preamble3.tex` and `proposals3.bib` were not found anywhere in the repository or the upload directory. The upload directory has Paper I–IV zip packages that I did not unpack, so the files may exist inside one of them.

## Q8. requirements.txt and solvers

### Takeaway
No MPC or QP stack is declared or installed: no cvxpy, OSQP, CasADi, do-mpc, qpsolvers, Clarabel, ECOS or SCS. The only optimisers used in the repository are `scipy.optimize.linear_sum_assignment` (Paper III) and `scipy.optimize.linprog` (Paper IV r8). SciPy 1.18.1 and NumPy 2.5.3 are installed here, so a small QP can be solved with `scipy.optimize.minimize(method="SLSQP"/"trust-constr")` or `linprog`/HiGHS without new installs.

### Cited Findings
- **Root requirements.txt.** jsonschema, kagglehub, torch ≥2.0, numpy ≥1.24, scipy ≥1.10, pandas ≥2.0 and pyyaml ≥6.0. `models/uav_defense/requirements.txt` adds torch ≥2.1, scikit-learn, matplotlib, requests and torchdiffeq. — [requirements.txt](file://requirements.txt); [models/uav_defense/requirements.txt](file://models/uav_defense/requirements.txt)
- **Solver usage.** A grep across *.py and *.txt for cvxpy|osqp|casadi|do_mpc|qpsolvers returned nothing outside third_party. The only solver uses are `linear_sum_assignment` (combinatorics.py L14) and `linprog` (r8_analytic_bound.py L54). — [combinatorics.py](file://paperIII/experiments/certcmdp/combinatorics.py)
- **Installed here.** numpy 2.5.3, scipy 1.18.1, pandas 3.0.5, jsonschema 4.26, pyyaml 6.0.3. Missing: torch, cvxpy, osqp, casadi, do_mpc, qpsolvers, clarabel, ecos, scs, fastapi, httpx, anthropic, openai, cma, optuna, pyulog. — local `python3 -I -c import ...` probe in this container

### Inferences
- Recommended approach: make the plant linear (double integrator per aircraft) and the safe set polyhedral (corridor half-planes tightened by R_i(t) + δ_tot, a velocity box, an acceleration box). The filter is then a small convex QP: about 12 aircraft × H ≈ 10–20 steps × 4 decision variables, which is decoupled per aircraft unless separation constraints are added.
- Add `cvxpy` + `osqp` (or `osqp` alone, or `clarabel`) to a new `paperV/requirements.txt` once network installs are allowed. Keep a SciPy-only fallback, e.g. an explicit closed-form projection for box/half-plane constraints with a one-step-reachable invariant set, so the harness runs in this container today.
- Recursive feasibility and the control-invariant terminal set: loiter (zero-velocity hold) inside the tightened corridor is invariant for a double integrator if the braking distance v²/(2·u_max) fits inside the margin. This gives an analytic terminal constraint without a reachability toolbox.

### Gaps
- No solver benchmarks exist for this problem. MPC runtime per call is unmeasured. Based on generic OSQP performance this would be expected at sub-ms to a few ms for problems of this size, but no source in the repository confirms that.

## Q9. Compute, memory and cost feasibility

### Takeaway
Everything except real LLM calls is CPU-light and feasible in this 2-vCPU / 7 GB container. The certificate is ~2 µs per call, the Paper III projection ~46 µs, the Paper IV pilot is CPU-only, and a linear MPC over 12 aircraft is expected at ms scale. The binding constraints are LLM API cost, latency and rate limits, plus provider non-determinism, and no API keys or network SDKs are present here.

### Cited Findings
- **Container resources.** 2 CPUs, 7 GB RAM, no `nvidia-smi` (no GPU), 30 GB free disk. — local probe
- **Measured per-call costs.** certify_staleness 2.32 µs, CertificateProcess.step 65.8 µs, lexicographic_projection 46.2 µs (N = 12). — local timing (Q1)
- **Paper IV pilot cost.** 1,839,600 missions in 1,637 s wall time. — [run_meta.json](file://paperIV/results/run_meta.json)
- **Paper III run times.** E1–E4 take "~10 min on 2 CPU cores". The MARL study takes "about 1 h on 2 cores". — [paperIII run_all.sh](file://paperIII/experiments/run_all.sh)
- **LLM call timeout.** 30 s per call in llm.py, with no batching. — [llm.py L21](file://platform/backend/app/llm.py)

### Inferences
- **LLM call volume.** One episode is T = 70 s. At a planning cadence of one call every 5 s that is 14 LLM calls per aircraft-episode, and 168 calls per 12-aircraft episode (fewer with one fleet-level planner call per epoch). A campaign of, for example:
  - 4 providers × 3 attack strengths × 4 δ_tot levels × 2 (filter on/off) × 20 seeds

  is 1,920 episodes, which is roughly 27k to 320k calls. At ~1–3 k tokens per call that is tens to hundreds of millions of tokens.
- **Cost implication.** That volume is a paid-API, server-side job with caching. It is not feasible in this container (no keys, no SDKs) and is expensive at frontier-model prices.
- **Mitigations.**
  - (i) Use one fleet-level planner call per decision epoch rather than per aircraft.
  - (ii) Run the adaptive search (CMA-ES/TPE over injection templates) against a cheap model or a local open-weights model, then transfer-evaluate on frontier models with fewer seeds.
  - (iii) Cache every completion by hash for replay.
  - (iv) Report the RQ1 zero-violation result mainly with a **worst-case adversarial planner**, i.e. a non-LLM oracle that outputs the action maximising boundary pressure. Prop. 1 covers every sequence of planner outputs, so a direct adversarial-action search is a stronger and free stress test. Real LLMs are then needed only for RQ2 and RQ4 realism.
- **Local open-weights models.** Running these, for example via vLLM, would need a GPU server. That is infeasible here.
- **Feasible now, with no network.** The simulator core, the QP filter (SciPy fallback), the δ_tot coupling from committed Paper IV results, a scripted/mock planner, an oracle adversarial planner, and the full RQ1/RQ3/RQ4 pipeline with mock agents, including numbers.tex generation.

### Gaps
- Token counts per prompt and current provider prices are unknown from the repository. No cost model exists. The configured model IDs have not been checked against live catalogues.

## Q10. Gaps: new modules Paper V must add (suggested paths consistent with repository conventions)

### Takeaway
Paper V needs a new `paperV/` tree mirroring Paper III/IV, about 10 new Python modules, and a platform integration of 1 backend module, ~4 routes and 1 screen. Nothing in the repository today implements the MPC filter, a controllable fleet plant, an LLM planner loop, structured LLM actions, prompt-injection attacks, or intervention/denial metrics.

### Cited Findings
- **Platform item V is planned, not built.** "Every item below is planned, not built" applies to item V, the Safety Filter page. — [Documentation_v2.tex L1108-1133](file://docs/Documentation_v2.tex)
- **Fleet simulator lacks an action channel.** It has no action input and uses wall-clock RNG. — [uav.py L686-760](file://platform/backend/app/uav.py)
- **LLM router is completion-only.** It has no structured output, usage logging or caching. — [llm.py](file://platform/backend/app/llm.py)

### Inferences
The proposed new files are as follows.

**`paperV/experiments/`**
- `constants.py`: imports or mirrors GAMMA_SUP = 1.625, L_LOC = 1.1814, T_C = 1, SLACK_S, H_HOPS, CORRIDOR_M = (2, 5, 10, 20), MAX_FLEET = 12, T = 70 s, KAPPA_SCHED = 0.25, dt, horizon H, u_max and v_max. Each value carries a [parent]/[model]/[assumption] tag. Paper III already uses the name KAPPA for e^{LT}γ, so the schedule κ needs a distinct name.
- `plant.py`: seeded, vectorised, controllable fleet plant. Per-aircraft double integrator in 2-D (optionally plus altitude), with actions {waypoint, velocity setpoint, mode ∈ {nominal, loiter, rtl}}. It adds the existing attack effects (staleness, gnss conf, link) from uav.py `ATTACKS` through a deterministic RNG, so the 9 + 1 classes carry over. A model-mismatch term (wind or drag from Paper IV `sim.py`) is included and bounded by w_max.
- `admissible.py`: per-aircraft R_i(t), reusing `paperIII/.../certificate.CertificateProcess` or `rho_of_staleness`, plus `admissible_set(x_t, R_i, delta_tot, m, H)`, which returns the tightened polyhedral constraints. It also includes the terminal invariant-set check (braking distance fits in the margin) and fallback recursive-feasibility checks.
- `filter.py`: `PredictiveSafetyFilter.filter(x_t, a_llm) -> (a_star, intervened, fallback, solve_ms, status)`. It solves min ||a − a_llm|| subject to the H-step tube staying in the tightened corridor and a terminal loiter-invariant constraint. A cvxpy/OSQP backend is used when available, with a SciPy fallback. A Simplex-style baseline (accept or reject only, no projection) and a "no filter" baseline are included for comparison.
- `budget.py`: a `delta_tot(theta, fpr, alpha, method)` wrapper over `paperIV/experiments/run_pilot.net_tube`, `depbounds.ra_bound`/`union_bound` and the committed `paperIV/results/e3_marginals.npz` and `e4_delta_adv.csv`.
- `agent.py`: LLM planner.
  - `situation_text(state, channels)` builds the prompt with explicitly separated operator, telemetry, map and peer channels.
  - `plan(...)` returns a JSON action validated with jsonschema.
  - Providers wrap or fork `platform/backend/app/llm.py`, adding temperature = 0 or seed, usage capture, retries, and a sha256 on-disk cache in `paperV/results/llm_cache/`.
  - `ScriptedAgent` (benign heuristic) and `OracleAdversarialPlanner` (direct worst-case actions) need no API.
- `attacks.py`: textual-channel injection model. The attacker controls a subset of channels. Template families: goal hijack, waypoint override, false-telemetry ("GNSS degraded, RTL now"), authority spoof, stealthy denial. A parameterised search space is defined for adaptive search.
- `adaptive.py`: adaptive attacker loop. It uses filter-aware objectives (maximise fallback or intervention rate; maximise boundary proximity; stealth constraint), with optimisers CMA-ES/TPE as in Paper IV `r1_attackers.py`, plus a greedy/LLM-red-teamer variant. It follows the same seed-block and held-out evaluation discipline as Paper IV `run_meta.json`.
- `episode.py` / `run_campaign.py`: the RQ1–RQ4 grid. Per-step JSONL logs record proposal, filtered action, admissible-set summary, R_i, δ_tot, intervention, fallback, violation, provider, model, tokens and latency. They aggregate to `results/rq1_violations.csv`, `rq2_denial.csv`, `rq3_denial_vs_dtot.csv`, `rq4_benign_cost.csv` and `run_meta.json`.
- `stats.py`: Clopper–Pearson upper bound on the violation rate (zero-violation claims as "0/n, 95% CP upper ≤ x"), bootstrap CIs on the denial rate, and Holm correction. These reuse patterns from `paperIII/experiments/e6_aggregate.py` (`cp_upper`, `strat_boot`) and `paperIV/run_pilot.py` (`cp_interval`, `holm`).
- `make_numbers.py`, `export_figdata.py` and `run_all.sh`: same convention as Papers III/IV.

**Other paperV files**
- `paperV/manuscript/`: main.tex, numbers.tex, figdata/, refs.bib.
- `paperV/README.md` and `paperV/RUNBOOK.md`.

**Platform**
- `platform/backend/app/safety_filter.py`: session store analogous to the uav.py fleet `_STORE`. Exposes `/api/papers/V/filter/reset`, `/step` (with an optional user api_key and provider, charged to the "llm" rate bucket), `/state` and `/defaults`. Add `"V": "paperV"` to papers.py `PAPERS` (L48) so the results browser works.
- `platform/mobile/src/screens/papers/PaperVScreen.js` (or `screens/uav/SafetyFilterScreen.js`): shows the proposal vs filtered action, the admissible-set polygon (react-native-svg), the live fallback rate and the intervention log, with `ExportMenu` and provenance chips. Register it in `layout/nav.js` (Papers group) and `layout/Shell.js`, and add client functions in `src/api/papers.js`.
- Optional: a runner in `platform/backend/app/runners.py` (`register(Runner(kind="safety_filter_sweep"...))`) so Agent Studio can launch small mock-agent sweeps.

**Housekeeping**
- Either add `paper/proposals/proposal_preamble3.tex` and `proposals3.bib`, or align the uploaded tex to the repository names.
- Fix or parameterise the L default in `StalenessGronwallCertificate` (engine.py L237). Changing the engine would alter parent self-check assertions (r6 at engine.py L386 depends on L = 1.01), so pass `L=1.1814` from Paper V instead of editing the engine.
- Document "9 attack classes + nominal", or add `prompt_injection` as the tenth.

### Gaps
- Whether Prop. 1 can be claimed for the simulated plant depends on a stated, bounded model-mismatch disturbance w_max. The current fleet simulator's U(−0.6, 0.6) m lateral jitter is position noise, not a disturbance model. Paper V must define this, and none of the existing code provides it.
- No existing test harness for the platform's new routes beyond `platform/backend/tests_smoke.py`, which I did not inspect in detail.
