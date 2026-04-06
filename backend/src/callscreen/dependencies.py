"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.config import Settings, get_settings
from callscreen.db.session import get_db

# Type aliases for dependency injection
DatabaseDep = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_redis() -> AsyncGenerator:
    """Get a Redis connection from the pool."""
    import redis.asyncio as aioredis

    settings = get_settings()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield r
    finally:
        await r.aclose()


RedisDep = Annotated[object, Depends(get_redis)]
