"""Row-Level Security helpers.

Postgres RLS policies on tenant-scoped tables read the current tenant from a
session-local GUC (grand-unified-config) variable named ``app.current_tenant``.
The middleware in ``app.middleware.tenant_rls`` calls
:func:`set_tenant_context` at the start of each request so the variable is
available for the duration of the transaction.

We use ``SELECT set_config(name, value, is_local := true)`` instead of
``SET LOCAL <name> = <value>`` because ``set_config`` accepts bind parameters
and we never want to interpolate user-controlled UUIDs into SQL strings,
even after type coercion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

TENANT_GUC = "app.current_tenant"


async def set_tenant_context(session: AsyncSession, tenant_id: UUID | None) -> None:
    """Bind the current tenant to the active transaction.

    ``tenant_id=None`` clears the variable, which causes RLS policies to
    evaluate against the empty string and reject all rows.
    """
    value = "" if tenant_id is None else str(tenant_id)
    await session.execute(
        text("SELECT set_config(:name, :value, true)"),
        {"name": TENANT_GUC, "value": value},
    )


async def clear_tenant_context(session: AsyncSession) -> None:
    """Convenience wrapper for tests and request-teardown paths."""
    await set_tenant_context(session, None)
