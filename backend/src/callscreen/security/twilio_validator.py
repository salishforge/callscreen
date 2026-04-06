"""Twilio request signature validation."""

import logging

from fastapi import HTTPException, Request, status

from callscreen.config import get_settings

logger = logging.getLogger("callscreen.twilio")


async def validate_twilio_signature(request: Request) -> None:
    """Validate the X-Twilio-Signature header on incoming webhooks.

    In development mode, validation can be bypassed.
    """
    settings = get_settings()

    if not settings.is_production and not settings.twilio_auth_token:
        # Skip validation in dev when no auth token configured
        return

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        logger.warning("Missing Twilio signature header")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing Twilio signature",
        )

    from twilio.request_validator import RequestValidator

    validator = RequestValidator(settings.twilio_auth_token)

    # Reconstruct the full URL
    url = str(request.url)

    # Get form data
    form = await request.form()
    params = {key: str(value) for key, value in form.items()}

    if not validator.validate(url, params, signature):
        logger.warning("Invalid Twilio signature for %s", url)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature",
        )
