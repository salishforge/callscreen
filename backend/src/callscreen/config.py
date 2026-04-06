"""Application configuration using Pydantic Settings."""

from enum import Enum
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    callscreen_env: Environment = Environment.DEVELOPMENT
    callscreen_secret_key: str = "change-me-in-production"
    callscreen_encryption_key: str = "change-me-to-base64-32-byte-key"
    callscreen_allowed_origins: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://callscreen:callscreen@localhost:5432/callscreen"
    redis_url: str = "redis://localhost:6379/0"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_webhook_base_url: str = ""

    # AI Providers
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    litellm_default_model: str = "anthropic/claude-sonnet-4-20250514"

    # STT / TTS
    deepgram_api_key: str = ""
    elevenlabs_api_key: str = ""

    # Object Storage
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_recordings: str = "callscreen-recordings"

    # Email
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "noreply@callscreen.local"

    # Messaging
    telegram_bot_token: str = ""
    discord_bot_token: str = ""

    # Auth
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Rate Limiting
    rate_limit_login: int = 5  # per minute
    rate_limit_api: int = 100  # per minute

    @property
    def is_production(self) -> bool:
        return self.callscreen_env == Environment.PRODUCTION

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.callscreen_allowed_origins.split(",")]

    @field_validator("callscreen_secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v == "change-me-in-production":
            import warnings

            warnings.warn(
                "Using default secret key. Set CALLSCREEN_SECRET_KEY in production.",
                stacklevel=2,
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
