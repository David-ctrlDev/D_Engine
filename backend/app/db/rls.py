"""Row-Level Security helpers.

Postgres RLS policies read two session-local GUC (grand-unified-config)
variables:

* ``app.current_tenant`` — the active workspace UUID for the request
* ``app.current_user`` — the authenticated user UUID for the request

Both are set by the middleware in ``app.middleware.tenant_rls`` at the start
of every authenticated request. Policies on tenant-scoped tables (``tenants``,
``tenant_memberships``, ``audit_log``) compare these values against row
columns; mismatches return zero rows even on raw ``SELECT *``.

We use ``SELECT set_config(name, value, is_local := true)`` instead of
``SET LOCAL <name> = <value>`` because ``set_config`` accepts bind
parameters and we never want to interpolate user-controlled UUIDs into SQL
strings, even after type coercion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

TENANT_GUC = "app.current_tenant"
USER_GUC = "app.current_user"


async def _set_guc(session: AsyncSession, name: str, value: str) -> None:
    await session.execute(
        text("SELECT set_config(:name, :value, true)"),
        {"name": name, "value": value},
    )


async def set_tenant_context(session: AsyncSession, tenant_id: UUID | None) -> None:
    """Bind the current tenant UUID to the active transaction.

    ``tenant_id=None`` clears the variable; RLS policies then evaluate
    against an empty string and reject every tenant-scoped row.
    """
    await _set_guc(session, TENANT_GUC, "" if tenant_id is None else str(tenant_id))


async def set_user_context(session: AsyncSession, user_id: UUID | None) -> None:
    """Bind the current user UUID to the active transaction."""
    await _set_guc(session, USER_GUC, "" if user_id is None else str(user_id))


async def set_request_context(
    session: AsyncSession,
    user_id: UUID | None,
    tenant_id: UUID | None,
) -> None:
    """Set both GUCs in one call. Use this from request middleware."""
    await set_user_context(session, user_id)
    await set_tenant_context(session, tenant_id)


async def clear_request_context(session: AsyncSession) -> None:
    """Convenience wrapper for tests and request-teardown paths."""
    await set_request_context(session, user_id=None, tenant_id=None)
