"""Tests for input validation utilities."""

import pytest

from callscreen.security.input_validation import (
    is_valid_e164,
    is_valid_email,
    is_valid_uuid,
    sanitize_string,
    validate_pagination,
    validate_sort_field,
    detect_injection_patterns,
)


class TestE164Validation:
    def test_valid_us_number(self):
        assert is_valid_e164("+15551234567") is True

    def test_valid_uk_number(self):
        assert is_valid_e164("+442071234567") is True

    def test_missing_plus(self):
        assert is_valid_e164("15551234567") is False

    def test_too_short(self):
        assert is_valid_e164("+1") is False

    def test_empty_string(self):
        assert is_valid_e164("") is False

    def test_letters_rejected(self):
        assert is_valid_e164("+1555abc4567") is False

    def test_leading_zero_country_code(self):
        assert is_valid_e164("+0551234567") is False


class TestEmailValidation:
    def test_valid_email(self):
        assert is_valid_email("user@example.com") is True

    def test_valid_complex_email(self):
        assert is_valid_email("user.name+tag@domain.co.uk") is True

    def test_missing_at(self):
        assert is_valid_email("userexample.com") is False

    def test_missing_domain(self):
        assert is_valid_email("user@") is False

    def test_empty_string(self):
        assert is_valid_email("") is False


class TestUUIDValidation:
    def test_valid_uuid(self):
        assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_uppercase_valid(self):
        assert is_valid_uuid("550E8400-E29B-41D4-A716-446655440000") is True

    def test_missing_dashes(self):
        assert is_valid_uuid("550e8400e29b41d4a716446655440000") is False

    def test_empty(self):
        assert is_valid_uuid("") is False


class TestSanitizeString:
    def test_strips_whitespace(self):
        assert sanitize_string("  hello  ") == "hello"

    def test_removes_null_bytes(self):
        assert sanitize_string("hel\x00lo") == "hello"

    def test_truncates_to_max_length(self):
        assert len(sanitize_string("a" * 2000, max_length=100)) == 100

    def test_non_string_returns_empty(self):
        assert sanitize_string(123) == ""  # type: ignore


class TestPagination:
    def test_default_values(self):
        offset, limit = validate_pagination()
        assert offset == 0
        assert limit == 25

    def test_page_2(self):
        offset, limit = validate_pagination(page=2, per_page=10)
        assert offset == 10
        assert limit == 10

    def test_clamps_negative_page(self):
        offset, limit = validate_pagination(page=-1)
        assert offset == 0

    def test_clamps_excessive_per_page(self):
        _, limit = validate_pagination(per_page=500, max_per_page=100)
        assert limit == 100


class TestSortField:
    def test_allowed_field(self):
        assert validate_sort_field("created_at", {"created_at", "name"}) == "created_at"

    def test_disallowed_field(self):
        assert validate_sort_field("password", {"created_at", "name"}) is None

    def test_injection_attempt(self):
        assert validate_sort_field("name; DROP TABLE", {"name"}) is None


class TestInjectionDetection:
    def test_sql_or_injection(self):
        assert detect_injection_patterns("' OR 1=1 --") is True

    def test_union_select(self):
        assert detect_injection_patterns("UNION SELECT * FROM users") is True

    def test_xss_script(self):
        assert detect_injection_patterns('<script>alert("xss")</script>') is True

    def test_clean_input(self):
        assert detect_injection_patterns("Dr. Smith's Office") is False

    def test_nosql_injection(self):
        assert detect_injection_patterns('{"$gt": ""}') is True

    def test_normal_text_with_apostrophe(self):
        assert detect_injection_patterns("John's pharmacy") is False
