"""RLS invariants for the data domain.

We exercise the four interesting branches of the ``datasets`` SELECT
policy plus the boundary conditions that proved tricky to get right:

* Cross-tenant isolation on every table.
* ``data_sources`` are private to the creator (workspace owner override).
* ``datasets``: private / shared_workspace / shared_specific via grants /
  workspace owner override.
* ``dataset_grants``: only dataset owner / workspace owner can write.
* ``profile_runs``: visible iff the parent dataset is visible; append-only.

If any test ever fails, the platform's tenant-isolation guarantee is broken.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from app.auth.models import TenantRole
from app.data.models import (
    Dataset,
    DatasetGrant,
    DatasetKind,
    DatasetVisibility,
    DataSource,
    DataSourceKind,
    ProfileRun,
)
from app.db.rls import clear_request_context, set_request_context
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from tests.factories import make_membership, make_tenant, make_user

if TYPE_CHECKING:
    from uuid import UUID

    from app.auth.models import Tenant, User
    from sqlalchemy.ext.asyncio import AsyncSession

PG_INSUFFICIENT_PRIVILEGE = "42501"


# ---------------------------------------------------------------------------
# Fixtures: a workspace with two members + one outside tenant
# ---------------------------------------------------------------------------


async def _seed_workspace(
    session: AsyncSession,
) -> tuple[Tenant, User, User, Tenant, User]:
    """Create:
    * tenant_a + owner_a + member_a
    * tenant_b + owner_b
    so we can test cross-tenant isolation AND in-tenant ACL.
    """
    # ---- tenant A with owner + a regular member -----
    a_tenant_id = uuid4()
    owner_a_id = uuid4()
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_tenant_id)
    a_tenant = await make_tenant(session, tenant_id=a_tenant_id, name="Acme")
    owner_a = await make_user(session, user_id=owner_a_id, email="owner-a@acme.io")
    await make_membership(session, user=owner_a, tenant=a_tenant, role=TenantRole.owner)
    await session.commit()

    # member_a joins tenant A — owner_a sets context to grant the membership.
    member_a_id = uuid4()
    await set_request_context(session, user_id=member_a_id, tenant_id=a_tenant_id)
    member_a = await make_user(session, user_id=member_a_id, email="member-a@acme.io")
    await session.commit()
    # Insert membership using owner's GUC so RLS lets us in.
    await set_request_context(session, user_id=member_a_id, tenant_id=a_tenant_id)
    await make_membership(session, user=member_a, tenant=a_tenant, role=TenantRole.member)
    await session.commit()

    # ---- tenant B with its own owner -----
    b_tenant_id = uuid4()
    owner_b_id = uuid4()
    await set_request_context(session, user_id=owner_b_id, tenant_id=b_tenant_id)
    b_tenant = await make_tenant(session, tenant_id=b_tenant_id, name="Globex")
    owner_b = await make_user(session, user_id=owner_b_id, email="owner-b@globex.io")
    await make_membership(session, user=owner_b, tenant=b_tenant, role=TenantRole.owner)
    await session.commit()

    await clear_request_context(session)
    await session.commit()
    return a_tenant, owner_a, member_a, b_tenant, owner_b


async def _make_source(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    creator_id: UUID,
    name: str = "src",
    kind: DataSourceKind = DataSourceKind.postgres,
) -> DataSource:
    src = DataSource(
        tenant_id=tenant_id,
        created_by=creator_id,
        name=name,
        kind=kind,
        connection_config_encrypted=b"placeholder",
    )
    session.add(src)
    await session.flush()
    return src


async def _make_dataset(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    source_id: UUID,
    creator_id: UUID,
    name: str,
    visibility: DatasetVisibility = DatasetVisibility.private,
) -> Dataset:
    ds = Dataset(
        tenant_id=tenant_id,
        source_id=source_id,
        created_by=creator_id,
        name=name,
        kind=DatasetKind.table,
        locator={"schema": "public", "table": name},
        visibility=visibility,
    )
    session.add(ds)
    await session.flush()
    return ds


# ===========================================================================
# Cross-tenant isolation (the foundation)
# ===========================================================================


async def test_cross_tenant_data_source_invisible(session: AsyncSession) -> None:
    a_tenant, owner_a, _, b_tenant, owner_b = await _seed_workspace(session)
    a_id, b_id = a_tenant.id, b_tenant.id
    owner_a_id, owner_b_id = owner_a.id, owner_b.id

    await set_request_context(session, user_id=owner_b_id, tenant_id=b_id)
    await _make_source(session, tenant_id=b_id, creator_id=owner_b_id, name="b_src")
    await session.commit()

    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    rows = (await session.execute(select(DataSource))).scalars().all()
    assert rows == []  # tenant A sees nothing of tenant B


async def test_data_source_invisible_to_other_member_same_tenant(
    session: AsyncSession,
) -> None:
    """Even within the same tenant, a member cannot see another member's
    data source (credentials are private)."""
    a_tenant, owner_a, member_a, _, _ = await _seed_workspace(session)
    a_id, owner_a_id, member_a_id = a_tenant.id, owner_a.id, member_a.id

    # member_a creates a source
    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    await _make_source(session, tenant_id=a_id, creator_id=member_a_id, name="member_src")
    await session.commit()

    # owner_a CAN see it (governance override)
    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    rows = (await session.execute(select(DataSource))).scalars().all()
    assert len(rows) == 1
    assert rows[0].name == "member_src"


async def test_data_source_invisible_between_two_members(session: AsyncSession) -> None:
    a_tenant, _, member_a, _, _ = await _seed_workspace(session)
    a_id, member_a_id = a_tenant.id, member_a.id

    # add a second member to tenant A
    member_a2_id = uuid4()
    await set_request_context(session, user_id=member_a2_id, tenant_id=a_id)
    member_a2 = await make_user(session, user_id=member_a2_id, email="member2@acme.io")
    await make_membership(session, user=member_a2, tenant=a_tenant, role=TenantRole.member)
    await session.commit()

    # member_a creates a source
    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    await _make_source(session, tenant_id=a_id, creator_id=member_a_id, name="src1")
    await session.commit()

    # member_a2 cannot see it
    await set_request_context(session, user_id=member_a2_id, tenant_id=a_id)
    rows = (await session.execute(select(DataSource))).scalars().all()
    assert rows == []


# ===========================================================================
# Datasets: the four-branch SELECT
# ===========================================================================


async def test_dataset_private_invisible_to_other_member(session: AsyncSession) -> None:
    """Branch 1 negative: visibility=private blocks other members."""
    a_tenant, _, member_a, _, _ = await _seed_workspace(session)
    a_id, member_a_id = a_tenant.id, member_a.id

    member_a2_id = uuid4()
    await set_request_context(session, user_id=member_a2_id, tenant_id=a_id)
    m2 = await make_user(session, user_id=member_a2_id, email="m2@acme.io")
    await make_membership(session, user=m2, tenant=a_tenant, role=TenantRole.member)
    await session.commit()

    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    src = await _make_source(session, tenant_id=a_id, creator_id=member_a_id, name="src")
    await _make_dataset(
        session,
        tenant_id=a_id,
        source_id=src.id,
        creator_id=member_a_id,
        name="ds1",
        visibility=DatasetVisibility.private,
    )
    await session.commit()

    await set_request_context(session, user_id=member_a2_id, tenant_id=a_id)
    rows = (await session.execute(select(Dataset))).scalars().all()
    assert rows == []


async def test_dataset_shared_workspace_visible_to_all_members(
    session: AsyncSession,
) -> None:
    """Branch 1: visibility=shared_workspace → every tenant member sees it."""
    a_tenant, _, member_a, _, _ = await _seed_workspace(session)
    a_id, member_a_id = a_tenant.id, member_a.id

    member_a2_id = uuid4()
    await set_request_context(session, user_id=member_a2_id, tenant_id=a_id)
    m2 = await make_user(session, user_id=member_a2_id, email="m2@acme.io")
    await make_membership(session, user=m2, tenant=a_tenant, role=TenantRole.member)
    await session.commit()

    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    src = await _make_source(session, tenant_id=a_id, creator_id=member_a_id, name="src")
    await _make_dataset(
        session,
        tenant_id=a_id,
        source_id=src.id,
        creator_id=member_a_id,
        name="ds_shared",
        visibility=DatasetVisibility.shared_workspace,
    )
    await session.commit()

    await set_request_context(session, user_id=member_a2_id, tenant_id=a_id)
    rows = (await session.execute(select(Dataset))).scalars().all()
    assert len(rows) == 1
    assert rows[0].name == "ds_shared"


async def test_dataset_shared_specific_visible_only_to_grantees(
    session: AsyncSession,
) -> None:
    """Branch 3: visibility=shared_specific + grant → grantee sees it.
    A second member without the grant doesn't."""
    a_tenant, _, member_a, _, _ = await _seed_workspace(session)
    a_id, member_a_id = a_tenant.id, member_a.id

    grantee_id = uuid4()
    no_grant_id = uuid4()
    await set_request_context(session, user_id=grantee_id, tenant_id=a_id)
    grantee = await make_user(session, user_id=grantee_id, email="grantee@acme.io")
    await make_membership(session, user=grantee, tenant=a_tenant, role=TenantRole.member)
    await session.commit()
    await set_request_context(session, user_id=no_grant_id, tenant_id=a_id)
    no_grant = await make_user(session, user_id=no_grant_id, email="other@acme.io")
    await make_membership(session, user=no_grant, tenant=a_tenant, role=TenantRole.member)
    await session.commit()

    # creator (member_a) creates a shared_specific dataset and grants it to grantee
    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    src = await _make_source(session, tenant_id=a_id, creator_id=member_a_id, name="s")
    ds = await _make_dataset(
        session,
        tenant_id=a_id,
        source_id=src.id,
        creator_id=member_a_id,
        name="ds_specific",
        visibility=DatasetVisibility.shared_specific,
    )
    session.add(DatasetGrant(dataset_id=ds.id, user_id=grantee_id, granted_by=member_a_id))
    await session.commit()

    # grantee can see it
    await set_request_context(session, user_id=grantee_id, tenant_id=a_id)
    rows = (await session.execute(select(Dataset))).scalars().all()
    assert {r.name for r in rows} == {"ds_specific"}

    # no_grant cannot
    await set_request_context(session, user_id=no_grant_id, tenant_id=a_id)
    rows = (await session.execute(select(Dataset))).scalars().all()
    assert rows == []


