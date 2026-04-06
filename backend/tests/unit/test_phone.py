"""Tests for phone number utilities."""

import pytest

from callscreen.utils.phone import mask_number, normalize_e164


class TestNormalizeE164:
    @pytest.mark.unit
    def test_already_e164(self):
        assert normalize_e164("+15551234567") == "+15551234567"

    @pytest.mark.unit
    def test_ten_digit_us(self):
        assert normalize_e164("5551234567") == "+15551234567"

    @pytest.mark.unit
    def test_eleven_digit_us(self):
        assert normalize_e164("15551234567") == "+15551234567"

    @pytest.mark.unit
    def test_strips_formatting(self):
        assert normalize_e164("(555) 123-4567") == "+15551234567"

    @pytest.mark.unit
    def test_strips_dashes(self):
        assert normalize_e164("555-123-4567") == "+15551234567"

    @pytest.mark.unit
    def test_invalid_empty_raises(self):
        with pytest.raises(ValueError):
            normalize_e164("")

    @pytest.mark.unit
    def test_too_short_raises(self):
        with pytest.raises(ValueError):
            normalize_e164("123")

    @pytest.mark.unit
    def test_international_number(self):
        result = normalize_e164("+442071234567")
        assert result == "+442071234567"


class TestMaskNumber:
    @pytest.mark.unit
    def test_mask_full_number(self):
        assert mask_number("+15551234567") == "********4567"

    @pytest.mark.unit
    def test_mask_short_number(self):
        assert mask_number("1234") == "****"
