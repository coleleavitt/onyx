"""add emoji to user_project

Revision ID: f4a2c1b9d3e7
Revises: 8a1b2c3d4e5f
Create Date: 2026-07-14 19:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f4a2c1b9d3e7"
down_revision = "8a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_project",
        sa.Column("emoji", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_project", "emoji")
