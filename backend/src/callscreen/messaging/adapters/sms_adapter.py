"""Twilio SMS adapter."""

import logging
from datetime import UTC, datetime

import httpx

from callscreen.config import get_settings
from callscreen.messaging.adapters.base import DeliveryResult, MessageAdapter

logger = logging.getLogger(__name__)

SMS_MAX_LENGTH = 1600


class SMSAdapter(MessageAdapter):
    """Sends messages via Twilio REST API using httpx."""

    adapter_name: str = "sms"

    async def send(
        self, recipient: str, subject: str, body: str, **kwargs: object
    ) -> DeliveryResult:
        """Send an SMS through Twilio.

        Args:
            recipient: Phone number in E.164 format.
            subject: Prepended to body as a header line.
            body: Message text (truncated to 1600 chars).
        """
        settings = get_settings()

        full_text = f"{subject}\n{body}" if subject else body
        if len(full_text) > SMS_MAX_LENGTH:
            full_text = full_text[: SMS_MAX_LENGTH - 3] + "..."

        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{settings.twilio_account_sid}/Messages.json"
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    data={
                        "To": recipient,
                        "From": settings.twilio_phone_number,
                        "Body": full_text,
                    },
                    auth=settings.twilio_api_credentials,
                    timeout=30.0,
                )

            if response.status_code in (200, 201):
                data = response.json()
                return DeliveryResult(
                    success=True,
                    adapter_name=self.adapter_name,
                    message_id=data.get("sid"),
                    delivered_at=datetime.now(UTC),
                )

            error_text = response.text
            logger.error("Twilio API error %s: %s", response.status_code, error_text)
            return DeliveryResult(
                success=False,
                adapter_name=self.adapter_name,
                error=f"Twilio returned {response.status_code}: {error_text}",
            )

        except httpx.HTTPError as exc:
            logger.exception("Twilio SMS request failed")
            return DeliveryResult(
                success=False,
                adapter_name=self.adapter_name,
                error=str(exc),
            )

    async def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.twilio_account_sid and settings.twilio_auth_token)
