"""Base messaging adapter interface."""

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class DeliveryResult(BaseModel):
    """Result of a message delivery attempt."""

    success: bool
    adapter_name: str = ""
    channel: str = ""
    recipient: str = ""
    message_id: str | None = None
    error: str | None = None
    delivered_at: datetime | None = None


class MessageAdapter(ABC):
    """Abstract base class for messaging adapters.

    Each adapter wraps a single delivery channel (email, SMS, Telegram, etc.)
    using httpx.AsyncClient for all external API calls.
    """

    adapter_name: str

    @abstractmethod
    async def send(
        self, recipient: str, subject: str, body: str, **kwargs: object
    ) -> DeliveryResult:
        """Send a message through this adapter.

        Args:
            recipient: Channel-specific recipient identifier
                (email address, phone number, chat ID, webhook URL).
            subject: Message subject line.
            body: Message body text.
            **kwargs: Adapter-specific options (html_body, audio_url, etc.).

        Returns:
            DeliveryResult with success status and metadata.
        """
        ...

    @abstractmethod
    async def is_configured(self) -> bool:
        """Check whether the adapter has the credentials it needs.

        Returns:
            True if the adapter can attempt delivery.
        """
        ...
