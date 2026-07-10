"""add artifact library and versions

Revision ID: 07bc5b4a5bef
Revises: b2ab88089039
Create Date: 2026-07-10 13:28:39.294288

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "07bc5b4a5bef"
down_revision = "b2ab88089039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    artifact_type = sa.Enum(
        "web_app",
        "pptx",
        "docx",
        "pdf",
        "image",
        "markdown",
        "excel",
        "csv",
        "other",
        name="artifacttype",
        native_enum=False,
    )
    op.create_table(
        "artifact_library_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", artifact_type, nullable=False),
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_artifact_library_item_owner_updated",
        "artifact_library_item",
        ["owner_user_id", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_artifact_library_item_published",
        "artifact_library_item",
        ["published_at"],
    )
    op.create_table(
        "artifact_library_item__user",
        sa.Column(
            "artifact_library_item_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_library_item_id"],
            ["artifact_library_item.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("artifact_library_item_id", "user_id"),
    )
    op.create_index(
        "ix_artifact_library_item__user_user_id",
        "artifact_library_item__user",
        ["user_id"],
    )
    op.create_table(
        "artifact_library_item__user_group",
        sa.Column(
            "artifact_library_item_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("user_group_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_library_item_id"],
            ["artifact_library_item.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_group_id"], ["user_group.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("artifact_library_item_id", "user_group_id"),
    )

    op.drop_constraint("artifact_session_id_fkey", "artifact", type_="foreignkey")
    op.alter_column("artifact", "session_id", nullable=True)
    op.create_foreign_key(
        "artifact_session_id_fkey",
        "artifact",
        "build_session",
        ["session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "artifact",
        sa.Column("library_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "artifact",
        sa.Column("version_number", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column("artifact", sa.Column("storage_file_id", sa.String(), nullable=True))
    op.add_column("artifact", sa.Column("mime_type", sa.String(), nullable=True))
    op.add_column("artifact", sa.Column("size_bytes", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "artifact_library_item_id_fkey",
        "artifact",
        "artifact_library_item",
        ["library_item_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_artifact_library_item_version",
        "artifact",
        ["library_item_id", "version_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_library_item_version", table_name="artifact")
    op.drop_constraint("artifact_library_item_id_fkey", "artifact", type_="foreignkey")
    op.drop_column("artifact", "size_bytes")
    op.drop_column("artifact", "mime_type")
    op.drop_column("artifact", "storage_file_id")
    op.drop_column("artifact", "version_number")
    op.drop_column("artifact", "library_item_id")
    op.drop_constraint("artifact_session_id_fkey", "artifact", type_="foreignkey")
    op.alter_column("artifact", "session_id", nullable=False)
    op.create_foreign_key(
        "artifact_session_id_fkey",
        "artifact",
        "build_session",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_table("artifact_library_item__user_group")
    op.drop_index(
        "ix_artifact_library_item__user_user_id",
        table_name="artifact_library_item__user",
    )
    op.drop_table("artifact_library_item__user")
    op.drop_index(
        "ix_artifact_library_item_published", table_name="artifact_library_item"
    )
    op.drop_index(
        "ix_artifact_library_item_owner_updated",
        table_name="artifact_library_item",
    )
    op.drop_table("artifact_library_item")
