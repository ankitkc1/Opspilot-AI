"""link actions to weekly reviews

Revision ID: e7b2c4d9a631
Revises: d6a1f3c8b920
Create Date: 2026-10-08

"""

import sqlalchemy as sa
from alembic import op

revision = "e7b2c4d9a631"
down_revision = "d6a1f3c8b920"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "actionitem",
        sa.Column("source_weekly_review_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_actionitem_source_weekly_review_id_aiweeklyreview",
        "actionitem",
        "aiweeklyreview",
        ["source_weekly_review_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_actionitem_single_ai_source",
        "actionitem",
        "NOT (source_briefing_id IS NOT NULL "
        "AND source_weekly_review_id IS NOT NULL)",
    )
    op.create_index(
        "ix_actionitem_source_weekly_review_id",
        "actionitem",
        ["source_weekly_review_id"],
        unique=False,
    )
    op.create_index(
        "uq_actionitem_owner_weekly_source_suggestion",
        "actionitem",
        [
            "created_by_id",
            "source_weekly_review_id",
            "category",
            "source_suggestion",
        ],
        unique=True,
        postgresql_where=sa.text(
            "source_weekly_review_id IS NOT NULL "
            "AND source_suggestion IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_actionitem_owner_weekly_source_suggestion",
        table_name="actionitem",
    )
    op.drop_index(
        "ix_actionitem_source_weekly_review_id",
        table_name="actionitem",
    )
    op.drop_constraint(
        "ck_actionitem_single_ai_source",
        "actionitem",
        type_="check",
    )
    op.drop_constraint(
        "fk_actionitem_source_weekly_review_id_aiweeklyreview",
        "actionitem",
        type_="foreignkey",
    )
    op.drop_column("actionitem", "source_weekly_review_id")
