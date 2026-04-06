"""Emergency number detection - LIFE-SAFETY CRITICAL.

This module must operate with ZERO external dependencies (no database,
no cache, no network calls). Emergency callbacks receive unconditional
immediate forwarding with no screening.
"""

import re

# Hardcoded emergency number patterns - NEVER require DB lookup
_EMERGENCY_EXACT = frozenset({
    "911",
    "933",  # 911 test line
    "+1911",
    "+1933",
})

# Known PSAP and emergency service patterns (US-focused)
_EMERGENCY_PREFIXES = (
    "+1800222",  # Poison Control (1-800-222-1222)
    "+1800273",  # Suicide Prevention (1-800-273-8255)
    "+1988",     # Suicide & Crisis Lifeline
)

# Configurable local emergency numbers (immutable defaults + user additions)
_local_emergency_numbers: set[str] = set()


def is_emergency_number(phone_number: str) -> bool:
    """Check if a number is an emergency service number.

    Returns True for 911, known PSAP numbers, and configured emergency numbers.
    This check must be INSTANT with zero external dependencies.
    """
    # Strip formatting
    cleaned = re.sub(r"[^\d+]", "", phone_number)

    # Exact match
    if cleaned in _EMERGENCY_EXACT:
        return True

    # Just digits for 3-digit checks
    digits = re.sub(r"\D", "", cleaned)
    if digits in ("911", "933"):
        return True

    # Prefix match
    for prefix in _EMERGENCY_PREFIXES:
        if cleaned.startswith(prefix):
            return True

    # Configurable local numbers
    if cleaned in _local_emergency_numbers:
        return True

    return False


def add_local_emergency_number(phone_number: str) -> None:
    """Add a local emergency number (e.g., local police non-emergency).

    These are additive only - default emergency numbers cannot be removed.
    """
    cleaned = re.sub(r"[^\d+]", "", phone_number)
    _local_emergency_numbers.add(cleaned)


def get_emergency_numbers() -> set[str]:
    """Return all configured emergency numbers for display/audit."""
    return set(_EMERGENCY_EXACT) | set(_EMERGENCY_PREFIXES) | _local_emergency_numbers
