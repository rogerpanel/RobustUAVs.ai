"""Fail-loud LLM harness for the planner, attacker and judge roles (runbook P3.1).

Never a synthetic completion: a missing key, a non-retryable HTTP error, retries exhausted or an
empty response raises LLMUnavailable (the episode becomes status=api_error and is re-run on
--resume). A refusal or malformed output is planner BEHAVIOUR, not an API failure: the caller
maps it to per-aircraft holds counted as parse_fail, with the reason logged.

Providers
  anthropic      official `anthropic` SDK, structured output via output_config.format (json_schema).
                 No forced tool_choice and no temperature on current models (both are rejected);
                 no server-side refusal fallbacks: a fallback would silently swap the model under
                 test, which the runbook forbids within a cell.
  openai         Chat Completions over httpx, response_format json_schema (strict).
  gemini         generateContent over httpx, responseSchema; key in the x-goog-api-key header.
  deepseek       OpenAI-compatible endpoint, response_format json_object (schema in the prompt).
  openai_compat  vLLM / llama.cpp server at PAPERV_OPENAI_COMPAT_BASE_URL, json_schema.

Every call: budget check (ledger total + projected cost <= PAPERV_MAX_USD) -> sha256 cache ->
retries with exponential backoff and jitter on 408/409/429/5xx/timeouts (Retry-After honoured,
at most 6 attempts, 60 s per attempt) -> ledger row (no prompt text) -> atomic cache write.
Keys come from os.environ only and are redacted from every logged error.
"""
from __future__ import annotations

import csv
import fcntl
import hashlib
import json
import os
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    from . import constants as C
except ImportError:
    import constants as C

LOCK_PATH = C.HERE / "models.lock.json"
LEDGER = C.RESULTS / "llm_ledger.csv"
CACHE_BENIGN = C.RESULTS / "llm_cache_benign"
CACHE_RESTRICTED = C.RESTRICTED / "llm_cache"
MAX_ATTEMPTS = 6
TIMEOUT_S = 60.0
RETRYABLE = {408, 409, 429, 500, 502, 503, 504, 520, 522, 524, 529}
KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY",
           "deepseek": "DEEPSEEK_API_KEY", "openai_compat": "OPENAI_COMPAT_API_KEY"}
LEDGER_FIELDS = ["ts", "campaign_id", "cell_id", "mission_seed", "epoch", "role", "provider", "model_id",
                 "prompt_sha", "cache_hit", "tokens_in", "tokens_in_cached", "tokens_cache_write", "tokens_out",
                 "latency_s", "usd", "http_status", "attempt", "stop_reason"]
_SECRET = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|AIza[0-9A-Za-z_\-]{10,}|sk-ant-[A-Za-z0-9_\-]{8,})")


class LLMUnavailable(RuntimeError):
    """The provider could not deliver a completion. Never replaced by synthetic text."""


class BudgetExceeded(RuntimeError):
    """The next call would push the ledger past PAPERV_MAX_USD; the campaign stops cleanly."""


class CacheMiss(RuntimeError):
    """--cache-only replay found no cached completion for a request."""


def redact(s):
    return _SECRET.sub("[REDACTED]", str(s))


# ------------------------------------------------------------------ model pins
def load_lock(path=LOCK_PATH):
    if not Path(path).exists():
        raise LLMUnavailable(f"{path} missing: pin the models first (agent.py --pin ...)")
    return json.loads(Path(path).read_text())


def role_entry(role, lock=None):
    lock = lock if lock is not None else load_lock()
    e = lock.get("roles", {}).get(role)
    if e is None:
        raise LLMUnavailable(f"role {role!r} is not pinned in models.lock.json")
    if e.get("status") == "unused":
        raise LLMUnavailable(f"role {role!r} is marked unused in models.lock.json")
    for k in ("provider", "model_id", "price_in_per_mtok", "price_out_per_mtok"):
        if e.get(k) in (None, ""):
            raise LLMUnavailable(f"role {role!r}: {k} is not set in models.lock.json (no call without prices)")
    if e["provider"] != "openai_compat":           # only a self-hosted model may be free
        for k in ("price_in_per_mtok", "price_out_per_mtok"):
            if float(e[k]) <= 0:
                raise LLMUnavailable(f"role {role!r}: {k} = {e[k]} in models.lock.json; a paid provider needs its real "
                                     "price, otherwise the spend cap cannot see this model's cost")
    return e


