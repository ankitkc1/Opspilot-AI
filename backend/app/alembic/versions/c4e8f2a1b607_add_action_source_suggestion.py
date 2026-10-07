"""add action source suggestion

Revision ID: c4e8f2a1b607
Revises: 7b3d1e9f6a20
Create Date: 2026-10-07

"""

import sqlalchemy as sa
from alembic import op

revision = "c4e8f2a1b607"
down_revision = "7b3d1e9f6a20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "actionitem",
        sa.Column("source_suggestion", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "uq_actionitem_owner_source_suggestion",
        "actionitem",
        [
            "created_by_id",
            "source_briefing_id",
            "category",
            "source_suggestion",
        ],
        unique=True,
        postgresql_where=sa.text(
            "source_briefing_id IS NOT NULL AND source_suggestion IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_actionitem_owner_source_suggestion",
        table_name="actionitem",
    )
    op.drop_column("actionitem", "source_suggestion")
