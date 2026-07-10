"""normalize memory category values

Revision ID: 7e0f1a2b3c4d
Revises: 6d9e0f1a2b3c
Create Date: 2026-07-10 17:05:00.000000

"""

import sqlalchemy as sa
from alembic import op


revision = "7e0f1a2b3c4d"
down_revision = "6d9e0f1a2b3c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE memory
            SET category = lower(category)
            WHERE category IN ('NOTES', 'CONCEPTS', 'ENTITIES', 'WORKSTREAMS')
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE memory_revision
            SET category = lower(category)
            WHERE category IN ('NOTES', 'CONCEPTS', 'ENTITIES', 'WORKSTREAMS')
            """
        )
    )


def downgrade() -> None:
    pass
