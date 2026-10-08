"""add weekly ai automation

Revision ID: b0e5f7a2c964
Revises: a9d4e6f1b853
Create Date: 2026-10-08

"""

import sqlalchemy as sa
from alembic import op

revision = "b0e5f7a2c964"
down_revision = "a9d4e6f1b853"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "aiweeklyreview",
        sa.Column(
            "generation_mode",
            sa.String(length=20),
            server_default="manual",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_aiweeklyreview_generation_mode",
        "aiweeklyreview",
        "generation_mode IN ('manual', 'automation')",
    )

    op.add_column(
        "aiautomationsetting",
        sa.Column(
            "weekly_review_enabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "aiautomationsetting",
        sa.Column(
            "weekly_review_weekday",
            sa.SmallInteger(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "aiautomationsetting",
        sa.Column(
            "weekly_review_time",
            sa.Time(),
            server_default="09:00:00",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_aiautomationsetting_weekday",
        "aiautomationsetting",
        "weekly_review_weekday BETWEEN 0 AND 6",
    )

    op.add_column(
        "aiautomationrun",
        sa.Column(
            "automation_type",
            sa.String(length=30),
            server_default="daily_briefing",
            nullable=False,
        ),
    )
    op.add_column(
        "aiautomationrun",
        sa.Column("weekly_review_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_aiautomationrun_weekly_review_id",
        "aiautomationrun",
        "aiweeklyreview",
        ["weekly_review_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_aiautomationrun_type",
        "aiautomationrun",
        "automation_type IN ('daily_briefing', 'weekly_review')",
    )
    op.create_check_constraint(
        "ck_aiautomationrun_single_result",
        "aiautomationrun",
        "NOT (briefing_id IS NOT NULL AND weekly_review_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_aiautomationrun_single_result",
        "aiautomationrun",
        type_="check",
    )
    op.drop_constraint(
        "ck_aiautomationrun_type",
        "aiautomationrun",
        type_="check",
    )
    op.drop_constraint(
        "fk_aiautomationrun_weekly_review_id",
        "aiautomationrun",
        type_="foreignkey",
    )
    op.drop_column("aiautomationrun", "weekly_review_id")
    op.drop_column("aiautomationrun", "automation_type")

    op.drop_constraint(
        "ck_aiautomationsetting_weekday",
        "aiautomationsetting",
        type_="check",
    )
    op.drop_column("aiautomationsetting", "weekly_review_time")
    op.drop_column("aiautomationsetting", "weekly_review_weekday")
    op.drop_column("aiautomationsetting", "weekly_review_enabled")

    op.drop_constraint(
        "ck_aiweeklyreview_generation_mode",
        "aiweeklyreview",
        type_="check",
    )
    op.drop_column("aiweeklyreview", "generation_mode")
