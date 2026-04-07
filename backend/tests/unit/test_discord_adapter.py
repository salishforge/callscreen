"""Tests for the Discord webhook adapter."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from callscreen.messaging.adapters.discord_adapter import DiscordAdapter


class TestDiscordAdapter:
    """Discord adapter tests."""

    @pytest.mark.asyncio
    async def test_send_success_embed(self):
        adapter = DiscordAdapter()
        mock_response = httpx.Response(
            204,
            request=httpx.Request("POST", "https://discord.com/api/webhooks/123/abc"),
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("callscreen.messaging.adapters.discord_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.discord_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.discord_bot_token = "https://discord.com/api/webhooks/123/abc"

            result = await adapter.send(
                "https://discord.com/api/webhooks/123/abc",
                "Test Subject",
                "Test body",
            )

        assert result.success is True
        assert result.adapter_name == "discord"
        assert result.delivered_at is not None
        payload = mock_client.post.call_args.kwargs["json"]
        assert "embeds" in payload
        assert payload["embeds"][0]["title"] == "Test Subject"

    @pytest.mark.asyncio
    async def test_send_plain_text(self):
        adapter = DiscordAdapter()
        mock_response = httpx.Response(
            204,
            request=httpx.Request("POST", "https://discord.com/api/webhooks/123/abc"),
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("callscreen.messaging.adapters.discord_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.discord_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.discord_bot_token = "https://discord.com/api/webhooks/123/abc"

            result = await adapter.send(
                "https://discord.com/api/webhooks/123/abc",
                "Title",
                "body",
                use_embed=False,
            )

        assert result.success is True
        payload = mock_client.post.call_args.kwargs["json"]
        assert "content" in payload
        assert "embeds" not in payload

    @pytest.mark.asyncio
    async def test_send_api_error(self):
        adapter = DiscordAdapter()
        mock_response = httpx.Response(
            400,
            request=httpx.Request("POST", "https://discord.com/api/webhooks/123/abc"),
            text="Bad Request",
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("callscreen.messaging.adapters.discord_adapter.httpx.AsyncClient", return_value=mock_client),
            patch("callscreen.messaging.adapters.discord_adapter.get_settings") as mock_settings,
        ):
            mock_settings.return_value.discord_bot_token = "https://discord.com/api/webhooks/123/abc"

            result = await adapter.send(
                "https://discord.com/api/webhooks/123/abc",
                "Title",
                "body",
            )

        assert result.success is False
        assert "400" in result.error

    @pytest.mark.asyncio
    async def test_is_configured_true(self):
        adapter = DiscordAdapter()
        with patch("callscreen.messaging.adapters.discord_adapter.get_settings") as mock_settings:
            mock_settings.return_value.discord_bot_token = "https://discord.com/api/webhooks/123/abc"
            assert await adapter.is_configured() is True

    @pytest.mark.asyncio
    async def test_is_configured_false(self):
        adapter = DiscordAdapter()
        with patch("callscreen.messaging.adapters.discord_adapter.get_settings") as mock_settings:
            mock_settings.return_value.discord_bot_token = ""
            assert await adapter.is_configured() is False
