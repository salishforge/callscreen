"""Phone number normalization utilities."""

import re


def normalize_e164(number: str) -> str:
    """Normalize a phone number to E.164 format.

    Strips non-digit characters (except leading +), ensures + prefix.
    Returns the normalized number or raises ValueError for invalid input.
    """
    cleaned = re.sub(r"[^\d+]", "", number)
    if not cleaned:
        raise ValueError(f"Invalid phone number: {number}")

    if not cleaned.startswith("+"):
        # Assume US/Canada if 10 digits
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) == 10:
            cleaned = f"+1{digits}"
        elif len(digits) == 11 and digits.startswith("1"):
            cleaned = f"+{digits}"
        else:
            cleaned = f"+{digits}"

    digits_only = cleaned[1:]
    if not digits_only.isdigit() or len(digits_only) < 7 or len(digits_only) > 15:
        raise ValueError(f"Invalid phone number: {number}")

    return cleaned


def mask_number(number: str) -> str:
    """Mask a phone number for display, showing only last 4 digits."""
    if len(number) <= 4:
        return "****"
    return "*" * (len(number) - 4) + number[-4:]
