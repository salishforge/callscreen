"""AI message processor -- converts completed calls into summarized messages."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.ai.llm import classify_intent, summarize_voicemail
from callscreen.messaging.adapters.base import DeliveryResult
from callscreen.messaging.delivery_service import deliver_message_to_channel
from callscreen.messaging.forking import fork_message_to_caretaker
from callscreen.models.message import Message, MessageCategory, MessagePriority
from callscreen.models.settings import UserSettings
from callscreen.models.user import User

logger = logging.getLogger("callscreen.messaging.processor")


async def process_call_to_message(
    call_sid: str,
    transcript: str,
    caller_info: dict,
    db: AsyncSession,
) -> Message:
    """Process a completed call into a Message with AI summarization.

    Steps:
        1. Summarize the transcript via LLM.
        2. Classify intent and derive category / priority.
        3. Persist the Message row.
        4. Deliver through the user's preferred channel.
        5. Fork to caretaker if applicable.

    Args:
        call_sid: Twilio Call SID used to look up the CallRecord.
        transcript: Full call transcript text.
        caller_info: Dict with at least ``user_id`` and ``call_id``.
            May also contain ``caller_name`` and ``from_number``.
        db: Async SQLAlchemy session.

    Returns:
        The newly created and persisted :class:`Message`.
    """
    user_id = caller_info["user_id"]
    call_id = caller_info["call_id"]

    # --- AI summarisation & classification --------------------------------
    summary = await summarize_voicemail(transcript)

    classification = await classify_intent(transcript)
    raw_category = classification.get("category", "other")
    raw_priority = classification.get("priority", "normal")

    # Map to enums (with fallback)
    try:
        category = MessageCategory(raw_category)
    except ValueError:
        category = MessageCategory.OTHER

    try:
        priority = MessagePriority(raw_priority)
    except ValueError:
        priority = MessagePriority.NORMAL

    # Medical calls are always urgent
    if category == MessageCategory.MEDICAL:
        priority = MessagePriority.URGENT

    # --- Persist -----------------------------------------------------------
    message = Message(
        call_id=call_id,
        user_id=user_id,
        content=transcript,
        summary=summary,
        priority=priority,
        category=category,
    )
    db.add(message)
    await db.flush()

    # --- Deliver -----------------------------------------------------------
    settings_result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    user_settings = settings_result.scalar_one_or_none()

    if user_settings is not None:
        channel = user_settings.preferred_channel or "email"

        # Resolve recipient address
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()

        if user is not None:
            recipient = user.email
            if channel == "sms":
                recipient = user.phone_number

            try:
                await deliver_message_to_channel(
                    message=message,
                    channel=channel,
                    recipient=recipient,
                    db=db,
                )
            except Exception:
                logger.exception("Primary delivery failed for message %s", message.id)

        # --- Caretaker fork -----------------------------------------------
        try:
            await fork_message_to_caretaker(
                message=message,
                user_settings=user_settings,
                db=db,
            )
        except Exception:
            logger.exception("Caretaker fork failed for message %s", message.id)

    return message
