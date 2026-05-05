"""Test data factories.

These helpers do **not** manage RLS context — the caller must call
``set_request_context`` (or its underlying helpers) before invoking a
factory so that ``WITH CHECK`` clauses pass. Keeping factories
context-agnostic makes intent explicit at every call site.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from app.auth.models import (
    Tenant,
    TenantMembership,
    TenantRole,
    User,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _slug(name: str) -> str:
    return name.lower().replace(" ", "-")


async def make_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    name: str = "Acme",
    slug: str | None = None,
) -> Tenant:
    tenant = Tenant(
        id=tenant_id or uuid4(),
        name=name,
        slug=slug or f"{_slug(name)}-{uuid4().hex[:8]}",
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def make_user(
    session: AsyncSession,
    *,
    user_id: UUID | None = None,
    email: str | None = None,
    hashed_password: str = "$2b$12$placeholderplaceholderplaceholderplaceholderplaceholder",  # noqa: S107  test fixture: this is a hash placeholder, not a real password
    is_verified: bool = True,
    is_active: bool = True,
) -> User:
    user = User(
        id=user_id or uuid4(),
        email=email or f"user-{uuid4().hex[:8]}@example.com",
        hashed_password=hashed_password,
        is_active=is_active,
        is_verified=is_verified,
    )
    session.add(user)
    await session.flush()
    return user


async def make_membership(
    session: AsyncSession,
    *,
    user: User,
    tenant: Tenant,
    role: TenantRole = TenantRole.owner,
) -> TenantMembership:
    membership = TenantMembership(user_id=user.id, tenant_id=tenant.id, role=role)
    session.add(membership)
    await session.flush()
    return membership


async def make_tenant_with_owner(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    name: str = "Acme",
    email: str | None = None,
) -> tuple[Tenant, User, TenantMembership]:
    """Create a tenant + an owner user + the owner membership in one shot.

    ``tenant_id`` and ``user_id`` are required because RLS ``WITH CHECK``
    clauses verify the inserted IDs match the active GUCs. The caller must
    have called ``set_request_context(session, user_id, tenant_id)`` with
    these same values *before* invoking the factory.
    """
    tenant = await make_tenant(session, tenant_id=tenant_id, name=name)
    user = await make_user(session, user_id=user_id, email=email)
    membership = await make_membership(session, user=user, tenant=tenant, role=TenantRole.owner)
    return tenant, user, membership
