"""Telegram Bot API adapter."""

import logging
from datetime import UTC, datetime

import httpx

from callscreen.config import get_settings
from callscreen.messaging.adapters.base import DeliveryResult, MessageAdapter

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramAdapter(MessageAdapter):
    """Sends messages via Telegram Bot API using httpx."""

    adapter_name: str = "telegram"

    async def send(
        self, recipient: str, subject: str, body: str, **kwargs: object
    ) -> DeliveryResult:
        """Send a message through Telegram.

        Args:
            recipient: Telegram chat ID (numeric string).
            subject: Used as bold header in the message.
            body: Message text (supports Markdown).
            **kwargs: Optional keys:
                audio_url (str): URL to an audio file to send via sendAudio.
                parse_mode (str): Telegram parse mode (default "Markdown").
        """
        settings = get_settings()
        token = settings.telegram_bot_token
        parse_mode = kwargs.get("parse_mode", "Markdown")
        audio_url: str | None = kwargs.get("audio_url")  # type: ignore[assignment]

        formatted = f"*{subject}*\n{body}" if subject else body

        try:
            async with httpx.AsyncClient() as client:
                # Send the text message
                response = await client.post(
                    f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
                    json={
                        "chat_id": recipient,
                        "text": formatted,
                        "parse_mode": str(parse_mode),
                    },
                    timeout=30.0,
                )

                if response.status_code != 200 or not response.json().get("ok"):
                    error_text = response.text
                    logger.error("Telegram API error %s: %s", response.status_code, error_text)
                    return DeliveryResult(
                        success=False,
                        adapter_name=self.adapter_name,
                        error=f"Telegram returned {response.status_code}: {error_text}",
                    )

                result_data = response.json().get("result", {})
                message_id = str(result_data.get("message_id", ""))

                # If there is an audio file, send it as well
                if audio_url:
                    await client.post(
                        f"{TELEGRAM_API_BASE}/bot{token}/sendAudio",
                        json={
                            "chat_id": recipient,
                            "audio": str(audio_url),
                        },
                        timeout=30.0,
                    )

            return DeliveryResult(
                success=True,
                adapter_name=self.adapter_name,
                message_id=message_id,
                delivered_at=datetime.now(UTC),
            )

        except httpx.HTTPError as exc:
            logger.exception("Telegram request failed")
            return DeliveryResult(
                success=False,
                adapter_name=self.adapter_name,
                error=str(exc),
            )

    async def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.telegram_bot_token)