def call_cost(e, tokens_in, tokens_cached, tokens_cache_write, tokens_out):
    """USD = uncached input * p_in + cache reads * p_cache_read + cache writes * p_cache_write + output * p_out."""
    p_in = float(e["price_in_per_mtok"]); p_out = float(e["price_out_per_mtok"])
    p_cr = float(e.get("price_cache_read_per_mtok") if e.get("price_cache_read_per_mtok") is not None else p_in)
    p_cw = float(e.get("price_cache_write_per_mtok") if e.get("price_cache_write_per_mtok") is not None else p_in)
    uncached = max(tokens_in - tokens_cached - tokens_cache_write, 0)
    return (uncached * p_in + tokens_cached * p_cr + tokens_cache_write * p_cw + tokens_out * p_out) / 1e6


# ------------------------------------------------------------------ ledger and budget
class Ledger:
    """Append-only CSV with a running total, both under an exclusive file lock (safe across processes)."""

    def __init__(self, path=LEDGER, max_usd=None):
        self.path = Path(path)
        self.total_path = self.path.with_suffix(".total.json")
        self.max_usd = float(os.environ.get("PAPERV_MAX_USD", "nan")) if max_usd is None else float(max_usd)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _locked(self):
        fh = open(self.path.with_suffix(".lock"), "a+")
        fcntl.flock(fh, fcntl.LOCK_EX)
        return fh

    def total(self):
        try:
            return float(json.loads(self.total_path.read_text())["usd"])
        except (OSError, ValueError, KeyError):
            return 0.0

    def check(self, projected):
        if not (self.max_usd == self.max_usd):            # NaN: no cap configured
            raise BudgetExceeded("PAPERV_MAX_USD is not set: refusing to make paid calls without a spend cap")
        if self.total() + projected > self.max_usd:
            raise BudgetExceeded(f"ledger ${self.total():.2f} + projected ${projected:.4f} > cap ${self.max_usd:.2f}")

    def append(self, row):
        lk = self._locked()
        try:
            new = not self.path.exists()
            with open(self.path, "a", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=LEDGER_FIELDS)
                if new:
                    w.writeheader()
                w.writerow({k: row.get(k, "") for k in LEDGER_FIELDS})
            tot = self.total() + float(row.get("usd") or 0.0)
            tmp = self.total_path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"usd": tot, "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
            os.replace(tmp, self.total_path)
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN); lk.close()


