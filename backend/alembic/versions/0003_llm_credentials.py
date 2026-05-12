"""LLM credentials

Adds the two tables that back the BYOK workspace model:

* ``llm_credentials``         — encrypted provider credentials (API keys for
  Anthropic, OpenAI, Google, Ollama). Owned by admins; members can
  use the ones the admins share with them.
* ``llm_credential_grants``   — per-user grants for the
  ``member_access = 'specific_members'`` case.

Access model
------------

For SELECT (i.e., "can I use this credential?"):

  * Workspace admins (role ``owner`` or ``admin``) always see all
    credentials in their tenant. They're the ones who registered
    them and can rotate them.
  * Members see a credential when ``member_access = 'all_members'``
    AND they belong to the tenant; or ``member_access =
    'specific_members'`` AND a ``llm_credential_grants`` row exists.
  * ``member_access = 'admins_only'`` is the default — completely
    invisible to members.

For INSERT/UPDATE/DELETE: only admins. Members never get to
register or rotate keys.

A new SECURITY DEFINER helper :func:`app_is_workspace_admin`
is added — same shape as the existing ``app_is_workspace_owner``
but matches BOTH ``owner`` and ``admin`` roles. Reused across
the LLM-credential policies to keep the SQL DRY.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-13
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def upgrade() -> None:
    # ----- Enums -----------------------------------------------------------
    op.execute("CREATE TYPE llm_provider_kind AS ENUM ('anthropic', 'openai', 'google', 'ollama')")
    op.execute(
        "CREATE TYPE llm_member_access AS ENUM ('admins_only', 'all_members', 'specific_members')"
    )

    # ----- llm_credentials -------------------------------------------------
    op.create_table(
        "llm_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "provider",
            postgresql.ENUM(
                "anthropic",
                "openai",
                "google",
                "ollama",
                name="llm_provider_kind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("nickname", sa.String(length=120), nullable=False),
        sa.Column("api_key_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("model_default", sa.String(length=120), nullable=True),
        # Base URL is only meaningful for Ollama (self-hosted) and
        # OpenAI-compatible custom endpoints. Cloud providers ignore it.
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column(
            "member_access",
            postgresql.ENUM(
                "admins_only",
                "all_members",
                "specific_members",
                name="llm_member_access",
                create_type=False,
            ),
            server_default=sa.text("'admins_only'"),
            nullable=False,
        ),
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
            name="fk_llm_credentials_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_llm_credentials_created_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_llm_credentials"),
        sa.UniqueConstraint("tenant_id", "nickname", name="uq_llm_credentials_tenant_id_nickname"),
    )
    op.create_index("ix_llm_credentials_tenant_id", "llm_credentials", ["tenant_id"])
    op.create_index("ix_llm_credentials_created_by", "llm_credentials", ["created_by"])

    # ----- llm_credential_grants ------------------------------------------
    op.create_table(
        "llm_credential_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("llm_credential_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["llm_credential_id"],
            ["llm_credentials.id"],
            name="fk_llm_credential_grants_credential_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_llm_credential_grants_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name="fk_llm_credential_grants_granted_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_llm_credential_grants"),
        sa.UniqueConstraint(
            "llm_credential_id", "user_id", name="uq_llm_credential_grants_cred_user"
        ),
    )
    op.create_index("ix_llm_credential_grants_user_id", "llm_credential_grants", ["user_id"])
    op.create_index(
        "ix_llm_credential_grants_credential_id",
        "llm_credential_grants",
        ["llm_credential_id"],
    )

    # ======================================================================
    # RLS
    # ======================================================================
    _enable_rls("llm_credentials")
    _enable_rls("llm_credential_grants")

    # ----- Helper functions (SECURITY DEFINER, bypass RLS) ----------------
    #
    # ``app_is_workspace_admin`` is the new piece: matches BOTH the
    # ``owner`` and ``admin`` roles. We reuse it across all
    # llm_credentials policies and (later) any other admin-only
    # resource.
    #
    # ``app_user_has_llm_grant`` is the dataset-grant equivalent
    # for credentials.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_is_workspace_admin(tid uuid)
        RETURNS boolean
        LANGUAGE sql SECURITY DEFINER STABLE
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM tenant_memberships
            WHERE tenant_id = tid
              AND user_id::text = current_setting('app.current_user', true)
              AND role IN ('owner', 'admin')
          );
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_user_has_llm_grant(cid uuid)
        RETURNS boolean
        LANGUAGE sql SECURITY DEFINER STABLE
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM llm_credential_grants
            WHERE llm_credential_id = cid
              AND user_id::text = current_setting('app.current_user', true)
          );
        $$
        """
    )
    # Helper for grants policy — checks whether the calling user is
    # an admin of the credential's tenant. Needed because
    # llm_credential_grants doesn't carry tenant_id directly; we
    # resolve via the parent credential.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_user_admins_llm_credential(cid uuid)
        RETURNS boolean
        LANGUAGE sql SECURITY DEFINER STABLE
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM llm_credentials c
            WHERE c.id = cid
              AND app_is_workspace_admin(c.tenant_id)
          );
        $$
        """
    )
    op.execute("GRANT EXECUTE ON FUNCTION app_is_workspace_admin(uuid) TO dataprep_app")
    op.execute("GRANT EXECUTE ON FUNCTION app_user_has_llm_grant(uuid) TO dataprep_app")
    op.execute("GRANT EXECUTE ON FUNCTION app_user_admins_llm_credential(uuid) TO dataprep_app")

    # ----- llm_credentials policies ---------------------------------------
    #
    # SELECT — 3 branches:
    #   1. admin of the tenant → sees everything
    #   2. member_access = 'all_members' AND user belongs to tenant
    #   3. member_access = 'specific_members' AND grant exists
    op.execute(
        """
        CREATE POLICY llm_credentials_select ON llm_credentials FOR SELECT
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND (
                app_is_workspace_admin(tenant_id)
                OR (
                    member_access = 'all_members'
                    AND EXISTS (
                        SELECT 1 FROM tenant_memberships tm
                        WHERE tm.user_id::text = current_setting('app.current_user', true)
                          AND tm.tenant_id = llm_credentials.tenant_id
                    )
                )
                OR (
                    member_access = 'specific_members'
                    AND app_user_has_llm_grant(id)
                )
            )
        )
        """
    )
    # INSERT / UPDATE / DELETE — admins only.
    op.execute(
        """
        CREATE POLICY llm_credentials_insert ON llm_credentials FOR INSERT
        WITH CHECK (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND created_by::text = current_setting('app.current_user', true)
            AND app_is_workspace_admin(tenant_id)
        )
        """
    )
    op.execute(
        """
        CREATE POLICY llm_credentials_update ON llm_credentials FOR UPDATE
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND app_is_workspace_admin(tenant_id)
        )
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true))
        """
    )
    op.execute(
        """
        CREATE POLICY llm_credentials_delete ON llm_credentials FOR DELETE
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND app_is_workspace_admin(tenant_id)
        )
        """
    )

    # ----- llm_credential_grants policies ---------------------------------
    # SELECT: the user themself (so they can verify what they have),
    # plus admins of the credential's tenant.
    op.execute(
        """
        CREATE POLICY llm_credential_grants_select ON llm_credential_grants FOR SELECT
        USING (
            user_id::text = current_setting('app.current_user', true)
            OR app_user_admins_llm_credential(llm_credential_id)
        )
        """
    )
    op.execute(
        """
        CREATE POLICY llm_credential_grants_insert ON llm_credential_grants FOR INSERT
        WITH CHECK (app_user_admins_llm_credential(llm_credential_id))
        """
    )
    op.execute(
        """
        CREATE POLICY llm_credential_grants_delete ON llm_credential_grants FOR DELETE
        USING (app_user_admins_llm_credential(llm_credential_id))
        """
    )

    # ======================================================================
    # Runtime grants
    # ======================================================================
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON llm_credentials TO dataprep_app")
    op.execute("GRANT SELECT, INSERT, DELETE ON llm_credential_grants TO dataprep_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS llm_credential_grants_delete ON llm_credential_grants")
    op.execute("DROP POLICY IF EXISTS llm_credential_grants_insert ON llm_credential_grants")
    op.execute("DROP POLICY IF EXISTS llm_credential_grants_select ON llm_credential_grants")
    op.execute("DROP POLICY IF EXISTS llm_credentials_delete ON llm_credentials")
    op.execute("DROP POLICY IF EXISTS llm_credentials_update ON llm_credentials")
    op.execute("DROP POLICY IF EXISTS llm_credentials_insert ON llm_credentials")
    op.execute("DROP POLICY IF EXISTS llm_credentials_select ON llm_credentials")

    op.execute("DROP FUNCTION IF EXISTS app_user_admins_llm_credential(uuid)")
    op.execute("DROP FUNCTION IF EXISTS app_user_has_llm_grant(uuid)")
    op.execute("DROP FUNCTION IF EXISTS app_is_workspace_admin(uuid)")

    op.drop_index("ix_llm_credential_grants_credential_id", table_name="llm_credential_grants")
    op.drop_index("ix_llm_credential_grants_user_id", table_name="llm_credential_grants")
    op.drop_table("llm_credential_grants")

    op.drop_index("ix_llm_credentials_created_by", table_name="llm_credentials")
    op.drop_index("ix_llm_credentials_tenant_id", table_name="llm_credentials")
    op.drop_table("llm_credentials")

    op.execute("DROP TYPE IF EXISTS llm_member_access")
    op.execute("DROP TYPE IF EXISTS llm_provider_kind")
