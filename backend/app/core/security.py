"""Cryptographic primitives used by the auth layer.

Three concerns live here, with intentionally different mechanisms:

* **Passwords** — bcrypt via passlib. Slow + salted, designed to make
  offline cracking expensive if a database dump leaks.
* **Recovery codes** — also bcrypt. They are human-readable and lower
  entropy than random tokens, so the same brute-force resistance applies.
* **Opaque server-issued tokens** (refresh tokens, email-verify tokens,
  password-reset tokens) — high-entropy random bytes hashed with HMAC-SHA256
  using the JWT signing secret as the key. We use HMAC instead of bcrypt
  because lookup is by hash equality (deterministic) and the underlying
  tokens already have ≥256 bits of entropy, so brute-force resistance is
  intrinsic; the HMAC adds protection if a DB dump leaks but the secret
  does not.

Every public function uses :func:`secrets.compare_digest` or constant-time
primitives provided by passlib / hmac, never plain ``==``.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.config import settings

# Single pwdlib hasher for both passwords and recovery codes. We pin to
# bcrypt explicitly (rather than using ``PasswordHash.recommended()`` which
# prefers argon2) to match the spec's "passwords con bcrypt" requirement.
_password_hash = PasswordHash((BcryptHasher(),))


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------


def hash_password(plain_password: str) -> str:
    """Hash a user-chosen password. Result is the full bcrypt-encoded string
    (algorithm, cost factor, salt, digest)."""
    return _password_hash.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time verification of a password against its stored hash."""
    return _password_hash.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# Recovery codes (same primitive as passwords, separate functions for clarity)
# ---------------------------------------------------------------------------


def hash_recovery_code(plain_code: str) -> str:
    return _password_hash.hash(plain_code)


def verify_recovery_code(plain_code: str, hashed_code: str) -> bool:
    return _password_hash.verify(plain_code, hashed_code)


# ---------------------------------------------------------------------------
# Opaque high-entropy tokens (refresh / email-verify / password-reset)
# ---------------------------------------------------------------------------

# 32 bytes = 256 bits of entropy, URL-safe-encoded to ~43 chars.
DEFAULT_TOKEN_BYTES = 32


def generate_random_token(num_bytes: int = DEFAULT_TOKEN_BYTES) -> str:
    """Cryptographically random URL-safe token, suitable for refresh tokens
    and the opaque tokens stored in ``auth_tokens``."""
    return secrets.token_urlsafe(num_bytes)


def hmac_token(token: str) -> str:
    """Deterministic HMAC-SHA256 of an opaque token, hex-encoded.

    Used to store tokens at rest: the database keeps only the HMAC, the
    cleartext is given to the user / placed in a cookie. On lookup we
    HMAC the incoming value and compare against the stored row.
    """
    key = settings.jwt_secret.get_secret_value().encode()
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    """Wrapper around :func:`secrets.compare_digest` for any two strings.

    Use when comparing token hashes that we have already computed locally
    (e.g. token_hashed coming from the DB vs token_hashed of the request).
    """
    return secrets.compare_digest(a, b)
