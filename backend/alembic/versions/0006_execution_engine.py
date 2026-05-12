"""Execution engine — working copies, operation log, message visuals

Three additions in one migration, all wired together so the agent can
actually *do* things instead of just describing them:

* ``dataset_working_copies`` — one mutable "draft" per dataset. The
  agent applies transformations here while the original dataset stays
  untouched. The user can "promote" a working copy to a new dataset
  when they're happy, or discard it.

* ``dataset_operations`` — append-only journal of every transformation
  applied to a working copy: ``{op, args, before_metrics, after_metrics,
  conversation_id, message_id}``. Powers "deshacer último paso" today
  and a full timeline view later. Each row references the
  conversation that proposed it for auditability.

* ``agent_messages.visualizations`` — JSONB list of typed viz specs the
  frontend renders inline (histograms, before/after bars, table
  previews, value-count pies). Same idea as ``suggestions``: keep the
  message content as human-readable markdown and pin the structured
  payload alongside it.

The agent emits all three via tool-use (Anthropic ``tool_use`` blocks
for v1) — the loop lives in :mod:`app.agent.service`.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-13
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def upgrade() -> None:
    # ----- agent_messages.visualizations ---------------------------------
    # Lives on the existing table, no separate row — visuals are bound
    # 1:1 with the assistant turn that produced them.
    op.add_column(
        "agent_messages",
        sa.Column("visualizations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # And a tool-call/tool-result envelope so we can replay agent loops
    # exactly, including the steps the user never saw rendered.
    op.add_column(
        "agent_messages",
        sa.Column("tool_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # ----- dataset_working_copies ----------------------------------------
    op.create_table(
        "dataset_working_copies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        # Absolute path under the storage root pointing at the current
        # parquet snapshot of the working copy. Every operation rewrites
        # this file; the previous bytes live on disk until garbage
        # collected via the ``dataset_operations`` journal.
        sa.Column("snapshot_path", sa.String(length=500), nullable=False),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("column_count", sa.Integer(), nullable=True),
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
            name="fk_dataset_working_copies_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_dataset_working_copies_dataset_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_dataset_working_copies_created_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_working_copies"),
        # One working copy per (dataset, user). Lets the same person
        # iterate without colliding with their colleagues' drafts.
        sa.UniqueConstraint(
            "dataset_id", "created_by", name="uq_dataset_working_copies_dataset_user"
        ),
    )
    op.create_index("ix_dataset_working_copies_tenant_id", "dataset_working_copies", ["tenant_id"])
    op.create_index(
        "ix_dataset_working_copies_dataset_id", "dataset_working_copies", ["dataset_id"]
    )

    # ----- dataset_operations --------------------------------------------
    op.create_table(
        "dataset_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("working_copy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        # Free-form op kind so we don't have to ship a migration every
        # time we add a new transform. The dispatcher in
        # ``app.transforms`` enforces what's valid.
        sa.Column("op", sa.String(length=64), nullable=False),
        sa.Column("args", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        # Snapshots of the working copy *before* and *after* this
        # operation. Lets us cheaply roll back to "the state before
        # step N" without re-running the whole pipeline.
        sa.Column("snapshot_before_path", sa.String(length=500), nullable=False),
        sa.Column("snapshot_after_path", sa.String(length=500), nullable=False),
        sa.Column("rows_before", sa.BigInteger(), nullable=True),
        sa.Column("rows_after", sa.BigInteger(), nullable=True),
        # The conversation + message that proposed this. Useful both
        # for auditing ("the agent did this when Juan asked X") and
        # for the UI to highlight the message that drove the op.
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        # The freeform result block we surface in the chat ("eliminé 3
        # filas duplicadas"). Same shape as ``visualizations`` so the
        # message can reference it.
        sa.Column("result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # ``undone_at`` doubles as the "active vs reverted" flag —
        # we never actually delete a row from this table; undo just
        # stamps the column.
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dataset_operations_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["working_copy_id"],
            ["dataset_working_copies.id"],
            name="fk_dataset_operations_working_copy_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_dataset_operations_created_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["agent_conversations.id"],
            name="fk_dataset_operations_conversation_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["agent_messages.id"],
            name="fk_dataset_operations_message_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_operations"),
    )
    op.create_index(
        "ix_dataset_operations_working_copy_id", "dataset_operations", ["working_copy_id"]
    )
    op.create_index(
        "ix_dataset_operations_conversation_id", "dataset_operations", ["conversation_id"]
    )
    op.create_index("ix_dataset_operations_created_at", "dataset_operations", ["created_at"])

    # ======================================================================
    # RLS
    # ======================================================================
    _enable_rls("dataset_working_copies")
    _enable_rls("dataset_operations")

    # Working copies are private to their creator (same model as
    # conversations) — the workspace owner sees everything as a
    # governance override.
    op.execute(
        """
        CREATE POLICY dataset_working_copies_select ON dataset_working_copies FOR SELECT
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
        CREATE POLICY dataset_working_copies_insert ON dataset_working_copies FOR INSERT
        WITH CHECK (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND created_by::text = current_setting('app.current_user', true)
        )
        """
    )
    op.execute(
        """
        CREATE POLICY dataset_working_copies_update ON dataset_working_copies FOR UPDATE
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND created_by::text = current_setting('app.current_user', true)
        )
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true))
        """
    )
    op.execute(
        """
        CREATE POLICY dataset_working_copies_delete ON dataset_working_copies FOR DELETE
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND (
                created_by::text = current_setting('app.current_user', true)
                OR app_is_workspace_owner(tenant_id)
            )
        )
        """
    )

    # Operations inherit their parent working copy's visibility via an
    # EXISTS sub-select, same pattern as messages → conversations.
    op.execute(
        """
        CREATE POLICY dataset_operations_select ON dataset_operations FOR SELECT
        USING (
            EXISTS (
                SELECT 1 FROM dataset_working_copies w
                WHERE w.id = dataset_operations.working_copy_id
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY dataset_operations_insert ON dataset_operations FOR INSERT
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM dataset_working_copies w
                WHERE w.id = dataset_operations.working_copy_id
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY dataset_operations_update ON dataset_operations FOR UPDATE
        USING (
            EXISTS (
                SELECT 1 FROM dataset_working_copies w
                WHERE w.id = dataset_operations.working_copy_id
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM dataset_working_copies w
                WHERE w.id = dataset_operations.working_copy_id
            )
        )
        """
    )

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON dataset_working_copies TO dataprep_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON dataset_operations TO dataprep_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS dataset_operations_update ON dataset_operations")
    op.execute("DROP POLICY IF EXISTS dataset_operations_insert ON dataset_operations")
    op.execute("DROP POLICY IF EXISTS dataset_operations_select ON dataset_operations")
    op.execute("DROP POLICY IF EXISTS dataset_working_copies_delete ON dataset_working_copies")
    op.execute("DROP POLICY IF EXISTS dataset_working_copies_update ON dataset_working_copies")
    op.execute("DROP POLICY IF EXISTS dataset_working_copies_insert ON dataset_working_copies")
    op.execute("DROP POLICY IF EXISTS dataset_working_copies_select ON dataset_working_copies")

    op.drop_index("ix_dataset_operations_created_at", table_name="dataset_operations")
    op.drop_index("ix_dataset_operations_conversation_id", table_name="dataset_operations")
    op.drop_index("ix_dataset_operations_working_copy_id", table_name="dataset_operations")
    op.drop_table("dataset_operations")

    op.drop_index("ix_dataset_working_copies_dataset_id", table_name="dataset_working_copies")
    op.drop_index("ix_dataset_working_copies_tenant_id", table_name="dataset_working_copies")
    op.drop_table("dataset_working_copies")

    op.drop_column("agent_messages", "tool_payload")
    op.drop_column("agent_messages", "visualizations")
