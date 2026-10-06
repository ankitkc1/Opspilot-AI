import uuid
from decimal import Decimal

from sqlmodel import Session, col, func, select

from app.models import InventoryBalancePublic, InventoryMovement, Product

QUANTITY_QUANTUM = Decimal("0.001")


def get_quantity_on_hand(session: Session, product_id: uuid.UUID) -> Decimal:
    quantity = session.exec(
        select(
            func.coalesce(
                func.sum(InventoryMovement.quantity_delta),
                Decimal("0.000"),
            )
        ).where(InventoryMovement.product_id == product_id)
    ).one()
    return Decimal(quantity).quantize(QUANTITY_QUANTUM)


def build_inventory_balance(
    session: Session,
    product: Product,
) -> InventoryBalancePublic:
    quantity_on_hand = get_quantity_on_hand(session, product.id)
    return InventoryBalancePublic(
        product_id=product.id,
        product_name=product.name,
        unit=product.unit,
        is_active=product.is_active,
        track_inventory=product.track_inventory,
        reorder_level=product.reorder_level,
        quantity_on_hand=quantity_on_hand,
        is_low_stock=(
            product.is_active
            and product.track_inventory
            and quantity_on_hand <= product.reorder_level
        ),
    )


def get_low_stock_balances(session: Session) -> list[InventoryBalancePublic]:
    products = session.exec(
        select(Product)
        .where(
            col(Product.track_inventory).is_(True),
            col(Product.is_active).is_(True),
        )
        .order_by(col(Product.name))
    ).all()
    return [
        balance
        for product in products
        if (balance := build_inventory_balance(session, product)).is_low_stock
    ]
