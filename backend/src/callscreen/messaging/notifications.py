"""Notification scheduler -- daily digests and similar periodic alerts."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.messaging.adapters.base import DeliveryResult
from callscreen.messaging.delivery_service import deliver_message_to_channel, get_adapter
from callscreen.models.message import Message, MessageCategory, MessagePriority
from callscreen.models.settings import UserSettings
from callscreen.models.user import User

logger = logging.getLogger("callscreen.messaging.notifications")

# Priority display ordering (highest first)
_PRIORITY_DISPLAY = [
    MessagePriority.URGENT,
    MessagePriority.NORMAL,
    MessagePriority.LOW,
]


def _format_digest(messages: list[Message]) -> str:
    """Format a list of messages into a readable daily digest string."""
    if not messages:
        return "You have no new messages in the last 24 hours."

    # Group by category
    by_category: dict[str, list[Message]] = {}
    for msg in messages:
        cat = msg.category.value if hasattr(msg.category, "value") else str(msg.category)
        by_category.setdefault(cat, []).append(msg)

    lines: list[str] = [
        "CallScreen Daily Digest",
        f"Total messages: {len(messages)}",
        "",
    ]

    # Show urgent messages first
    urgent_msgs = [m for m in messages if m.priority == MessagePriority.URGENT]
    if urgent_msgs:
        lines.append(f"URGENT ({len(urgent_msgs)}):")
        for msg in urgent_msgs:
            summary = msg.summary or msg.content[:80]
            lines.append(f"  - {summary}")
        lines.append("")

    # Then by category
    for cat_name in sorted(by_category.keys()):
        cat_msgs = by_category[cat_name]
        non_urgent = [m for m in cat_msgs if m.priority != MessagePriority.URGENT]
        if non_urgent:
            lines.append(f"{cat_name.upper()} ({len(non_urgent)}):")
            for msg in non_urgent:
                priority_label = msg.priority.value if hasattr(msg.priority, "value") else str(msg.priority)
                summary = msg.summary or msg.content[:80]
                lines.append(f"  [{priority_label}] {summary}")
            lines.append("")

    return "\n".join(lines).rstrip()


async def send_daily_digest(
    user_id: str,
    db: AsyncSession,
) -> DeliveryResult | None:
    """Send a daily digest of missed calls and messages.

    Queries messages from the last 24 hours, groups them by category and
    priority, formats a readable digest, and delivers via the user's
    preferred channel.

    Returns the :class:`DeliveryResult` or ``None`` if no messages exist.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    result = await db.execute(
        select(Message)
        .where(
            Message.user_id == user_id,
            Message.created_at >= cutoff,
        )
        .order_by(Message.created_at.desc())
    )
    messages = list(result.scalars().all())

    if not messages:
        logger.debug("No messages in last 24h for user %s, skipping digest", user_id)
        return None

    digest_body = _format_digest(messages)

    # Fetch user settings for preferred channel
    settings_result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    user_settings = settings_result.scalar_one_or_none()
    channel = "email"
    if user_settings is not None:
        channel = user_settings.preferred_channel or "email"

    # Resolve recipient
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        logger.warning("User %s not found, cannot send digest", user_id)
        return None

    recipient = user.email
    if channel == "sms":
        recipient = user.phone_number

    # We need an adapter; if none registered, build a lightweight result
    adapter = get_adapter(channel)
    if adapter is None:
        logger.warning("No adapter for channel %s; digest not sent", channel)
        return DeliveryResult(
            success=False,
            channel=channel,
            recipient=recipient,
            error=f"No adapter for channel '{channel}'",
        )

    try:
        delivery_result = await adapter.send(
            recipient=recipient,
            subject="CallScreen Daily Digest",
            body=digest_body,
        )
        return delivery_result
    except Exception as exc:
        logger.exception("Daily digest delivery failed for user %s", user_id)
        return DeliveryResult(
            success=False,
            channel=channel,
            recipient=recipient,
            error=str(exc),
        )
