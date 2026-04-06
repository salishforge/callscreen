"""Tests for field-level encryption."""

import pytest

from callscreen.db.encryption import decrypt_field, encrypt_field


class TestFieldEncryption:
    @pytest.mark.unit
    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "sensitive-data-here"
        encrypted = encrypt_field(plaintext)
        assert encrypted != plaintext
        decrypted = decrypt_field(encrypted)
        assert decrypted == plaintext

    @pytest.mark.unit
    def test_different_ciphertexts_for_same_plaintext(self):
        """Each encryption uses a unique nonce, so ciphertexts differ."""
        plaintext = "same-data"
        enc1 = encrypt_field(plaintext)
        enc2 = encrypt_field(plaintext)
        assert enc1 != enc2
        assert decrypt_field(enc1) == decrypt_field(enc2) == plaintext

    @pytest.mark.unit
    def test_empty_string(self):
        encrypted = encrypt_field("")
        assert decrypt_field(encrypted) == ""

    @pytest.mark.unit
    def test_unicode_data(self):
        plaintext = "Hello, World! Nombre: Jose Garcia"
        encrypted = encrypt_field(plaintext)
        assert decrypt_field(encrypted) == plaintext

    @pytest.mark.unit
    def test_long_string(self):
        plaintext = "x" * 10000
        encrypted = encrypt_field(plaintext)
        assert decrypt_field(encrypted) == plaintext
