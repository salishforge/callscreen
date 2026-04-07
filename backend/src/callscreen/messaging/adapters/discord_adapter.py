"""Discord webhook adapter."""

import logging
from datetime import UTC, datetime

import httpx

from callscreen.config import get_settings
from callscreen.messaging.adapters.base import DeliveryResult, MessageAdapter

logger = logging.getLogger(__name__)


class DiscordAdapter(MessageAdapter):
    """Sends messages via Discord webhook URL using httpx.

    The discord_bot_token setting is used as the webhook URL.
    """

    adapter_name: str = "discord"

    async def send(
        self, recipient: str, subject: str, body: str, **kwargs: object
    ) -> DeliveryResult:
        """Send a message through a Discord webhook.

        Args:
            recipient: Discord webhook URL (overrides the default from settings if provided).
            subject: Used as the embed title.
            body: Used as the embed description.
            **kwargs: Optional keys:
                use_embed (bool): If True, sends a rich embed (default True).
                color (int): Embed sidebar colour as decimal int.
        """
        settings = get_settings()
        webhook_url = recipient or settings.discord_bot_token
        use_embed = kwargs.get("use_embed", True)
        color: int = kwargs.get("color", 0x5865F2)  # type: ignore[assignment]

        if use_embed:
            payload: dict = {
                "embeds": [
                    {
                        "title": subject,
                        "description": body,
                        "color": int(color),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ]
            }
        else:
            text = f"**{subject}**\n{body}" if subject else body
            payload = {"content": text}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    timeout=30.0,
                )

            if response.status_code in (200, 204):
                return DeliveryResult(
                    success=True,
                    adapter_name=self.adapter_name,
                    message_id=None,
                    delivered_at=datetime.now(UTC),
                )

            error_text = response.text
            logger.error("Discord webhook error %s: %s", response.status_code, error_text)
            return DeliveryResult(
                success=False,
                adapter_name=self.adapter_name,
                error=f"Discord returned {response.status_code}: {error_text}",
            )

        except httpx.HTTPError as exc:
            logger.exception("Discord webhook request failed")
            return DeliveryResult(
                success=False,
                adapter_name=self.adapter_name,
                error=str(exc),
            )

    async def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.discord_bot_token)
