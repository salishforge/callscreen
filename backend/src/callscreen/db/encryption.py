"""Field-level AES-256-GCM encryption for sensitive data."""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from callscreen.config import get_settings

_NONCE_SIZE = 12  # 96-bit nonce for AES-GCM


def _get_key() -> bytes:
    settings = get_settings()
    raw = settings.callscreen_encryption_key
    try:
        key = base64.b64decode(raw)
    except Exception:
        key = raw.encode("utf-8")[:32].ljust(32, b"\0")
    if len(key) != 32:
        key = key[:32].ljust(32, b"\0")
    return key


def encrypt_field(plaintext: str) -> str:
    """Encrypt a string field using AES-256-GCM. Returns base64-encoded ciphertext."""
    key = _get_key()
    nonce = os.urandom(_NONCE_SIZE)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_field(encrypted: str) -> str:
    """Decrypt a base64-encoded AES-256-GCM ciphertext back to string."""
    key = _get_key()
    raw = base64.b64decode(encrypted)
    nonce = raw[:_NONCE_SIZE]
    ciphertext = raw[_NONCE_SIZE:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
