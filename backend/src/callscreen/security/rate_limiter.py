"""Redis-backed sliding window rate limiter."""

import time

from fastapi import HTTPException, Request, status

from callscreen.config import get_settings


def rate_limit(key_prefix: str = "api"):
    """Create a rate limiting dependency.

    Uses a sliding window counter stored in Redis.
    """

    async def _limiter(request: Request):
        settings = get_settings()

        if key_prefix == "login":
            max_requests = settings.rate_limit_login
        else:
            max_requests = settings.rate_limit_api

        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"
        window_key = f"ratelimit:{key_prefix}:{client_ip}"

        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(settings.redis_url)
            now = time.time()
            window_start = now - 60  # 1-minute window

            pipe = r.pipeline()
            # Remove expired entries
            pipe.zremrangebyscore(window_key, 0, window_start)
            # Add current request
            pipe.zadd(window_key, {str(now): now})
            # Count requests in window
            pipe.zcard(window_key)
            # Set key expiry
            pipe.expire(window_key, 120)
            results = await pipe.execute()
            await r.aclose()

            request_count = results[2]
            if request_count > max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": "60"},
                )
        except HTTPException:
            raise
        except Exception:
            # If Redis is down, allow the request (fail open for availability)
            pass

    return _limiter
