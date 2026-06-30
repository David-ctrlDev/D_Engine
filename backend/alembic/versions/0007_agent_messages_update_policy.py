"""agent_messages UPDATE policy — let the agent attach visualizations

``agent_messages`` was created append-only (migration 0004): only SELECT
and INSERT RLS policies, no UPDATE. Migration 0006 then added the
``visualizations`` JSONB column, and the agent loop in
:mod:`app.agent.service` updates a freshly-inserted assistant row to pin
the charts a tool produced (``_run_agent_loop`` and
``resolve_pending_action``).

With RLS enabled and **no** UPDATE policy, Postgres makes zero rows
visible to an UPDATE, so SQLAlchemy's ``flush()`` raises
``StaleDataError: expected to update 1 row(s); 0 were matched`` and the
whole turn rolls back. The visible symptom: text-only turns (the kickoff
greeting, plain chat) work, but the moment the agent runs any tool that
emits a visualization the request 500s — i.e. the product "only works as
a chat" and never executes its agentic pipeline.

This migration adds the missing UPDATE policy, mirroring the
conversation-ownership ``EXISTS`` check used by the SELECT/INSERT
policies. The 0004 comment anticipated exactly this ("If we ever need
... we'll add a policy"). The table stays effectively append-only at the
content level — we only ever update ``visualizations`` server-side — but
the database now permits the owner's update.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-29
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A message stays editable only while its parent conversation is
    # visible to the caller — same cascading-visibility rule the SELECT
    # and INSERT policies use. ``WITH CHECK`` re-asserts it on the new
    # row image so an update can't re-parent a message into a
    # conversation the caller can't see.
    op.execute(
        """
        CREATE POLICY agent_messages_update ON agent_messages FOR UPDATE
        USING (
            EXISTS (
                SELECT 1 FROM agent_conversations c
                WHERE c.id = agent_messages.conversation_id
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM agent_conversations c
                WHERE c.id = agent_messages.conversation_id
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS agent_messages_update ON agent_messages")
