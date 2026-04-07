"""MCP (Model Context Protocol) server for CallScreen.

Exposes CallScreen functionality as MCP tools that can be consumed by
AI assistants (Claude Desktop, custom agents) to manage call screening.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# MCP Tool definitions for CallScreen
TOOLS = [
    {
        "name": "callscreen_lookup_number",
        "description": "Look up intelligence data for a phone number including carrier, trust score, and reputation",
        "inputSchema": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "Phone number in E.164 format (e.g., +15551234567)",
                },
            },
            "required": ["phone_number"],
        },
    },
    {
        "name": "callscreen_add_contact",
        "description": "Add a phone number to the whitelist, blocklist, or known contacts",
        "inputSchema": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "E.164 phone number"},
                "name": {"type": "string", "description": "Contact name"},
                "contact_type": {
                    "type": "string",
                    "enum": ["whitelist", "blocklist", "known"],
                    "description": "Contact list type",
                },
                "category": {
                    "type": "string",
                    "enum": ["personal", "medical", "business", "government", "other"],
                    "description": "Contact category",
                    "default": "other",
                },
            },
            "required": ["phone_number", "name", "contact_type"],
        },
    },
    {
        "name": "callscreen_recent_calls",
        "description": "Get recent call history with screening results and dispositions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of calls to return (max 50)",
                    "default": 10,
                },
                "disposition": {
                    "type": "string",
                    "enum": ["forwarded", "messaged", "blocked", "engaged", "emergency"],
                    "description": "Filter by disposition",
                },
            },
        },
    },
    {
        "name": "callscreen_unread_messages",
        "description": "Get unread messages from screened callers with summaries and priority",
        "inputSchema": {
            "type": "object",
            "properties": {
                "priority": {
                    "type": "string",
                    "enum": ["urgent", "normal", "low"],
                    "description": "Filter by minimum priority",
                },
            },
        },
    },
    {
        "name": "callscreen_update_settings",
        "description": "Update call screening settings like greeting message, screening strictness, or quiet hours",
        "inputSchema": {
            "type": "object",
            "properties": {
                "greeting_message": {"type": "string", "description": "Custom greeting for callers"},
                "screening_strictness": {
                    "type": "string",
                    "enum": ["permissive", "moderate", "strict"],
                },
                "quiet_hours_start": {"type": "string", "description": "HH:MM format"},
                "quiet_hours_end": {"type": "string", "description": "HH:MM format"},
            },
        },
    },
    {
        "name": "callscreen_community_report",
        "description": "Submit a community report about a phone number (scam, spam, legitimate, etc.)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "E.164 phone number"},
                "report_type": {
                    "type": "string",
                    "enum": ["scam", "spam", "robocall", "spoofed", "legitimate"],
                },
                "category": {"type": "string", "description": "Scam category (e.g., 'IRS scam')"},
                "description": {"type": "string", "description": "Optional details"},
            },
            "required": ["phone_number", "report_type"],
        },
    },
]


async def handle_tool_call(tool_name: str, arguments: dict[str, Any], api_client) -> dict[str, Any]:
    """Route an MCP tool call to the appropriate CallScreen API handler.

    Args:
        tool_name: MCP tool name
        arguments: Tool input arguments
        api_client: Authenticated API client (httpx.AsyncClient with base_url and auth)

    Returns:
        Tool result dict
    """
    handlers = {
        "callscreen_lookup_number": _handle_lookup,
        "callscreen_add_contact": _handle_add_contact,
        "callscreen_recent_calls": _handle_recent_calls,
        "callscreen_unread_messages": _handle_unread_messages,
        "callscreen_update_settings": _handle_update_settings,
        "callscreen_community_report": _handle_community_report,
    }

    handler = handlers.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        return await handler(arguments, api_client)
    except Exception as e:
        logger.error("MCP tool %s failed: %s", tool_name, e)
        return {"error": str(e)}


async def _handle_lookup(args: dict, client) -> dict:
    phone = args["phone_number"]
    resp = await client.get(f"/api/v1/intel/{phone}")
    resp.raise_for_status()
    return resp.json()


async def _handle_add_contact(args: dict, client) -> dict:
    resp = await client.post("/api/v1/contacts", json=args)
    resp.raise_for_status()
    return resp.json()


async def _handle_recent_calls(args: dict, client) -> dict:
    params = {"limit": min(args.get("limit", 10), 50), "offset": 0}
    if "disposition" in args:
        params["disposition"] = args["disposition"]
    resp = await client.get("/api/v1/calls", params=params)
    resp.raise_for_status()
    return resp.json()


async def _handle_unread_messages(args: dict, client) -> dict:
    params = {}
    if "priority" in args:
        params["priority"] = args["priority"]
    resp = await client.get("/api/v1/messages", params=params)
    resp.raise_for_status()
    data = resp.json()
    # Filter to unread only
    if "messages" in data:
        data["messages"] = [m for m in data["messages"] if not m.get("read_at")]
    return data


async def _handle_update_settings(args: dict, client) -> dict:
    resp = await client.put("/api/v1/settings", json=args)
    resp.raise_for_status()
    return resp.json()


async def _handle_community_report(args: dict, client) -> dict:
    resp = await client.post("/api/v1/community/report", json=args)
    resp.raise_for_status()
    return resp.json()


def get_tool_definitions() -> list[dict]:
    """Return MCP tool definitions for server initialization."""
    return TOOLS
