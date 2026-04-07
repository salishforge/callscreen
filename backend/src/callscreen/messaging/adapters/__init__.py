"""Messaging adapters package."""

from callscreen.messaging.adapters.base import DeliveryResult, MessageAdapter
from callscreen.messaging.adapters.discord_adapter import DiscordAdapter
from callscreen.messaging.adapters.email_adapter import EmailAdapter
from callscreen.messaging.adapters.sms_adapter import SMSAdapter
from callscreen.messaging.adapters.telegram_adapter import TelegramAdapter

__all__ = [
    "DeliveryResult",
    "DiscordAdapter",
    "EmailAdapter",
    "MessageAdapter",
    "SMSAdapter",
    "TelegramAdapter",
]