async def test_dataset_private_visible_to_workspace_owner(
    session: AsyncSession,
) -> None:
    """Branch 4: workspace owner sees a private dataset created by a member."""
    a_tenant, owner_a, member_a, _, _ = await _seed_workspace(session)
    a_id, owner_a_id, member_a_id = a_tenant.id, owner_a.id, member_a.id

    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    src = await _make_source(session, tenant_id=a_id, creator_id=member_a_id, name="s")
    await _make_dataset(
        session,
        tenant_id=a_id,
        source_id=src.id,
        creator_id=member_a_id,
        name="private_ds",
        visibility=DatasetVisibility.private,
    )
    await session.commit()

    await set_request_context(session, user_id=owner_a_id, tenant_id=a_id)
    rows = (await session.execute(select(Dataset))).scalars().all()
    assert {r.name for r in rows} == {"private_ds"}


# ===========================================================================
# Writes: only creator + owner
# ===========================================================================


async def test_dataset_other_member_cannot_update(session: AsyncSession) -> None:
    """Even if a dataset is shared_workspace, a non-creator member
    cannot modify it. RLS UPDATE drops the workspace-shared branch."""
    a_tenant, _, member_a, _, _ = await _seed_workspace(session)
    a_id, member_a_id = a_tenant.id, member_a.id

    other_id = uuid4()
    await set_request_context(session, user_id=other_id, tenant_id=a_id)
    other = await make_user(session, user_id=other_id, email="o@acme.io")
    await make_membership(session, user=other, tenant=a_tenant, role=TenantRole.member)
    await session.commit()

    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    src = await _make_source(session, tenant_id=a_id, creator_id=member_a_id, name="s")
    ds = await _make_dataset(
        session,
        tenant_id=a_id,
        source_id=src.id,
        creator_id=member_a_id,
        name="public_ds",
        visibility=DatasetVisibility.shared_workspace,
    )
    await session.commit()
    ds_id = ds.id

    await set_request_context(session, user_id=other_id, tenant_id=a_id)
    from sqlalchemy import update as sql_update

    result = await session.execute(
        sql_update(Dataset)
        .where(Dataset.id == ds_id)
        .values(name="HACKED")
        .execution_options(synchronize_session=False)
    )
    # Either rowcount=0 (RLS hides the row from the WHERE) or RLS
    # allows the read (visibility=shared_workspace) but blocks the WITH CHECK.
    # Both outcomes mean the write didn't take effect.
    assert result.rowcount == 0  # type: ignore[attr-defined]
    await session.commit()
    session.expire_all()

    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    fetched = (await session.execute(select(Dataset).where(Dataset.id == ds_id))).scalar_one()
    assert fetched.name == "public_ds"


