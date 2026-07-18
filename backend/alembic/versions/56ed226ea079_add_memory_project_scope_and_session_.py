"""add memory project scope and session source urls

Revision ID: 56ed226ea079
Revises: 1a1559fcb1d7
Create Date: 2026-07-17 20:18:43.176022

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "56ed226ea079"
down_revision = "1a1559fcb1d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Space scoping: memories can be tied to a project (space); NULL = global.
    # Deleting the project releases its memories back to the global scope.
    op.add_column(
        "memory",
        sa.Column("project_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_memory_project_id",
        "memory",
        "user_project",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_memory_user_project", "memory", ["user_id", "project_id"])

    # Chat-session memory sources become clickable citations: point them at the
    # session in the app. Backfill existing rows that never got a URL.
    op.execute(
        "UPDATE memory_source "
        "SET url = '/app?chatId=' || source_id "
        "WHERE source_type = 'chat_session' AND url IS NULL AND source_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE memory_source "
        "SET url = NULL "
        "WHERE source_type = 'chat_session' AND url = '/app?chatId=' || source_id"
    )
    op.drop_index("ix_memory_user_project", table_name="memory")
    op.drop_constraint("fk_memory_project_id", "memory", type_="foreignkey")
    op.drop_column("memory", "project_id")
