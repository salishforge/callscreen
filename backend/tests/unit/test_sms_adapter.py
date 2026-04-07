"""Tests for the Twilio SMS adapter."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from callscreen.messaging.adapters.sms_adapter import SMSAdapter, SMS_MAX_LENGTH


class TestSMSAdapter:
    """SMS adapter tests."""

    @pytest.mark.asyncio
    async def test_send_success(self):
        adapter = SMSAdapter()
        mock_response = httpx.Response(
            201,
            request=httpx.Request("POST", "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json"),
            json={"sid": "SM123abc"},
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("callscreen.messaging.adapters.sms_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.sms_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.twilio_account_sid = "AC123"
            mock_settings.return_value.twilio_auth_token = "authtoken"
            mock_settings.return_value.twilio_phone_number = "+15550001111"

            result = await adapter.send("+15559999999", "Alert", "Hello")

        assert result.success is True
        assert result.adapter_name == "sms"
        assert result.message_id == "SM123abc"
        assert result.delivered_at is not None

    @pytest.mark.asyncio
    async def test_truncation_long_message(self):
        adapter = SMSAdapter()
        mock_response = httpx.Response(
            201,
            request=httpx.Request("POST", "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json"),
            json={"sid": "SM999"},
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        long_body = "x" * 2000

        with (
            patch("callscreen.messaging.adapters.sms_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.sms_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.twilio_account_sid = "AC123"
            mock_settings.return_value.twilio_auth_token = "authtoken"
            mock_settings.return_value.twilio_phone_number = "+15550001111"

            result = await adapter.send("+15559999999", "", long_body)

        assert result.success is True
        call_kwargs = mock_client.post.call_args
        sent_body = call_kwargs.kwargs["data"]["Body"]
        assert len(sent_body) <= SMS_MAX_LENGTH
        assert sent_body.endswith("...")

    @pytest.mark.asyncio
    async def test_send_api_error(self):
        adapter = SMSAdapter()
        mock_response = httpx.Response(
            400,
            request=httpx.Request("POST", "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json"),
            text="Invalid phone number",
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("callscreen.messaging.adapters.sms_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.sms_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.twilio_account_sid = "AC123"
            mock_settings.return_value.twilio_auth_token = "authtoken"
            mock_settings.return_value.twilio_phone_number = "+15550001111"

            result = await adapter.send("+15559999999", "Alert", "Hello")

        assert result.success is False
        assert "400" in result.error

    @pytest.mark.asyncio
    async def test_send_network_error(self):
        adapter = SMSAdapter()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("callscreen.messaging.adapters.sms_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.sms_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.twilio_account_sid = "AC123"
            mock_settings.return_value.twilio_auth_token = "authtoken"
            mock_settings.return_value.twilio_phone_number = "+15550001111"

            result = await adapter.send("+15559999999", "Alert", "Hello")

        assert result.success is False
        assert "timeout" in result.error

    @pytest.mark.asyncio
    async def test_is_configured_true(self):
        adapter = SMSAdapter()
        with patch("callscreen.messaging.adapters.sms_adapter.get_settings") as mock_settings:
            mock_settings.return_value.twilio_account_sid = "AC123"
            mock_settings.return_value.twilio_auth_token = "authtoken"
            assert await adapter.is_configured() is True

    @pytest.mark.asyncio
    async def test_is_configured_false_no_sid(self):
        adapter = SMSAdapter()
        with patch("callscreen.messaging.adapters.sms_adapter.get_settings") as mock_settings:
            mock_settings.return_value.twilio_account_sid = ""
            mock_settings.return_value.twilio_auth_token = "authtoken"
            assert await adapter.is_configured() is False

    @pytest.mark.asyncio
    async def test_is_configured_false_no_token(self):
        adapter = SMSAdapter()
        with patch("callscreen.messaging.adapters.sms_adapter.get_settings") as mock_settings:
            mock_settings.return_value.twilio_account_sid = "AC123"
            mock_settings.return_value.twilio_auth_token = ""
            assert await adapter.is_configured() is False
