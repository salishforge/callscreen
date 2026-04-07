"""Twilio Lookup v2 provider for carrier info, CNAM, and line type."""

import logging
from base64 import b64encode

import httpx

from callscreen.config import get_settings
from callscreen.intelligence.base import NumberIntelProvider, NumberIntelResult

logger = logging.getLogger("callscreen.intelligence.twilio")

TWILIO_LOOKUP_V2_URL = "https://lookups.twilio.com/v2/PhoneNumbers"

# Map Twilio line_type_intelligence values to our LineType strings
_LINE_TYPE_MAP = {
    "landline": "landline",
    "mobile": "mobile",
    "voip": "voip",
    "nonFixedVoip": "voip",
    "fixedVoip": "voip",
    "tollFree": "landline",
    "pager": "unknown",
    "personal": "mobile",
    "unknown": "unknown",
}


class TwilioLookupProvider(NumberIntelProvider):
    """Fetches carrier, CNAM, and line type from Twilio Lookup v2 API."""

    provider_name = "twilio_lookup"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_user, self._api_pass = settings.twilio_api_credentials

    def _auth_header(self) -> dict[str, str]:
        creds = b64encode(f"{self._api_user}:{self._api_pass}".encode()).decode()
        return {"Authorization": f"Basic {creds}"}

    async def is_available(self) -> bool:
        """Check whether Twilio credentials are configured."""
        return bool(self._api_user and self._api_pass)

    async def lookup(self, phone_number: str) -> NumberIntelResult:
        """Query Twilio Lookup v2 for carrier, CNAM, and line type.

        Returns partial results on error rather than raising.
        """
        result = NumberIntelResult()

        if not await self.is_available():
            logger.warning("Twilio Lookup not available: missing credentials")
            return result

        url = f"{TWILIO_LOOKUP_V2_URL}/{phone_number}"
        params = {
            "Fields": "line_type_intelligence,caller_name",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._auth_header(),
                )

            if response.status_code != 200:
                logger.error(
                    "Twilio Lookup returned %d for %s: %s",
                    response.status_code,
                    phone_number,
                    response.text[:200],
                )
                return result

            data = response.json()
            result = self._parse_response(data)

        except httpx.TimeoutException:
            logger.warning("Twilio Lookup timed out for %s", phone_number)
        except httpx.HTTPError as exc:
            logger.error("Twilio Lookup HTTP error for %s: %s", phone_number, exc)
        except Exception:
            logger.exception("Unexpected error in Twilio Lookup for %s", phone_number)

        return result

    @staticmethod
    def _parse_response(data: dict) -> NumberIntelResult:
        """Extract relevant fields from the Twilio Lookup v2 JSON response."""
        carrier_name: str | None = None
        line_type: str | None = None
        cnam: str | None = None

        # Line type intelligence
        lti = data.get("line_type_intelligence") or {}
        if lti:
            carrier_name = lti.get("carrier_name") or lti.get("mobile_network_code")
            raw_type = lti.get("type", "unknown")
            line_type = _LINE_TYPE_MAP.get(raw_type, "unknown")

        # Caller name (CNAM)
        caller_name_info = data.get("caller_name") or {}
        if caller_name_info:
            cnam = caller_name_info.get("caller_name")

        return NumberIntelResult(
            carrier_name=carrier_name,
            line_type=line_type,
            cnam=cnam,
        )
