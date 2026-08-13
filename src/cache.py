"""Redis-backed cache for expensive pipeline stages.

Model training and scenario stress runs are the slow steps; caching them
by content hash means a re-run with an unchanged pool skips retraining.
Falls back to an in-process dict when Redis is unavailable so the
pipeline runs anywhere.
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle

_MEMORY: dict[str, bytes] = {}


def _client():
    if os.environ.get("DISABLE_REDIS"):
        return None
    try:
        import redis
        c = redis.Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
            socket_connect_timeout=0.5,
        )
        c.ping()
        return c
    except Exception:
        return None


def make_key(prefix: str, payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    return f"spai:{prefix}:{hashlib.sha256(blob).hexdigest()[:16]}"


def get(key: str):
    c = _client()
    raw = c.get(key) if c else _MEMORY.get(key)
    return pickle.loads(raw) if raw else None


def set(key: str, value, ttl: int = 3600) -> None:
    raw = pickle.dumps(value)
    c = _client()
    if c:
        c.setex(key, ttl, raw)
    else:
        _MEMORY[key] = raw


def backend_name() -> str:
    return "redis" if _client() else "in-memory"
