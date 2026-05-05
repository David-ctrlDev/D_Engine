"""Tests for app.core.security."""

from __future__ import annotations

import pytest
from app.core.security import (
    DEFAULT_TOKEN_BYTES,
    constant_time_equals,
    generate_random_token,
    hash_password,
    hash_recovery_code,
    hmac_token,
    verify_password,
    verify_recovery_code,
)

# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------


def test_hash_password_returns_bcrypt_string() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    # bcrypt output is always 60 chars
    assert len(hashed) == 60


def test_verify_password_accepts_correct_and_rejects_wrong() -> None:
    plain = "correct horse battery staple"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong password", hashed) is False


def test_hash_password_is_salted_and_nondeterministic() -> None:
    """Two hashes of the same plaintext must differ — a deterministic hash
    would let an attacker correlate users with identical passwords across
    a leaked DB dump."""
    plain = "correct horse battery staple"
    assert hash_password(plain) != hash_password(plain)


# ---------------------------------------------------------------------------
# Recovery codes (same backend, separate API surface)
# ---------------------------------------------------------------------------


def test_recovery_code_roundtrip() -> None:
    code = "ABCD-EFGH-1234"
    hashed = hash_recovery_code(code)
    assert verify_recovery_code(code, hashed) is True
    assert verify_recovery_code("WRONG-CODE-9999", hashed) is False


# ---------------------------------------------------------------------------
# Random opaque tokens
# ---------------------------------------------------------------------------


def test_generate_random_token_default_length() -> None:
    token = generate_random_token()
    # token_urlsafe(32) yields ~43 chars (4 * ceil(32 / 3) without padding)
    assert len(token) >= 40
    # Two calls must not collide
    assert token != generate_random_token()


def test_generate_random_token_custom_length() -> None:
    short = generate_random_token(num_bytes=8)
    assert len(short) >= 10  # 4 * ceil(8/3) = 12, but '=' is stripped
    assert short != generate_random_token(num_bytes=8)


@pytest.mark.parametrize("num_bytes", [8, 16, DEFAULT_TOKEN_BYTES, 64])
def test_generate_random_token_uses_urlsafe_charset(num_bytes: int) -> None:
    token = generate_random_token(num_bytes=num_bytes)
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
    assert set(token) <= allowed


# ---------------------------------------------------------------------------
# HMAC of opaque tokens
# ---------------------------------------------------------------------------


def test_hmac_token_is_deterministic() -> None:
    token = "some-opaque-token-value"
    assert hmac_token(token) == hmac_token(token)


def test_hmac_token_differs_per_input() -> None:
    assert hmac_token("token-a") != hmac_token("token-b")


def test_hmac_token_output_format() -> None:
    digest = hmac_token("anything")
    # SHA-256 → 32 bytes → 64 hex chars
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


# ---------------------------------------------------------------------------
# Constant-time comparison
# ---------------------------------------------------------------------------


def test_constant_time_equals_matches_native_equality() -> None:
    assert constant_time_equals("abc", "abc") is True
    assert constant_time_equals("abc", "abd") is False
    assert constant_time_equals("", "") is True
    assert constant_time_equals("a", "ab") is False