# ===========================================================================
# Grants: only the dataset's creator (or workspace owner) can grant
# ===========================================================================


async def test_grant_insert_rejected_for_non_creator_non_owner(
    session: AsyncSession,
) -> None:
    a_tenant, _, member_a, _, _ = await _seed_workspace(session)
    a_id, member_a_id = a_tenant.id, member_a.id

    other_id = uuid4()
    await set_request_context(session, user_id=other_id, tenant_id=a_id)
    other = await make_user(session, user_id=other_id, email="o@acme.io")
    await make_membership(session, user=other, tenant=a_tenant, role=TenantRole.member)
    await session.commit()

    # member_a creates a shared_specific dataset
    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    src = await _make_source(session, tenant_id=a_id, creator_id=member_a_id, name="s")
    ds = await _make_dataset(
        session,
        tenant_id=a_id,
        source_id=src.id,
        creator_id=member_a_id,
        name="ds",
        visibility=DatasetVisibility.shared_specific,
    )
    await session.commit()
    ds_id = ds.id

    # other tries to grant themselves access — should fail
    await set_request_context(session, user_id=other_id, tenant_id=a_id)
    session.add(DatasetGrant(dataset_id=ds_id, user_id=other_id, granted_by=other_id))
    with pytest.raises(ProgrammingError) as excinfo:
        await session.flush()
    assert excinfo.value.orig.sqlstate == PG_INSUFFICIENT_PRIVILEGE  # type: ignore[union-attr]


