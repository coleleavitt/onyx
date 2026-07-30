"""add default model to user project

Revision ID: c3d4e5f6a7b8
Revises: f2a7c4e8b19d
Create Date: 2026-07-30 16:37:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "f2a7c4e8b19d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_project",
        sa.Column("default_model_configuration_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_user_project_default_model_configuration_id",
        "user_project",
        "model_configuration",
        ["default_model_configuration_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_user_project_default_model_configuration_id",
        "user_project",
        type_="foreignkey",
    )
    op.drop_column("user_project", "default_model_configuration_id")
