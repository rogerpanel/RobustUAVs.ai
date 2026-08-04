"""Redis cache with a graceful in-memory fallback.

Lifted from `backend/redis_cache.py` in RobustIDPS.ai, including the property
that matters most here: **if Redis is unavailable the process does not fail, it
degrades**. A conference demo must not die because a container did not come up,
and a reviewer cloning the artifact must not be required to run Redis at all.

The fallback is a bounded dict with the same TTL semantics, so behaviour is
identical apart from not being shared between processes.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional

log = logging.getLogger("robustuavs.cache")

REDIS_URL = os.getenv("REDIS_URL", "")
DEFAULT_TTL = int(os.getenv("CACHE_DEFAULT_TTL", "300"))
MAX_LOCAL_ENTRIES = 512


class _Local:
    """In-memory fallback. Bounded, so a long-running demo cannot leak."""

    def __init__(self) -> None:
        self._d: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        hit = self._d.get(key)
        if hit is None:
            return None
        expires, value = hit
        if expires and expires < time.time():
            self._d.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        if len(self._d) >= MAX_LOCAL_ENTRIES:
            # Drop the entry closest to expiry rather than an arbitrary one.
            oldest = min(self._d, key=lambda k: self._d[k][0])
            self._d.pop(oldest, None)
        self._d[key] = (time.time() + ttl if ttl else 0, value)

    def delete_prefix(self, prefix: str) -> int:
        doomed = [k for k in self._d if k.startswith(prefix)]
        for k in doomed:
            self._d.pop(k, None)
        return len(doomed)

    def clear(self) -> None:
        self._d.clear()


class Cache:
    def __init__(self) -> None:
        self._local = _Local()
        self._redis = None
        self.backend = "memory"
        if REDIS_URL:
            try:
                import redis  # noqa: PLC0415 - optional dependency

                client = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=2,
                                              decode_responses=True)
                client.ping()
                self._redis, self.backend = client, "redis"
                log.info("cache: redis at %s", REDIS_URL)
            except Exception as exc:  # noqa: BLE001 - any failure means fall back
                log.warning("cache: redis unavailable (%s); using memory", exc)

    def get(self, key: str) -> Optional[Any]:
        if self._redis is not None:
            try:
                raw = self._redis.get(key)
                return json.loads(raw) if raw is not None else None
            except Exception:  # noqa: BLE001
                self._demote()
        return self._local.get(key)

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
        if self._redis is not None:
            try:
                self._redis.setex(key, ttl, json.dumps(value, default=str))
                return
            except Exception:  # noqa: BLE001
                self._demote()
        self._local.set(key, value, ttl)

    def invalidate(self, prefix: str) -> int:
        if self._redis is not None:
            try:
                keys = list(self._redis.scan_iter(match=f"{prefix}*", count=500))
                return self._redis.delete(*keys) if keys else 0
            except Exception:  # noqa: BLE001
                self._demote()
        return self._local.delete_prefix(prefix)

    def _demote(self) -> None:
        """One Redis failure moves the whole process to memory permanently.

        Flapping between backends mid-demo would be worse than committing to
        the degraded one: results would appear and disappear between requests.
        """
        log.warning("cache: redis error; demoting to memory for this process")
        self._redis, self.backend = None, "memory"

    def status(self) -> dict:
        return {"backend": self.backend, "configured": bool(REDIS_URL)}


cache = Cache()
