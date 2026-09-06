"""Sliding-window rate limits backed by Redis, with in-memory fallback."""

from __future__ import annotations

from collections.abc import Callable
from time import time
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from app.exceptions import error_payload

_buckets: dict[str, list[float]] = {}
_redis_client = None
_redis_failed_until = 0.0

LIMITS = {
    "/api/v1/auth/login": (5, 60),
    "/api/v1/auth/guest": (10, 60),
    "/api/v1/auth/register": (10, 60),
    "/api/v1/auth/google": (10, 60),
    "/api/v1/auth/forgot-password": (5, 60),
    "/api/v1/documents/upload": (30, 60),
    "/api/v1/documents/export": (3, 300),
    "/api/v1/ingest/email": (30, 300),
    "/api/v1/ingest/poll": (6, 60),
    "/api/v1/ai/chat": (20, 60),
}


def _memory_allow(key: str, max_hits: int, window: float) -> bool:
    now = time()
    hits = [t for t in _buckets.get(key, []) if now - t < window]
    if len(hits) >= max_hits:
        _buckets[key] = hits
        return False
    hits.append(now)
    _buckets[key] = hits
    return True


async def _redis_allow(key: str, max_hits: int, window: float) -> bool | None:
    """Return True/False if Redis answered; None if Redis is unavailable."""
    global _redis_client, _redis_failed_until
    now = time()
    if now < _redis_failed_until:
        return None
    try:
        import redis.asyncio as redis

        from app.config import get_settings

        if _redis_client is None:
            _redis_client = redis.from_url(get_settings().redis_url, decode_responses=True)
        rkey = f"rl:{key}"
        member = f"{now}:{uuid4().hex}"
        pipe = _redis_client.pipeline()
        pipe.zremrangebyscore(rkey, 0, now - window)
        pipe.zcard(rkey)
        pipe.zadd(rkey, {member: now})
        pipe.expire(rkey, int(window) + 2)
        results = await pipe.execute()
        count_before = int(results[1] or 0)
        return count_before < max_hits
    except Exception:
        _redis_failed_until = now + 5
        try:
            if _redis_client is not None:
                await _redis_client.aclose()
        except Exception:
            pass
        _redis_client = None
        return None


async def _allow(key: str, max_hits: int, window: float) -> bool:
    redis_result = await _redis_allow(key, max_hits, window)
    if redis_result is not None:
        return redis_result
    return _memory_allow(key, max_hits, window)


def rate_limit_middleware(app):
    @app.middleware("http")
    async def _limit(request: Request, call_next: Callable):
        path = request.url.path
        for prefix, (max_hits, window) in LIMITS.items():
            if path.startswith(prefix):
                ip = request.client.host if request.client else "unknown"
                key = f"{prefix}:{ip}"
                if not await _allow(key, max_hits, window):
                    return JSONResponse(
                        status_code=429,
                        content=error_payload("RATE_LIMITED", "Too many requests"),
                    )
                break
        return await call_next(request)

    return app
