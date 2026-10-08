"""add ai weekly reviews

Revision ID: d6a1f3c8b920
Revises: c4e8f2a1b607
Create Date: 2026-10-07

"""

import sqlalchemy as sa
from alembic import op

revision = "d6a1f3c8b920"
down_revision = "c4e8f2a1b607"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "aiweeklyreview",
        sa.Column("headline", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=800), nullable=False),
        sa.Column("wins", sa.JSON(), nullable=False),
        sa.Column("concerns", sa.JSON(), nullable=False),
        sa.Column("priorities", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("period_start_date", sa.Date(), nullable=False),
        sa.Column("period_end_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("source", sa.JSON(), nullable=False),
        sa.Column("generated_by_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["generated_by_id"],
            ["user.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_aiweeklyreview_generated_by_id",
        "aiweeklyreview",
        ["generated_by_id"],
        unique=False,
    )
    op.create_index(
        "ix_aiweeklyreview_period_end_generated_at",
        "aiweeklyreview",
        ["period_end_date", "generated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_aiweeklyreview_period_end_generated_at",
        table_name="aiweeklyreview",
    )
    op.drop_index(
        "ix_aiweeklyreview_generated_by_id",
        table_name="aiweeklyreview",
    )
    op.drop_table("aiweeklyreview")
