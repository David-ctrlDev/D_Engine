"""Tests for app.core.tokens."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.config import settings
from app.core.tokens import (
    TokenExpiredError,
    TokenInvalidError,
    TokenScope,
    TokenScopeMismatchError,
    create_access_token,
    create_mfa_pending_token,
    decode_token,
)
from jose import jwt

# ---------------------------------------------------------------------------
# Encoding shape
# ---------------------------------------------------------------------------


def test_access_token_carries_user_and_tenant() -> None:
    user_id = uuid4()
    tenant_id = uuid4()
    token = create_access_token(user_id=user_id, tenant_id=tenant_id)
    payload = decode_token(token, expected_scope=TokenScope.access)
    assert payload["sub"] == str(user_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["scope"] == "access"
    assert "jti" in payload
    assert "iat" in payload
    assert "exp" in payload


def test_mfa_pending_token_does_not_leak_tenant() -> None:
    user_id = uuid4()
    token = create_mfa_pending_token(user_id=user_id)
    payload = decode_token(token, expected_scope=TokenScope.mfa_pending)
    assert payload["sub"] == str(user_id)
    assert payload["scope"] == "mfa_pending"
    assert "tenant_id" not in payload


def test_each_token_has_unique_jti() -> None:
    user_id = uuid4()
    tenant_id = uuid4()
    a = create_access_token(user_id=user_id, tenant_id=tenant_id)
    b = create_access_token(user_id=user_id, tenant_id=tenant_id)
    pa = decode_token(a, expected_scope=TokenScope.access)
    pb = decode_token(b, expected_scope=TokenScope.access)
    assert pa["jti"] != pb["jti"]


# ---------------------------------------------------------------------------
# Scope enforcement
# ---------------------------------------------------------------------------


def test_decode_rejects_wrong_scope() -> None:
    """An access token presented to an mfa-pending decoder must be rejected,
    even if the signature is valid."""
    token = create_access_token(user_id=uuid4(), tenant_id=uuid4())
    with pytest.raises(TokenScopeMismatchError):
        decode_token(token, expected_scope=TokenScope.mfa_pending)


# ---------------------------------------------------------------------------
# Tampering and expiration
# ---------------------------------------------------------------------------


def test_decode_rejects_bad_signature() -> None:
    token = create_access_token(user_id=uuid4(), tenant_id=uuid4())
    # Mutate one char of the signature segment
    head, _, sig = token.rpartition(".")
    tampered = head + "." + ("A" if sig[0] != "A" else "B") + sig[1:]
    with pytest.raises(TokenInvalidError):
        decode_token(tampered, expected_scope=TokenScope.access)


def test_decode_rejects_garbage() -> None:
    with pytest.raises(TokenInvalidError):
        decode_token("not.a.jwt", expected_scope=TokenScope.access)


def test_decode_rejects_expired_token() -> None:
    """Forge a JWT with ``exp`` in the past and verify the decoder rejects it."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid4()),
        "scope": TokenScope.access.value,
        "iat": int((now - timedelta(hours=2)).timestamp()),
        "exp": int((now - timedelta(hours=1)).timestamp()),
        "jti": str(uuid4()),
        "tenant_id": str(uuid4()),
    }
    expired = jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(TokenExpiredError):
        decode_token(expired, expected_scope=TokenScope.access)


# ---------------------------------------------------------------------------
# Smoke: tokens issued back-to-back differ in time
# ---------------------------------------------------------------------------


def test_iat_advances_between_calls() -> None:
    user_id = uuid4()
    tenant_id = uuid4()
    a = decode_token(
        create_access_token(user_id=user_id, tenant_id=tenant_id),
        expected_scope=TokenScope.access,
    )
    time.sleep(1.1)
    b = decode_token(
        create_access_token(user_id=user_id, tenant_id=tenant_id),
        expected_scope=TokenScope.access,
    )
    assert b["iat"] >= a["iat"]
