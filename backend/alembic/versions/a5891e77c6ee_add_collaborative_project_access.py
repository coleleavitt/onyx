"""add collaborative project access

Revision ID: a5891e77c6ee
Revises: 8e3a1b6d4f20
Create Date: 2026-07-10 12:46:22.098960

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a5891e77c6ee"
down_revision = "8e3a1b6d4f20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_project",
        sa.Column("organization_permission", sa.String(), nullable=True),
    )
    op.create_table(
        "project__user",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission", sa.String(), nullable=False, server_default="VIEWER"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["user_project.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "user_id"),
    )
    op.create_index("ix_project__user_user_id", "project__user", ["user_id"])
    op.create_table(
        "project__user_group",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(), nullable=False, server_default="VIEWER"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["user_project.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_group_id"], ["user_group.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("project_id", "user_group_id"),
    )
    op.create_table(
        "project_join_request",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("requester_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "requested_permission",
            sa.String(),
            nullable=False,
            server_default="VIEWER",
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("resolution_comment", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["user_project.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["requester_user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "requester_user_id",
            name="uq_project_join_request_project_requester",
        ),
    )
    op.create_index(
        "ix_project_join_request_project_status",
        "project_join_request",
        ["project_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_join_request_project_status",
        table_name="project_join_request",
    )
    op.drop_table("project_join_request")
    op.drop_table("project__user_group")
    op.drop_index("ix_project__user_user_id", table_name="project__user")
    op.drop_table("project__user")
    op.drop_column("user_project", "organization_permission")
