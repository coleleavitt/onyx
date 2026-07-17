"""add brain memory graph (relations, sources, per-user brain settings)

Revision ID: b7c3e9f1a2d4
Revises: f4a2c1b9d3e7
Create Date: 2026-07-14 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b7c3e9f1a2d4"
down_revision = "f4a2c1b9d3e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "brain_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "user",
        sa.Column(
            "brain_use_connectors",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "user",
        sa.Column("brain_focus_instructions", sa.Text(), nullable=True),
    )
    op.add_column(
        "user",
        sa.Column("brain_last_run_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "memory_relation",
        sa.Column("memory_id_low", sa.Integer(), nullable=False),
        sa.Column("memory_id_high", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["memory_id_low"], ["memory.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["memory_id_high"], ["memory.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("memory_id_low", "memory_id_high"),
        sa.CheckConstraint(
            "memory_id_low < memory_id_high", name="memory_relation_ordered"
        ),
    )
    op.create_index("ix_memory_relation_high", "memory_relation", ["memory_id_high"])

    op.create_table(
        "memory_source",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("memory_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("label", sa.String(length=512), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["memory_id"], ["memory.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_source_memory", "memory_source", ["memory_id"])


def downgrade() -> None:
    op.drop_index("ix_memory_source_memory", table_name="memory_source")
    op.drop_table("memory_source")
    op.drop_index("ix_memory_relation_high", table_name="memory_relation")
    op.drop_table("memory_relation")
    op.drop_column("user", "brain_last_run_at")
    op.drop_column("user", "brain_focus_instructions")
    op.drop_column("user", "brain_use_connectors")
    op.drop_column("user", "brain_enabled")
