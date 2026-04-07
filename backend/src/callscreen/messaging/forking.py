"""Message forking service -- copies messages to a caretaker when configured."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.messaging.adapters.base import DeliveryResult
from callscreen.messaging.delivery_service import deliver_message_to_channel
from callscreen.models.message import Message, MessagePriority
from callscreen.models.settings import UserSettings

logger = logging.getLogger("callscreen.messaging.forking")

# Priority ordering: urgent > normal > low.  Lower index == higher priority.
_PRIORITY_ORDER: dict[str, int] = {
    MessagePriority.URGENT.value: 0,
    MessagePriority.NORMAL.value: 1,
    MessagePriority.LOW.value: 2,
}


def _meets_priority_threshold(
    message_priority: str,
    threshold: str,
) -> bool:
    """Return True if *message_priority* meets or exceeds *threshold*.

    "Meets or exceeds" means the message is at least as urgent as the
    configured threshold.  For example, if the threshold is ``normal``,
    both ``urgent`` and ``normal`` messages qualify, but ``low`` does not.
    """
    msg_rank = _PRIORITY_ORDER.get(message_priority, 2)
    thr_rank = _PRIORITY_ORDER.get(threshold, 0)
    return msg_rank <= thr_rank


async def fork_message_to_caretaker(
    message: Message,
    user_settings: UserSettings,
    db: AsyncSession,
) -> list[DeliveryResult]:
    """Fork a message to the caretaker if enabled and priority meets threshold.

    Returns a list of :class:`DeliveryResult` objects (one per channel attempted).
    Returns an empty list when forking is skipped.
    """
    if not user_settings.caretaker_fork_enabled:
        logger.debug("Caretaker forking disabled for user %s", user_settings.user_id)
        return []

    if user_settings.caretaker_user_id is None:
        logger.warning(
            "Caretaker forking enabled but no caretaker_user_id set for user %s",
            user_settings.user_id,
        )
        return []

    threshold = user_settings.caretaker_fork_priority or MessagePriority.URGENT.value
    if not _meets_priority_threshold(message.priority.value, threshold):
        logger.debug(
            "Message priority %s does not meet caretaker threshold %s",
            message.priority.value,
            threshold,
        )
        return []

    # Look up the caretaker's own settings to find preferred channel
    result = await db.execute(
        select(UserSettings).where(
            UserSettings.user_id == user_settings.caretaker_user_id,
        )
    )
    caretaker_settings = result.scalar_one_or_none()

    if caretaker_settings is None:
        logger.warning(
            "Caretaker user %s has no settings; cannot determine preferred channel",
            user_settings.caretaker_user_id,
        )
        return []

    channel = caretaker_settings.preferred_channel or "email"

    # Determine recipient -- we need the caretaker user's contact info.
    from callscreen.models.user import User

    user_result = await db.execute(
        select(User).where(User.id == user_settings.caretaker_user_id)
    )
    caretaker_user = user_result.scalar_one_or_none()
    if caretaker_user is None:
        logger.warning("Caretaker user %s not found", user_settings.caretaker_user_id)
        return []

    recipient = caretaker_user.email  # default for email channel
    if channel == "sms":
        recipient = caretaker_user.phone_number

    delivery_result = await deliver_message_to_channel(
        message=message,
        channel=channel,
        recipient=recipient,
        db=db,
    )
    return [delivery_result]
