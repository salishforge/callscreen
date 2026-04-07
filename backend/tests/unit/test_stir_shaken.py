"""Tests for STIR/SHAKEN attestation parsing."""

import pytest

from callscreen.intelligence.providers.stir_shaken import parse_stir_verstat


class TestStirShakenParser:
    """Test the StirVerstat header parser."""

    def test_attestation_a(self):
        """TN-Validation-Passed-A maps to attestation level A."""
        result = parse_stir_verstat("TN-Validation-Passed-A")
        assert result.stir_attestation == "A"

    def test_attestation_b(self):
        """TN-Validation-Passed-B maps to attestation level B."""
        result = parse_stir_verstat("TN-Validation-Passed-B")
        assert result.stir_attestation == "B"

    def test_attestation_c(self):
        """TN-Validation-Passed-C maps to attestation level C."""
        result = parse_stir_verstat("TN-Validation-Passed-C")
        assert result.stir_attestation == "C"

    def test_validation_failed(self):
        """TN-Validation-Failed maps to 'failed'."""
        result = parse_stir_verstat("TN-Validation-Failed")
        assert result.stir_attestation == "failed"

    def test_no_validation(self):
        """No-TN-Validation maps to 'failed'."""
        result = parse_stir_verstat("No-TN-Validation")
        assert result.stir_attestation == "failed"

    def test_none_input(self):
        """None input returns None attestation."""
        result = parse_stir_verstat(None)
        assert result.stir_attestation is None

    def test_empty_string(self):
        """Empty string returns None attestation."""
        result = parse_stir_verstat("")
        assert result.stir_attestation is None

    def test_unknown_value(self):
        """Unrecognized value returns 'unknown'."""
        result = parse_stir_verstat("SomeRandomValue")
        assert result.stir_attestation == "unknown"

    def test_whitespace_handling(self):
        """Leading/trailing whitespace should be stripped."""
        result = parse_stir_verstat("  TN-Validation-Passed-A  ")
        assert result.stir_attestation == "A"

    def test_failed_with_level(self):
        """TN-Validation-Failed-A maps to 'failed'."""
        result = parse_stir_verstat("TN-Validation-Failed-A")
        assert result.stir_attestation == "failed"

    def test_result_is_number_intel_result(self):
        """Returned object should be a NumberIntelResult."""
        from callscreen.intelligence.base import NumberIntelResult

        result = parse_stir_verstat("TN-Validation-Passed-A")
        assert isinstance(result, NumberIntelResult)

    def test_other_fields_are_none(self):
        """Only stir_attestation should be set; other fields remain None."""
        result = parse_stir_verstat("TN-Validation-Passed-B")
        assert result.carrier_name is None
        assert result.cnam is None
        assert result.line_type is None
        assert result.community_blocklist_hit is None
