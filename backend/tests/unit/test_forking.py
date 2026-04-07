"""Tests for the message forking service."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.messaging.forking import (
    _meets_priority_threshold,
    fork_message_to_caretaker,
)
from callscreen.models.message import (
    DeliveryStatus,
    Message,
    MessageCategory,
    MessagePriority,
)
from callscreen.models.settings import UserSettings
from callscreen.models.user import User, UserRole
from callscreen.security.auth import hash_password


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def owner_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="owner@test.com",
        hashed_password=hash_password("pw"),
        role=UserRole.USER,
        phone_number="+15550001111",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def caretaker_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="caretaker@test.com",
        hashed_password=hash_password("pw"),
        role=UserRole.CARETAKER,
        phone_number="+15550002222",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def caretaker_settings(
    db_session: AsyncSession,
    caretaker_user: User,
) -> UserSettings:
    settings = UserSettings(
        user_id=caretaker_user.id,
        preferred_channel="email",
    )
    db_session.add(settings)
    await db_session.flush()
    return settings


@pytest_asyncio.fixture
async def owner_settings_fork_enabled(
    db_session: AsyncSession,
    owner_user: User,
    caretaker_user: User,
    caretaker_settings: UserSettings,
) -> UserSettings:
    settings = UserSettings(
        user_id=owner_user.id,
        preferred_channel="email",
        caretaker_fork_enabled=True,
        caretaker_user_id=caretaker_user.id,
        caretaker_fork_priority="normal",
    )
    db_session.add(settings)
    await db_session.flush()
    return settings


@pytest_asyncio.fixture
async def sample_message(db_session: AsyncSession, owner_user: User) -> Message:
    from callscreen.models.call import CallRecord, CallStatus

    call = CallRecord(
        call_sid=f"CA{uuid.uuid4().hex[:32]}",
        user_id=owner_user.id,
        from_number="+15559999999",
        to_number="+15550001111",
        status=CallStatus.COMPLETED,
    )
    db_session.add(call)
    await db_session.flush()

    msg = Message(
        call_id=call.id,
        user_id=owner_user.id,
        content="Test message content",
        summary="Test summary",
        priority=MessagePriority.URGENT,
        category=MessageCategory.MEDICAL,
    )
    db_session.add(msg)
    await db_session.flush()
    return msg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPriorityThreshold:
    def test_urgent_meets_urgent(self):
        assert _meets_priority_threshold("urgent", "urgent") is True

    def test_urgent_meets_normal(self):
        assert _meets_priority_threshold("urgent", "normal") is True

    def test_normal_does_not_meet_urgent(self):
        assert _meets_priority_threshold("normal", "urgent") is False

    def test_low_meets_low(self):
        assert _meets_priority_threshold("low", "low") is True

    def test_low_does_not_meet_normal(self):
        assert _meets_priority_threshold("low", "normal") is False


class TestForkMessageToCaretaker:
    @pytest.mark.asyncio
    @patch("callscreen.messaging.forking.deliver_message_to_channel", new_callable=AsyncMock)
    async def test_fork_disabled_returns_empty(
        self,
        mock_deliver,
        db_session,
        owner_user,
        sample_message,
    ):
        """When fork is disabled, no delivery is attempted."""
        settings = UserSettings(
            user_id=owner_user.id,
            preferred_channel="email",
            caretaker_fork_enabled=False,
        )
        db_session.add(settings)
        await db_session.flush()

        results = await fork_message_to_caretaker(sample_message, settings, db_session)
        assert results == []
        mock_deliver.assert_not_called()

    @pytest.mark.asyncio
    @patch("callscreen.messaging.forking.deliver_message_to_channel", new_callable=AsyncMock)
    async def test_fork_enabled_delivers_to_caretaker(
        self,
        mock_deliver,
        db_session,
        sample_message,
        owner_settings_fork_enabled,
        caretaker_user,
    ):
        """When fork is enabled and priority meets threshold, message is delivered."""
        from callscreen.messaging.adapters.base import DeliveryResult

        mock_deliver.return_value = DeliveryResult(
            success=True,
            channel="email",
            recipient=caretaker_user.email,
        )

        results = await fork_message_to_caretaker(
            sample_message, owner_settings_fork_enabled, db_session
        )

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].recipient == caretaker_user.email
        mock_deliver.assert_called_once()

    @pytest.mark.asyncio
    @patch("callscreen.messaging.forking.deliver_message_to_channel", new_callable=AsyncMock)
    async def test_priority_below_threshold_skips(
        self,
        mock_deliver,
        db_session,
        owner_user,
        caretaker_user,
        caretaker_settings,
    ):
        """A low-priority message should be skipped when threshold is 'urgent'."""
        settings = UserSettings(
            user_id=owner_user.id,
            preferred_channel="email",
            caretaker_fork_enabled=True,
            caretaker_user_id=caretaker_user.id,
            caretaker_fork_priority="urgent",
        )
        db_session.add(settings)
        await db_session.flush()

        from callscreen.models.call import CallRecord, CallStatus

        call = CallRecord(
            call_sid=f"CA{uuid.uuid4().hex[:32]}",
            user_id=owner_user.id,
            from_number="+15559999999",
            to_number="+15550001111",
            status=CallStatus.COMPLETED,
        )
        db_session.add(call)
        await db_session.flush()

        msg = Message(
            call_id=call.id,
            user_id=owner_user.id,
            content="Low priority message",
            priority=MessagePriority.LOW,
            category=MessageCategory.OTHER,
        )
        db_session.add(msg)
        await db_session.flush()

        results = await fork_message_to_caretaker(msg, settings, db_session)
        assert results == []
        mock_deliver.assert_not_called()

    @pytest.mark.asyncio
    @patch("callscreen.messaging.forking.deliver_message_to_channel", new_callable=AsyncMock)
    async def test_no_caretaker_user_id_returns_empty(
        self,
        mock_deliver,
        db_session,
        owner_user,
        sample_message,
    ):
        """Fork enabled but no caretaker_user_id should return empty."""
        settings = UserSettings(
            user_id=owner_user.id,
            preferred_channel="email",
            caretaker_fork_enabled=True,
            caretaker_user_id=None,
            caretaker_fork_priority="normal",
        )
        db_session.add(settings)
        await db_session.flush()

        results = await fork_message_to_caretaker(sample_message, settings, db_session)
        assert results == []
        mock_deliver.assert_not_called()

    @pytest.mark.asyncio
    @patch("callscreen.messaging.forking.deliver_message_to_channel", new_callable=AsyncMock)
    async def test_caretaker_with_no_settings_returns_empty(
        self,
        mock_deliver,
        db_session,
        owner_user,
        sample_message,
    ):
        """If the caretaker user has no settings record, fork is skipped."""
        # Create a caretaker user but no UserSettings for them
        ct_user = User(
            id=uuid.uuid4(),
            email="nosettings@test.com",
            hashed_password=hash_password("pw"),
            role=UserRole.CARETAKER,
            phone_number="+15550009999",
            is_active=True,
        )
        db_session.add(ct_user)
        await db_session.flush()

        settings = UserSettings(
            user_id=owner_user.id,
            preferred_channel="email",
            caretaker_fork_enabled=True,
            caretaker_user_id=ct_user.id,
            caretaker_fork_priority="low",
        )
        db_session.add(settings)
        await db_session.flush()

        results = await fork_message_to_caretaker(sample_message, settings, db_session)
        assert results == []
        mock_deliver.assert_not_called()
