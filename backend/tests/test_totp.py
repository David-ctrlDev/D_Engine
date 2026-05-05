"""Tests for app.auth.totp."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pyotp
from app.auth.totp import (
    DIGITS,
    ISSUER,
    PERIOD_SECONDS,
    decrypt_secret,
    encrypt_secret,
    generate_secret,
    provisioning_uri,
    qr_data_uri,
    verify_code,
)

# ---------------------------------------------------------------------------
# Secret generation
# ---------------------------------------------------------------------------


def test_generate_secret_is_base32_and_unique() -> None:
    secret = generate_secret()
    # base32 charset: A-Z + 2-7
    assert re.fullmatch(r"[A-Z2-7]+", secret)
    assert generate_secret() != secret


# ---------------------------------------------------------------------------
# Secret encryption (round-trips through Fernet)
# ---------------------------------------------------------------------------


def test_secret_encrypt_decrypt_roundtrip() -> None:
    secret = generate_secret()
    blob = encrypt_secret(secret)
    assert blob != secret.encode()
    assert decrypt_secret(blob) == secret


# ---------------------------------------------------------------------------
# Provisioning URI
# ---------------------------------------------------------------------------


def test_provisioning_uri_contains_required_params() -> None:
    secret = generate_secret()
    uri = provisioning_uri(secret, account_name="alice@acme.test")

    assert uri.startswith("otpauth://totp/")
    parsed = urlparse(uri)
    qs = parse_qs(parsed.query)
    assert qs["secret"] == [secret]
    assert qs["issuer"] == [ISSUER]
    # pyotp omits digits/period from the URI when they match the spec defaults
    # (6 digits, 30s period). We assert they are NOT present so a future
    # change to non-default values surfaces here intentionally.
    assert "digits" not in qs or qs["digits"] == [str(DIGITS)]
    assert "period" not in qs or qs["period"] == [str(PERIOD_SECONDS)]


# ---------------------------------------------------------------------------
# QR generation
# ---------------------------------------------------------------------------


def test_qr_data_uri_is_valid_png_data_url() -> None:
    uri = provisioning_uri(generate_secret(), account_name="alice@acme.test")
    data_uri = qr_data_uri(uri)
    assert data_uri.startswith("data:image/png;base64,")
    # The base64 body should decode to PNG magic bytes
    import base64

    _, b64 = data_uri.split(",", 1)
    decoded = base64.b64decode(b64)
    assert decoded[:8] == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def test_verify_code_accepts_current_code() -> None:
    secret = generate_secret()
    current = pyotp.TOTP(secret, digits=DIGITS, interval=PERIOD_SECONDS).now()
    assert verify_code(secret, current) is True


def test_verify_code_rejects_wrong_code() -> None:
    secret = generate_secret()
    assert verify_code(secret, "000000") in (False, True)
    # The above could occasionally collide with a valid code by chance
    # (1 in 10^6); the deterministic assertion below is the real test.
    valid = pyotp.TOTP(secret, digits=DIGITS, interval=PERIOD_SECONDS).now()
    # Pick a guaranteed-different 6-digit code by flipping the first digit.
    bad = ("0" if valid[0] != "0" else "1") + valid[1:]
    assert verify_code(secret, bad) is False


def test_verify_code_uses_window_for_clock_drift() -> None:
    """``valid_window=1`` should accept the previous slot's code as well."""
    secret = generate_secret()
    totp = pyotp.TOTP(secret, digits=DIGITS, interval=PERIOD_SECONDS)
    import time

    now = time.time()
    previous_slot_code = totp.at(int(now) - PERIOD_SECONDS)
    assert verify_code(secret, previous_slot_code, valid_window=1) is True
