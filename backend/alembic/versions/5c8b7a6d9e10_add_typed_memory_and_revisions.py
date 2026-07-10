"""add typed memory and revisions

Revision ID: 5c8b7a6d9e10
Revises: e9eded47e31a
Create Date: 2026-07-10 16:05:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "5c8b7a6d9e10"
down_revision = "e9eded47e31a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "memory",
        sa.Column("title", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "memory",
        sa.Column(
            "category",
            sa.String(length=32),
            server_default="notes",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_memory_user_category_updated",
        "memory",
        ["user_id", "category", "updated_at"],
    )
    op.create_table(
        "memory_revision",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("memory_text", sa.Text(), nullable=False),
        sa.Column(
            "source",
            sa.String(length=32),
            server_default="manual",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["memory_id"], ["memory.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memory_revision_memory_created",
        "memory_revision",
        ["memory_id", "created_at"],
    )
    op.execute(
        sa.text(
            """
            INSERT INTO memory_revision (
                id,
                memory_id,
                title,
                category,
                memory_text,
                source,
                created_at
            )
            SELECT
                gen_random_uuid(),
                id,
                title,
                category,
                memory_text,
                'migration',
                created_at
            FROM memory
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_memory_revision_memory_created", table_name="memory_revision")
    op.drop_table("memory_revision")
    op.drop_index("ix_memory_user_category_updated", table_name="memory")
    op.drop_column("memory", "category")
    op.drop_column("memory", "title")