# ------------------------------------------------------------------ cache
def cache_key(**parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Cache:
    def __init__(self, directory):
        self.dir = Path(directory)

    def get(self, key):
        p = self.dir / key[:2] / f"{key}.json"
        return json.loads(p.read_text()) if p.exists() else None

    def put(self, key, value):
        d = self.dir / key[:2]
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f".{key}.{os.getpid()}.tmp"
        tmp.write_text(json.dumps(value, sort_keys=True))
        os.replace(tmp, d / f"{key}.json")


# ------------------------------------------------------------------ result
@dataclass
class Completion:
    text: str | None                 # the JSON text the model returned (None on refusal)
    refusal: bool = False
    stop_reason: str = ""
    tokens_in: int = 0               # all prompt tokens, cached or not
    tokens_in_cached: int = 0
    tokens_cache_write: int = 0
    tokens_out: int = 0              # includes thinking tokens where the provider bills them as output
    model_returned: str = ""
    fingerprint: str = ""
    http_status: int = 200
    raw: dict = field(default_factory=dict)


# ------------------------------------------------------------------ providers
def _key(provider, required=True):
    k = os.environ.get(KEY_ENV[provider], "")
    if required and not k:
        raise LLMUnavailable(f"{KEY_ENV[provider]} is not set (keys are read from the environment only)")
    return k


class _Retryable(Exception):
    def __init__(self, status, retry_after=None, msg=""):
        super().__init__(msg); self.status, self.retry_after = status, retry_after


def _retry_after(headers):
    try:
        v = headers.get("retry-after")
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, entry, http_client=None, base_url=None):
        import anthropic
        self.anthropic = anthropic
        self.e = entry
        kw = dict(api_key=_key("anthropic"), max_retries=0, timeout=TIMEOUT_S)
        if http_client is not None:
            kw["http_client"] = http_client
        if base_url:
            kw["base_url"] = base_url
        self.client = anthropic.Anthropic(**kw)

    def request(self, system, prompt, schema, temperature=None, seed=None, max_tokens=None):
        oc = {"format": {"type": "json_schema", "schema": schema}}
        if self.e.get("effort"):
            oc["effort"] = self.e["effort"]
        kw = dict(model=self.e["model_id"], max_tokens=int(max_tokens or self.e.get("max_output_tokens", 16000)),
                  system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                  messages=[{"role": "user", "content": prompt}], output_config=oc)
        if temperature is not None and self.e.get("supports_temperature"):
            kw["temperature"] = temperature
        a = self.anthropic
        try:
            r = self.client.messages.create(**kw)
        except (a.RateLimitError, a.InternalServerError) as ex:
            raise _Retryable(ex.status_code, _retry_after(ex.response.headers), redact(ex))
        except a.APIStatusError as ex:
            if ex.status_code in RETRYABLE:
                raise _Retryable(ex.status_code, _retry_after(ex.response.headers), redact(ex))
            raise LLMUnavailable(f"anthropic HTTP {ex.status_code}: {redact(ex)}")
        except (a.APITimeoutError, a.APIConnectionError) as ex:
            raise _Retryable(0, None, redact(ex))
        u = r.usage
        cr = int(getattr(u, "cache_read_input_tokens", 0) or 0)
        cw = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
        text = next((b.text for b in r.content if getattr(b, "type", "") == "text"), None)
        refusal = r.stop_reason == "refusal"
        if not refusal and not text:
            raise _Retryable(0, None, f"empty completion (stop_reason={r.stop_reason})")
        return Completion(text=None if refusal else text, refusal=refusal, stop_reason=str(r.stop_reason),
                          tokens_in=int(u.input_tokens) + cr + cw, tokens_in_cached=cr, tokens_cache_write=cw,
                          tokens_out=int(u.output_tokens), model_returned=str(r.model),
                          raw={"id": r.id, "stop_details": str(getattr(r, "stop_details", None))})


class _HttpProvider:
    """Shared httpx plumbing for the non-Anthropic providers (injectable transport for tests)."""

    def __init__(self, entry, transport=None):
        import httpx
        self.httpx = httpx
        self.e = entry
        self.http = httpx.Client(timeout=TIMEOUT_S, transport=transport)

    def _post(self, url, headers, body):
        h = self.httpx
        try:
            resp = self.http.post(url, headers=headers, json=body)
        except (h.TimeoutException, h.TransportError) as ex:
            raise _Retryable(0, None, redact(ex))
        if resp.status_code in RETRYABLE:
            raise _Retryable(resp.status_code, _retry_after(resp.headers), redact(resp.text[:300]))
        if resp.status_code >= 400:
            raise LLMUnavailable(f"{self.name} HTTP {resp.status_code}: {redact(resp.text[:300])}")
        try:
            return resp.json()
        except ValueError:
            raise _Retryable(resp.status_code, None, "non-JSON body")


