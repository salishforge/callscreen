"""Tests for the Telegram adapter."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from callscreen.messaging.adapters.telegram_adapter import TelegramAdapter


class TestTelegramAdapter:
    """Telegram adapter tests."""

    @pytest.mark.asyncio
    async def test_send_success(self):
        adapter = TelegramAdapter()
        mock_response = httpx.Response(
            200,
            request=httpx.Request(
                "POST", "https://api.telegram.org/botTEST/sendMessage"
            ),
            json={"ok": True, "result": {"message_id": 42}},
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("callscreen.messaging.adapters.telegram_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.telegram_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.telegram_bot_token = "TEST"

            result = await adapter.send("123456789", "Hello", "World")

        assert result.success is True
        assert result.adapter_name == "telegram"
        assert result.message_id == "42"
        assert result.delivered_at is not None

    @pytest.mark.asyncio
    async def test_send_with_audio(self):
        adapter = TelegramAdapter()
        text_response = httpx.Response(
            200,
            request=httpx.Request(
                "POST", "https://api.telegram.org/botTEST/sendMessage"
            ),
            json={"ok": True, "result": {"message_id": 99}},
        )
        audio_response = httpx.Response(
            200,
            request=httpx.Request(
                "POST", "https://api.telegram.org/botTEST/sendAudio"
            ),
            json={"ok": True, "result": {"message_id": 100}},
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[text_response, audio_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("callscreen.messaging.adapters.telegram_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.telegram_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.telegram_bot_token = "TEST"

            result = await adapter.send(
                "123456789", "VM", "body", audio_url="https://example.com/audio.wav"
            )

        assert result.success is True
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_api_error(self):
        adapter = TelegramAdapter()
        mock_response = httpx.Response(
            403,
            request=httpx.Request(
                "POST", "https://api.telegram.org/botTEST/sendMessage"
            ),
            json={"ok": False, "description": "Forbidden"},
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("callscreen.messaging.adapters.telegram_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.telegram_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.telegram_bot_token = "TEST"

            result = await adapter.send("123456789", "Hello", "World")

        assert result.success is False
        assert "403" in result.error

    @pytest.mark.asyncio
    async def test_is_configured_true(self):
        adapter = TelegramAdapter()
        with patch("callscreen.messaging.adapters.telegram_adapter.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = "bot-token"
            assert await adapter.is_configured() is True

    @pytest.mark.asyncio
    async def test_is_configured_false(self):
        adapter = TelegramAdapter()
        with patch("callscreen.messaging.adapters.telegram_adapter.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = ""
            assert await adapter.is_configured() is False
