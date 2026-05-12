"""Agent message: suggestions column

Adds a JSONB ``suggestions`` column to ``agent_messages`` so the agent
can attach intent-capture chips to a turn. The frontend renders the
list as clickable buttons under the message; picking one sends its
text as the next user message.

We deliberately keep this *out* of the structured tool-use surface
(which lands in G2.3 with provider-specific function calling). For
G2.1+ we just ask the LLM to emit a ``SUGGESTIONS:[...]`` line at the
end of its text, strip + parse it server-side, store the resulting
list here.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-13
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_messages",
        sa.Column("suggestions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_messages", "suggestions")