class OpenAIProvider(_HttpProvider):
    name = "openai"
    base = "https://api.openai.com/v1"
    key_required = True
    response_format = "json_schema"

    def _base(self):
        return self.base

    def request(self, system, prompt, schema, temperature=None, seed=None, max_tokens=None):
        headers = {"Content-Type": "application/json"}
        k = _key(self.name, self.key_required)
        if k:
            headers["Authorization"] = f"Bearer {k}"
        body = {"model": self.e["model_id"],
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "max_completion_tokens": int(max_tokens or self.e.get("max_output_tokens", 16000))}
        if self.response_format == "json_schema":
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "fleet_actions", "strict": True, "schema": schema}}
        else:
            body["response_format"] = {"type": "json_object"}
        if temperature is not None and self.e.get("supports_temperature"):
            body["temperature"] = temperature
        if seed is not None and self.e.get("supports_seed"):
            body["seed"] = int(seed)
        j = self._post(f"{self._base()}/chat/completions", headers, body)
        ch = (j.get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        u = j.get("usage") or {}
        cached = int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or u.get("prompt_cache_hit_tokens") or 0)
        refusal = bool(msg.get("refusal")) or ch.get("finish_reason") == "content_filter"
        text = msg.get("content")
        if not refusal and not text:
            raise _Retryable(200, None, f"empty completion (finish_reason={ch.get('finish_reason')})")
        return Completion(text=None if refusal else text, refusal=refusal, stop_reason=str(ch.get("finish_reason")),
                          tokens_in=int(u.get("prompt_tokens") or 0), tokens_in_cached=cached,
                          tokens_out=int(u.get("completion_tokens") or 0), model_returned=str(j.get("model", "")),
                          fingerprint=str(j.get("system_fingerprint") or ""))


class DeepSeekProvider(OpenAIProvider):
    name = "deepseek"
    base = "https://api.deepseek.com"
    response_format = "json_object"


class OpenAICompatProvider(OpenAIProvider):
    name = "openai_compat"
    key_required = False

    def _base(self):
        b = os.environ.get("PAPERV_OPENAI_COMPAT_BASE_URL", "")
        if not b:
            raise LLMUnavailable("PAPERV_OPENAI_COMPAT_BASE_URL is not set")
        return b.rstrip("/")


def to_gemini_schema(s):
    """JSON schema -> Gemini responseSchema (OpenAPI subset: upper-case types, no additionalProperties)."""
    if not isinstance(s, dict):
        return s
    out = {}
    for k, v in s.items():
        if k == "type":
            out["type"] = v.upper()
        elif k == "properties":
            out["properties"] = {pk: to_gemini_schema(pv) for pk, pv in v.items()}
        elif k == "items":
            out["items"] = to_gemini_schema(v)
        elif k in ("required", "enum", "description"):
            out[k] = v
    return out


class GeminiProvider(_HttpProvider):
    name = "gemini"
    base = "https://generativelanguage.googleapis.com/v1beta"

    def request(self, system, prompt, schema, temperature=None, seed=None, max_tokens=None):
        headers = {"Content-Type": "application/json", "x-goog-api-key": _key("gemini")}   # never in the URL
        gc = {"responseMimeType": "application/json", "responseSchema": to_gemini_schema(schema),
              "maxOutputTokens": int(max_tokens or self.e.get("max_output_tokens", 16000))}
        if temperature is not None and self.e.get("supports_temperature"):
            gc["temperature"] = temperature
        if seed is not None and self.e.get("supports_seed"):
            gc["seed"] = int(seed)
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gc}
        j = self._post(f"{self.base}/models/{self.e['model_id']}:generateContent", headers, body)
        cand = (j.get("candidates") or [{}])[0]
        u = j.get("usageMetadata") or {}
        fr = str(cand.get("finishReason", ""))
        refusal = fr in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII") or bool(j.get("promptFeedback", {}).get("blockReason"))
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought")) or None
        if not refusal and not text:
            raise _Retryable(200, None, f"empty completion (finishReason={fr})")
        return Completion(text=None if refusal else text, refusal=refusal, stop_reason=fr,
                          tokens_in=int(u.get("promptTokenCount") or 0),
                          tokens_in_cached=int(u.get("cachedContentTokenCount") or 0),
                          tokens_out=int(u.get("candidatesTokenCount") or 0) + int(u.get("thoughtsTokenCount") or 0),
                          model_returned=str(j.get("modelVersion", "")))


PROVIDERS = {"anthropic": AnthropicProvider, "openai": OpenAIProvider, "gemini": GeminiProvider,
             "deepseek": DeepSeekProvider, "openai_compat": OpenAICompatProvider}


