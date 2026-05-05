"""Tests for app.auth.service.register + verify_email."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from app.auth import service
from app.auth.email import CapturingEmailSender
from app.auth.errors import (
    AuthTokenAlreadyUsedError,
    AuthTokenInvalidError,
    EmailAlreadyTakenError,
)
from app.auth.models import (
    AuditLog,
    AuthToken,
    AuthTokenType,
    Tenant,
    TenantMembership,
    User,
)
from app.auth.passwords import WeakPasswordError
from app.db.rls import set_request_context
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


STRONG_PASSWORD = "velvet-harbor-pumice-galaxy"


async def test_register_creates_tenant_user_membership_and_email(
    session: AsyncSession,
) -> None:
    sender = CapturingEmailSender()

    result = await service.register(
        session,
        email="alice@acme.test",
        password=STRONG_PASSWORD,
        workspace_name="Acme Inc",
        email_sender=sender,
        ip="203.0.113.5",
        user_agent="pytest",
    )
    await session.commit()

    # GUC was set inside register; we re-set after commit because is_local=true.
    await set_request_context(session, user_id=result.user_id, tenant_id=result.tenant_id)

    tenants = (await session.execute(select(Tenant))).scalars().all()
    users = (await session.execute(select(User))).scalars().all()
    memberships = (await session.execute(select(TenantMembership))).scalars().all()
    auth_tokens = (await session.execute(select(AuthToken))).scalars().all()

    assert {t.id for t in tenants} == {result.tenant_id}
    assert tenants[0].name == "Acme Inc"
    assert tenants[0].slug.startswith("acme-inc")

    assert {u.email for u in users} == {"alice@acme.test"}
    assert users[0].is_verified is False  # email not yet verified
    assert users[0].is_active is True

    assert len(memberships) == 1
    assert memberships[0].user_id == result.user_id
    assert memberships[0].tenant_id == result.tenant_id

    assert len(auth_tokens) == 1
    assert auth_tokens[0].token_type == AuthTokenType.email_verify
    assert auth_tokens[0].user_id == result.user_id

    # Email captured with the cleartext token in the link.
    assert len(sender.outbox) == 1
    assert sender.outbox[0].to == "alice@acme.test"
    assert result.verify_token in sender.outbox[0].text_body


async def test_register_normalises_email_case(session: AsyncSession) -> None:
    sender = CapturingEmailSender()
    result = await service.register(
        session,
        email="Alice@ACME.TEST",
        password=STRONG_PASSWORD,
        workspace_name="Acme",
        email_sender=sender,
    )
    await session.commit()

    await set_request_context(session, user_id=result.user_id, tenant_id=result.tenant_id)
    user = (await session.execute(select(User))).scalar_one()
    assert user.email == "alice@acme.test"


async def test_register_rejects_duplicate_email(session: AsyncSession) -> None:
    sender = CapturingEmailSender()
    await service.register(
        session,
        email="dup@example.test",
        password=STRONG_PASSWORD,
        workspace_name="First",
        email_sender=sender,
    )
    await session.commit()

    with pytest.raises(EmailAlreadyTakenError):
        await service.register(
            session,
            email="dup@example.test",
            password=STRONG_PASSWORD,
            workspace_name="Second",
            email_sender=sender,
        )


async def test_register_rejects_weak_password(session: AsyncSession) -> None:
    sender = CapturingEmailSender()
    with pytest.raises(WeakPasswordError):
        await service.register(
            session,
            email="alice@acme.test",
            password="short",
            workspace_name="Acme",
            email_sender=sender,
        )
    # Nothing should have been written.
    assert sender.outbox == []


async def test_register_writes_register_audit_event(session: AsyncSession) -> None:
    sender = CapturingEmailSender()
    result = await service.register(
        session,
        email="alice@acme.test",
        password=STRONG_PASSWORD,
        workspace_name="Acme",
        email_sender=sender,
        ip="203.0.113.5",
        user_agent="pytest",
    )
    await session.commit()

    await set_request_context(session, user_id=result.user_id, tenant_id=result.tenant_id)
    events = (await session.execute(select(AuditLog))).scalars().all()
    assert any(e.event_type == "register" for e in events)


# ---------------------------------------------------------------------------
# verify_email
# ---------------------------------------------------------------------------


async def test_verify_email_marks_user_verified_and_burns_token(
    session: AsyncSession,
) -> None:
    sender = CapturingEmailSender()
    result = await service.register(
        session,
        email="alice@acme.test",
        password=STRONG_PASSWORD,
        workspace_name="Acme",
        email_sender=sender,
    )
    await session.commit()

    user_id = await service.verify_email(session, token=result.verify_token)
    await session.commit()

    assert user_id == result.user_id

    await set_request_context(session, user_id=result.user_id, tenant_id=result.tenant_id)
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    assert user.is_verified is True

    auth_token = (await session.execute(select(AuthToken))).scalar_one()
    assert auth_token.used_at is not None


async def test_verify_email_rejects_unknown_token(session: AsyncSession) -> None:
    with pytest.raises(AuthTokenInvalidError):
        await service.verify_email(session, token="not-a-real-token")


async def test_verify_email_rejects_replay(session: AsyncSession) -> None:
    sender = CapturingEmailSender()
    result = await service.register(
        session,
        email="alice@acme.test",
        password=STRONG_PASSWORD,
        workspace_name="Acme",
        email_sender=sender,
    )
    await session.commit()

    await service.verify_email(session, token=result.verify_token)
    await session.commit()

    with pytest.raises(AuthTokenAlreadyUsedError):
        await service.verify_email(session, token=result.verify_token)
