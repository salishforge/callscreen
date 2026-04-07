"""Tests for the AI message processor."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.messaging.processor import process_call_to_message
from callscreen.models.call import CallRecord, CallStatus
from callscreen.models.message import MessageCategory, MessagePriority
from callscreen.models.settings import UserSettings
from callscreen.models.user import User, UserRole
from callscreen.security.auth import hash_password


@pytest_asyncio.fixture
async def proc_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="proc@test.com",
        hashed_password=hash_password("pw"),
        role=UserRole.USER,
        phone_number="+15551112222",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def proc_user_settings(
    db_session: AsyncSession, proc_user: User
) -> UserSettings:
    settings = UserSettings(
        user_id=proc_user.id,
        preferred_channel="email",
        caretaker_fork_enabled=False,
    )
    db_session.add(settings)
    await db_session.flush()
    return settings


@pytest_asyncio.fixture
async def proc_call(db_session: AsyncSession, proc_user: User) -> CallRecord:
    call = CallRecord(
        call_sid=f"CA{uuid.uuid4().hex[:32]}",
        user_id=proc_user.id,
        from_number="+15559998888",
        to_number="+15551112222",
        status=CallStatus.COMPLETED,
    )
    db_session.add(call)
    await db_session.flush()
    return call


class TestProcessCallToMessage:
    @pytest.mark.asyncio
    @patch("callscreen.messaging.processor.deliver_message_to_channel", new_callable=AsyncMock)
    @patch("callscreen.messaging.processor.classify_intent", new_callable=AsyncMock)
    @patch("callscreen.messaging.processor.summarize_voicemail", new_callable=AsyncMock)
    async def test_creates_message_with_ai_summary(
        self,
        mock_summarize,
        mock_classify,
        mock_deliver,
        db_session,
        proc_user,
        proc_user_settings,
        proc_call,
    ):
        """Processor creates a Message with LLM-generated summary."""
        mock_summarize.return_value = "Doctor called about prescription refill."
        mock_classify.return_value = {"category": "medical", "priority": "urgent"}

        from callscreen.messaging.adapters.base import DeliveryResult

        mock_deliver.return_value = DeliveryResult(
            success=True, channel="email", recipient=proc_user.email
        )

        message = await process_call_to_message(
            call_sid=proc_call.call_sid,
            transcript="Hi, this is Dr. Smith calling about your prescription.",
            caller_info={
                "user_id": proc_user.id,
                "call_id": proc_call.id,
            },
            db=db_session,
        )

        assert message.summary == "Doctor called about prescription refill."
        assert message.category == MessageCategory.MEDICAL
        assert message.priority == MessagePriority.URGENT
        mock_summarize.assert_called_once()
        mock_classify.assert_called_once()

    @pytest.mark.asyncio
    @patch("callscreen.messaging.processor.deliver_message_to_channel", new_callable=AsyncMock)
    @patch("callscreen.messaging.processor.classify_intent", new_callable=AsyncMock)
    @patch("callscreen.messaging.processor.summarize_voicemail", new_callable=AsyncMock)
    async def test_medical_calls_forced_urgent(
        self,
        mock_summarize,
        mock_classify,
        mock_deliver,
        db_session,
        proc_user,
        proc_user_settings,
        proc_call,
    ):
        """Medical category always gets upgraded to urgent priority."""
        mock_summarize.return_value = "Pharmacy callback."
        # LLM returns normal but category is medical => force urgent
        mock_classify.return_value = {"category": "medical", "priority": "normal"}

        from callscreen.messaging.adapters.base import DeliveryResult

        mock_deliver.return_value = DeliveryResult(
            success=True, channel="email", recipient=proc_user.email
        )

        message = await process_call_to_message(
            call_sid=proc_call.call_sid,
            transcript="Pharmacy calling about your medication.",
            caller_info={
                "user_id": proc_user.id,
                "call_id": proc_call.id,
            },
            db=db_session,
        )

        assert message.category == MessageCategory.MEDICAL
        assert message.priority == MessagePriority.URGENT

    @pytest.mark.asyncio
    @patch("callscreen.messaging.processor.deliver_message_to_channel", new_callable=AsyncMock)
    @patch("callscreen.messaging.processor.classify_intent", new_callable=AsyncMock)
    @patch("callscreen.messaging.processor.summarize_voicemail", new_callable=AsyncMock)
    async def test_unknown_category_defaults_to_other(
        self,
        mock_summarize,
        mock_classify,
        mock_deliver,
        db_session,
        proc_user,
        proc_user_settings,
        proc_call,
    ):
        """Invalid category from LLM falls back to OTHER."""
        mock_summarize.return_value = "Unknown."
        mock_classify.return_value = {"category": "alien", "priority": "ultra"}

        from callscreen.messaging.adapters.base import DeliveryResult

        mock_deliver.return_value = DeliveryResult(
            success=True, channel="email", recipient=proc_user.email
        )

        message = await process_call_to_message(
            call_sid=proc_call.call_sid,
            transcript="Garbled message.",
            caller_info={
                "user_id": proc_user.id,
                "call_id": proc_call.id,
            },
            db=db_session,
        )

        assert message.category == MessageCategory.OTHER
        assert message.priority == MessagePriority.NORMAL

    @pytest.mark.asyncio
    @patch("callscreen.messaging.processor.fork_message_to_caretaker", new_callable=AsyncMock)
    @patch("callscreen.messaging.processor.deliver_message_to_channel", new_callable=AsyncMock)
    @patch("callscreen.messaging.processor.classify_intent", new_callable=AsyncMock)
    @patch("callscreen.messaging.processor.summarize_voicemail", new_callable=AsyncMock)
    async def test_triggers_caretaker_fork(
        self,
        mock_summarize,
        mock_classify,
        mock_deliver,
        mock_fork,
        db_session,
        proc_user,
        proc_call,
    ):
        """When caretaker fork is enabled, fork_message_to_caretaker is called."""
        caretaker = User(
            id=uuid.uuid4(),
            email="ct@test.com",
            hashed_password=hash_password("pw"),
            role=UserRole.CARETAKER,
            phone_number="+15550003333",
            is_active=True,
        )
        db_session.add(caretaker)
        await db_session.flush()

        ct_settings = UserSettings(
            user_id=caretaker.id,
            preferred_channel="email",
        )
        db_session.add(ct_settings)

        settings = UserSettings(
            user_id=proc_user.id,
            preferred_channel="email",
            caretaker_fork_enabled=True,
            caretaker_user_id=caretaker.id,
            caretaker_fork_priority="normal",
        )
        db_session.add(settings)
        await db_session.flush()

        mock_summarize.return_value = "Friend called to chat."
        mock_classify.return_value = {"category": "personal", "priority": "normal"}

        from callscreen.messaging.adapters.base import DeliveryResult

        mock_deliver.return_value = DeliveryResult(
            success=True, channel="email", recipient=proc_user.email
        )
        mock_fork.return_value = []

        message = await process_call_to_message(
            call_sid=proc_call.call_sid,
            transcript="Hey, it's your friend Bob.",
            caller_info={
                "user_id": proc_user.id,
                "call_id": proc_call.id,
            },
            db=db_session,
        )

        mock_fork.assert_called_once()
        assert message.category == MessageCategory.PERSONAL
