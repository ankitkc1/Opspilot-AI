"""add ai action center

Revision ID: 7b3d1e9f6a20
Revises: 4f7c2b9d1e30
Create Date: 2026-10-07

"""

import sqlalchemy as sa
from alembic import op

revision = "7b3d1e9f6a20"
down_revision = "4f7c2b9d1e30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "actionitem",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_briefing_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "category IN ('priority', 'risk', 'opportunity')",
            name="ck_actionitem_category",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high')",
            name="ck_actionitem_priority",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'completed', 'dismissed')",
            name="ck_actionitem_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["user.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_briefing_id"],
            ["aidailybriefing.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_actionitem_created_by_id",
        "actionitem",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        "ix_actionitem_source_briefing_id",
        "actionitem",
        ["source_briefing_id"],
        unique=False,
    )
    op.create_index(
        "ix_actionitem_owner_status_created",
        "actionitem",
        ["created_by_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_actionitem_owner_status_created",
        table_name="actionitem",
    )
    op.drop_index(
        "ix_actionitem_source_briefing_id",
        table_name="actionitem",
    )
    op.drop_index(
        "ix_actionitem_created_by_id",
        table_name="actionitem",
    )
    op.drop_table("actionitem")
