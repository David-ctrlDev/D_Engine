"""Model + Row-Level Security invariants.

These tests are the contract that everything downstream relies on: if any
of them ever fail, the application's tenant isolation guarantee is broken.
They exercise the database directly (no service / endpoint layer).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from app.auth.models import (
    AuditLog,
    MFAMethod,
    MFAMethodType,
    Tenant,
    TenantMembership,
    TenantRole,
    User,
)
from app.db.rls import clear_request_context, set_request_context
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, ProgrammingError

from tests.factories import make_membership, make_tenant, make_tenant_with_owner, make_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Postgres pgcode for RLS WITH CHECK violations and other privilege errors.
PG_INSUFFICIENT_PRIVILEGE = "42501"


async def _seed_two_tenants(
    session: AsyncSession,
) -> tuple[
    tuple[Tenant, User, TenantMembership],
    tuple[Tenant, User, TenantMembership],
]:
    """Create two complete (tenant, owner, membership) triples in isolation."""
    # ----- Tenant A -----
    tenant_a_id = uuid4()
    user_a_id = uuid4()
    await set_request_context(session, user_id=user_a_id, tenant_id=tenant_a_id)
    a_tenant = await make_tenant(session, tenant_id=tenant_a_id, name="Acme")
    a_user = await make_user(session, user_id=user_a_id, email="alice@acme.test")
    a_membership = await make_membership(
        session, user=a_user, tenant=a_tenant, role=TenantRole.owner
    )
    await session.commit()

    # ----- Tenant B -----
    tenant_b_id = uuid4()
    user_b_id = uuid4()
    await set_request_context(session, user_id=user_b_id, tenant_id=tenant_b_id)
    b_tenant = await make_tenant(session, tenant_id=tenant_b_id, name="Globex")
    b_user = await make_user(session, user_id=user_b_id, email="bob@globex.test")
    b_membership = await make_membership(
        session, user=b_user, tenant=b_tenant, role=TenantRole.owner
    )
    await session.commit()

    await clear_request_context(session)
    await session.commit()
    return (a_tenant, a_user, a_membership), (b_tenant, b_user, b_membership)


# ----------------------------------------------------------------------------
# Bootstrap: registration-flow inserts succeed when GUCs are pre-set
# ----------------------------------------------------------------------------


async def test_registration_inserts_succeed_with_guc_set(session: AsyncSession) -> None:
    """The pattern (set GUCs → insert tenant + user + membership) must work.

    This is the actual flow the registration endpoint will use.
    """
    tenant_id = uuid4()
    user_id = uuid4()
    await set_request_context(session, user_id=user_id, tenant_id=tenant_id)

    await make_tenant_with_owner(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        name="Initech",
        email="peter@initech.test",
    )
    await session.commit()

    # GUCs set with is_local=true reset on COMMIT — re-bind for the next read.
    await set_request_context(session, user_id=user_id, tenant_id=tenant_id)
    tenants = (await session.execute(select(Tenant))).scalars().all()
    memberships = (await session.execute(select(TenantMembership))).scalars().all()
    assert len(tenants) == 1
    assert len(memberships) == 1


async def test_tenant_insert_blocked_when_guc_does_not_match(
    session: AsyncSession,
) -> None:
    """RLS WITH CHECK rejects inserts whose ``id`` does not match
    ``app.current_tenant``."""
    tenant_id = uuid4()
    other_id = uuid4()
    await set_request_context(session, user_id=uuid4(), tenant_id=tenant_id)
    session.add(Tenant(id=other_id, name="Mismatched", slug="mismatched"))
    with pytest.raises(ProgrammingError) as excinfo:
        await session.flush()
    assert excinfo.value.orig.sqlstate == PG_INSUFFICIENT_PRIVILEGE  # type: ignore[union-attr]


# ----------------------------------------------------------------------------
# Tenant isolation: SELECT
# ----------------------------------------------------------------------------


async def test_select_tenants_returns_only_visible_to_user(
    session: AsyncSession,
) -> None:
    a, b = await _seed_two_tenants(session)
    a_tenant, a_user, _ = a
    _b_tenant, _, _ = b

    # Authenticated as A: see only tenant A.
    await set_request_context(session, user_id=a_user.id, tenant_id=a_tenant.id)
    rows = (await session.execute(select(Tenant))).scalars().all()
    assert {t.id for t in rows} == {a_tenant.id}


async def test_select_tenant_memberships_blocks_cross_tenant_view(
    session: AsyncSession,
) -> None:
    a, b = await _seed_two_tenants(session)
    a_tenant, a_user, a_membership = a
    _, _, b_membership = b

    await set_request_context(session, user_id=a_user.id, tenant_id=a_tenant.id)
    rows = (await session.execute(select(TenantMembership))).scalars().all()
    ids = {m.id for m in rows}
    assert a_membership.id in ids
    assert b_membership.id not in ids


async def test_select_with_no_context_returns_zero_rows(session: AsyncSession) -> None:
    """Defense in depth: if the middleware ever forgets to set GUCs, RLS
    still hides every row."""
    await _seed_two_tenants(session)
    await clear_request_context(session)

    tenants = (await session.execute(select(Tenant))).scalars().all()
    memberships = (await session.execute(select(TenantMembership))).scalars().all()
    audit = (await session.execute(select(AuditLog))).scalars().all()
    assert tenants == [] and memberships == [] and audit == []


# ----------------------------------------------------------------------------
# Tenant isolation: cross-tenant write attempts
# ----------------------------------------------------------------------------


async def test_cross_tenant_update_silently_filters(session: AsyncSession) -> None:
    """``UPDATE`` against a foreign tenant's row reports zero rowcount —
    the row is invisible to the policy, so the WHERE matches nothing.

    Note: ``synchronize_session=False`` is essential here. With the default
    ``"auto"`` strategy, SQLAlchemy evaluates the WHERE clause in Python and
    eagerly updates matching instances in the session's identity map — even
    if RLS blocks the actual DB write. That would mask isolation bugs.
    Production service code that does bulk DML against RLS-protected tables
    must follow the same pattern.
    """
    a, b = await _seed_two_tenants(session)
    a_tenant, a_user, _ = a
    b_tenant, b_user, _ = b
    # Snapshot UUIDs before expiring the identity map — accessing attributes
    # of expired instances would trigger an async lazy-load in the wrong place.
    a_tenant_id, a_user_id = a_tenant.id, a_user.id
    b_tenant_id, b_user_id = b_tenant.id, b_user.id

    await set_request_context(session, user_id=a_user_id, tenant_id=a_tenant_id)
    result = await session.execute(
        update(Tenant)
        .where(Tenant.id == b_tenant_id)
        .values(name="HACKED")
        .execution_options(synchronize_session=False)
    )
    assert result.rowcount == 0  # type: ignore[attr-defined]
    await session.commit()
    session.expire_all()

    await set_request_context(session, user_id=b_user_id, tenant_id=b_tenant_id)
    fetched = (await session.execute(select(Tenant).where(Tenant.id == b_tenant_id))).scalar_one()
    assert fetched.name == "Globex"


async def test_cross_tenant_delete_silently_filters(session: AsyncSession) -> None:
    a, b = await _seed_two_tenants(session)
    a_tenant, a_user, _ = a
    b_tenant, b_user, _ = b
    a_tenant_id, a_user_id = a_tenant.id, a_user.id
    b_tenant_id, b_user_id = b_tenant.id, b_user.id

    await set_request_context(session, user_id=a_user_id, tenant_id=a_tenant_id)
    result = await session.execute(
        delete(Tenant).where(Tenant.id == b_tenant_id).execution_options(synchronize_session=False)
    )
    assert result.rowcount == 0  # type: ignore[attr-defined]
    await session.commit()
    session.expire_all()

    await set_request_context(session, user_id=b_user_id, tenant_id=b_tenant_id)
    fetched = (await session.execute(select(Tenant).where(Tenant.id == b_tenant_id))).scalar_one()
    assert fetched.id == b_tenant_id


async def test_cross_tenant_membership_insert_rejected(session: AsyncSession) -> None:
    """An attacker authenticated to tenant A cannot create a membership
    that grants their user access to tenant B."""
    a, b = await _seed_two_tenants(session)
    a_tenant, a_user, _ = a
    b_tenant, _, _ = b

    await set_request_context(session, user_id=a_user.id, tenant_id=a_tenant.id)
    session.add(TenantMembership(user_id=a_user.id, tenant_id=b_tenant.id, role=TenantRole.member))
    with pytest.raises(ProgrammingError) as excinfo:
        await session.flush()
    assert excinfo.value.orig.sqlstate == PG_INSUFFICIENT_PRIVILEGE  # type: ignore[union-attr]


# ----------------------------------------------------------------------------
# Membership listing for the workspace picker
# ----------------------------------------------------------------------------


async def test_user_can_see_their_memberships_across_tenants(
    session: AsyncSession,
) -> None:
    """Foundation for the workspace picker: a user with memberships in
    multiple tenants can list all of them with only ``current_user`` set."""
    # Seed two separate tenants...
    (a_tenant, a_user, _), (b_tenant, _, _) = await _seed_two_tenants(session)

    # ...then add a second membership for a_user in b_tenant.
    await set_request_context(session, user_id=a_user.id, tenant_id=b_tenant.id)
    await make_membership(session, user=a_user, tenant=b_tenant, role=TenantRole.member)
    await session.commit()

    # With only current_user set (no active workspace yet), the user sees
    # both their memberships.
    await set_request_context(session, user_id=a_user.id, tenant_id=None)
    rows = (await session.execute(select(TenantMembership))).scalars().all()
    assert {m.tenant_id for m in rows} == {a_tenant.id, b_tenant.id}


# ----------------------------------------------------------------------------
# Audit log: append-only + tenant isolation
# ----------------------------------------------------------------------------


async def test_audit_log_insert_with_foreign_tenant_id_rejected(
    session: AsyncSession,
) -> None:
    a, b = await _seed_two_tenants(session)
    a_tenant, a_user, _ = a
    b_tenant, _, _ = b

    await set_request_context(session, user_id=a_user.id, tenant_id=a_tenant.id)
    session.add(
        AuditLog(
            tenant_id=b_tenant.id,
            user_id=a_user.id,
            event_type="login_success",
            event_metadata={"smuggled": True},
        )
    )
    with pytest.raises(ProgrammingError) as excinfo:
        await session.flush()
    assert excinfo.value.orig.sqlstate == PG_INSUFFICIENT_PRIVILEGE  # type: ignore[union-attr]


async def test_audit_log_update_denied_no_policy(session: AsyncSession) -> None:
    """No UPDATE policy exists — the table is append-only by RLS design."""
    (a_tenant, a_user, _), _ = await _seed_two_tenants(session)
    await set_request_context(session, user_id=a_user.id, tenant_id=a_tenant.id)
    session.add(
        AuditLog(
            tenant_id=a_tenant.id,
            user_id=a_user.id,
            event_type="login_success",
        )
    )
    await session.commit()

    await set_request_context(session, user_id=a_user.id, tenant_id=a_tenant.id)
    result = await session.execute(update(AuditLog).values(event_type="tampered"))
    assert result.rowcount == 0  # type: ignore[attr-defined]


# ----------------------------------------------------------------------------
# User-scoped tables: no RLS, so no GUC needed (smoke test)
# ----------------------------------------------------------------------------


async def test_user_scoped_tables_have_no_rls(session: AsyncSession) -> None:
    """``users``, ``mfa_methods``, etc. are NOT protected by RLS — they rely
    on app-level ``user_id`` filters. This test pins that decision so a future
    migration that adds RLS to these tables forces an explicit review."""
    await set_request_context(session, user_id=uuid4(), tenant_id=uuid4())

    expect_rls: dict[str, bool] = {
        "tenants": True,
        "tenant_memberships": True,
        "audit_log": True,
        "users": False,
        "mfa_methods": False,
        "mfa_recovery_codes": False,
        "refresh_tokens": False,
        "auth_tokens": False,
    }
    from sqlalchemy import text

    rows = (
        await session.execute(
            text(
                "SELECT relname, relrowsecurity FROM pg_class "
                "WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' "
                "AND relname = ANY(:names)"
            ),
            {"names": list(expect_rls.keys())},
        )
    ).all()
    actual: dict[str, bool] = {row[0]: row[1] for row in rows}
    assert actual == expect_rls


# ----------------------------------------------------------------------------
# Partial unique index: at most one TOTP per user
# ----------------------------------------------------------------------------


async def test_only_one_totp_method_per_user(session: AsyncSession) -> None:
    (a_tenant, a_user, _), _ = await _seed_two_tenants(session)
    await set_request_context(session, user_id=a_user.id, tenant_id=a_tenant.id)
    session.add(MFAMethod(user_id=a_user.id, method_type=MFAMethodType.totp, secret_encrypted=b"x"))
    await session.flush()

    session.add(MFAMethod(user_id=a_user.id, method_type=MFAMethodType.totp, secret_encrypted=b"y"))
    with pytest.raises(IntegrityError):
        await session.flush()


# ----------------------------------------------------------------------------
# Email is globally unique (option D)
# ----------------------------------------------------------------------------


async def test_email_is_globally_unique(session: AsyncSession) -> None:
    """Two users in different tenants cannot share the same email."""
    tenant_id = uuid4()
    user_id = uuid4()
    await set_request_context(session, user_id=user_id, tenant_id=tenant_id)
    await make_tenant(session, tenant_id=tenant_id, name="One")
    await make_user(session, user_id=user_id, email="dup@example.com")
    await session.commit()

    other_tenant = uuid4()
    other_user = uuid4()
    await set_request_context(session, user_id=other_user, tenant_id=other_tenant)
    await make_tenant(session, tenant_id=other_tenant, name="Two")
    session.add(User(id=other_user, email="dup@example.com", hashed_password="x"))
    with pytest.raises(IntegrityError):
        await session.flush()
