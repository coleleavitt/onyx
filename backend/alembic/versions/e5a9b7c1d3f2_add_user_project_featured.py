"""add user_project featured columns

Featuring auto-surfaces a space in entitled members' sidebars. featured_for_group_id
targets a department group; is_org_featured targets the whole org. Featuring grants
no access on its own.

Revision ID: e5a9b7c1d3f2
Revises: d4f8a1c9b2e3
Create Date: 2026-07-24 19:55:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e5a9b7c1d3f2"
down_revision = "d4f8a1c9b2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_project",
        sa.Column("featured_for_group_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "user_project_featured_for_group_id_fkey",
        "user_project",
        "user_group",
        ["featured_for_group_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "user_project",
        sa.Column(
            "is_org_featured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "user_project_featured_for_group_id_fkey",
        "user_project",
        type_="foreignkey",
    )
    op.drop_column("user_project", "is_org_featured")
    op.drop_column("user_project", "featured_for_group_id")
