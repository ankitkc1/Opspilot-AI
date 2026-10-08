"""add action outcome notes

Revision ID: f8c3d5e0a742
Revises: e7b2c4d9a631
Create Date: 2026-10-08

"""

import sqlalchemy as sa
from alembic import op

revision = "f8c3d5e0a742"
down_revision = "e7b2c4d9a631"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "actionitem",
        sa.Column("outcome_note", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("actionitem", "outcome_note")
