"""add inventory policy

Revision ID: 9d1f5e8b3a02
Revises: 8c0e4d7a2f91
Create Date: 2026-10-06

"""

import sqlalchemy as sa
from alembic import op


revision = "9d1f5e8b3a02"
down_revision = "8c0e4d7a2f91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product",
        sa.Column(
            "track_inventory",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "product",
        sa.Column(
            "reorder_level",
            sa.Numeric(precision=12, scale=3),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.drop_constraint(
        "ck_inventorymovement_type",
        "inventorymovement",
        type_="check",
    )
    op.drop_constraint(
        "ck_inventorymovement_receipt_positive",
        "inventorymovement",
        type_="check",
    )
    op.create_check_constraint(
        "ck_inventorymovement_type",
        "inventorymovement",
        "movement_type IN ('opening', 'receipt', 'adjustment', 'sale')",
    )
    op.create_check_constraint(
        "ck_inventorymovement_inbound_positive",
        "inventorymovement",
        "movement_type NOT IN ('opening', 'receipt') OR quantity_delta > 0",
    )
    op.create_index(
        "uq_inventorymovement_one_opening_per_product",
        "inventorymovement",
        ["product_id"],
        unique=True,
        postgresql_where=sa.text("movement_type = 'opening'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_inventorymovement_one_opening_per_product",
        table_name="inventorymovement",
    )
    op.execute(
        "UPDATE inventorymovement SET movement_type = 'receipt' "
        "WHERE movement_type = 'opening'"
    )
    op.drop_constraint(
        "ck_inventorymovement_inbound_positive",
        "inventorymovement",
        type_="check",
    )
    op.drop_constraint(
        "ck_inventorymovement_type",
        "inventorymovement",
        type_="check",
    )
    op.create_check_constraint(
        "ck_inventorymovement_type",
        "inventorymovement",
        "movement_type IN ('receipt', 'adjustment', 'sale')",
    )
    op.create_check_constraint(
        "ck_inventorymovement_receipt_positive",
        "inventorymovement",
        "movement_type <> 'receipt' OR quantity_delta > 0",
    )
    op.drop_column("product", "reorder_level")
    op.drop_column("product", "track_inventory")
