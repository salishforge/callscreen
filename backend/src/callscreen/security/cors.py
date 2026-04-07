"""CORS configuration for production safety."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from callscreen.config import get_settings


def configure_cors(app: FastAPI) -> None:
    """Configure CORS middleware with production-safe defaults."""
    settings = get_settings()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-CSRF-Token",
        ],
        expose_headers=["X-Request-ID"],
        max_age=600,  # Cache preflight for 10 minutes
    )
