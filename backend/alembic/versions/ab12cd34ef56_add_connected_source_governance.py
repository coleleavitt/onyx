"""add connected source governance

Revision ID: ab12cd34ef56
Revises: 9b1c2d3e4f5a
Create Date: 2026-07-23 16:45:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ab12cd34ef56"
down_revision = "9b1c2d3e4f5a"
branch_labels = None
depends_on = None


curation_status_enum = sa.Enum(
    "DEFAULT_SAFE",
    "STANDARD",
    "ARCHIVE",
    "HIDDEN",
    "DIAGNOSTIC",
    name="connectedsourcecurationstatus",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "connected_source_scope",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hierarchy_node_id", sa.Integer(), nullable=False),
        sa.Column(
            "curation_status",
            curation_status_enum,
            server_default="STANDARD",
            nullable=False,
        ),
        sa.Column("display_label", sa.String(), nullable=True),
        sa.Column("tenant_label", sa.String(), nullable=True),
        sa.Column("department_label", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("document_count_estimate", sa.Integer(), nullable=True),
        sa.Column("warning", sa.String(), nullable=True),
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
            ["hierarchy_node_id"], ["hierarchy_node.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hierarchy_node_id"),
    )
    op.create_index(
        "ix_connected_source_scope_hierarchy_node_id",
        "connected_source_scope",
        ["hierarchy_node_id"],
    )
    op.create_index(
        "ix_connected_source_scope_status",
        "connected_source_scope",
        ["curation_status"],
    )

    op.create_table(
        "connected_source_scope__user_group",
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.Column("user_group_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["connected_source_scope.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_group_id"], ["user_group.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("scope_id", "user_group_id"),
    )

    op.create_table(
        "connected_source_scope_exclusion",
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.Column("excluded_hierarchy_node_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["connected_source_scope.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["excluded_hierarchy_node_id"], ["hierarchy_node.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("scope_id", "excluded_hierarchy_node_id"),
    )
    op.create_index(
        "ix_connected_source_scope_exclusion_excluded_node",
        "connected_source_scope_exclusion",
        ["excluded_hierarchy_node_id"],
    )

    op.create_table(
        "project_connected_knowledge_preset",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("emoji", sa.String(), nullable=True),
        sa.Column("instructions", sa.String(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.false(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "project_connected_knowledge_preset__hierarchy_node",
        sa.Column("preset_id", sa.Integer(), nullable=False),
        sa.Column("hierarchy_node_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["preset_id"],
            ["project_connected_knowledge_preset.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hierarchy_node_id"], ["hierarchy_node.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("preset_id", "hierarchy_node_id"),
    )

    op.create_table(
        "project_connected_knowledge_preset__document",
        sa.Column("preset_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["preset_id"],
            ["project_connected_knowledge_preset.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("preset_id", "document_id"),
    )


def downgrade() -> None:
    op.drop_table("project_connected_knowledge_preset__document")
    op.drop_table("project_connected_knowledge_preset__hierarchy_node")
    op.drop_table("project_connected_knowledge_preset")
    op.drop_index(
        "ix_connected_source_scope_exclusion_excluded_node",
        table_name="connected_source_scope_exclusion",
    )
    op.drop_table("connected_source_scope_exclusion")
    op.drop_table("connected_source_scope__user_group")
    op.drop_index(
        "ix_connected_source_scope_status", table_name="connected_source_scope"
    )
    op.drop_index(
        "ix_connected_source_scope_hierarchy_node_id",
        table_name="connected_source_scope",
    )
    op.drop_table("connected_source_scope")
