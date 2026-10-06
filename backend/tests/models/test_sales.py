import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlmodel import Session

from app.models import (
    Product,
    Sale,
    SaleCreate,
    SaleItem,
    SaleItemBase,
    SaleItemCreate,
)


def _create_product(db: Session, *, price: Decimal = Decimal("5.50")) -> Product:
    product = Product.model_validate(
        {
            "name": "Flat White",
            "category": "Coffee",
            "selling_price": price,
            "unit": "each",
            "is_active": True,
        }
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def _create_sale_with_item(
    db: Session,
) -> tuple[Sale, SaleItem, Product]:
    product = _create_product(db)
    sale = Sale(
        sold_at=datetime(2026, 10, 6, 9, 30, tzinfo=UTC),
        total_amount=Decimal("11.00"),
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)

    item = SaleItem(
        sale_id=sale.id,
        product_id=product.id,
        quantity=Decimal("2.000"),
        unit_price=Decimal("5.50"),
        line_total=Decimal("11.00"),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return sale, item, product


@pytest.mark.parametrize("quantity", [0, Decimal("-0.001")])
def test_sale_item_create_rejects_non_positive_quantity(
    quantity: int | Decimal,
) -> None:
    with pytest.raises(ValidationError):
        SaleItemCreate.model_validate(
            {
                "product_id": uuid.uuid4(),
                "quantity": quantity,
            }
        )


def test_sale_create_requires_at_least_one_item() -> None:
    with pytest.raises(ValidationError):
        SaleCreate.model_validate(
            {
                "sold_at": datetime(2026, 10, 6, 9, 30, tzinfo=UTC),
                "items": [],
            }
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("unit_price", Decimal("-0.01")),
        ("unit_price", Decimal("1.234")),
        ("line_total", Decimal("-0.01")),
        ("line_total", Decimal("1.234")),
    ],
)
def test_sale_item_rejects_invalid_money_values(
    field: str,
    value: Decimal,
) -> None:
    data: dict[str, object] = {
        "product_id": uuid.uuid4(),
        "quantity": Decimal("1.000"),
        "unit_price": Decimal("5.50"),
        "line_total": Decimal("5.50"),
    }
    data[field] = value

    with pytest.raises(ValidationError):
        SaleItemBase.model_validate(data)


def test_sale_persists_items_and_historical_unit_price(db: Session) -> None:
    sale, item, product = _create_sale_with_item(db)

    product.selling_price = Decimal("6.25")
    db.add(product)
    db.commit()
    db.refresh(item)
    db.refresh(sale)

    assert item.unit_price == Decimal("5.50")
    assert item.line_total == Decimal("11.00")
    assert item.product_id == product.id
    assert item.sale_id == sale.id
    assert [sale_item.id for sale_item in sale.items] == [item.id]


def test_deleting_sale_cascades_to_items(db: Session) -> None:
    sale, item, _product = _create_sale_with_item(db)
    item_id = item.id

    db.delete(sale)
    db.commit()
    db.expire_all()

    assert db.get(SaleItem, item_id) is None
