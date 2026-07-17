"""add user_project__user_state for per-user space pinning

Revision ID: 8a1b2c3d4e5f
Revises: 7e0f1a2b3c4d
Create Date: 2026-07-14 18:30:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "8a1b2c3d4e5f"
down_revision = "7e0f1a2b3c4d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_project__user_state",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "is_pinned",
            sa.Boolean(),
            server_default=sa.false(),
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
        sa.ForeignKeyConstraint(
            ["project_id"], ["user_project.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "user_id"),
    )
    op.create_index(
        "ix_user_project__user_state_user_pinned",
        "user_project__user_state",
        ["user_id", "is_pinned"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_project__user_state_user_pinned",
        table_name="user_project__user_state",
    )
    op.drop_table("user_project__user_state")
