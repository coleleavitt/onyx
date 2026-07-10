"""add memory governance

Revision ID: 273cacc1decf
Revises: 07bc5b4a5bef
Create Date: 2026-07-10 14:05:37.917056

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "273cacc1decf"
down_revision = "07bc5b4a5bef"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_memory_created_at", "memory", ["created_at"])
    op.create_table(
        "memory_governance_policy",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column(
            "memories_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "memory_creation_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="memory_governance_policy_singleton"),
        sa.CheckConstraint(
            "retention_days IS NULL OR retention_days BETWEEN 1 AND 3650",
            name="memory_governance_retention_days_range",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "memory_governance_audit",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "POLICY_UPDATED",
                "RETENTION_CLEANUP",
                "BULK_DELETE",
                name="memorygovernanceauditaction",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("affected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memory_governance_audit_created_at",
        "memory_governance_audit",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_memory_governance_audit_created_at",
        table_name="memory_governance_audit",
    )
    op.drop_table("memory_governance_audit")
    op.drop_table("memory_governance_policy")
    op.drop_index("ix_memory_created_at", table_name="memory")
