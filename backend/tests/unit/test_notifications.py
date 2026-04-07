"""Tests for the notification / daily digest service."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.messaging.adapters.base import DeliveryResult
from callscreen.messaging.notifications import _format_digest, send_daily_digest
from callscreen.models.call import CallRecord, CallStatus
from callscreen.models.message import Message, MessageCategory, MessagePriority
from callscreen.models.settings import UserSettings
from callscreen.models.user import User, UserRole
from callscreen.security.auth import hash_password


@pytest_asyncio.fixture
async def digest_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="digest@test.com",
        hashed_password=hash_password("pw"),
        role=UserRole.USER,
        phone_number="+15553334444",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def digest_user_settings(
    db_session: AsyncSession, digest_user: User
) -> UserSettings:
    settings = UserSettings(
        user_id=digest_user.id,
        preferred_channel="email",
    )
    db_session.add(settings)
    await db_session.flush()
    return settings


@pytest_asyncio.fixture
async def _seed_messages(
    db_session: AsyncSession, digest_user: User
):
    """Insert a handful of messages from the last 24h."""
    call = CallRecord(
        call_sid=f"CA{uuid.uuid4().hex[:32]}",
        user_id=digest_user.id,
        from_number="+15559998888",
        to_number="+15553334444",
        status=CallStatus.COMPLETED,
    )
    db_session.add(call)
    await db_session.flush()

    now = datetime.now(UTC)
    msgs = [
        Message(
            call_id=call.id,
            user_id=digest_user.id,
            content="Urgent medical message",
            summary="Doctor called about lab results",
            priority=MessagePriority.URGENT,
            category=MessageCategory.MEDICAL,
            created_at=now - timedelta(hours=2),
        ),
        Message(
            call_id=call.id,
            user_id=digest_user.id,
            content="Friend called to say hi",
            summary="Bob wants to have lunch",
            priority=MessagePriority.NORMAL,
            category=MessageCategory.PERSONAL,
            created_at=now - timedelta(hours=5),
        ),
        Message(
            call_id=call.id,
            user_id=digest_user.id,
            content="Low-priority spam",
            summary="Survey request",
            priority=MessagePriority.LOW,
            category=MessageCategory.OTHER,
            created_at=now - timedelta(hours=10),
        ),
    ]
    for m in msgs:
        db_session.add(m)
    await db_session.flush()
    return msgs


def _make_message(summary, content, priority, category):
    """Create a lightweight Message-like object for unit tests that don't need a DB."""

    class _FakeMsg:
        pass

    m = _FakeMsg()
    m.summary = summary
    m.content = content
    m.priority = priority
    m.category = category
    return m


class TestFormatDigest:
    def test_no_messages(self):
        result = _format_digest([])
        assert "no new messages" in result.lower()

    def test_urgent_shown_first(self):
        m1 = _make_message(
            "Urgent call", "Urgent", MessagePriority.URGENT, MessageCategory.MEDICAL
        )
        m2 = _make_message(
            "Normal call", "Normal", MessagePriority.NORMAL, MessageCategory.PERSONAL
        )

        digest = _format_digest([m1, m2])
        assert "URGENT" in digest
        assert digest.index("URGENT") < digest.index("PERSONAL")

    def test_total_count_displayed(self):
        m = _make_message("Hi", "Hi", MessagePriority.NORMAL, MessageCategory.OTHER)

        digest = _format_digest([m])
        assert "Total messages: 1" in digest


class TestSendDailyDigest:
    @pytest.mark.asyncio
    async def test_no_messages_returns_none(
        self,
        db_session,
        digest_user,
        digest_user_settings,
    ):
        """When there are no messages in 24h, None is returned."""
        result = await send_daily_digest(str(digest_user.id), db_session)
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_seed_messages")
    @patch(
        "callscreen.messaging.notifications.get_adapter",
    )
    async def test_sends_digest_via_adapter(
        self,
        mock_get_adapter,
        db_session,
        digest_user,
        digest_user_settings,
    ):
        """When messages exist, digest is sent through the adapter."""
        mock_adapter = AsyncMock()
        mock_adapter.send.return_value = DeliveryResult(
            success=True,
            channel="email",
            recipient=digest_user.email,
        )
        mock_get_adapter.return_value = mock_adapter

        result = await send_daily_digest(str(digest_user.id), db_session)

        assert result is not None
        assert result.success is True
        mock_adapter.send.assert_called_once()
        call_kwargs = mock_adapter.send.call_args
        assert "Daily Digest" in call_kwargs.kwargs["subject"]

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_seed_messages")
    @patch("callscreen.messaging.notifications.get_adapter", return_value=None)
    async def test_no_adapter_returns_failure(
        self,
        mock_get_adapter,
        db_session,
        digest_user,
        digest_user_settings,
    ):
        """When no adapter is registered, a failure result is returned."""
        result = await send_daily_digest(str(digest_user.id), db_session)

        assert result is not None
        assert result.success is False
        assert "No adapter" in (result.error or "")
