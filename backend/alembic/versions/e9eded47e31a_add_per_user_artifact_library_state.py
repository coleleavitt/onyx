"""add per-user artifact library state

Revision ID: e9eded47e31a
Revises: 273cacc1decf
Create Date: 2026-07-10 15:12:29.983411

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "e9eded47e31a"
down_revision = "273cacc1decf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_library_item__user_state",
        sa.Column(
            "artifact_library_item_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "is_pinned",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_dismissed",
            sa.Boolean(),
            server_default=sa.text("false"),
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
            ["artifact_library_item_id"],
            ["artifact_library_item.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("artifact_library_item_id", "user_id"),
    )
    op.create_index(
        "ix_artifact_library_item__user_state_user_pinned",
        "artifact_library_item__user_state",
        ["user_id", "is_pinned"],
    )
    op.create_index(
        "ix_artifact_library_item__user_state_user_dismissed",
        "artifact_library_item__user_state",
        ["user_id", "is_dismissed"],
    )
    op.execute(
        sa.text(
            """
            INSERT INTO artifact_library_item__user_state (
                artifact_library_item_id,
                user_id,
                is_pinned,
                is_dismissed
            )
            SELECT id, owner_user_id, true, false
            FROM artifact_library_item
            WHERE is_pinned = true
            """
        )
    )
    op.drop_column("artifact_library_item", "is_pinned")


def downgrade() -> None:
    op.add_column(
        "artifact_library_item",
        sa.Column(
            "is_pinned",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE artifact_library_item AS item
            SET is_pinned = true
            FROM artifact_library_item__user_state AS state
            WHERE state.artifact_library_item_id = item.id
              AND state.user_id = item.owner_user_id
              AND state.is_pinned = true
            """
        )
    )
    op.drop_index(
        "ix_artifact_library_item__user_state_user_dismissed",
        table_name="artifact_library_item__user_state",
    )
    op.drop_index(
        "ix_artifact_library_item__user_state_user_pinned",
        table_name="artifact_library_item__user_state",
    )
    op.drop_table("artifact_library_item__user_state")
