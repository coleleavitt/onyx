"""add chat_session project_visibility

Per-thread visibility of a project (space) chat session to OTHER space members.
PRIVATE (default) preserves today's behavior — a member only sees their own
threads in a space; SHARED opts a thread in for all space members.

Revision ID: d4f8a1c9b2e3
Revises: ac23de45fa67
Create Date: 2026-07-24 19:40:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d4f8a1c9b2e3"
down_revision = "ac23de45fa67"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # native_enum=False in the model -> stored as VARCHAR. Default 'private'
    # backfills every existing row, which matches current per-user visibility.
    op.add_column(
        "chat_session",
        sa.Column(
            "project_visibility",
            sa.String(),
            nullable=False,
            server_default="private",
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_session", "project_visibility")
