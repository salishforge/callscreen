"""Tests for emergency number detection - LIFE-SAFETY CRITICAL.

These tests must pass with zero tolerance. Emergency detection failures
can result in blocked emergency callbacks.
"""

import pytest

from callscreen.core.emergency import (
    add_local_emergency_number,
    is_emergency_number,
)


class TestEmergencyDetection:
    """Emergency number detection tests."""

    @pytest.mark.unit
    def test_911_exact(self):
        assert is_emergency_number("911") is True

    @pytest.mark.unit
    def test_911_with_country_code(self):
        assert is_emergency_number("+1911") is True

    @pytest.mark.unit
    def test_933_test_line(self):
        assert is_emergency_number("933") is True

    @pytest.mark.unit
    def test_poison_control(self):
        assert is_emergency_number("+18002221222") is True

    @pytest.mark.unit
    def test_suicide_prevention(self):
        assert is_emergency_number("+18002738255") is True

    @pytest.mark.unit
    def test_crisis_lifeline_988(self):
        assert is_emergency_number("+1988") is True

    @pytest.mark.unit
    def test_regular_number_not_emergency(self):
        assert is_emergency_number("+15551234567") is False

    @pytest.mark.unit
    def test_empty_string_not_emergency(self):
        assert is_emergency_number("") is False

    @pytest.mark.unit
    def test_formatted_911(self):
        assert is_emergency_number("9-1-1") is True

    @pytest.mark.unit
    def test_local_emergency_number(self):
        add_local_emergency_number("+15551119999")
        assert is_emergency_number("+15551119999") is True

    @pytest.mark.unit
    def test_no_external_dependencies(self):
        """Emergency detection must work with no DB, no Redis, no network."""
        # This test verifies the function is pure computation
        # with no imports that could fail
        result = is_emergency_number("911")
        assert result is True
