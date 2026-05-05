"""Tests for app.core.encryption."""

from __future__ import annotations

import pytest
from app.core.encryption import decrypt, encrypt
from cryptography.fernet import InvalidToken


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = b"some TOTP secret"
    ciphertext = encrypt(plaintext)
    assert ciphertext != plaintext
    assert decrypt(ciphertext) == plaintext


def test_encrypt_is_nondeterministic() -> None:
    """Fernet uses a fresh IV per call: identical inputs must produce
    different ciphertexts."""
    plaintext = b"identical"
    assert encrypt(plaintext) != encrypt(plaintext)


def test_decrypt_rejects_tampered_ciphertext() -> None:
    ciphertext = encrypt(b"hello world")
    # Flip a byte in the body (skip the version + timestamp header).
    tampered = bytearray(ciphertext)
    tampered[-1] ^= 0xFF
    with pytest.raises(InvalidToken):
        decrypt(bytes(tampered))


def test_decrypt_rejects_garbage() -> None:
    with pytest.raises(InvalidToken):
        decrypt(b"not-a-fernet-token")