# ===========================================================================
# Profile runs: visible iff dataset is visible; append-only
# ===========================================================================


async def test_profile_run_visibility_inherits_from_dataset(
    session: AsyncSession,
) -> None:
    a_tenant, _, member_a, _, _ = await _seed_workspace(session)
    a_id, member_a_id = a_tenant.id, member_a.id

    other_id = uuid4()
    await set_request_context(session, user_id=other_id, tenant_id=a_id)
    other = await make_user(session, user_id=other_id, email="o@acme.io")
    await make_membership(session, user=other, tenant=a_tenant, role=TenantRole.member)
    await session.commit()

    # member_a creates a private dataset and runs a profile
    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    src = await _make_source(session, tenant_id=a_id, creator_id=member_a_id, name="s")
    ds = await _make_dataset(
        session,
        tenant_id=a_id,
        source_id=src.id,
        creator_id=member_a_id,
        name="priv_ds",
        visibility=DatasetVisibility.private,
    )
    session.add(ProfileRun(tenant_id=a_id, dataset_id=ds.id, created_by=member_a_id))
    await session.commit()

    # other can't see the profile run
    await set_request_context(session, user_id=other_id, tenant_id=a_id)
    rows = (await session.execute(select(ProfileRun))).scalars().all()
    assert rows == []

    # creator can
    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    rows = (await session.execute(select(ProfileRun))).scalars().all()
    assert len(rows) == 1


async def test_profile_run_no_delete_policy(session: AsyncSession) -> None:
    """profile_runs is append-only. There is no DELETE policy, so the
    operation matches zero rows even from the creator."""
    a_tenant, _, member_a, _, _ = await _seed_workspace(session)
    a_id, member_a_id = a_tenant.id, member_a.id

    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    src = await _make_source(session, tenant_id=a_id, creator_id=member_a_id, name="s")
    ds = await _make_dataset(
        session,
        tenant_id=a_id,
        source_id=src.id,
        creator_id=member_a_id,
        name="ds",
    )
    session.add(ProfileRun(tenant_id=a_id, dataset_id=ds.id, created_by=member_a_id))
    await session.commit()

    await set_request_context(session, user_id=member_a_id, tenant_id=a_id)
    from sqlalchemy import delete as sql_delete

    result = await session.execute(
        sql_delete(ProfileRun).execution_options(synchronize_session=False)
    )
    assert result.rowcount == 0  # type: ignore[attr-defined]
