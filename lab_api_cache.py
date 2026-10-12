"""Short-lived in-memory cache for dashboard GET payloads.

Keeps tab switches from re-hitting the APIs. Pass refresh=1 (or force=True) to bypass.
"""

from __future__ import annotations

import time

_STORE: dict[str, tuple[float, object]] = {}
DEFAULT_TTL_SEC = 300


def cached(key: str, loader, *, force: bool = False, ttl: int = DEFAULT_TTL_SEC):
    now = time.monotonic()
    if not force and key in _STORE:
        stored_at, value = _STORE[key]
        if now - stored_at < ttl:
            return value
    value = loader()
    _STORE[key] = (now, value)
    return value


def invalidate(*keys: str) -> None:
    for key in keys:
        _STORE.pop(key, None)


def invalidate_prefix(prefix: str) -> None:
    for key in [existing for existing in _STORE if existing.startswith(prefix)]:
        _STORE.pop(key, None)
