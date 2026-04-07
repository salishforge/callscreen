"""STIR/SHAKEN attestation parser for Twilio StirVerstat header values."""

import logging

from callscreen.intelligence.base import NumberIntelResult

logger = logging.getLogger("callscreen.intelligence.stir_shaken")

# Twilio passes STIR/SHAKEN verification results via the StirVerstat parameter.
# Values follow the pattern TN-Validation-Passed-{A|B|C} or TN-Validation-Failed etc.

_ATTESTATION_MAP: dict[str, str] = {
    "TN-Validation-Passed-A": "A",
    "TN-Validation-Passed-B": "B",
    "TN-Validation-Passed-C": "C",
}

# Values indicating the call failed STIR/SHAKEN verification
_FAILED_VALUES = frozenset(
    {
        "TN-Validation-Failed",
        "No-TN-Validation",
        "TN-Validation-Failed-A",
        "TN-Validation-Failed-B",
        "TN-Validation-Failed-C",
    }
)


def parse_stir_verstat(verstat_header: str | None) -> NumberIntelResult:
    """Parse a Twilio StirVerstat header value into a NumberIntelResult.

    This is a pure function with no external calls.

    Args:
        verstat_header: The raw StirVerstat value from Twilio, e.g.
            "TN-Validation-Passed-A".

    Returns:
        NumberIntelResult with stir_attestation set (A, B, C, failed, or unknown).
    """
    if not verstat_header:
        return NumberIntelResult(stir_attestation=None)

    cleaned = verstat_header.strip()

    # Check for passed attestation levels
    attestation = _ATTESTATION_MAP.get(cleaned)
    if attestation:
        logger.debug("STIR/SHAKEN attestation level %s for header %s", attestation, cleaned)
        return NumberIntelResult(stir_attestation=attestation)

    # Check for explicit failure
    if cleaned in _FAILED_VALUES:
        logger.debug("STIR/SHAKEN validation failed: %s", cleaned)
        return NumberIntelResult(stir_attestation="failed")

    # Unknown / unrecognized value
    logger.warning("Unrecognized StirVerstat value: %s", cleaned)
    return NumberIntelResult(stir_attestation="unknown")
