"""add daily ai automation

Revision ID: a9d4e6f1b853
Revises: f8c3d5e0a742
Create Date: 2026-10-08

"""

import sqlalchemy as sa
from alembic import op

revision = "a9d4e6f1b853"
down_revision = "f8c3d5e0a742"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "aidailybriefing",
        sa.Column(
            "generation_mode",
            sa.String(length=20),
            server_default="manual",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_aidailybriefing_generation_mode",
        "aidailybriefing",
        "generation_mode IN ('manual', 'automation')",
    )
    op.create_table(
        "aiautomationsetting",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "daily_briefing_enabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("daily_briefing_time", sa.Time(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_aiautomationsetting_user_id",
        "aiautomationsetting",
        ["user_id"],
        unique=True,
    )
    op.create_table(
        "aiautomationrun",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_key", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("scheduled_for", sa.Date(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("briefing_id", sa.Uuid(), nullable=True),
        sa.Column("error", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(
            ["briefing_id"],
            ["aidailybriefing.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "trigger IN ('manual', 'scheduled')",
            name="ck_aiautomationrun_trigger",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ck_aiautomationrun_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_aiautomationrun_run_key",
        "aiautomationrun",
        ["run_key"],
        unique=True,
    )
    op.create_index(
        "ix_aiautomationrun_user_id",
        "aiautomationrun",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_aiautomationrun_user_started_at",
        "aiautomationrun",
        ["user_id", "started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_aiautomationrun_user_started_at",
        table_name="aiautomationrun",
    )
    op.drop_index("ix_aiautomationrun_user_id", table_name="aiautomationrun")
    op.drop_index("ix_aiautomationrun_run_key", table_name="aiautomationrun")
    op.drop_table("aiautomationrun")
    op.drop_index(
        "ix_aiautomationsetting_user_id",
        table_name="aiautomationsetting",
    )
    op.drop_table("aiautomationsetting")
    op.drop_constraint(
        "ck_aidailybriefing_generation_mode",
        "aidailybriefing",
        type_="check",
    )
    op.drop_column("aidailybriefing", "generation_mode")
