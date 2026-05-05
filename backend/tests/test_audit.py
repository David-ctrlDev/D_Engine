"""Tests for app.auth.audit."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from app.auth.audit import (
    AUDIT_LOGIN_FAILURE,
    AUDIT_LOGIN_SUCCESS,
    log_event,
)
from app.auth.models import AuditLog
from app.db.rls import set_request_context
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from tests.factories import make_tenant_with_owner

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

PG_INSUFFICIENT_PRIVILEGE = "42501"


async def test_log_event_writes_a_row(session: AsyncSession) -> None:
    tenant_id = uuid4()
    user_id = uuid4()
    await set_request_context(session, user_id=user_id, tenant_id=tenant_id)
    await make_tenant_with_owner(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        name="Acme",
        email="alice@acme.test",
    )

    await log_event(
        session,
        event_type=AUDIT_LOGIN_SUCCESS,
        user_id=user_id,
        tenant_id=tenant_id,
        ip="203.0.113.5",
        user_agent="Mozilla/5.0",
        metadata={"membership_count": 1},
    )
    await session.commit()

    await set_request_context(session, user_id=user_id, tenant_id=tenant_id)
    rows = (await session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.event_type == AUDIT_LOGIN_SUCCESS
    assert row.user_id == user_id
    assert row.tenant_id == tenant_id
    assert row.ip == "203.0.113.5"
    assert row.user_agent == "Mozilla/5.0"
    assert row.event_metadata == {"membership_count": 1}


async def test_log_event_allows_tenantless_failure_event(session: AsyncSession) -> None:
    """A failed login for an unknown email has no tenant context. The
    ``audit_log_insert`` policy must permit the row when the GUCs are
    null and the row's tenant_id / user_id are also null."""
    # No tenant context — both GUCs cleared.
    await set_request_context(session, user_id=None, tenant_id=None)

    await log_event(
        session,
        event_type=AUDIT_LOGIN_FAILURE,
        ip="203.0.113.5",
        user_agent="Mozilla/5.0",
        metadata={"email_attempted": "nobody@example.test"},
    )
    await session.commit()


async def test_log_event_blocks_foreign_tenant(session: AsyncSession) -> None:
    """A caller authenticated to tenant A cannot write an audit row
    attributed to tenant B."""
    a_tenant_id = uuid4()
    a_user_id = uuid4()
    await set_request_context(session, user_id=a_user_id, tenant_id=a_tenant_id)
    await make_tenant_with_owner(
        session,
        tenant_id=a_tenant_id,
        user_id=a_user_id,
        name="Acme",
        email="alice@acme.test",
    )
    await session.commit()

    await set_request_context(session, user_id=a_user_id, tenant_id=a_tenant_id)
    await log_event(
        session,
        event_type=AUDIT_LOGIN_SUCCESS,
        user_id=a_user_id,
        tenant_id=uuid4(),  # foreign tenant
        ip="203.0.113.5",
    )
    with pytest.raises(ProgrammingError) as excinfo:
        await session.flush()
    assert excinfo.value.orig.sqlstate == PG_INSUFFICIENT_PRIVILEGE  # type: ignore[union-attr]
