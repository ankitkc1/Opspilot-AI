"""add ai daily briefings

Revision ID: 4f7c2b9d1e30
Revises: 2f1c7a8d4b60
Create Date: 2026-10-07

"""

import sqlalchemy as sa
from alembic import op


revision = "4f7c2b9d1e30"
down_revision = "2f1c7a8d4b60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "aidailybriefing",
        sa.Column("headline", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False),
        sa.Column("priorities", sa.JSON(), nullable=False),
        sa.Column("risks", sa.JSON(), nullable=False),
        sa.Column("opportunities", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
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
        "ix_aidailybriefing_generated_by_id",
        "aidailybriefing",
        ["generated_by_id"],
        unique=False,
    )
    op.create_index(
        "ix_aidailybriefing_report_date_generated_at",
        "aidailybriefing",
        ["report_date", "generated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_aidailybriefing_report_date_generated_at",
        table_name="aidailybriefing",
    )
    op.drop_index(
        "ix_aidailybriefing_generated_by_id",
        table_name="aidailybriefing",
    )
    op.drop_table("aidailybriefing")
