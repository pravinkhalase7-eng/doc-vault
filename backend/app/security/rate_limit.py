from collections.abc import Callable
from time import time

from fastapi import Request
from fastapi.responses import JSONResponse

from app.exceptions import error_payload

_buckets: dict[str, list[float]] = {}

LIMITS = {
    "/api/v1/auth/login": (5, 60),
    "/api/v1/auth/guest": (10, 60),
    "/api/v1/auth/register": (10, 60),
    "/api/v1/auth/google": (10, 60),
    "/api/v1/auth/forgot-password": (5, 60),
    "/api/v1/documents/upload": (30, 60),
    "/api/v1/documents/export": (3, 300),
    "/api/v1/ingest/email": (30, 300),
    "/api/v1/ai/chat": (20, 60),
}


def rate_limit_middleware(app):
    @app.middleware("http")
    async def _limit(request: Request, call_next: Callable):
        path = request.url.path
        for prefix, (max_hits, window) in LIMITS.items():
            if path.startswith(prefix):
                ip = request.client.host if request.client else "unknown"
                key = f"{prefix}:{ip}"
                now = time()
                hits = [t for t in _buckets.get(key, []) if now - t < window]
                if len(hits) >= max_hits:
                    return JSONResponse(status_code=429, content=error_payload("RATE_LIMITED", "Too many requests"))
                hits.append(now)
                _buckets[key] = hits
                break
        return await call_next(request)

    return app
