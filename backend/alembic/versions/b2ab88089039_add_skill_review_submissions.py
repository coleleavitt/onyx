"""add skill review submissions

Revision ID: b2ab88089039
Revises: a5891e77c6ee
Create Date: 2026-07-10 13:12:48.196361

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b2ab88089039"
down_revision = "a5891e77c6ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill_review_submission",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "submitted_by_user_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("bundle_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(), server_default="PENDING", nullable=False),
        sa.Column("submission_comment", sa.Text(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["skill_id"], ["skill.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"], ["user.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_skill_review_submission_status_submitted",
        "skill_review_submission",
        ["status", "submitted_at"],
    )
    op.create_index(
        "ix_skill_review_submission_skill",
        "skill_review_submission",
        ["skill_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_skill_review_submission_skill", table_name="skill_review_submission"
    )
    op.drop_index(
        "ix_skill_review_submission_status_submitted",
        table_name="skill_review_submission",
    )
    op.drop_table("skill_review_submission")