# ------------------------------------------------------------------ the harness
class Harness:
    """One role (planner_frontier_1, attacker, judge, ...) bound to its pinned model."""

    def __init__(self, role, *, lock=None, ledger=None, cache_dir=None, cache_only=False, provider=None,
                 sleep=time.sleep, rng=None, context=None):
        self.role = role
        self.e = role_entry(role, lock)
        self.ledger = ledger or Ledger()
        self.cache = Cache(cache_dir or CACHE_BENIGN)
        self.cache_only = cache_only
        self._provider = provider                  # injected in tests; built lazily otherwise
        self.sleep = sleep
        self.rng = rng or random.Random(16000)
        self.context = dict(context or {})         # campaign_id, cell_id, mission_seed for the ledger
        self.totals = dict(calls=0, cache_hits=0, tokens_in=0, tokens_in_cached=0, tokens_out=0, usd=0.0)

    @property
    def provider(self):
        if self._provider is None:
            self._provider = PROVIDERS[self.e["provider"]](self.e)
        return self._provider

    def projected_cost(self, system, prompt):
        est_in = (len(system) + len(prompt)) / 3.5
        est_out = float(self.e.get("expected_output_tokens", 2000))
        return call_cost(self.e, int(est_in), 0, 0, int(est_out))

    def complete(self, system, prompt, schema, *, prompt_version, schema_version, temperature=0.0, seed=None,
                 repeat_idx=0, epoch=0):
        temp = temperature if self.e.get("supports_temperature") else None
        sd = seed if self.e.get("supports_seed") else None
        key = cache_key(provider=self.e["provider"], model_id=self.e["model_id"], prompt_version=prompt_version,
                        system=system, prompt=prompt, schema_version=schema_version, temperature=temp, seed=sd,
                        repeat_idx=repeat_idx, effort=self.e.get("effort"))
        row = dict(ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), role=self.role, provider=self.e["provider"],
                   model_id=self.e["model_id"], prompt_sha=key[:16], epoch=epoch, **self.context)
        hit = self.cache.get(key)
        if hit is not None:
            c = Completion(**{k: v for k, v in hit.items() if k in Completion.__dataclass_fields__})
            self.totals["calls"] += 1; self.totals["cache_hits"] += 1
            self.ledger.append(dict(row, cache_hit=1, tokens_in=c.tokens_in, tokens_in_cached=c.tokens_in_cached,
                                    tokens_cache_write=c.tokens_cache_write, tokens_out=c.tokens_out, latency_s=0.0,
                                    usd=0.0, http_status=c.http_status, attempt=0, stop_reason=c.stop_reason))
            return c
        if self.cache_only:
            raise CacheMiss(f"cache-only replay: no completion for {key[:16]} (role {self.role})")
        self.ledger.check(self.projected_cost(system, prompt))
        last = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            t0 = time.perf_counter()
            try:
                c = self.provider.request(system, prompt, schema, temperature=temp, seed=sd)
            except _Retryable as ex:
                last = ex
                if attempt == MAX_ATTEMPTS:
                    break
                back = min(60.0, 2.0 ** (attempt - 1)) + self.rng.uniform(0, 1.0)
                self.sleep(max(back, ex.retry_after or 0.0))
                continue
            lat = time.perf_counter() - t0
            usd = call_cost(self.e, c.tokens_in, c.tokens_in_cached, c.tokens_cache_write, c.tokens_out)
            self.ledger.append(dict(row, cache_hit=0, tokens_in=c.tokens_in, tokens_in_cached=c.tokens_in_cached,
                                    tokens_cache_write=c.tokens_cache_write, tokens_out=c.tokens_out,
                                    latency_s=round(lat, 3), usd=round(usd, 6), http_status=c.http_status,
                                    attempt=attempt, stop_reason=c.stop_reason))
            self.cache.put(key, {k: getattr(c, k) for k in Completion.__dataclass_fields__})
            for k in ("tokens_in", "tokens_in_cached", "tokens_out"):
                self.totals[k] += getattr(c, k)
            self.totals["calls"] += 1; self.totals["usd"] += usd
            return c
        raise LLMUnavailable(f"{self.e['provider']}/{self.e['model_id']}: {MAX_ATTEMPTS} attempts failed "
                             f"(last: HTTP {getattr(last, 'status', '?')}: {redact(last)})")
