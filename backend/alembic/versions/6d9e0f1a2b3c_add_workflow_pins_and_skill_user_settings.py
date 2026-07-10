"""add workflow pins and skill user settings

Revision ID: 6d9e0f1a2b3c
Revises: 5c8b7a6d9e10
Create Date: 2026-07-10 16:06:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "6d9e0f1a2b3c"
down_revision = "5c8b7a6d9e10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skill",
        sa.Column(
            "category",
            sa.String(length=80),
            server_default="Custom",
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE skill
            SET category = CASE
                WHEN built_in_skill_id IN ('pptx', 'image-generation')
                    THEN 'Content creation'
                WHEN built_in_skill_id IN ('company-search', 'browser')
                    THEN 'Research'
                WHEN built_in_skill_id IN ('slack', 'google-calendar', 'gmail')
                    THEN 'Productivity'
                WHEN built_in_skill_id IS NOT NULL
                    THEN 'Connected apps'
                ELSE 'Custom'
            END
            """
        )
    )
    op.create_table(
        "skill__user_state",
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["skill_id"], ["skill.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("skill_id", "user_id"),
    )
    op.create_index(
        "ix_skill__user_state_user_id",
        "skill__user_state",
        ["user_id"],
    )
    op.create_table(
        "workflow_pin",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "workflow_id"),
    )
    op.create_index(
        "ix_workflow_pin_user_created",
        "workflow_pin",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_pin_user_created", table_name="workflow_pin")
    op.drop_table("workflow_pin")
    op.drop_index("ix_skill__user_state_user_id", table_name="skill__user_state")
    op.drop_table("skill__user_state")
    op.drop_column("skill", "category")
