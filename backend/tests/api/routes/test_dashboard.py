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

    trends_response = client.get(f"{settings.API_V1_STR}/dashboard/trends/")
    assert trends_response.status_code == 401


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


def test_dashboard_trends_empty_period_returns_zero_filled_days(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/dashboard/trends/",
        headers=superuser_token_headers,
        params={"end_date": "2099-01-07", "days": 7},
    )

    assert response.status_code == 200
    content = response.json()
    assert content["start_date"] == "2099-01-01"
    assert content["end_date"] == "2099-01-07"
    assert content["timezone"] == "Australia/Sydney"
    assert content["days"] == 7
    assert Decimal(content["revenue"]) == Decimal("0.00")
    assert content["sales_count"] == 0
    assert Decimal(content["units_sold"]) == Decimal("0.000")
    assert Decimal(content["average_sale_value"]) == Decimal("0.00")
    assert len(content["daily"]) == 7
    assert [day["report_date"] for day in content["daily"]] == [
        f"2099-01-0{day}" for day in range(1, 8)
    ]
    assert all(Decimal(day["revenue"]) == 0 for day in content["daily"])
    assert Decimal(
        content["previous_period"]["revenue_change_percent"]
    ) == Decimal("0.0")


@pytest.mark.parametrize(
    ("days", "expected_start"),
    [(14, "2098-12-25"), (30, "2098-12-09")],
)
def test_dashboard_trends_supports_longer_periods(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    days: int,
    expected_start: str,
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/dashboard/trends/",
        headers=superuser_token_headers,
        params={"end_date": "2099-01-07", "days": days},
    )

    assert response.status_code == 200
    assert response.json()["start_date"] == expected_start
    assert len(response.json()["daily"]) == days


def test_dashboard_trends_aggregate_and_compare_periods(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(
        db,
        name="Trend product",
        price=Decimal("10.00"),
    )
    assert _create_sale(
        client,
        superuser_token_headers,
        sold_at="2040-01-26T13:00:00Z",
        items=[(product, "1.000")],
    ).status_code == 201
    assert _create_sale(
        client,
        superuser_token_headers,
        sold_at="2040-02-01T13:00:00Z",
        items=[(product, "2.000")],
    ).status_code == 201
    assert _create_sale(
        client,
        superuser_token_headers,
        sold_at="2040-02-02T13:00:00Z",
        items=[(product, "3.000")],
    ).status_code == 201

    response = client.get(
        f"{settings.API_V1_STR}/dashboard/trends/",
        headers=superuser_token_headers,
        params={"end_date": "2040-02-03", "days": 7},
    )

    assert response.status_code == 200
    content = response.json()
    assert content["start_date"] == "2040-01-28"
    assert Decimal(content["revenue"]) == Decimal("50.00")
    assert content["sales_count"] == 2
    assert Decimal(content["units_sold"]) == Decimal("5.000")
    assert Decimal(content["average_sale_value"]) == Decimal("25.00")

    daily = {day["report_date"]: day for day in content["daily"]}
    assert Decimal(daily["2040-02-02"]["revenue"]) == Decimal("20.00")
    assert daily["2040-02-02"]["sales_count"] == 1
    assert Decimal(daily["2040-02-03"]["revenue"]) == Decimal("30.00")
    assert Decimal(daily["2040-01-28"]["revenue"]) == Decimal("0.00")

    previous = content["previous_period"]
    assert previous["start_date"] == "2040-01-21"
    assert previous["end_date"] == "2040-01-27"
    assert Decimal(previous["revenue"]) == Decimal("10.00")
    assert previous["sales_count"] == 1
    assert Decimal(previous["units_sold"]) == Decimal("1.000")
    assert Decimal(previous["revenue_change_percent"]) == Decimal("400.0")
    assert Decimal(previous["sales_count_change_percent"]) == Decimal("100.0")
    assert Decimal(previous["units_sold_change_percent"]) == Decimal("400.0")


def test_dashboard_trends_marks_growth_from_zero_as_new(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(
        db,
        name="New trend product",
        price=Decimal("4.00"),
    )
    assert _create_sale(
        client,
        superuser_token_headers,
        sold_at="2041-02-01T13:00:00Z",
        items=[(product, "1.000")],
    ).status_code == 201

    response = client.get(
        f"{settings.API_V1_STR}/dashboard/trends/",
        headers=superuser_token_headers,
        params={"end_date": "2041-02-02", "days": 7},
    )

    assert response.status_code == 200
    previous = response.json()["previous_period"]
    assert Decimal(previous["revenue"]) == 0
    assert previous["revenue_change_percent"] is None
    assert previous["sales_count_change_percent"] is None
    assert previous["units_sold_change_percent"] is None


@pytest.mark.parametrize("days", [1, 8, 31])
def test_dashboard_trends_rejects_unsupported_periods(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    days: int,
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/dashboard/trends/",
        headers=superuser_token_headers,
        params={"end_date": "2040-02-03", "days": days},
    )
    assert response.status_code == 422
