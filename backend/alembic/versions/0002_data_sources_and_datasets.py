"""data sources and datasets

Adds the four tables that back the data-domain MVP:

* ``data_sources``   — credentials / file pointers, always private to creator
* ``datasets``       — logical views over a source (table or sheet)
* ``dataset_grants`` — per-user grants for ``visibility = 'shared_specific'``
* ``profile_runs``   — append-only profiler executions

RLS is wired from the start. The interesting policy is the ``datasets``
SELECT, which has four permissive branches:

  1. ``visibility = 'shared_workspace'`` → every member of the tenant
  2. ``created_by = current_user``      → the creator always sees their own
  3. ``visibility = 'shared_specific'`` AND row exists in ``dataset_grants``
  4. caller has ``tenant_role = 'owner'`` → workspace governance override

UPDATE / DELETE branches drop (1) and (3): writes are creator + owner only.

``profile_runs`` and ``dataset_grants`` carry no UPDATE / DELETE policies
beyond what the migration declares; we deliberately keep them append-only
where it makes sense (profile_runs is audit-grade history; grants are
revoked by INSERT-then-DELETE rather than UPDATE).

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-07
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # ----- Enums -----------------------------------------------------------
    op.execute(
        "CREATE TYPE data_source_kind AS ENUM "
        "('postgres', 'mssql', 'mssql_azure', 'csv', 'parquet', 'xlsx')"
    )
    op.execute("CREATE TYPE dataset_kind AS ENUM ('table', 'file_sheet', 'query')")
    op.execute(
        "CREATE TYPE dataset_visibility AS ENUM ('private', 'shared_workspace', 'shared_specific')"
    )
    op.execute("CREATE TYPE profile_run_status AS ENUM ('running', 'completed', 'failed')")

    # ----- data_sources ----------------------------------------------------
    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "postgres",
                "mssql",
                "mssql_azure",
                "csv",
                "parquet",
                "xlsx",
                name="data_source_kind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("connection_config_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(length=20), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_data_sources_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_data_sources_created_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_data_sources"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_data_sources_tenant_id_name"),
    )
    op.create_index("ix_data_sources_tenant_id", "data_sources", ["tenant_id"])
    op.create_index("ix_data_sources_created_by", "data_sources", ["created_by"])

    # ----- datasets --------------------------------------------------------
    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM("table", "file_sheet", "query", name="dataset_kind", create_type=False),
            nullable=False,
        ),
        sa.Column("locator", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("inferred_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("row_count_estimate", sa.BigInteger(), nullable=True),
        sa.Column(
            "visibility",
            postgresql.ENUM(
                "private",
                "shared_workspace",
                "shared_specific",
                name="dataset_visibility",
                create_type=False,
            ),
            server_default=sa.text("'private'"),
            nullable=False,
        ),
        sa.Column("last_introspected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_datasets_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["data_sources.id"],
            name="fk_datasets_source_id_data_sources",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_datasets_created_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_datasets"),
        sa.UniqueConstraint(
            "tenant_id", "source_id", "name", name="uq_datasets_tenant_source_name"
        ),
    )
    op.create_index("ix_datasets_tenant_id", "datasets", ["tenant_id"])
    op.create_index("ix_datasets_source_id", "datasets", ["source_id"])
    op.create_index("ix_datasets_created_by", "datasets", ["created_by"])
    op.create_index("ix_datasets_visibility", "datasets", ["visibility"])

    # ----- dataset_grants --------------------------------------------------
    op.create_table(
        "dataset_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_dataset_grants_dataset_id_datasets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_dataset_grants_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name="fk_dataset_grants_granted_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_grants"),
        sa.UniqueConstraint("dataset_id", "user_id", name="uq_dataset_grants_dataset_user"),
    )
    op.create_index("ix_dataset_grants_user_id", "dataset_grants", ["user_id"])
    op.create_index("ix_dataset_grants_dataset_id", "dataset_grants", ["dataset_id"])

    # ----- profile_runs ----------------------------------------------------
    op.create_table(
        "profile_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "running",
                "completed",
                "failed",
                name="profile_run_status",
                create_type=False,
            ),
            server_default=sa.text("'running'"),
            nullable=False,
        ),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_profile_runs_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_profile_runs_dataset_id_datasets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_profile_runs_created_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_profile_runs"),
    )
    op.create_index("ix_profile_runs_dataset_id", "profile_runs", ["dataset_id"])
    op.create_index("ix_profile_runs_tenant_id", "profile_runs", ["tenant_id"])

    # =======================================================================
    # Row-Level Security
    # =======================================================================
    _enable_rls("data_sources")
    _enable_rls("datasets")
    _enable_rls("dataset_grants")
    _enable_rls("profile_runs")

    # ----- Helper functions to break RLS recursion ------------------------
    #
    # The ``datasets_select`` policy needs to peek at ``dataset_grants``
    # and vice versa — Postgres detects the cycle and aborts with
    # ``infinite recursion detected in policy``. To break it we expose
    # these cross-table lookups as ``SECURITY DEFINER`` SQL functions.
    #
    # The migration runs as the ``dataprep`` superuser, so the function
    # owner is a superuser and queries inside the function bypass RLS.
    # That's exactly what we want: the function is the *only* gate, and
    # callers can't smuggle extra data out because each function returns
    # ``boolean``.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_is_workspace_owner(tid uuid)
        RETURNS boolean
        LANGUAGE sql SECURITY DEFINER STABLE
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM tenant_memberships
            WHERE tenant_id = tid
              AND user_id::text = current_setting('app.current_user', true)
              AND role = 'owner'
          );
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_user_has_dataset_grant(did uuid)
        RETURNS boolean
        LANGUAGE sql SECURITY DEFINER STABLE
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM dataset_grants
            WHERE dataset_id = did
              AND user_id::text = current_setting('app.current_user', true)
          );
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_user_admins_dataset(did uuid)
        RETURNS boolean
        LANGUAGE sql SECURITY DEFINER STABLE
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM datasets
            WHERE id = did
              AND (
                created_by::text = current_setting('app.current_user', true)
                OR app_is_workspace_owner(tenant_id)
              )
          );
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_user_can_select_dataset(did uuid)
        RETURNS boolean
        LANGUAGE sql SECURITY DEFINER STABLE
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM datasets
            WHERE id = did
              AND tenant_id::text = current_setting('app.current_tenant', true)
              AND (
                visibility = 'shared_workspace'
                OR created_by::text = current_setting('app.current_user', true)
                OR (visibility = 'shared_specific' AND app_user_has_dataset_grant(id))
                OR app_is_workspace_owner(tenant_id)
              )
          );
        $$
        """
    )
    # The runtime role calls these helpers from inside policy expressions;
    # SECURITY DEFINER means the body runs as the owner, but EXECUTE still
    # has to be granted to the caller.
    op.execute("GRANT EXECUTE ON FUNCTION app_is_workspace_owner(uuid) TO dataprep_app")
    op.execute("GRANT EXECUTE ON FUNCTION app_user_has_dataset_grant(uuid) TO dataprep_app")
    op.execute("GRANT EXECUTE ON FUNCTION app_user_admins_dataset(uuid) TO dataprep_app")
    op.execute("GRANT EXECUTE ON FUNCTION app_user_can_select_dataset(uuid) TO dataprep_app")

    # ----- data_sources policies — creator + workspace_owner --------------
    op.execute(
        """
        CREATE POLICY data_sources_select ON data_sources FOR SELECT
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND (
                created_by::text = current_setting('app.current_user', true)
                OR app_is_workspace_owner(tenant_id)
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY data_sources_insert ON data_sources FOR INSERT
        WITH CHECK (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND created_by::text = current_setting('app.current_user', true)
        )
        """
    )
    op.execute(
        """
        CREATE POLICY data_sources_update ON data_sources FOR UPDATE
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND (
                created_by::text = current_setting('app.current_user', true)
                OR app_is_workspace_owner(tenant_id)
            )
        )
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true))
        """
    )
    op.execute(
        """
        CREATE POLICY data_sources_delete ON data_sources FOR DELETE
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND (
                created_by::text = current_setting('app.current_user', true)
                OR app_is_workspace_owner(tenant_id)
            )
        )
        """
    )

    # ----- datasets policies — 4-branch SELECT, narrower UPDATE/DELETE ----
    #
    # The grant subquery uses ``app_user_has_dataset_grant`` rather than
    # an inline EXISTS — that breaks the recursion with the
    # ``dataset_grants`` policies (the helper is SECURITY DEFINER and
    # bypasses RLS).
    op.execute(
        """
        CREATE POLICY datasets_select ON datasets FOR SELECT
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND (
                visibility = 'shared_workspace'
                OR created_by::text = current_setting('app.current_user', true)
                OR (
                    visibility = 'shared_specific'
                    AND app_user_has_dataset_grant(id)
                )
                OR app_is_workspace_owner(tenant_id)
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY datasets_insert ON datasets FOR INSERT
        WITH CHECK (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND created_by::text = current_setting('app.current_user', true)
        )
        """
    )
    op.execute(
        """
        CREATE POLICY datasets_update ON datasets FOR UPDATE
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND (
                created_by::text = current_setting('app.current_user', true)
                OR app_is_workspace_owner(tenant_id)
            )
        )
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true))
        """
    )
    op.execute(
        """
        CREATE POLICY datasets_delete ON datasets FOR DELETE
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND (
                created_by::text = current_setting('app.current_user', true)
                OR app_is_workspace_owner(tenant_id)
            )
        )
        """
    )

    # ----- dataset_grants policies — only dataset owner / workspace owner -
    # SELECT: own grants (so a user can verify what they have) plus full
    # visibility for the dataset's creator + workspace owner. The
    # cross-table check goes through ``app_user_admins_dataset`` to
    # avoid recursing into the ``datasets_select`` policy.
    op.execute(
        """
        CREATE POLICY dataset_grants_select ON dataset_grants FOR SELECT
        USING (
            user_id::text = current_setting('app.current_user', true)
            OR app_user_admins_dataset(dataset_id)
        )
        """
    )
    op.execute(
        """
        CREATE POLICY dataset_grants_insert ON dataset_grants FOR INSERT
        WITH CHECK (app_user_admins_dataset(dataset_id))
        """
    )
    op.execute(
        """
        CREATE POLICY dataset_grants_delete ON dataset_grants FOR DELETE
        USING (app_user_admins_dataset(dataset_id))
        """
    )
    # No UPDATE policy → grants are revoke-and-reissue, not editable.

    # ----- profile_runs policies — visible if you can see the dataset -----
    op.execute(
        """
        CREATE POLICY profile_runs_select ON profile_runs FOR SELECT
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND app_user_can_select_dataset(dataset_id)
        )
        """
    )
    op.execute(
        """
        CREATE POLICY profile_runs_insert ON profile_runs FOR INSERT
        WITH CHECK (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND created_by::text = current_setting('app.current_user', true)
            AND app_user_can_select_dataset(dataset_id)
        )
        """
    )
    # The service that inserted the row updates its status. Restrict updates
    # to the same user, same tenant, same row's creator.
    op.execute(
        """
        CREATE POLICY profile_runs_update ON profile_runs FOR UPDATE
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND created_by::text = current_setting('app.current_user', true)
        )
        WITH CHECK (
            tenant_id::text = current_setting('app.current_tenant', true)
        )
        """
    )
    # No DELETE policy → profile history is append-only.

    # =======================================================================
    # Runtime grants for the dataprep_app role
    # =======================================================================
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON data_sources TO dataprep_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON datasets TO dataprep_app")
    op.execute("GRANT SELECT, INSERT, DELETE ON dataset_grants TO dataprep_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON profile_runs TO dataprep_app")


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS profile_runs_update ON profile_runs")
    op.execute("DROP POLICY IF EXISTS profile_runs_insert ON profile_runs")
    op.execute("DROP POLICY IF EXISTS profile_runs_select ON profile_runs")
    op.execute("DROP POLICY IF EXISTS dataset_grants_delete ON dataset_grants")
    op.execute("DROP POLICY IF EXISTS dataset_grants_insert ON dataset_grants")
    op.execute("DROP POLICY IF EXISTS dataset_grants_select ON dataset_grants")
    op.execute("DROP POLICY IF EXISTS datasets_delete ON datasets")
    op.execute("DROP POLICY IF EXISTS datasets_update ON datasets")
    op.execute("DROP POLICY IF EXISTS datasets_insert ON datasets")
    op.execute("DROP POLICY IF EXISTS datasets_select ON datasets")
    op.execute("DROP POLICY IF EXISTS data_sources_delete ON data_sources")
    op.execute("DROP POLICY IF EXISTS data_sources_update ON data_sources")
    op.execute("DROP POLICY IF EXISTS data_sources_insert ON data_sources")
    op.execute("DROP POLICY IF EXISTS data_sources_select ON data_sources")

    op.execute("DROP FUNCTION IF EXISTS app_user_can_select_dataset(uuid)")
    op.execute("DROP FUNCTION IF EXISTS app_user_admins_dataset(uuid)")
    op.execute("DROP FUNCTION IF EXISTS app_user_has_dataset_grant(uuid)")
    op.execute("DROP FUNCTION IF EXISTS app_is_workspace_owner(uuid)")

    op.drop_index("ix_profile_runs_tenant_id", table_name="profile_runs")
    op.drop_index("ix_profile_runs_dataset_id", table_name="profile_runs")
    op.drop_table("profile_runs")

    op.drop_index("ix_dataset_grants_dataset_id", table_name="dataset_grants")
    op.drop_index("ix_dataset_grants_user_id", table_name="dataset_grants")
    op.drop_table("dataset_grants")

    op.drop_index("ix_datasets_visibility", table_name="datasets")
    op.drop_index("ix_datasets_created_by", table_name="datasets")
    op.drop_index("ix_datasets_source_id", table_name="datasets")
    op.drop_index("ix_datasets_tenant_id", table_name="datasets")
    op.drop_table("datasets")

    op.drop_index("ix_data_sources_created_by", table_name="data_sources")
    op.drop_index("ix_data_sources_tenant_id", table_name="data_sources")
    op.drop_table("data_sources")

    op.execute("DROP TYPE IF EXISTS profile_run_status")
    op.execute("DROP TYPE IF EXISTS dataset_visibility")
    op.execute("DROP TYPE IF EXISTS dataset_kind")
    op.execute("DROP TYPE IF EXISTS data_source_kind")
