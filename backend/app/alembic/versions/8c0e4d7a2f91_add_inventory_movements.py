"""add inventory movements

Revision ID: 8c0e4d7a2f91
Revises: 6b4f2c8a9d10
Create Date: 2026-10-06

"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op


revision = "8c0e4d7a2f91"
down_revision = "6b4f2c8a9d10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventorymovement",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=True),
        sa.Column(
            "movement_type",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column(
            "quantity_delta",
            sa.Numeric(precision=12, scale=3),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "note",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quantity_delta <> 0",
            name="ck_inventorymovement_quantity_nonzero",
        ),
        sa.CheckConstraint(
            "movement_type IN ('receipt', 'adjustment', 'sale')",
            name="ck_inventorymovement_type",
        ),
        sa.CheckConstraint(
            "movement_type <> 'receipt' OR quantity_delta > 0",
            name="ck_inventorymovement_receipt_positive",
        ),
        sa.CheckConstraint(
            "(movement_type = 'sale' AND sale_id IS NOT NULL) OR "
            "(movement_type <> 'sale' AND sale_id IS NULL)",
            name="ck_inventorymovement_sale_reference",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"],
            ["sale.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_inventorymovement_product_id"),
        "inventorymovement",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inventorymovement_sale_id"),
        "inventorymovement",
        ["sale_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inventorymovement_movement_type"),
        "inventorymovement",
        ["movement_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inventorymovement_occurred_at"),
        "inventorymovement",
        ["occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_inventorymovement_occurred_at"),
        table_name="inventorymovement",
    )
    op.drop_index(
        op.f("ix_inventorymovement_movement_type"),
        table_name="inventorymovement",
    )
    op.drop_index(
        op.f("ix_inventorymovement_sale_id"),
        table_name="inventorymovement",
    )
    op.drop_index(
        op.f("ix_inventorymovement_product_id"),
        table_name="inventorymovement",
    )
    op.drop_table("inventorymovement")
