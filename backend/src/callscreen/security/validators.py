"""Input sanitization and validation utilities."""

import re


def sanitize_html(text: str) -> str:
    """Strip HTML tags from input text."""
    return re.sub(r"<[^>]+>", "", text)


def sanitize_for_twiml(text: str) -> str:
    """Sanitize text for safe inclusion in TwiML responses."""
    replacements = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&apos;",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text
