"""Input validation utilities for API endpoints."""

import re
from typing import Any

E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def is_valid_e164(phone: str) -> bool:
    """Validate E.164 phone number format."""
    return bool(E164_PATTERN.match(phone))


def is_valid_email(email: str) -> bool:
    """Basic email format validation."""
    return bool(EMAIL_PATTERN.match(email)) and len(email) <= 254


def is_valid_uuid(value: str) -> bool:
    """Validate UUID format."""
    return bool(UUID_PATTERN.match(value))


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize a user-provided string: strip, truncate, remove null bytes."""
    if not isinstance(value, str):
        return ""
    cleaned = value.strip()
    cleaned = cleaned.replace("\x00", "")  # Remove null bytes
    return cleaned[:max_length]


def validate_pagination(
    page: int = 1,
    per_page: int = 25,
    max_per_page: int = 100,
) -> tuple[int, int]:
    """Validate and clamp pagination parameters.

    Returns (offset, limit) tuple.
    """
    page = max(1, page)
    per_page = max(1, min(per_page, max_per_page))
    offset = (page - 1) * per_page
    return offset, per_page


def validate_sort_field(field: str, allowed: set[str]) -> str | None:
    """Validate a sort field against an allowlist to prevent SQL injection."""
    return field if field in allowed else None


def detect_injection_patterns(value: str) -> bool:
    """Detect common SQL/NoSQL injection patterns in input.

    Returns True if suspicious patterns are found.
    """
    suspicious = [
        "' OR ",
        "'; DROP",
        "1=1",
        "UNION SELECT",
        "$where",
        "$gt",
        "<script",
        "javascript:",
        "on(?:error|load|click)=",
    ]
    upper = value.upper()
    for pattern in suspicious:
        if pattern.upper() in upper:
            return True
    return False
