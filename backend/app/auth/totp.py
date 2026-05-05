"""TOTP helpers — secret generation, otpauth URI, QR data URI, verification.

The TOTP secret never lives in plain text in the database. The flow is:

* :func:`generate_secret` returns a base32 string (RFC 4648), which is the
  format Google Authenticator and friends expect.
* :func:`encrypt_secret` wraps it in Fernet so it can be persisted to
  ``mfa_methods.secret_encrypted``.
* :func:`decrypt_secret` does the reverse on read.
* :func:`provisioning_uri` builds the ``otpauth://totp/...`` URI that
  encodes the secret + issuer + account name.
* :func:`qr_data_uri` renders that URI as a PNG and returns it as a
  ``data:`` URL the browser can render inline. Doing the QR rendering on
  the backend keeps the frontend free of any QR library dependency.
* :func:`verify_code` checks a 6-digit user-supplied code with a small
  ±30s window for clock drift.
"""

from __future__ import annotations

import base64
from io import BytesIO

import pyotp
import qrcode

from app.core.encryption import decrypt, encrypt

ISSUER = "dataprep"
DIGITS = 6
PERIOD_SECONDS = 30
DEFAULT_VALID_WINDOW = 1  # ± 30 seconds


# ---------------------------------------------------------------------------
# Secret lifecycle
# ---------------------------------------------------------------------------


def generate_secret() -> str:
    """Random base32 secret suitable for TOTP authenticators."""
    return pyotp.random_base32()


def encrypt_secret(secret: str) -> bytes:
    return encrypt(secret.encode())


def decrypt_secret(blob: bytes) -> str:
    return decrypt(blob).decode()


# ---------------------------------------------------------------------------
# Provisioning + QR
# ---------------------------------------------------------------------------


def provisioning_uri(secret: str, *, account_name: str, issuer: str = ISSUER) -> str:
    """Return the ``otpauth://totp/...`` URI used by authenticator apps."""
    return pyotp.TOTP(secret, digits=DIGITS, interval=PERIOD_SECONDS).provisioning_uri(
        name=account_name, issuer_name=issuer
    )


def qr_data_uri(uri: str) -> str:
    """Render an otpauth URI as a base64-encoded PNG ``data:`` URL.

    box_size + border are tuned for ~200x200 px display in a card.
    """
    img = qrcode.make(uri, box_size=8, border=4)
    buf = BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify_code(secret: str, code: str, *, valid_window: int = DEFAULT_VALID_WINDOW) -> bool:
    """Return True iff ``code`` matches the current TOTP for ``secret``.

    ``valid_window=1`` accepts the previous and the next 30-second slot in
    addition to the current one, tolerating ~30s of clock drift.
    """
    return pyotp.TOTP(secret, digits=DIGITS, interval=PERIOD_SECONDS).verify(
        code, valid_window=valid_window
    )
