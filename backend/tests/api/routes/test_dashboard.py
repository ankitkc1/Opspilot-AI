from decimal import Decimal
from typing import cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session

from app.core.config import settings
from app.models import Product

REPORT_DATE = "2040-02-02"


def _create_product(
    db: Session,
    *,
    name: str,
    price: Decimal,
    track_inventory: bool = False,
    reorder_level: Decimal = Decimal("0.000"),
) -> Product:
    product = Product(
        name=name,
        category="Dashboard test",
        selling_price=price,
        unit="each",
        track_inventory=track_inventory,
        reorder_level=reorder_level,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def _create_sale(
    client: TestClient,
    headers: dict[str, str],
    *,
    sold_at: str,
    items: list[tuple[Product, str]],
) -> Response:
    return cast(
        Response,
        client.post(
            f"{settings.API_V1_STR}/sales/",
            headers=headers,
            json={
                "sold_at": sold_at,
                "items": [
                    {
                        "product_id": str(product.id),
                        "quantity": quantity,
                    }
                    for product, quantity in items
                ],
            },
        ),
    )


def _create_opening_balance(
    client: TestClient,
    headers: dict[str, str],
    product: Product,
    quantity: str,
) -> Response:
    return cast(
        Response,
        client.post(
            f"{settings.API_V1_STR}/inventory/movements/",
            headers=headers,
            json={
                "product_id": str(product.id),
                "movement_type": "opening",
                "quantity_delta": quantity,
            },
        ),
    )


def test_dashboard_requires_authentication(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/dashboard/summary/")
    assert response.status_code == 401


def test_dashboard_empty_day_returns_zero_metrics(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/dashboard/summary/",
        headers=superuser_token_headers,
        params={"report_date": "2099-01-01"},
    )

    assert response.status_code == 200
    content = response.json()
    assert content["report_date"] == "2099-01-01"
    assert content["timezone"] == "Australia/Sydney"
    assert Decimal(content["revenue"]) == Decimal("0.00")
    assert content["sales_count"] == 0
    assert Decimal(content["units_sold"]) == Decimal("0.000")
    assert Decimal(content["average_sale_value"]) == Decimal("0.00")
    assert content["top_products"] == []


def test_dashboard_calculates_daily_metrics_and_top_products(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    coffee = _create_product(
        db,
        name="Dashboard coffee",
        price=Decimal("5.00"),
    )
    meal = _create_product(
        db,
        name="Dashboard meal",
        price=Decimal("10.00"),
    )

    assert _create_sale(
        client,
        superuser_token_headers,
        sold_at="2040-02-01T13:00:00Z",
        items=[(coffee, "2.000"), (meal, "1.000")],
    ).status_code == 201
    assert _create_sale(
        client,
        superuser_token_headers,
        sold_at="2040-02-02T12:59:59Z",
        items=[(coffee, "1.000")],
    ).status_code == 201
    assert _create_sale(
        client,
        superuser_token_headers,
        sold_at="2040-02-02T13:00:00Z",
        items=[(meal, "5.000")],
    ).status_code == 201

    response = client.get(
        f"{settings.API_V1_STR}/dashboard/summary/",
        headers=superuser_token_headers,
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 200
    content = response.json()
    assert Decimal(content["revenue"]) == Decimal("25.00")
    assert content["sales_count"] == 2
    assert Decimal(content["units_sold"]) == Decimal("4.000")
    assert Decimal(content["average_sale_value"]) == Decimal("12.50")

    top_products = content["top_products"]
    assert [item["product_id"] for item in top_products[:2]] == [
        str(coffee.id),
        str(meal.id),
    ]
    assert Decimal(top_products[0]["quantity_sold"]) == Decimal("3.000")
    assert Decimal(top_products[0]["revenue"]) == Decimal("15.00")
    assert Decimal(top_products[1]["quantity_sold"]) == Decimal("1.000")
    assert Decimal(top_products[1]["revenue"]) == Decimal("10.00")


def test_dashboard_respects_top_product_limit(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    first = _create_product(db, name="Top limit first", price=Decimal("8.00"))
    second = _create_product(db, name="Top limit second", price=Decimal("3.00"))
    assert _create_sale(
        client,
        superuser_token_headers,
        sold_at="2040-02-01T14:00:00Z",
        items=[(first, "1.000"), (second, "1.000")],
    ).status_code == 201

    response = client.get(
        f"{settings.API_V1_STR}/dashboard/summary/",
        headers=superuser_token_headers,
        params={"report_date": REPORT_DATE, "top_limit": 1},
    )

    assert response.status_code == 200
    assert len(response.json()["top_products"]) == 1
    assert response.json()["top_products"][0]["product_id"] == str(first.id)


def test_dashboard_includes_current_low_stock_summary(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    low = _create_product(
        db,
        name="Dashboard low stock",
        price=Decimal("4.00"),
        track_inventory=True,
        reorder_level=Decimal("5.000"),
    )
    adequate = _create_product(
        db,
        name="Dashboard adequate stock",
        price=Decimal("4.00"),
        track_inventory=True,
        reorder_level=Decimal("5.000"),
    )
    assert _create_opening_balance(
        client,
        superuser_token_headers,
        low,
        "3.000",
    ).status_code == 201
    assert _create_opening_balance(
        client,
        superuser_token_headers,
        adequate,
        "8.000",
    ).status_code == 201

    response = client.get(
        f"{settings.API_V1_STR}/dashboard/summary/",
        headers=superuser_token_headers,
        params={"report_date": "2099-01-01", "low_stock_limit": 50},
    )

    assert response.status_code == 200
    content = response.json()
    low_stock_ids = {item["product_id"] for item in content["low_stock"]}
    assert content["low_stock_count"] >= 1
    assert str(low.id) in low_stock_ids
    assert str(adequate.id) not in low_stock_ids


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("top_limit", 0),
        ("top_limit", 21),
        ("low_stock_limit", 0),
        ("low_stock_limit", 51),
    ],
)
def test_dashboard_rejects_invalid_limits(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    parameter: str,
    value: int,
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/dashboard/summary/",
        headers=superuser_token_headers,
        params={"report_date": REPORT_DATE, parameter: value},
    )
    assert response.status_code == 422
