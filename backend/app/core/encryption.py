"""Symmetric encryption for at-rest secrets (currently only TOTP seeds).

Fernet provides authenticated encryption (AES-128-CBC + HMAC-SHA256) and
includes a built-in framing format with a version byte, IV, and timestamp.
That last piece — the timestamp — lets us add a TTL later if we ever need
to rotate secrets on a deadline; for now we store secrets indefinitely so
``ttl=None`` is passed on decrypt.

Key rotation is not used in v0 (single ``FERNET_KEY``), but the encoder is
written with :class:`MultiFernet` in mind: when we add a second key, we
prepend it to the list so new ciphertexts are encrypted with the new key
while old ciphertexts can still be decrypted.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, MultiFernet

from app.config import settings


def _build_fernet() -> MultiFernet:
    primary = Fernet(settings.fernet_key.get_secret_value().encode())
    # MultiFernet today carries one key, but the call site does not change
    # the day we add a second one for rotation.
    return MultiFernet([primary])


_cipher: MultiFernet = _build_fernet()


def encrypt(plaintext: bytes) -> bytes:
    """Encrypt arbitrary bytes. Output is a URL-safe base64 token."""
    return _cipher.encrypt(plaintext)


def decrypt(token: bytes) -> bytes:
    """Decrypt a token previously produced by :func:`encrypt`.

    Raises :class:`cryptography.fernet.InvalidToken` if the token is
    tampered with or signed by a key we no longer hold.
    """
    return _cipher.decrypt(token)
