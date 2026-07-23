"""add connected source access type

Revision ID: ac23de45fa67
Revises: ab12cd34ef56
Create Date: 2026-07-23 18:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ac23de45fa67"
down_revision = "ab12cd34ef56"
branch_labels = None
depends_on = None


access_type_enum = sa.Enum(
    "PUBLIC",
    "RESTRICTED",
    name="connectedsourceaccesstype",
    native_enum=False,
)


def upgrade() -> None:
    op.add_column(
        "connected_source_scope",
        sa.Column(
            "access_type",
            access_type_enum,
            server_default="PUBLIC",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("connected_source_scope", "access_type")
