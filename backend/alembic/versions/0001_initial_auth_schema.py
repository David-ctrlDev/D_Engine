"""initial auth schema

Creates all auth-related tables and the Row-Level Security policies that
enforce tenant isolation in the database itself.

RLS scope decision
------------------

The user-scoped tables (``users``, ``mfa_methods``, ``mfa_recovery_codes``,
``refresh_tokens``, ``auth_tokens``) are NOT protected by RLS. They are
accessed either:

* by a JWT-derived ``user_id`` filter at the application layer, or
* by an unguessable hashed token (``token_hashed``) — which is itself the
  authenticator.

Putting RLS on those tables would require a bypass GUC for every pre-auth
flow (login, refresh, email verification, password reset), and the bypass
would defeat the protection it was meant to add. We instead apply RLS to
exactly the tables whose rows could leak data BETWEEN tenants:

* ``tenants``
* ``tenant_memberships``
* ``audit_log``

Registration sets both GUCs (``app.current_tenant``, ``app.current_user``)
to the about-to-be-created UUIDs *before* inserting, so the ``WITH CHECK``
clauses pass without any bypass mechanism.

Revision ID: 0001
Revises:
Create Date: 2026-05-04
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enable_rls(table: str) -> None:
    """Enable + force RLS on a table. ``FORCE`` makes policies apply to the
    table owner too — without it, the migration role bypasses RLS, which would
    cause subtle test failures."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # ----- Enums -----------------------------------------------------------
    op.execute("CREATE TYPE tenant_role AS ENUM ('owner', 'admin', 'member')")
    op.execute("CREATE TYPE mfa_method_type AS ENUM ('totp')")
    op.execute("CREATE TYPE auth_token_type AS ENUM ('email_verify', 'password_reset')")

    # ----- tenants ---------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenants"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )

    # ----- users -----------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # ----- tenant_memberships ----------------------------------------------
    op.create_table(
        "tenant_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("owner", "admin", "member", name="tenant_role", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_tenant_memberships_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_tenant_memberships_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenant_memberships"),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_tenant_memberships_user_id_tenant_id"),
    )
    op.create_index("ix_tenant_memberships_user_id", "tenant_memberships", ["user_id"])
    op.create_index("ix_tenant_memberships_tenant_id", "tenant_memberships", ["tenant_id"])

    # ----- mfa_methods -----------------------------------------------------
    op.create_table(
        "mfa_methods",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "method_type",
            postgresql.ENUM("totp", name="mfa_method_type", create_type=False),
            nullable=False,
        ),
        sa.Column("secret_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_mfa_methods_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mfa_methods"),
    )
    op.create_index("ix_mfa_methods_user_id", "mfa_methods", ["user_id"])
    # Partial unique: at most one TOTP method per user. WebAuthn keys
    # (future) are unconstrained, allowing several hardware tokens per user.
    op.execute(
        "CREATE UNIQUE INDEX uq_mfa_methods_user_id_totp ON mfa_methods (user_id) "
        "WHERE method_type = 'totp'"
    )

    # ----- mfa_recovery_codes ---------------------------------------------
    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hashed", sa.String(length=255), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_mfa_recovery_codes_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mfa_recovery_codes"),
    )
    op.create_index("ix_mfa_recovery_codes_user_id", "mfa_recovery_codes", ["user_id"])

    # ----- refresh_tokens --------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hashed", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_refresh_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_refresh_tokens_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
        sa.UniqueConstraint("token_hashed", name="uq_refresh_tokens_token_hashed"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_tenant_id", "refresh_tokens", ["tenant_id"])
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])

    # ----- auth_tokens -----------------------------------------------------
    op.create_table(
        "auth_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "token_type",
            postgresql.ENUM(
                "email_verify",
                "password_reset",
                name="auth_token_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("token_hashed", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_auth_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_tokens"),
        sa.UniqueConstraint("token_hashed", name="uq_auth_tokens_token_hashed"),
    )
    op.create_index("ix_auth_tokens_user_id", "auth_tokens", ["user_id"])
    op.create_index("ix_auth_tokens_expires_at", "auth_tokens", ["expires_at"])

    # ----- audit_log -------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_audit_log_tenant_id_tenants",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_audit_log_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )
    op.create_index("ix_audit_log_tenant_id", "audit_log", ["tenant_id"])
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_event_type", "audit_log", ["event_type"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # =======================================================================
    # Row-Level Security
    # =======================================================================
    #
    # Convention: every policy is anchored on
    #   current_setting('app.current_tenant', true)
    #   current_setting('app.current_user',   true)
    # The trailing ``true`` argument means "missing setting returns NULL"
    # rather than raising. Policies coalesce against an empty string so a
    # missing GUC denies access by default.
    # -----------------------------------------------------------------------

    _enable_rls("tenants")
    _enable_rls("tenant_memberships")
    _enable_rls("audit_log")

    # ----- tenants ---------------------------------------------------------
    op.execute(
        """
        CREATE POLICY tenants_select ON tenants
        FOR SELECT
        USING (
            id::text = current_setting('app.current_tenant', true)
            OR EXISTS (
                SELECT 1 FROM tenant_memberships tm
                WHERE tm.tenant_id = tenants.id
                  AND tm.user_id::text = current_setting('app.current_user', true)
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY tenants_insert ON tenants
        FOR INSERT
        WITH CHECK (id::text = current_setting('app.current_tenant', true))
        """
    )
    op.execute(
        """
        CREATE POLICY tenants_update ON tenants
        FOR UPDATE
        USING (id::text = current_setting('app.current_tenant', true))
        WITH CHECK (id::text = current_setting('app.current_tenant', true))
        """
    )
    op.execute(
        """
        CREATE POLICY tenants_delete ON tenants
        FOR DELETE
        USING (id::text = current_setting('app.current_tenant', true))
        """
    )

    # ----- tenant_memberships ----------------------------------------------
    # SELECT: a user sees their own memberships across all tenants (so they
    # can pick a workspace), AND, when scoped to a tenant, sees other
    # members of that tenant.
    op.execute(
        """
        CREATE POLICY tenant_memberships_select ON tenant_memberships
        FOR SELECT
        USING (
            user_id::text = current_setting('app.current_user', true)
            OR tenant_id::text = current_setting('app.current_tenant', true)
        )
        """
    )
    # INSERT: only by setting both GUCs to the values being inserted
    # (registration creates membership for the new user/tenant).
    op.execute(
        """
        CREATE POLICY tenant_memberships_insert ON tenant_memberships
        FOR INSERT
        WITH CHECK (
            user_id::text = current_setting('app.current_user', true)
            AND tenant_id::text = current_setting('app.current_tenant', true)
        )
        """
    )
    # UPDATE / DELETE: scoped to the active tenant.
    op.execute(
        """
        CREATE POLICY tenant_memberships_update ON tenant_memberships
        FOR UPDATE
        USING (tenant_id::text = current_setting('app.current_tenant', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true))
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_memberships_delete ON tenant_memberships
        FOR DELETE
        USING (tenant_id::text = current_setting('app.current_tenant', true))
        """
    )

    # ----- audit_log -------------------------------------------------------
    # Reads: rows from the active tenant, OR rows attributed to the active
    # user (covers tenant-less events like a failed login).
    op.execute(
        """
        CREATE POLICY audit_log_select ON audit_log
        FOR SELECT
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            OR user_id::text = current_setting('app.current_user', true)
        )
        """
    )
    # Writes: must match either the active tenant (most events) or the
    # active user (tenant-less events). Cannot write rows attributed to
    # another tenant.
    op.execute(
        """
        CREATE POLICY audit_log_insert ON audit_log
        FOR INSERT
        WITH CHECK (
            (tenant_id IS NULL OR
             tenant_id::text = current_setting('app.current_tenant', true))
            AND
            (user_id IS NULL OR
             user_id::text = current_setting('app.current_user', true))
        )
        """
    )
    # The audit log is append-only; no UPDATE / DELETE policies are created,
    # so those operations are denied by default.

    # =======================================================================
    # Runtime grants
    # =======================================================================
    #
    # The ``dataprep_app`` role is created at cluster init time by
    # backend/scripts/init-app-role.sql. It is NOSUPERUSER + NOBYPASSRLS so
    # RLS policies actually apply to it (FORCE RLS only catches the table
    # owner, not superusers). Migrations run as the owner; runtime traffic
    # connects as ``dataprep_app``.
    # -----------------------------------------------------------------------
    op.execute("GRANT USAGE ON SCHEMA public TO dataprep_app")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO dataprep_app"
    )
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO dataprep_app")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO dataprep_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO dataprep_app"
    )


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_log_insert ON audit_log")
    op.execute("DROP POLICY IF EXISTS audit_log_select ON audit_log")
    op.execute("DROP POLICY IF EXISTS tenant_memberships_delete ON tenant_memberships")
    op.execute("DROP POLICY IF EXISTS tenant_memberships_update ON tenant_memberships")
    op.execute("DROP POLICY IF EXISTS tenant_memberships_insert ON tenant_memberships")
    op.execute("DROP POLICY IF EXISTS tenant_memberships_select ON tenant_memberships")
    op.execute("DROP POLICY IF EXISTS tenants_delete ON tenants")
    op.execute("DROP POLICY IF EXISTS tenants_update ON tenants")
    op.execute("DROP POLICY IF EXISTS tenants_insert ON tenants")
    op.execute("DROP POLICY IF EXISTS tenants_select ON tenants")

    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_event_type", table_name="audit_log")
    op.drop_index("ix_audit_log_user_id", table_name="audit_log")
    op.drop_index("ix_audit_log_tenant_id", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_auth_tokens_expires_at", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_user_id", table_name="auth_tokens")
    op.drop_table("auth_tokens")

    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_tenant_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_mfa_recovery_codes_user_id", table_name="mfa_recovery_codes")
    op.drop_table("mfa_recovery_codes")

    op.execute("DROP INDEX IF EXISTS uq_mfa_methods_user_id_totp")
    op.drop_index("ix_mfa_methods_user_id", table_name="mfa_methods")
    op.drop_table("mfa_methods")

    op.drop_index("ix_tenant_memberships_tenant_id", table_name="tenant_memberships")
    op.drop_index("ix_tenant_memberships_user_id", table_name="tenant_memberships")
    op.drop_table("tenant_memberships")
    op.drop_table("users")
    op.drop_table("tenants")

    op.execute("DROP TYPE IF EXISTS auth_token_type")
    op.execute("DROP TYPE IF EXISTS mfa_method_type")
    op.execute("DROP TYPE IF EXISTS tenant_role")
