"""Tests for the message delivery service."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from callscreen.messaging.adapters.base import DeliveryResult
from callscreen.messaging.delivery_service import (
    _meets_priority_threshold,
    _send_with_retry,
    deliver_message,
    get_configured_adapters,
)
from callscreen.models.message import DeliveryStatus, MessagePriority


class TestPriorityThreshold:
    """Tests for priority threshold comparison."""

    def test_urgent_meets_urgent(self):
        assert _meets_priority_threshold(MessagePriority.URGENT, "urgent") is True

    def test_normal_does_not_meet_urgent(self):
        assert _meets_priority_threshold(MessagePriority.NORMAL, "urgent") is False

    def test_urgent_meets_normal(self):
        assert _meets_priority_threshold(MessagePriority.URGENT, "normal") is True

    def test_low_meets_low(self):
        assert _meets_priority_threshold(MessagePriority.LOW, "low") is True


class TestSendWithRetry:
    """Tests for retry logic."""

    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        adapter = AsyncMock()
        adapter.send = AsyncMock(
            return_value=DeliveryResult(
                success=True, adapter_name="test", message_id="m1", delivered_at=datetime.now(UTC)
            )
        )
        result = await _send_with_retry(adapter, "r", "s", "b")
        assert result.success is True
        assert adapter.send.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self):
        fail_result = DeliveryResult(success=False, adapter_name="test", error="fail")
        ok_result = DeliveryResult(
            success=True, adapter_name="test", message_id="m2", delivered_at=datetime.now(UTC)
        )
        adapter = AsyncMock()
        adapter.send = AsyncMock(side_effect=[fail_result, ok_result])

        with patch("callscreen.messaging.delivery_service.asyncio.sleep", new_callable=AsyncMock):
            result = await _send_with_retry(adapter, "r", "s", "b")

        assert result.success is True
        assert adapter.send.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        fail_result = DeliveryResult(success=False, adapter_name="test", error="persistent error")
        adapter = AsyncMock()
        adapter.send = AsyncMock(return_value=fail_result)

        with patch("callscreen.messaging.delivery_service.asyncio.sleep", new_callable=AsyncMock):
            result = await _send_with_retry(adapter, "r", "s", "b")

        assert result.success is False
        assert adapter.send.call_count == 3
        assert "persistent error" in result.error


class TestGetConfiguredAdapters:
    """Tests for configured adapter discovery."""

    @pytest.mark.asyncio
    async def test_returns_only_configured(self):
        with (
            patch("callscreen.messaging.delivery_service.EmailAdapter") as email_cls,
            patch("callscreen.messaging.delivery_service.SMSAdapter") as sms_cls,
            patch("callscreen.messaging.delivery_service.TelegramAdapter") as tg_cls,
            patch("callscreen.messaging.delivery_service.DiscordAdapter") as dc_cls,
        ):
            email_inst = AsyncMock()
            email_inst.is_configured = AsyncMock(return_value=True)
            email_cls.return_value = email_inst

            sms_inst = AsyncMock()
            sms_inst.is_configured = AsyncMock(return_value=False)
            sms_cls.return_value = sms_inst

            tg_inst = AsyncMock()
            tg_inst.is_configured = AsyncMock(return_value=False)
            tg_cls.return_value = tg_inst

            dc_inst = AsyncMock()
            dc_inst.is_configured = AsyncMock(return_value=True)
            dc_cls.return_value = dc_inst

            adapters = await get_configured_adapters()

        assert len(adapters) == 2


class TestDeliverMessage:
    """Tests for full delivery orchestration."""

    def _make_message(self, priority=MessagePriority.NORMAL):
        msg = MagicMock()
        msg.id = uuid.uuid4()
        msg.user_id = uuid.uuid4()
        msg.content = "Test message body"
        msg.summary = "Test summary"
        msg.priority = priority
        msg.delivery_status = DeliveryStatus.PENDING
        msg.delivered_at = None
        msg.delivered_via = None
        return msg

    def _make_user(self, user_id, email="user@test.com", phone="+15551234567"):
        user = MagicMock()
        user.id = user_id
        user.email = email
        user.phone_number = phone
        return user

    def _make_settings(self, user_id, channel="email", fork_enabled=False, caretaker_id=None, fork_priority="urgent"):
        settings = MagicMock()
        settings.user_id = user_id
        settings.preferred_channel = channel
        settings.caretaker_fork_enabled = fork_enabled
        settings.caretaker_user_id = caretaker_id
        settings.caretaker_fork_priority = fork_priority
        return settings

    @pytest.mark.asyncio
    async def test_deliver_via_preferred_channel(self):
        msg = self._make_message()
        user = self._make_user(msg.user_id)
        user_settings = self._make_settings(msg.user_id, channel="email")

        # Mock DB queries
        db = AsyncMock()
        settings_result = MagicMock()
        settings_result.scalars.return_value.first.return_value = user_settings
        user_result = MagicMock()
        user_result.scalars.return_value.first.return_value = user
        db.execute = AsyncMock(side_effect=[settings_result, user_result])
        db.flush = AsyncMock()

        ok_result = DeliveryResult(
            success=True, adapter_name="email", message_id="e1", delivered_at=datetime.now(UTC)
        )

        with (
            patch("callscreen.messaging.delivery_service._send_with_retry", new_callable=AsyncMock, return_value=ok_result),
            patch("callscreen.messaging.delivery_service._record_delivery", new_callable=AsyncMock),
        ):
            results = await deliver_message(msg, db)

        assert len(results) == 1
        assert results[0].success is True
        assert msg.delivery_status == DeliveryStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_deliver_marks_failed(self):
        msg = self._make_message()
        user = self._make_user(msg.user_id)
        user_settings = self._make_settings(msg.user_id, channel="email")

        db = AsyncMock()
        settings_result = MagicMock()
        settings_result.scalars.return_value.first.return_value = user_settings
        user_result = MagicMock()
        user_result.scalars.return_value.first.return_value = user
        db.execute = AsyncMock(side_effect=[settings_result, user_result])
        db.flush = AsyncMock()

        fail_result = DeliveryResult(success=False, adapter_name="email", error="fail")

        with (
            patch("callscreen.messaging.delivery_service._send_with_retry", new_callable=AsyncMock, return_value=fail_result),
            patch("callscreen.messaging.delivery_service._record_delivery", new_callable=AsyncMock),
        ):
            results = await deliver_message(msg, db)

        assert len(results) == 1
        assert results[0].success is False
        assert msg.delivery_status == DeliveryStatus.FAILED

    @pytest.mark.asyncio
    async def test_caretaker_fork(self):
        caretaker_id = uuid.uuid4()
        msg = self._make_message(priority=MessagePriority.URGENT)
        user = self._make_user(msg.user_id)
        user_settings = self._make_settings(
            msg.user_id,
            channel="email",
            fork_enabled=True,
            caretaker_id=caretaker_id,
            fork_priority="urgent",
        )
        caretaker = self._make_user(caretaker_id, email="caretaker@test.com")
        caretaker_settings = self._make_settings(caretaker_id, channel="email")

        db = AsyncMock()
        settings_result = MagicMock()
        settings_result.scalars.return_value.first.return_value = user_settings
        user_result = MagicMock()
        user_result.scalars.return_value.first.return_value = user
        ct_user_result = MagicMock()
        ct_user_result.scalars.return_value.first.return_value = caretaker
        ct_settings_result = MagicMock()
        ct_settings_result.scalars.return_value.first.return_value = caretaker_settings

        db.execute = AsyncMock(
            side_effect=[settings_result, user_result, ct_user_result, ct_settings_result]
        )
        db.flush = AsyncMock()

        ok_result = DeliveryResult(
            success=True, adapter_name="email", message_id="e1", delivered_at=datetime.now(UTC)
        )

        with (
            patch("callscreen.messaging.delivery_service._send_with_retry", new_callable=AsyncMock, return_value=ok_result),
            patch("callscreen.messaging.delivery_service._record_delivery", new_callable=AsyncMock),
        ):
            results = await deliver_message(msg, db)

        # Should have sent to both user and caretaker
        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_caretaker_fork_skipped_low_priority(self):
        caretaker_id = uuid.uuid4()
        msg = self._make_message(priority=MessagePriority.LOW)
        user = self._make_user(msg.user_id)
        user_settings = self._make_settings(
            msg.user_id,
            channel="email",
            fork_enabled=True,
            caretaker_id=caretaker_id,
            fork_priority="urgent",
        )

        db = AsyncMock()
        settings_result = MagicMock()
        settings_result.scalars.return_value.first.return_value = user_settings
        user_result = MagicMock()
        user_result.scalars.return_value.first.return_value = user
        db.execute = AsyncMock(side_effect=[settings_result, user_result])
        db.flush = AsyncMock()

        ok_result = DeliveryResult(
            success=True, adapter_name="email", message_id="e1", delivered_at=datetime.now(UTC)
        )

        with (
            patch("callscreen.messaging.delivery_service._send_with_retry", new_callable=AsyncMock, return_value=ok_result),
            patch("callscreen.messaging.delivery_service._record_delivery", new_callable=AsyncMock),
        ):
            results = await deliver_message(msg, db)

        # Only user delivery, caretaker skipped (LOW does not meet URGENT threshold)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_no_user_returns_empty(self):
        msg = self._make_message()

        db = AsyncMock()
        settings_result = MagicMock()
        settings_result.scalars.return_value.first.return_value = None
        user_result = MagicMock()
        user_result.scalars.return_value.first.return_value = None
        db.execute = AsyncMock(side_effect=[settings_result, user_result])

        results = await deliver_message(msg, db)
        assert results == []
