"""Tests for authentication and JWT token handling."""

import pytest

from callscreen.security.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    @pytest.mark.unit
    def test_hash_and_verify(self):
        password = "secure_password_123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    @pytest.mark.unit
    def test_wrong_password_fails(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    @pytest.mark.unit
    def test_different_hashes_for_same_password(self):
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2  # bcrypt uses random salt


class TestJWTTokens:
    @pytest.mark.unit
    def test_create_and_decode_access_token(self):
        token = create_access_token(user_id="test-user-id", role="admin")
        payload = decode_token(token)
        assert payload["sub"] == "test-user-id"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    @pytest.mark.unit
    def test_create_and_decode_refresh_token(self):
        token = create_refresh_token(user_id="test-user-id")
        payload = decode_token(token)
        assert payload["sub"] == "test-user-id"
        assert payload["type"] == "refresh"

    @pytest.mark.unit
    def test_invalid_token_raises(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_token("invalid.token.here")
        assert exc_info.value.status_code == 401

    @pytest.mark.unit
    def test_token_contains_expiry(self):
        token = create_access_token(user_id="test", role="user")
        payload = decode_token(token)
        assert "exp" in payload
        assert "iat" in payload
