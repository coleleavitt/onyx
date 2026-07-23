"""Add project connected knowledge associations.

Revision ID: 9b1c2d3e4f5a
Revises: 56ed226ea079, c7bf5721733e
Create Date: 2026-07-22 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9b1c2d3e4f5a"
down_revision = ("56ed226ea079", "c7bf5721733e")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project__hierarchy_node",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("hierarchy_node_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["hierarchy_node_id"], ["hierarchy_node.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["user_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "hierarchy_node_id"),
    )
    op.create_index(
        "ix_project__hierarchy_node_node_id",
        "project__hierarchy_node",
        ["hierarchy_node_id"],
        unique=False,
    )

    op.create_table(
        "project__document",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["user_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "document_id"),
    )
    op.create_index(
        "ix_project__document_document_id",
        "project__document",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_project__document_document_id", table_name="project__document")
    op.drop_table("project__document")
    op.drop_index(
        "ix_project__hierarchy_node_node_id", table_name="project__hierarchy_node"
    )
    op.drop_table("project__hierarchy_node")
