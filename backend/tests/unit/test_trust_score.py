"""Tests for composite trust score calculation."""

import pytest

from callscreen.intelligence.base import NumberIntelResult
from callscreen.intelligence.trust_score import calculate_trust_score


class TestTrustScoreCalculation:
    """Test the weighted composite trust score calculator."""

    def test_no_data_returns_neutral(self):
        """With no signals at all, score should be neutral 0.5."""
        result = NumberIntelResult()
        score = calculate_trust_score(result)
        assert score == 0.5

    def test_fully_trusted_caller(self):
        """A known medical provider with full STIR/SHAKEN A, CNAM, no blocklist."""
        result = NumberIntelResult(
            stir_attestation="A",
            carrier_name="Verizon",
            line_type="landline",
            cnam="Dr. Smith Office",
            community_blocklist_hit=False,
            ftc_complaint_count=0,
            is_medical_provider=True,
        )
        score = calculate_trust_score(result, call_count=5, has_disposition_history=True)
        assert score >= 0.85

    def test_definite_scam(self):
        """Blocklisted VoIP with failed STIR, no CNAM, many FTC complaints."""
        result = NumberIntelResult(
            stir_attestation="failed",
            carrier_name=None,
            line_type="voip",
            cnam="",
            community_blocklist_hit=True,
            ftc_complaint_count=50,
            is_medical_provider=False,
        )
        score = calculate_trust_score(result)
        assert score <= 0.2

    def test_stir_attestation_a_high_trust(self):
        """STIR/SHAKEN A attestation alone should contribute positively."""
        result = NumberIntelResult(stir_attestation="A")
        score = calculate_trust_score(result)
        assert score == 1.0

    def test_stir_attestation_c_moderate_trust(self):
        """STIR/SHAKEN C attestation is gateway level, moderate trust."""
        result = NumberIntelResult(stir_attestation="C")
        score = calculate_trust_score(result)
        assert score == 0.4

    def test_stir_failed_low_trust(self):
        """Failed STIR/SHAKEN should give low trust."""
        result = NumberIntelResult(stir_attestation="failed")
        score = calculate_trust_score(result)
        assert score <= 0.15

    def test_blocklist_hit_heavy_penalty(self):
        """Community blocklist hit should drag score down significantly."""
        result = NumberIntelResult(
            stir_attestation="B",
            community_blocklist_hit=True,
        )
        score_blocklisted = calculate_trust_score(result)

        result_clean = NumberIntelResult(
            stir_attestation="B",
            community_blocklist_hit=False,
        )
        score_clean = calculate_trust_score(result_clean)

        assert score_blocklisted < score_clean
        assert score_blocklisted < 0.5

    def test_ftc_complaints_scaling(self):
        """More FTC complaints should progressively lower the score."""
        scores = []
        for count in [0, 2, 5, 15]:
            result = NumberIntelResult(ftc_complaint_count=count)
            scores.append(calculate_trust_score(result))

        # Each step should be lower or equal
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_medical_provider_boost(self):
        """Medical providers should get higher trust than non-medical."""
        medical = NumberIntelResult(is_medical_provider=True)
        non_medical = NumberIntelResult(is_medical_provider=False)

        assert calculate_trust_score(medical) > calculate_trust_score(non_medical)

    def test_cnam_present_vs_empty(self):
        """Having a CNAM should score higher than an empty CNAM."""
        with_cnam = NumberIntelResult(cnam="John Doe")
        empty_cnam = NumberIntelResult(cnam="")

        assert calculate_trust_score(with_cnam) > calculate_trust_score(empty_cnam)

    def test_voip_lower_than_landline(self):
        """VoIP line type should score lower than landline."""
        voip = NumberIntelResult(line_type="voip")
        landline = NumberIntelResult(line_type="landline")

        assert calculate_trust_score(voip) < calculate_trust_score(landline)

    def test_call_history_positive_signal(self):
        """Call history should influence the composite score."""
        # Use signals that average around 0.5 so history's 0.7 is a net positive
        result = NumberIntelResult(
            stir_attestation="C",  # 0.4
            line_type="voip",  # 0.3
        )
        score_no_history = calculate_trust_score(result, call_count=0)
        score_with_history = calculate_trust_score(result, call_count=5, has_disposition_history=True)

        # With history (0.7) above the average of the other signals, it should lift the score
        assert score_with_history > score_no_history

    def test_score_always_between_0_and_1(self):
        """Score must be clamped to [0.0, 1.0] regardless of inputs."""
        extreme_bad = NumberIntelResult(
            stir_attestation="failed",
            line_type="voip",
            cnam="",
            community_blocklist_hit=True,
            ftc_complaint_count=100,
            is_medical_provider=False,
        )
        score = calculate_trust_score(extreme_bad, call_count=0)
        assert 0.0 <= score <= 1.0

        extreme_good = NumberIntelResult(
            stir_attestation="A",
            carrier_name="AT&T",
            line_type="landline",
            cnam="Known Caller",
            community_blocklist_hit=False,
            ftc_complaint_count=0,
            is_medical_provider=True,
        )
        score = calculate_trust_score(extreme_good, call_count=100, has_disposition_history=True)
        assert 0.0 <= score <= 1.0

    def test_mixed_signals(self):
        """Mixed positive and negative signals should produce a middle score."""
        result = NumberIntelResult(
            stir_attestation="A",  # positive
            line_type="voip",  # negative
            community_blocklist_hit=True,  # very negative
            cnam="Some Name",  # positive
            ftc_complaint_count=0,  # positive
            is_medical_provider=False,  # neutral
        )
        score = calculate_trust_score(result)
        assert 0.2 < score < 0.7

    def test_partial_data_normalizes_weights(self):
        """When only some signals are present, weights should renormalize."""
        # Only STIR attestation A available
        result_a = NumberIntelResult(stir_attestation="A")
        # Score should be high because the only signal is positive
        assert calculate_trust_score(result_a) == 1.0

        # Only blocklist hit
        result_b = NumberIntelResult(community_blocklist_hit=True)
        # Score should be low because the only signal is negative
        assert calculate_trust_score(result_b) == 0.0
