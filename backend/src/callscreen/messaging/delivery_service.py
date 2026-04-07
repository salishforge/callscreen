"""Message delivery orchestration service."""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.messaging.adapters.base import DeliveryResult, MessageAdapter
from callscreen.messaging.adapters.discord_adapter import DiscordAdapter
from callscreen.messaging.adapters.email_adapter import EmailAdapter
from callscreen.messaging.adapters.sms_adapter import SMSAdapter
from callscreen.messaging.adapters.telegram_adapter import TelegramAdapter
from callscreen.models.message import DeliveryStatus, Message, MessageDelivery, MessagePriority
from callscreen.models.settings import UserSettings
from callscreen.models.user import User

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 1  # seconds

_ADAPTER_MAP: dict[str, type[MessageAdapter]] = {
    "email": EmailAdapter,
    "sms": SMSAdapter,
    "telegram": TelegramAdapter,
    "discord": DiscordAdapter,
}

# Priority ordering: URGENT > NORMAL > LOW
_PRIORITY_ORDER = {
    MessagePriority.URGENT: 0,
    MessagePriority.NORMAL: 1,
    MessagePriority.LOW: 2,
}


def _meets_priority_threshold(
    message_priority: MessagePriority, threshold: str
) -> bool:
    """Check whether message_priority meets or exceeds threshold."""
    threshold_enum = MessagePriority(threshold)
    return _PRIORITY_ORDER.get(message_priority, 99) <= _PRIORITY_ORDER.get(
        threshold_enum, 99
    )


async def get_configured_adapters() -> list[MessageAdapter]:
    """Return only adapters whose credentials are present."""
    all_adapters: list[MessageAdapter] = [
        EmailAdapter(),
        SMSAdapter(),
        TelegramAdapter(),
        DiscordAdapter(),
    ]
    configured = []
    for adapter in all_adapters:
        if await adapter.is_configured():
            configured.append(adapter)
    return configured


def _get_adapter(channel: str) -> MessageAdapter | None:
    """Instantiate an adapter by channel name."""
    cls = _ADAPTER_MAP.get(channel)
    if cls is None:
        return None
    return cls()


def get_adapter(channel: str) -> MessageAdapter | None:
    """Public accessor: look up an adapter by channel name."""
    return _get_adapter(channel)


async def _send_with_retry(
    adapter: MessageAdapter,
    recipient: str,
    subject: str,
    body: str,
    **kwargs: object,
) -> DeliveryResult:
    """Send through an adapter with exponential-backoff retries."""
    last_result: DeliveryResult | None = None
    for attempt in range(MAX_RETRIES):
        result = await adapter.send(recipient, subject, body, **kwargs)
        if result.success:
            return result
        last_result = result
        if attempt < MAX_RETRIES - 1:
            delay = BACKOFF_BASE * (2**attempt)
            await asyncio.sleep(delay)
    # All retries exhausted -- return last failure
    assert last_result is not None
    return last_result


async def _record_delivery(
    db: AsyncSession,
    message_id: object,
    channel: str,
    recipient: str,
    result: DeliveryResult,
) -> MessageDelivery:
    """Persist a MessageDelivery row for one send attempt."""
    import uuid as _uuid

    delivery = MessageDelivery(
        id=_uuid.uuid4(),
        message_id=message_id,
        channel=channel,
        recipient=recipient,
        status=DeliveryStatus.DELIVERED if result.success else DeliveryStatus.FAILED,
        error_message=result.error,
        sent_at=datetime.now(UTC),
        delivered_at=result.delivered_at,
    )
    db.add(delivery)
    return delivery


