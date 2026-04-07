"""Tests for the SendGrid email adapter."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from callscreen.messaging.adapters.email_adapter import EmailAdapter


class TestEmailAdapter:
    """Email adapter tests."""

    @pytest.mark.asyncio
    async def test_send_success(self):
        adapter = EmailAdapter()
        mock_response = httpx.Response(
            202,
            request=httpx.Request("POST", "https://api.sendgrid.com/v3/mail/send"),
            headers={"X-Message-Id": "sg-abc123"},
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("callscreen.messaging.adapters.email_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.email_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.sendgrid_api_key = "SG.test-key"
            mock_settings.return_value.sendgrid_from_email = "noreply@test.com"

            result = await adapter.send("user@example.com", "Test Subject", "Test body")

        assert result.success is True
        assert result.adapter_name == "email"
        assert result.message_id == "sg-abc123"
        assert result.delivered_at is not None

    @pytest.mark.asyncio
    async def test_send_with_html_body(self):
        adapter = EmailAdapter()
        mock_response = httpx.Response(
            202,
            request=httpx.Request("POST", "https://api.sendgrid.com/v3/mail/send"),
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("callscreen.messaging.adapters.email_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.email_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.sendgrid_api_key = "SG.test-key"
            mock_settings.return_value.sendgrid_from_email = "noreply@test.com"

            result = await adapter.send(
                "user@example.com", "Subj", "text", html_body="<b>html</b>"
            )

        assert result.success is True
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert len(payload["content"]) == 2
        assert payload["content"][1]["type"] == "text/html"

    @pytest.mark.asyncio
    async def test_send_with_audio_attachment(self):
        adapter = EmailAdapter()
        mock_response = httpx.Response(
            202,
            request=httpx.Request("POST", "https://api.sendgrid.com/v3/mail/send"),
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("callscreen.messaging.adapters.email_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.email_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.sendgrid_api_key = "SG.test-key"
            mock_settings.return_value.sendgrid_from_email = "noreply@test.com"

            result = await adapter.send(
                "user@example.com",
                "Voicemail",
                "body",
                audio_data=b"fake-wav-data",
                audio_filename="msg.wav",
            )

        assert result.success is True
        payload = mock_client.post.call_args.kwargs["json"]
        assert "attachments" in payload
        assert payload["attachments"][0]["filename"] == "msg.wav"

    @pytest.mark.asyncio
    async def test_send_api_error(self):
        adapter = EmailAdapter()
        mock_response = httpx.Response(
            400,
            request=httpx.Request("POST", "https://api.sendgrid.com/v3/mail/send"),
            text="Bad Request",
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("callscreen.messaging.adapters.email_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.email_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.sendgrid_api_key = "SG.test-key"
            mock_settings.return_value.sendgrid_from_email = "noreply@test.com"

            result = await adapter.send("user@example.com", "Subj", "body")

        assert result.success is False
        assert "400" in result.error

    @pytest.mark.asyncio
    async def test_send_network_error(self):
        adapter = EmailAdapter()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("callscreen.messaging.adapters.email_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.email_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.sendgrid_api_key = "SG.test-key"
            mock_settings.return_value.sendgrid_from_email = "noreply@test.com"

            result = await adapter.send("user@example.com", "Subj", "body")

        assert result.success is False
        assert "Connection refused" in result.error

    @pytest.mark.asyncio
    async def test_is_configured_true(self):
        adapter = EmailAdapter()
        with patch("callscreen.messaging.adapters.email_adapter.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = "SG.test-key"
            assert await adapter.is_configured() is True

    @pytest.mark.asyncio
    async def test_is_configured_false(self):
        adapter = EmailAdapter()
        with patch("callscreen.messaging.adapters.email_adapter.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = ""
            assert await adapter.is_configured() is False
