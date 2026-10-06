"""add sales domain

Revision ID: 6b4f2c8a9d10
Revises: 18751d1b0c9a
Create Date: 2026-10-06

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = "6b4f2c8a9d10"
down_revision = "18751d1b0c9a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sale",
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sale_sold_at"), "sale", ["sold_at"], unique=False)

    op.create_table(
        "saleitem",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
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
        op.f("ix_saleitem_product_id"),
        "saleitem",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_saleitem_sale_id"),
        "saleitem",
        ["sale_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_saleitem_sale_id"), table_name="saleitem")
    op.drop_index(op.f("ix_saleitem_product_id"), table_name="saleitem")
    op.drop_table("saleitem")
    op.drop_index(op.f("ix_sale_sold_at"), table_name="sale")
    op.drop_table("sale")
