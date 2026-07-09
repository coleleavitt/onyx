"""add indexing source progress

Revision ID: 519005e974a3
Revises: f6b0949ea33d
Create Date: 2026-07-09 15:29:29.116227

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "519005e974a3"
down_revision = "f6b0949ea33d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "index_attempt",
        sa.Column(
            "source_docs_discovered",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "index_attempt",
        sa.Column("source_docs_estimated", sa.Integer(), nullable=True),
    )
    op.add_column(
        "index_attempt",
        sa.Column("source_doc_estimate_method", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "index_attempt",
        sa.Column(
            "source_doc_estimate_time", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "index_attempt",
        sa.Column("source_progress_label", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("index_attempt", "source_progress_label")
    op.drop_column("index_attempt", "source_doc_estimate_time")
    op.drop_column("index_attempt", "source_doc_estimate_method")
    op.drop_column("index_attempt", "source_docs_estimated")
    op.drop_column("index_attempt", "source_docs_discovered")
