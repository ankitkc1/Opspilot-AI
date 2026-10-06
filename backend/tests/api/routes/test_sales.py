import uuid
from decimal import Decimal
from typing import cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session, func, select

from app.core.config import settings
from app.models import Product, Sale


def _create_product(
    db: Session,
    *,
    name: str,
    price: Decimal,
    is_active: bool = True,
) -> Product:
    product = Product.model_validate(
        {
            "name": name,
            "category": "Test category",
            "selling_price": price,
            "unit": "each",
            "is_active": is_active,
        }
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def _create_sale(
    client: TestClient,
    headers: dict[str, str],
    product: Product,
    *,
    quantity: str = "1.000",
) -> Response:
    return cast(
        Response,
        client.post(
            f"{settings.API_V1_STR}/sales/",
            headers=headers,
            json={
                "sold_at": "2026-10-06T09:30:00Z",
                "items": [
                    {
                        "product_id": str(product.id),
                        "quantity": quantity,
                    }
                ],
            },
        ),
    )


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "POST",
            "/",
            {
                "items": [
                    {
                        "product_id": str(uuid.UUID(int=1)),
                        "quantity": "1.000",
                    }
                ]
            },
        ),
        ("GET", "/", None),
        ("GET", f"/{uuid.UUID(int=1)}", None),
    ],
)
def test_sale_endpoints_require_authentication(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    response = client.request(
        method,
        f"{settings.API_V1_STR}/sales{path}",
        json=payload,
    )
    assert response.status_code == 401


def test_create_sale_calculates_totals_from_product_prices(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    coffee = _create_product(
        db,
        name="Flat White",
        price=Decimal("5.50"),
    )
    burger = _create_product(
        db,
        name="Chicken Burger",
        price=Decimal("17.90"),
    )

    response = client.post(
        f"{settings.API_V1_STR}/sales/",
        headers=superuser_token_headers,
        json={
            "sold_at": "2026-10-06T09:30:00Z",
            "items": [
                {"product_id": str(coffee.id), "quantity": "2.000"},
                {"product_id": str(burger.id), "quantity": "1.000"},
            ],
        },
    )

    assert response.status_code == 201
    content = response.json()
    assert Decimal(content["total_amount"]) == Decimal("28.90")
    assert len(content["items"]) == 2

    items_by_product = {item["product_id"]: item for item in content["items"]}
    assert Decimal(items_by_product[str(coffee.id)]["unit_price"]) == Decimal("5.50")
    assert Decimal(items_by_product[str(coffee.id)]["line_total"]) == Decimal("11.00")
    assert Decimal(items_by_product[str(burger.id)]["unit_price"]) == Decimal("17.90")
    assert Decimal(items_by_product[str(burger.id)]["line_total"]) == Decimal("17.90")

    sale = db.get(Sale, uuid.UUID(content["id"]))
    assert sale is not None
    assert len(sale.items) == 2


def test_create_sale_with_missing_product_is_atomic(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Existing", price=Decimal("4.00"))
    count_before = db.exec(select(func.count()).select_from(Sale)).one()

    response = client.post(
        f"{settings.API_V1_STR}/sales/",
        headers=superuser_token_headers,
        json={
            "items": [
                {"product_id": str(product.id), "quantity": "1.000"},
                {"product_id": str(uuid.uuid4()), "quantity": "1.000"},
            ]
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}
    count_after = db.exec(select(func.count()).select_from(Sale)).one()
    assert count_after == count_before


def test_create_sale_rejects_inactive_product(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(
        db,
        name="Inactive",
        price=Decimal("4.00"),
        is_active=False,
    )

    response = _create_sale(client, superuser_token_headers, product)

    assert response.status_code == 409
    assert response.json() == {"detail": "Product is inactive"}


def test_create_sale_rejects_empty_items(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/sales/",
        headers=superuser_token_headers,
        json={"items": []},
    )
    assert response.status_code == 422


def test_read_sale_preserves_historical_price(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Latte", price=Decimal("5.80"))
    create_response = _create_sale(
        client,
        superuser_token_headers,
        product,
        quantity="2.000",
    )
    assert create_response.status_code == 201
    sale_id = create_response.json()["id"]

    product.selling_price = Decimal("6.40")
    db.add(product)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/sales/{sale_id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert Decimal(content["items"][0]["unit_price"]) == Decimal("5.80")
    assert Decimal(content["items"][0]["line_total"]) == Decimal("11.60")


def test_read_sale_not_found(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/sales/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Sale not found"}


def test_read_sales_supports_pagination(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Juice", price=Decimal("6.50"))
    assert _create_sale(client, superuser_token_headers, product).status_code == 201
    assert _create_sale(client, superuser_token_headers, product).status_code == 201

    response = client.get(
        f"{settings.API_V1_STR}/sales/",
        headers=superuser_token_headers,
        params={"skip": 0, "limit": 1},
    )

    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) == 1
    assert content["count"] >= 2
    assert len(content["data"][0]["items"]) == 1


def test_delete_product_with_sales_history_returns_conflict(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Protected", price=Decimal("3.50"))
    assert _create_sale(client, superuser_token_headers, product).status_code == 201

    response = client.delete(
        f"{settings.API_V1_STR}/products/{product.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Product has sales history and cannot be deleted"
    }
