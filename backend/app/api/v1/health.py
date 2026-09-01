from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.storage.local import storage_root

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
async def health():
    return {"success": True, "data": {"status": "ok", "app": settings.app_name, "env": settings.app_env}}


@router.get("/health/db")
async def health_db():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"success": True, "data": {"status": "ok"}}


@router.get("/health/redis")
async def health_redis():
    import redis.asyncio as redis

    client = redis.from_url(settings.redis_url)
    pong = await client.ping()
    await client.aclose()
    return {"success": True, "data": {"status": "ok" if pong else "down"}}


@router.get("/health/storage")
async def health_storage():
    root = storage_root()
    writable = root.exists() and os_writable(root)
    return {"success": True, "data": {"status": "ok" if writable else "down", "root_configured": True}}


@router.get("/health/ai")
async def health_ai():
    return {
        "success": True,
        "data": {
            "gemini_configured": settings.gemini_configured,
            "model": settings.gemini_model if settings.gemini_configured else None,
            "local_fallback": True,
        },
    }


def os_writable(path) -> bool:
    try:
        probe = path / ".write-test"
        probe.write_text("ok")
        probe.unlink()
        return True
    except Exception:
        return False
