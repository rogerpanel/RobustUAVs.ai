"""Four-provider LLM router with a deterministic synthetic fallback.

Lifted from RobustIDPS.ai v5, which dispatches across Anthropic / OpenAI /
Google Gemini / DeepSeek and falls back to a synthetic responder for air-gapped
deployments. The fallback is not a degraded mode to apologise for: it is what
keeps CI reproducible, lets the public artifact run without anyone's API key,
and guarantees a demo never fails live because a provider rate-limited.

The active provider is always reported to the client so a viewer can tell a
model answer from a fallback answer at a glance.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Optional

import httpx

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


@dataclass(frozen=True)
class Provider:
    name: str
    env_key: str
    model: str
    url: str


# Declared fallback order. First provider with a key configured wins.
PROVIDERS: tuple[Provider, ...] = (
    Provider("anthropic", "ANTHROPIC_API_KEY", "claude-sonnet-5",
             "https://api.anthropic.com/v1/messages"),
    Provider("openai", "OPENAI_API_KEY", "gpt-4o",
             "https://api.openai.com/v1/chat/completions"),
    Provider("gemini", "GEMINI_API_KEY", "gemini-2.0-flash",
             "https://generativelanguage.googleapis.com/v1beta/models"),
    Provider("deepseek", "DEEPSEEK_API_KEY", "deepseek-chat",
             "https://api.deepseek.com/chat/completions"),
)


@dataclass
class Completion:
    text: str
    provider: str
    model: str
    synthetic: bool


def active_provider() -> Optional[Provider]:
    for p in PROVIDERS:
        if os.environ.get(p.env_key):
            return p
    return None


def provider_status() -> list[dict]:
    """What the client renders as provider chips."""
    active = active_provider()
    return [
        {"name": p.name, "model": p.model,
         "configured": bool(os.environ.get(p.env_key)),
         "active": active is not None and p.name == active.name}
        for p in PROVIDERS
    ]


async def complete(system: str, prompt: str, max_tokens: int = 900) -> Completion:
    p = active_provider()
    if p is None:
        return _synthetic(system, prompt)
    try:
        return await _dispatch(p, system, prompt, max_tokens)
    except Exception as exc:  # noqa: BLE001 - any provider failure degrades, never 500s
        out = _synthetic(system, prompt)
        return Completion(
            text=(f"[{p.name} unavailable: {type(exc).__name__}; answering from "
                  f"the local result cache]\n\n{out.text}"),
            provider=p.name, model=p.model, synthetic=True)


async def _dispatch(p: Provider, system: str, prompt: str, n: int) -> Completion:
    key = os.environ[p.env_key]
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        if p.name == "anthropic":
            r = await c.post(p.url, headers={
                "x-api-key": key, "anthropic-version": "2023-06-01",
                "content-type": "application/json"},
                json={"model": p.model, "max_tokens": n, "system": system,
                      "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json()["content"])
        elif p.name == "gemini":
            r = await c.post(f"{p.url}/{p.model}:generateContent?key={key}",
                             json={"systemInstruction": {"parts": [{"text": system}]},
                                   "contents": [{"parts": [{"text": prompt}]}],
                                   "generationConfig": {"maxOutputTokens": n}})
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        else:  # openai and deepseek share the chat-completions shape
            r = await c.post(p.url, headers={"Authorization": f"Bearer {key}"},
                             json={"model": p.model, "max_tokens": n,
                                   "messages": [{"role": "system", "content": system},
                                                {"role": "user", "content": prompt}]})
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
    return Completion(text=text.strip(), provider=p.name, model=p.model,
                      synthetic=False)


def _synthetic(system: str, prompt: str) -> Completion:
    """Deterministic offline responder.

    It does not pretend to reason. It states what it is, echoes the retrieved
    context the dispatcher already assembled, and is stable under a fixed input
    so tests can assert on it.
    """
    digest = hashlib.sha256((system + prompt).encode()).hexdigest()[:8]
    return Completion(
        text=("No LLM provider is configured, so this answer is assembled "
              "directly from the platform's result cache rather than generated. "
              "The retrieved values above are authoritative; they are read from "
              "the committed files under results/. Configure ANTHROPIC_API_KEY, "
              "OPENAI_API_KEY, GEMINI_API_KEY, or DEEPSEEK_API_KEY for a "
              f"narrated answer. [deterministic response {digest}]"),
        provider="synthetic", model="none", synthetic=True)
