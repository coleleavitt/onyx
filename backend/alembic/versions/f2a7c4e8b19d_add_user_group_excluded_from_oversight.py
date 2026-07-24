"""add user_group excluded_from_oversight

Members of a group flagged `excluded_from_oversight` are never surfaced through
the query-history (oversight) surface, for anyone including admins. This keeps
an executive/leadership tier's sessions private.

Revision ID: f2a7c4e8b19d
Revises: e5a9b7c1d3f2
Create Date: 2026-07-24 22:45:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f2a7c4e8b19d"
down_revision = "e5a9b7c1d3f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_group",
        sa.Column(
            "excluded_from_oversight",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_group", "excluded_from_oversight")
