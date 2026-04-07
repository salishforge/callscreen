"""SendGrid email adapter."""

import base64
import logging
from datetime import UTC, datetime

import httpx

from callscreen.config import get_settings
from callscreen.messaging.adapters.base import DeliveryResult, MessageAdapter

logger = logging.getLogger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


class EmailAdapter(MessageAdapter):
    """Sends messages via SendGrid API using httpx."""

    adapter_name: str = "email"

    async def send(
        self, recipient: str, subject: str, body: str, **kwargs: object
    ) -> DeliveryResult:
        """Send an email through SendGrid.

        Args:
            recipient: Email address.
            subject: Email subject line.
            body: Plain-text body.
            **kwargs: Optional keys:
                html_body (str): HTML version of the body.
                audio_data (bytes): Raw audio file bytes for attachment.
                audio_filename (str): Filename for the audio attachment.
        """
        settings = get_settings()

        html_body = kwargs.get("html_body")
        audio_data: bytes | None = kwargs.get("audio_data")  # type: ignore[assignment]
        audio_filename: str = kwargs.get("audio_filename", "voicemail.wav")  # type: ignore[assignment]

        content_parts = [{"type": "text/plain", "value": body}]
        if html_body:
            content_parts.append({"type": "text/html", "value": str(html_body)})

        payload: dict = {
            "personalizations": [{"to": [{"email": recipient}]}],
            "from": {"email": settings.sendgrid_from_email},
            "subject": subject,
            "content": content_parts,
        }

        if audio_data:
            encoded = base64.b64encode(audio_data).decode("utf-8")
            payload["attachments"] = [
                {
                    "content": encoded,
                    "filename": str(audio_filename),
                    "type": "audio/wav",
                    "disposition": "attachment",
                }
            ]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    SENDGRID_API_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {settings.sendgrid_api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )

            if response.status_code in (200, 201, 202):
                message_id = response.headers.get("X-Message-Id")
                return DeliveryResult(
                    success=True,
                    adapter_name=self.adapter_name,
                    message_id=message_id,
                    delivered_at=datetime.now(UTC),
                )

            error_text = response.text
            logger.error("SendGrid API error %s: %s", response.status_code, error_text)
            return DeliveryResult(
                success=False,
                adapter_name=self.adapter_name,
                error=f"SendGrid returned {response.status_code}: {error_text}",
            )

        except httpx.HTTPError as exc:
            logger.exception("SendGrid request failed")
            return DeliveryResult(
                success=False,
                adapter_name=self.adapter_name,
                error=str(exc),
            )

    async def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.sendgrid_api_key)
