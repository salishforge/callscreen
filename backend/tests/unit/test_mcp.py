"""Tests for MCP server tool definitions and routing."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from callscreen.mcp.server import get_tool_definitions, handle_tool_call, TOOLS


class TestToolDefinitions:
    def test_all_tools_have_required_fields(self):
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_tool_names_are_prefixed(self):
        for tool in TOOLS:
            assert tool["name"].startswith("callscreen_")

    def test_expected_tool_count(self):
        assert len(TOOLS) == 6

    def test_get_tool_definitions_returns_all(self):
        defs = get_tool_definitions()
        assert len(defs) == 6


class TestHandleToolCall:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        result = await handle_tool_call("nonexistent_tool", {}, None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_lookup_number_calls_api(self):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"phone_number": "+15551234567", "trust_score": 0.8}
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        result = await handle_tool_call(
            "callscreen_lookup_number",
            {"phone_number": "+15551234567"},
            mock_client,
        )
        assert result["phone_number"] == "+15551234567"
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_contact_calls_api(self):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "123", "name": "Dr. Smith"}
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp

        result = await handle_tool_call(
            "callscreen_add_contact",
            {"phone_number": "+15551234567", "name": "Dr. Smith", "contact_type": "whitelist"},
            mock_client,
        )
        assert result["name"] == "Dr. Smith"

    @pytest.mark.asyncio
    async def test_recent_calls_limits_to_50(self):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"calls": []}
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        await handle_tool_call(
            "callscreen_recent_calls",
            {"limit": 100},
            mock_client,
        )
        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs["params"]["limit"] == 50

    @pytest.mark.asyncio
    async def test_unread_messages_filters_read(self):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "messages": [
                {"id": "1", "read_at": None},
                {"id": "2", "read_at": "2026-04-07T00:00:00Z"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        result = await handle_tool_call("callscreen_unread_messages", {}, mock_client)
        assert len(result["messages"]) == 1
        assert result["messages"][0]["id"] == "1"

    @pytest.mark.asyncio
    async def test_handler_catches_exceptions(self):
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Network error")

        result = await handle_tool_call(
            "callscreen_lookup_number",
            {"phone_number": "+15551234567"},
            mock_client,
        )
        assert "error" in result
        assert "Network error" in result["error"]
