"""Health check endpoints."""

import time

from fastapi import APIRouter
from pydantic import BaseModel

health_router = APIRouter()

_start_time = time.time()


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    database: str
    redis: str


@health_router.get("/health")
async def liveness() -> dict[str, str]:
    """Liveness probe - is the service running."""
    return {"status": "ok"}


@health_router.get("/ready", response_model=HealthResponse)
async def readiness() -> HealthResponse:
    """Readiness probe - are dependencies available."""
    db_status = "unknown"
    redis_status = "unknown"

    # Check database
    try:
        from sqlalchemy import text

        from callscreen.db.session import engine

        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unavailable"

    # Check Redis
    try:
        import redis.asyncio as aioredis

        from callscreen.config import get_settings

        settings = get_settings()
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        redis_status = "ok"
    except Exception:
        redis_status = "unavailable"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        version="0.1.0",
        uptime_seconds=round(time.time() - _start_time, 2),
        database=db_status,
        redis=redis_status,
    )
