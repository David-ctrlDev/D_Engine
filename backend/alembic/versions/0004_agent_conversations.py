"""Agent conversations + messages

Adds the two tables that back the chat-with-the-agent surface:

* ``agent_conversations`` — one chat thread anchored to a single
  dataset. Carries which BYOK credential + model the user picked when
  they started it; we never silently switch providers mid-thread.
* ``agent_messages``     — append-only message log. ``role`` follows
  the OpenAI / Anthropic convention (``user`` / ``assistant`` /
  ``system``); the ``system`` rows aren't shown in the UI but they
  let us replay a thread exactly when we add streaming or tool-use.

Privacy
-------

Conversations are **private to their creator** — even members of the
same workspace can't read another member's threads. The content is
free-form, often paste-of-business-context, so we err on the side of
strict. The workspace **owner** can still read everything for
governance (same override as datasets).

Cost / budget gate
------------------

Each conversation pins the ``credential_id`` it spends against, and
the FK uses ``ON DELETE RESTRICT`` so an admin can't accidentally
delete a credential that has live conversations. To remove a
credential, they first delete its conversations (cascade kills the
messages) or migrate them.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-13
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def upgrade() -> None:
    # ----- Enums -----------------------------------------------------------
    op.execute("CREATE TYPE agent_message_role AS ENUM ('user', 'assistant', 'system')")

    # ----- agent_conversations --------------------------------------------
    op.create_table(
        "agent_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        # Pin the credential + model picked at creation time. We never
        # silently switch providers mid-conversation; rotating means
        # creating a new conversation.
        sa.Column("credential_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        # Optional: a short summary the agent (or the user) can set so
        # the conversation list shows something better than the UUID.
        sa.Column("title", sa.String(length=160), nullable=True),
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
            name="fk_agent_conversations_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_agent_conversations_dataset_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_agent_conversations_created_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["llm_credentials.id"],
            name="fk_agent_conversations_credential_id",
            # RESTRICT, not CASCADE: deleting a credential with live
            # conversations is a workflow we want admins to confront
            # explicitly, not a silent data loss.
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_conversations"),
    )
    op.create_index("ix_agent_conversations_tenant_id", "agent_conversations", ["tenant_id"])
    op.create_index("ix_agent_conversations_dataset_id", "agent_conversations", ["dataset_id"])
    op.create_index("ix_agent_conversations_created_by", "agent_conversations", ["created_by"])
    op.create_index(
        "ix_agent_conversations_credential_id", "agent_conversations", ["credential_id"]
    )

    # ----- agent_messages -------------------------------------------------
    op.create_table(
        "agent_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "user",
                "assistant",
                "system",
                name="agent_message_role",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        # ``token_usage`` is a {prompt, completion, total} blob — we
        # only store it on assistant messages, but keeping the column
        # on every row avoids a separate table.
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["agent_conversations.id"],
            name="fk_agent_messages_conversation_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_messages"),
    )
    op.create_index("ix_agent_messages_conversation_id", "agent_messages", ["conversation_id"])
    op.create_index("ix_agent_messages_created_at", "agent_messages", ["created_at"])

    # ======================================================================
    # RLS
    # ======================================================================
    _enable_rls("agent_conversations")
    _enable_rls("agent_messages")

    # ----- agent_conversations policies -----------------------------------
    #
    # SELECT — creator or workspace owner. Conversations are private:
    # the content is free-form, often paste-of-business-context, so we
    # err strict by default. Owner override matches the dataset rules.
    op.execute(
        """
        CREATE POLICY agent_conversations_select ON agent_conversations FOR SELECT
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
        CREATE POLICY agent_conversations_insert ON agent_conversations FOR INSERT
        WITH CHECK (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND created_by::text = current_setting('app.current_user', true)
        )
        """
    )
    op.execute(
        """
        CREATE POLICY agent_conversations_update ON agent_conversations FOR UPDATE
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND created_by::text = current_setting('app.current_user', true)
        )
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true))
        """
    )
    op.execute(
        """
        CREATE POLICY agent_conversations_delete ON agent_conversations FOR DELETE
        USING (
            tenant_id::text = current_setting('app.current_tenant', true)
            AND (
                created_by::text = current_setting('app.current_user', true)
                OR app_is_workspace_owner(tenant_id)
            )
        )
        """
    )

    # ----- agent_messages policies ----------------------------------------
    # A message inherits its parent conversation's visibility. We use an
    # EXISTS sub-select against ``agent_conversations`` — that hits the
    # parent's SELECT policy too, so the cascading visibility check
    # stays consistent.
    op.execute(
        """
        CREATE POLICY agent_messages_select ON agent_messages FOR SELECT
        USING (
            EXISTS (
                SELECT 1 FROM agent_conversations c
                WHERE c.id = agent_messages.conversation_id
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY agent_messages_insert ON agent_messages FOR INSERT
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM agent_conversations c
                WHERE c.id = agent_messages.conversation_id
            )
        )
        """
    )
    # No DELETE policy on agent_messages — append-only by design. If we
    # ever need to retract a message we'll add a soft-delete column.

    # ======================================================================
    # Runtime grants
    # ======================================================================
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON agent_conversations TO dataprep_app")
    op.execute("GRANT SELECT, INSERT ON agent_messages TO dataprep_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS agent_messages_insert ON agent_messages")
    op.execute("DROP POLICY IF EXISTS agent_messages_select ON agent_messages")
    op.execute("DROP POLICY IF EXISTS agent_conversations_delete ON agent_conversations")
    op.execute("DROP POLICY IF EXISTS agent_conversations_update ON agent_conversations")
    op.execute("DROP POLICY IF EXISTS agent_conversations_insert ON agent_conversations")
    op.execute("DROP POLICY IF EXISTS agent_conversations_select ON agent_conversations")

    op.drop_index("ix_agent_messages_created_at", table_name="agent_messages")
    op.drop_index("ix_agent_messages_conversation_id", table_name="agent_messages")
    op.drop_table("agent_messages")

    op.drop_index("ix_agent_conversations_credential_id", table_name="agent_conversations")
    op.drop_index("ix_agent_conversations_created_by", table_name="agent_conversations")
    op.drop_index("ix_agent_conversations_dataset_id", table_name="agent_conversations")
    op.drop_index("ix_agent_conversations_tenant_id", table_name="agent_conversations")
    op.drop_table("agent_conversations")

    op.execute("DROP TYPE IF EXISTS agent_message_role")
