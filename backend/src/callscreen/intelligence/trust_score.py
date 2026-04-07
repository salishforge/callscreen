"""Composite trust score calculator.

Combines all available intelligence signals into a single 0.0-1.0 score.
Score of 0.0 = definitely scam, 1.0 = fully trusted.
"""

import logging

from callscreen.intelligence.base import NumberIntelResult

logger = logging.getLogger("callscreen.intelligence.trust_score")

# Weight allocation for each signal (must sum to 1.0)
WEIGHT_STIR_SHAKEN = 0.20
WEIGHT_CARRIER_LINE_TYPE = 0.12
WEIGHT_CNAM = 0.08
WEIGHT_COMMUNITY_BLOCKLIST = 0.15
WEIGHT_COMMUNITY_SCORE = 0.15
WEIGHT_FTC_COMPLAINTS = 0.15
WEIGHT_MEDICAL_PROVIDER = 0.10
WEIGHT_CALL_HISTORY = 0.05

# STIR/SHAKEN attestation trust values
_STIR_SCORES: dict[str | None, float] = {
    "A": 1.0,  # Full attestation: carrier verified originator
    "B": 0.7,  # Partial attestation: carrier verified call origin, not identity
    "C": 0.4,  # Gateway attestation: carrier received but cannot verify
    "failed": 0.1,  # Verification explicitly failed
    "unknown": 0.5,  # No data available, neutral
}

# Line type trust values
_LINE_TYPE_SCORES: dict[str | None, float] = {
    "landline": 0.8,
    "mobile": 0.6,
    "voip": 0.3,  # VoIP is commonly used by spammers
    "unknown": 0.5,
}


def calculate_trust_score(
    intel: NumberIntelResult,
    call_count: int = 0,
    has_disposition_history: bool = False,
    community_score: float | None = None,
) -> float:
    """Compute a weighted composite trust score from all available intelligence.

    Args:
        intel: Aggregated intelligence result with all available fields.
        call_count: Number of previous calls from this number.
        has_disposition_history: Whether there is prior user-disposition data.
        community_score: Optional community trust score (0.0-1.0) from
            community reports. None means insufficient data.

    Returns:
        Float between 0.0 (definite scam) and 1.0 (fully trusted).
    """
    weighted_sum = 0.0
    weight_total = 0.0

    # 1. STIR/SHAKEN attestation (0.20)
    stir_score = _score_stir_shaken(intel.stir_attestation)
    if stir_score is not None:
        weighted_sum += WEIGHT_STIR_SHAKEN * stir_score
        weight_total += WEIGHT_STIR_SHAKEN

    # 2. Carrier / line type (0.12)
    carrier_score = _score_carrier_line_type(intel.carrier_name, intel.line_type)
    if carrier_score is not None:
        weighted_sum += WEIGHT_CARRIER_LINE_TYPE * carrier_score
        weight_total += WEIGHT_CARRIER_LINE_TYPE

    # 3. CNAM presence (0.08)
    cnam_score = _score_cnam(intel.cnam)
    if cnam_score is not None:
        weighted_sum += WEIGHT_CNAM * cnam_score
        weight_total += WEIGHT_CNAM

    # 4. Community blocklist (0.15)
    blocklist_score = _score_blocklist(intel.community_blocklist_hit)
    if blocklist_score is not None:
        weighted_sum += WEIGHT_COMMUNITY_BLOCKLIST * blocklist_score
        weight_total += WEIGHT_COMMUNITY_BLOCKLIST

    # 5. Community score from reports (0.15)
    if community_score is not None:
        weighted_sum += WEIGHT_COMMUNITY_SCORE * community_score
        weight_total += WEIGHT_COMMUNITY_SCORE

    # 6. FTC complaints (0.15)
    ftc_score = _score_ftc_complaints(intel.ftc_complaint_count)
    if ftc_score is not None:
        weighted_sum += WEIGHT_FTC_COMPLAINTS * ftc_score
        weight_total += WEIGHT_FTC_COMPLAINTS

    # 7. Medical provider (0.10)
    medical_score = _score_medical_provider(intel.is_medical_provider)
    if medical_score is not None:
        weighted_sum += WEIGHT_MEDICAL_PROVIDER * medical_score
        weight_total += WEIGHT_MEDICAL_PROVIDER

    # 8. Call history (0.05)
    history_score = _score_call_history(call_count, has_disposition_history)
    if history_score is not None:
        weighted_sum += WEIGHT_CALL_HISTORY * history_score
        weight_total += WEIGHT_CALL_HISTORY

    # If we have no data at all, return neutral 0.5
    if weight_total == 0.0:
        logger.info("No intelligence signals available, returning neutral score")
        return 0.5

    # Normalize by actual weights used (handles partial data gracefully)
    score = weighted_sum / weight_total

    # Clamp to [0.0, 1.0]
    score = max(0.0, min(1.0, score))

    logger.debug("Composite trust score: %.3f (from %.2f weight coverage)", score, weight_total)
    return round(score, 4)


def _score_stir_shaken(attestation: str | None) -> float | None:
    """Score based on STIR/SHAKEN attestation level."""
    if attestation is None:
        return None
    return _STIR_SCORES.get(attestation, 0.5)


def _score_carrier_line_type(
    carrier_name: str | None, line_type: str | None
) -> float | None:
    """Score based on carrier and line type.

    Known carriers with landlines score highest; VoIP scores lowest.
    """
    if carrier_name is None and line_type is None:
        return None

    base = _LINE_TYPE_SCORES.get(line_type, 0.5)

    # Having a named carrier is a small positive signal
    if carrier_name:
        base = min(1.0, base + 0.1)

    return base


def _score_cnam(cnam: str | None) -> float | None:
    """Score based on caller name (CNAM) presence.

    A present CNAM is a positive signal; absence is slightly negative.
    """
    if cnam is None:
        return None
    if cnam.strip():
        return 0.8
    return 0.3


def _score_blocklist(community_blocklist_hit: bool | None) -> float | None:
    """Score based on community blocklist match.

    A blocklist hit is a strong negative signal.
    """
    if community_blocklist_hit is None:
        return None
    return 0.0 if community_blocklist_hit else 0.9


def _score_ftc_complaints(complaint_count: int | None) -> float | None:
    """Score based on FTC complaint count.

    More complaints = lower score, tapering off after ~10.
    """
    if complaint_count is None:
        return None
    if complaint_count == 0:
        return 0.9
    if complaint_count <= 2:
        return 0.6
    if complaint_count <= 5:
        return 0.3
    if complaint_count <= 10:
        return 0.1
    return 0.0


def _score_medical_provider(is_medical: bool | None) -> float | None:
    """Score based on whether the caller is a known medical provider.

    Medical providers get high trust since elderly users need these calls.
    """
    if is_medical is None:
        return None
    return 1.0 if is_medical else 0.5


def _score_call_history(call_count: int, has_disposition_history: bool) -> float | None:
    """Score based on call history with this number.

    Repeat callers with no negative history are more trusted.
    """
    if call_count == 0 and not has_disposition_history:
        return None

    if has_disposition_history:
        # If there is disposition data, slightly higher trust
        # (detailed disposition scoring would need the full history)
        return 0.7

    # Repeat calls from the same number without complaints
    if call_count >= 3:
        return 0.7
    if call_count >= 1:
        return 0.6
    return 0.5
