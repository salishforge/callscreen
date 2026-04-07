"""Tests for call state machine."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from callscreen.core.call_state import CallStateMachine, CallStateMetadata
from callscreen.models.call import CallStatus

CALL_SID = "CA1234567890abcdef1234567890abcdef"
FROM_NUMBER = "+15551234567"
TO_NUMBER = "+15559876543"
USER_ID = "user-abc-123"


class FakeRedis:
    """Dict-backed fake that mimics the async Redis hset/hget/expire interface."""

    def __init__(self):
        self.store: dict[str, dict[str, str]] = {}

    async def hset(self, key: str, field: str | None = None, value: str | None = None, mapping: dict | None = None) -> None:
        if key not in self.store:
            self.store[key] = {}
        if mapping:
            self.store[key].update(mapping)
        elif field is not None and value is not None:
            self.store[key][field] = value

    async def hget(self, key: str, field: str) -> str | None:
        return self.store.get(key, {}).get(field)

    async def expire(self, key: str, ttl: int) -> None:
        pass  # TTL behavior is not relevant for unit tests


@pytest.fixture(autouse=True)
def reset_redis_singleton():
    """Reset the class-level Redis singleton before and after each test."""
    CallStateMachine._redis = None
    yield
    CallStateMachine._redis = None


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def mock_get_redis(fake_redis):
    """Patch _get_redis to return our FakeRedis instance."""
    with patch.object(CallStateMachine, "_get_redis", new_callable=AsyncMock, return_value=fake_redis):
        yield fake_redis


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_initializes_state(self, mock_get_redis):
        """create() sets state to INCOMING and stores metadata."""
        await CallStateMachine.create(CALL_SID, FROM_NUMBER, TO_NUMBER, user_id=USER_ID)

        redis = mock_get_redis
        key = CallStateMachine._get_key(CALL_SID)

        assert redis.store[key]["state"] == CallStatus.INCOMING.value

        metadata = CallStateMetadata.model_validate_json(redis.store[key]["metadata"])
        assert metadata.from_number == FROM_NUMBER
        assert metadata.to_number == TO_NUMBER
        assert metadata.user_id == USER_ID


class TestGetState:
    @pytest.mark.asyncio
    async def test_get_state_returns_current(self, mock_get_redis):
        """get_state returns the stored state."""
        await CallStateMachine.create(CALL_SID, FROM_NUMBER, TO_NUMBER)

        state = await CallStateMachine.get_state(CALL_SID)
        assert state == CallStatus.INCOMING

    @pytest.mark.asyncio
    async def test_get_state_returns_none_for_missing(self, mock_get_redis):
        """Returns None for a nonexistent call."""
        state = await CallStateMachine.get_state("CA_nonexistent")
        assert state is None


class TestTransition:
    @pytest.mark.asyncio
    async def test_valid_transition(self, mock_get_redis):
        """Transition from INCOMING to TRIAGE succeeds."""
        await CallStateMachine.create(CALL_SID, FROM_NUMBER, TO_NUMBER)

        result = await CallStateMachine.transition(CALL_SID, CallStatus.TRIAGE)
        assert result == CallStatus.TRIAGE

        state = await CallStateMachine.get_state(CALL_SID)
        assert state == CallStatus.TRIAGE

    @pytest.mark.asyncio
    async def test_invalid_transition_raises(self, mock_get_redis):
        """Transition from INCOMING to COMPLETED raises ValueError."""
        await CallStateMachine.create(CALL_SID, FROM_NUMBER, TO_NUMBER)

        with pytest.raises(ValueError, match="Invalid transition"):
            await CallStateMachine.transition(CALL_SID, CallStatus.COMPLETED)

    @pytest.mark.asyncio
    async def test_transition_missing_call_raises(self, mock_get_redis):
        """Transition on a nonexistent call raises ValueError."""
        with pytest.raises(ValueError, match="No state found"):
            await CallStateMachine.transition("CA_missing", CallStatus.TRIAGE)

    @pytest.mark.asyncio
    async def test_any_state_can_fail(self, mock_get_redis):
        """All non-terminal states can transition to FAILED."""
        terminal = {CallStatus.COMPLETED, CallStatus.FAILED}
        non_terminal = [s for s in CallStatus if s not in terminal]

        for status in non_terminal:
            allowed = CallStateMachine.ALLOWED_TRANSITIONS[status]
            assert CallStatus.FAILED in allowed, (
                f"{status} should allow transition to FAILED"
            )

    @pytest.mark.asyncio
    async def test_terminal_states_cannot_transition(self, mock_get_redis):
        """COMPLETED and FAILED have no valid transitions."""
        assert CallStateMachine.ALLOWED_TRANSITIONS[CallStatus.COMPLETED] == set()
        assert CallStateMachine.ALLOWED_TRANSITIONS[CallStatus.FAILED] == set()


class TestMetadata:
    @pytest.mark.asyncio
    async def test_get_metadata(self, mock_get_redis):
        """Returns CallStateMetadata with correct fields."""
        await CallStateMachine.create(CALL_SID, FROM_NUMBER, TO_NUMBER, user_id=USER_ID)

        metadata = await CallStateMachine.get_metadata(CALL_SID)
        assert metadata is not None
        assert metadata.from_number == FROM_NUMBER
        assert metadata.to_number == TO_NUMBER
        assert metadata.user_id == USER_ID
        assert metadata.trust_score is None

    @pytest.mark.asyncio
    async def test_set_metadata(self, mock_get_redis):
        """Updates a specific metadata field."""
        await CallStateMachine.create(CALL_SID, FROM_NUMBER, TO_NUMBER)

        await CallStateMachine.set_metadata(CALL_SID, "trust_score", 0.95)

        metadata = await CallStateMachine.get_metadata(CALL_SID)
        assert metadata is not None
        assert metadata.trust_score == 0.95

    @pytest.mark.asyncio
    async def test_set_metadata_invalid_key_raises(self, mock_get_redis):
        """Raises ValueError for an unknown metadata key."""
        await CallStateMachine.create(CALL_SID, FROM_NUMBER, TO_NUMBER)

        with pytest.raises(ValueError, match="Invalid metadata key"):
            await CallStateMachine.set_metadata(CALL_SID, "nonexistent_field", "value")


class TestIsExpired:
    @pytest.mark.asyncio
    async def test_is_expired_returns_false_when_within_timeout(self, mock_get_redis):
        """Not expired when last_updated is within the state timeout."""
        await CallStateMachine.create(CALL_SID, FROM_NUMBER, TO_NUMBER)

        expired = await CallStateMachine.is_expired(CALL_SID)
        assert expired is False

    @pytest.mark.asyncio
    async def test_is_expired_returns_true_when_past_timeout(self, mock_get_redis):
        """Expired when last_updated is beyond the state timeout."""
        await CallStateMachine.create(CALL_SID, FROM_NUMBER, TO_NUMBER)

        # Manually backdate the metadata's last_updated to exceed the INCOMING timeout (5s)
        redis = mock_get_redis
        key = CallStateMachine._get_key(CALL_SID)
        metadata_json = redis.store[key]["metadata"]
        metadata = CallStateMetadata.model_validate_json(metadata_json)
        metadata.last_updated = datetime.now(timezone.utc) - timedelta(seconds=60)
        redis.store[key]["metadata"] = metadata.model_dump_json()

        expired = await CallStateMachine.is_expired(CALL_SID)
        assert expired is True


class TestAllowedTransitionsComplete:
    def test_allowed_transitions_complete(self):
        """Every CallStatus enum value has an entry in ALLOWED_TRANSITIONS."""
        for status in CallStatus:
            assert status in CallStateMachine.ALLOWED_TRANSITIONS, (
                f"{status} missing from ALLOWED_TRANSITIONS"
            )