async def deliver_message(
    message: Message,
    db: AsyncSession,
) -> list[DeliveryResult]:
    """Orchestrate delivery of a Message to the user (and optionally caretaker).

    Steps:
        1. Look up the user's preferred channel from UserSettings.
        2. Send via the preferred adapter (with retry).
        3. If caretaker forking is enabled and the message priority
           meets the configured threshold, send to the caretaker as well.
        4. Create MessageDelivery records and update the Message status.

    Returns:
        List of DeliveryResult for all attempted sends.
    """
    results: list[DeliveryResult] = []

    # Fetch user settings
    settings_result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == message.user_id)
    )
    user_settings = settings_result.scalars().first()
    preferred_channel = user_settings.preferred_channel if user_settings else "email"

    # Fetch user for recipient address
    user_result = await db.execute(
        select(User).where(User.id == message.user_id)
    )
    user = user_result.scalars().first()
    if not user:
        logger.error("User %s not found for message %s", message.user_id, message.id)
        return results

    # Determine recipient based on channel
    recipient = _resolve_recipient(user, preferred_channel)

    # Send via preferred channel
    adapter = _get_adapter(preferred_channel)
    if adapter:
        result = await _send_with_retry(
            adapter,
            recipient,
            message.summary or "CallScreen Notification",
            message.content,
        )
        await _record_delivery(db, message.id, preferred_channel, recipient, result)
        results.append(result)
    else:
        logger.warning("No adapter found for channel '%s'", preferred_channel)

    # Caretaker forking
    if (
        user_settings
        and user_settings.caretaker_fork_enabled
        and user_settings.caretaker_user_id
        and _meets_priority_threshold(
            message.priority, user_settings.caretaker_fork_priority
        )
    ):
        ct_result = await db.execute(
            select(User).where(User.id == user_settings.caretaker_user_id)
        )
        caretaker = ct_result.scalars().first()
        if caretaker:
            # Fetch caretaker settings for their preferred channel
            ct_settings_result = await db.execute(
                select(UserSettings).where(
                    UserSettings.user_id == caretaker.id
                )
            )
            ct_settings = ct_settings_result.scalars().first()
            ct_channel = ct_settings.preferred_channel if ct_settings else "email"
            ct_recipient = _resolve_recipient(caretaker, ct_channel)

            ct_adapter = _get_adapter(ct_channel)
            if ct_adapter:
                ct_delivery_result = await _send_with_retry(
                    ct_adapter,
                    ct_recipient,
                    f"[Caretaker] {message.summary or 'CallScreen Notification'}",
                    message.content,
                )
                await _record_delivery(
                    db, message.id, ct_channel, ct_recipient, ct_delivery_result
                )
                results.append(ct_delivery_result)

    # Update the message aggregate status
    any_success = any(r.success for r in results)
    if any_success:
        message.delivery_status = DeliveryStatus.DELIVERED
        message.delivered_at = datetime.now(UTC)
        message.delivered_via = preferred_channel
    elif results:
        message.delivery_status = DeliveryStatus.FAILED

    await db.flush()
    return results


def _resolve_recipient(user: User, channel: str) -> str:
    """Pick the correct recipient address for a channel."""
    if channel == "email":
        return user.email
    if channel in ("sms", "telegram"):
        return user.phone_number
    # discord and others fall back to email
    return user.email


async def deliver_message_to_channel(
    message: Message,
    channel: str,
    recipient: str,
    db: AsyncSession,
) -> DeliveryResult:
    """Deliver a message through a specific channel to a specific recipient.

    Lighter-weight variant used by the forking and processor modules when
    the channel and recipient are already resolved.
    """
    adapter = _get_adapter(channel)
    if adapter is None:
        logger.error("No adapter registered for channel %s", channel)
        return DeliveryResult(
            success=False,
            channel=channel,
            recipient=recipient,
            error=f"No adapter for channel '{channel}'",
        )

    subject = f"CallScreen: {message.category.value} message ({message.priority.value})"
    body = message.summary or message.content

    delivery = MessageDelivery(
        message_id=message.id,
        channel=channel,
        recipient=recipient,
        status=DeliveryStatus.PENDING,
    )
    db.add(delivery)
    await db.flush()

    try:
        result = await adapter.send(recipient=recipient, subject=subject, body=body)
    except Exception as exc:
        logger.exception("Delivery failed for message %s via %s", message.id, channel)
        delivery.status = DeliveryStatus.FAILED  # type: ignore[assignment]
        delivery.error_message = str(exc)
        await db.flush()
        return DeliveryResult(
            success=False,
            channel=channel,
            recipient=recipient,
            error=str(exc),
        )

    now = datetime.now(UTC)
    if result.success:
        delivery.status = DeliveryStatus.DELIVERED  # type: ignore[assignment]
        delivery.sent_at = now  # type: ignore[assignment]
        delivery.delivered_at = now  # type: ignore[assignment]
    else:
        delivery.status = DeliveryStatus.FAILED  # type: ignore[assignment]
        delivery.error_message = result.error

    await db.flush()
    return DeliveryResult(
        success=result.success,
        channel=channel,
        recipient=recipient,
        error=result.error,
    )
