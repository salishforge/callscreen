"""FastAPI application factory."""

import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from callscreen.config import get_settings

logger = logging.getLogger("callscreen")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    settings = get_settings()
    logger.info("CallScreen starting (env=%s)", settings.callscreen_env.value)

    # Import here to avoid circular imports at module level
    from callscreen.db.session import engine

    # Verify database connectivity
    try:
        async with engine.begin() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception:
        logger.warning("Database not available at startup")

    yield

    # Shutdown
    await engine.dispose()
    logger.info("CallScreen stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="CallScreen",
        description="AI-powered call screening system for landlines",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID
    app.add_middleware(RequestIDMiddleware)

    # Register routers
    from callscreen.api.v1.router import api_router

    app.include_router(api_router, prefix="/api/v1")

    # Health check at root level
    from callscreen.api.v1.health import health_router

    app.include_router(health_router)

    return app
