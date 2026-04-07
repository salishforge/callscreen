"""Call state machine for managing call lifecycle."""

import json
import logging
from datetime import datetime, timezone
from functools import partial
from typing import Any, ClassVar

import redis.asyncio as redis
from pydantic import BaseModel, Field

from callscreen.config import get_settings
from callscreen.models.call import CallStatus

logger = logging.getLogger(__name__)


class CallStateMetadata(BaseModel):
    """Metadata stored alongside call state."""
    from_number: str
    to_number: str
    user_id: str | None = None
    trust_score: float | None = None
    stir_attestation: str | None = None
    caller_name: str | None = None
    caller_intent: str | None = None
    screening_details: dict[str, Any] | None = None
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CallStateMachine:
    """State machine for call lifecycle management."""

    ALLOWED_TRANSITIONS: ClassVar[dict[CallStatus, set[CallStatus]]] = {
        CallStatus.INCOMING: {CallStatus.TRIAGE, CallStatus.FAILED},
        CallStatus.TRIAGE: {
            CallStatus.NUMBER_LOOKUP,
            CallStatus.FORWARDING,  # whitelist fast-path
            CallStatus.BLOCKING,    # blocklist fast-path
            CallStatus.FAILED,
        },
        CallStatus.NUMBER_LOOKUP: {CallStatus.SCREENING, CallStatus.FAILED},
        CallStatus.SCREENING: {CallStatus.INTERVIEWING, CallStatus.DECIDING, CallStatus.FAILED},
        CallStatus.INTERVIEWING: {CallStatus.DECIDING, CallStatus.FAILED},
        CallStatus.DECIDING: {
            CallStatus.FORWARDING,
            CallStatus.MESSAGING,
            CallStatus.BLOCKING,
            CallStatus.ENGAGING,
            CallStatus.FAILED,
        },
        CallStatus.FORWARDING: {CallStatus.COMPLETED, CallStatus.FAILED},
        CallStatus.MESSAGING: {CallStatus.COMPLETED, CallStatus.FAILED},
        CallStatus.BLOCKING: {CallStatus.COMPLETED, CallStatus.FAILED},
        CallStatus.ENGAGING: {CallStatus.COMPLETED, CallStatus.FAILED},
        CallStatus.FAILED: set(),
        CallStatus.COMPLETED: set(),
    }

    TIMEOUT: ClassVar[dict[CallStatus, int]] = {
        CallStatus.INCOMING: 5,
        CallStatus.TRIAGE: 10,
        CallStatus.NUMBER_LOOKUP: 15,
        CallStatus.SCREENING: 30,
        CallStatus.INTERVIEWING: 120,
        CallStatus.DECIDING: 30,
        CallStatus.FORWARDING: 60,
        CallStatus.MESSAGING: 60,
        CallStatus.BLOCKING: 10,
        CallStatus.ENGAGING: 60,
        CallStatus.COMPLETED: 0,
        CallStatus.FAILED: 0,
    }

    _redis: redis.Redis | None = None
    _ttl: int = 3600

    @classmethod
    async def _get_redis(cls) -> redis.Redis:
        """Get Redis connection."""
        if cls._redis is None:
            settings = get_settings()
            cls._redis = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                encoding="utf-8",
            )
        return cls._redis

    @classmethod
    def _get_key(cls, call_sid: str) -> str:
        """Get Redis key for call state."""
        return f"call_state:{call_sid}"

    @classmethod
    async def create(
        cls,
        call_sid: str,
        from_number: str,
        to_number: str,
        user_id: str | None = None,
    ) -> None:
        """Initialize call state in Redis."""
        redis_client = await cls._get_redis()
        key = cls._get_key(call_sid)

        metadata = CallStateMetadata(
            from_number=from_number,
            to_number=to_number,
            user_id=user_id,
        )

        await redis_client.hset(
            key,
            mapping={
                "state": CallStatus.INCOMING.value,
                "metadata": metadata.model_dump_json(),
            },
        )
        await redis_client.expire(key, cls._ttl)

        logger.info(
            f"Created call state for {call_sid}",
            extra={"call_sid": call_sid, "state": CallStatus.INCOMING},
        )

    @classmethod
    async def get_state(cls, call_sid: str) -> CallStatus | None:
        """Get current call state."""
        redis_client = await cls._get_redis()
        key = cls._get_key(call_sid)

        state_value = await redis_client.hget(key, "state")
        if not state_value:
            return None

        return CallStatus(state_value)

    @classmethod
    async def transition(cls, call_sid: str, new_state: CallStatus) -> CallStatus:
        """Transition call to new state."""
        current_state = await cls.get_state(call_sid)
        if current_state is None:
            raise ValueError(f"No state found for call {call_sid}")

        allowed = cls.ALLOWED_TRANSITIONS.get(current_state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition from {current_state} to {new_state}. "
                f"Allowed: {allowed}"
            )

        redis_client = await cls._get_redis()
        key = cls._get_key(call_sid)

        metadata_json = await redis_client.hget(key, "metadata")
        if metadata_json:
            metadata = CallStateMetadata.model_validate_json(metadata_json)
            metadata.last_updated = datetime.now(timezone.utc)
        else:
            metadata = CallStateMetadata(
                from_number="",
                to_number="",
                last_updated=datetime.now(timezone.utc),
            )

        await redis_client.hset(
            key,
            mapping={
                "state": new_state.value,
                "metadata": metadata.model_dump_json(),
            },
        )
        await redis_client.expire(key, cls._ttl)

        logger.info(
            f"Transitioned call {call_sid} from {current_state} to {new_state}",
            extra={
                "call_sid": call_sid,
                "from_state": current_state,
                "to_state": new_state,
            },
        )

        return new_state

    @classmethod
    async def get_metadata(cls, call_sid: str) -> CallStateMetadata | None:
        """Get call metadata."""
        redis_client = await cls._get_redis()
        key = cls._get_key(call_sid)

        metadata_json = await redis_client.hget(key, "metadata")
        if not metadata_json:
            return None

        return CallStateMetadata.model_validate_json(metadata_json)

    @classmethod
    async def set_metadata(
        cls,
        call_sid: str,
        key: str,
        value: Any,
    ) -> None:
        """Set a metadata field."""
        metadata = await cls.get_metadata(call_sid)
        if metadata is None:
            raise ValueError(f"No metadata found for call {call_sid}")

        if not hasattr(metadata, key):
            raise ValueError(f"Invalid metadata key: {key}")

        setattr(metadata, key, value)
        metadata.last_updated = datetime.now(timezone.utc)

        redis_client = await cls._get_redis()
        redis_key = cls._get_key(call_sid)

        await redis_client.hset(
            redis_key,
            "metadata",
            metadata.model_dump_json(),
        )
        await redis_client.expire(redis_key, cls._ttl)

    @classmethod
    async def is_expired(cls, call_sid: str) -> bool:
        """Check if call has exceeded timeout for current state."""
        state = await cls.get_state(call_sid)
        if state is None:
            return True

        metadata = await cls.get_metadata(call_sid)
        if metadata is None:
            return True

        timeout_seconds = cls.TIMEOUT.get(state, 0)
        if timeout_seconds <= 0:
            return False

        elapsed = (datetime.now(timezone.utc) - metadata.last_updated).total_seconds()
        return elapsed > timeout_seconds
