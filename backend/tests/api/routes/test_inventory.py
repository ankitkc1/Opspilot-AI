import uuid
from decimal import Decimal
from typing import cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session, func, select

from app.core.config import settings
from app.models import InventoryMovement, Product


def _create_product(
    db: Session,
    *,
    name: str,
    price: Decimal = Decimal("5.00"),
) -> Product:
    product = Product(
        name=name,
        category="Inventory test",
        selling_price=price,
        unit="each",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def _create_movement(
    client: TestClient,
    headers: dict[str, str],
    product: Product,
    *,
    movement_type: str = "receipt",
    quantity_delta: str = "10.000",
) -> Response:
    return cast(
        Response,
        client.post(
            f"{settings.API_V1_STR}/inventory/movements/",
            headers=headers,
            json={
                "product_id": str(product.id),
                "movement_type": movement_type,
                "quantity_delta": quantity_delta,
                "note": "Inventory test movement",
            },
        ),
    )


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "POST",
            "/movements/",
            {
                "product_id": str(uuid.UUID(int=1)),
                "movement_type": "receipt",
                "quantity_delta": "1.000",
            },
        ),
        ("GET", "/movements/", None),
        ("GET", "/balances/", None),
        ("GET", f"/balances/{uuid.UUID(int=1)}", None),
    ],
)
def test_inventory_endpoints_require_authentication(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    response = client.request(
        method,
        f"{settings.API_V1_STR}/inventory{path}",
        json=payload,
    )
    assert response.status_code == 401


def test_receipt_creates_movement_and_updates_balance(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Receipt product")

    response = _create_movement(client, superuser_token_headers, product)

    assert response.status_code == 201
    content = response.json()
    assert content["product_id"] == str(product.id)
    assert content["movement_type"] == "receipt"
    assert Decimal(content["quantity_delta"]) == Decimal("10.000")
    assert content["sale_id"] is None

    balance_response = client.get(
        f"{settings.API_V1_STR}/inventory/balances/{product.id}",
        headers=superuser_token_headers,
    )
    assert balance_response.status_code == 200
    assert Decimal(balance_response.json()["quantity_on_hand"]) == Decimal("10.000")


def test_negative_adjustment_reduces_balance(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Adjusted product")
    assert _create_movement(
        client,
        superuser_token_headers,
        product,
        quantity_delta="10.000",
    ).status_code == 201
    assert _create_movement(
        client,
        superuser_token_headers,
        product,
        movement_type="adjustment",
        quantity_delta="-2.500",
    ).status_code == 201

    response = client.get(
        f"{settings.API_V1_STR}/inventory/balances/{product.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert Decimal(response.json()["quantity_on_hand"]) == Decimal("7.500")


@pytest.mark.parametrize(
    ("movement_type", "quantity_delta"),
    [
        ("receipt", "0.000"),
        ("receipt", "-1.000"),
        ("adjustment", "0.000"),
        ("sale", "-1.000"),
    ],
)
def test_manual_movement_validation(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    movement_type: str,
    quantity_delta: str,
) -> None:
    product = _create_product(db, name=f"Invalid {movement_type} {quantity_delta}")

    response = _create_movement(
        client,
        superuser_token_headers,
        product,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
    )

    assert response.status_code == 422


def test_missing_product_does_not_create_movement(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    count_before = db.exec(select(func.count()).select_from(InventoryMovement)).one()

    response = client.post(
        f"{settings.API_V1_STR}/inventory/movements/",
        headers=superuser_token_headers,
        json={
            "product_id": str(uuid.uuid4()),
            "movement_type": "receipt",
            "quantity_delta": "5.000",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}
    count_after = db.exec(select(func.count()).select_from(InventoryMovement)).one()
    assert count_after == count_before


def test_read_movements_filters_by_product(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    first_product = _create_product(db, name="First inventory product")
    second_product = _create_product(db, name="Second inventory product")
    assert _create_movement(
        client,
        superuser_token_headers,
        first_product,
    ).status_code == 201
    assert _create_movement(
        client,
        superuser_token_headers,
        second_product,
    ).status_code == 201

    response = client.get(
        f"{settings.API_V1_STR}/inventory/movements/",
        headers=superuser_token_headers,
        params={"product_id": str(first_product.id)},
    )

    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 1
    assert len(content["data"]) == 1
    assert content["data"][0]["product_id"] == str(first_product.id)


def test_product_without_movements_has_zero_balance(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Zero balance product")

    response = client.get(
        f"{settings.API_V1_STR}/inventory/balances/{product.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["product_name"] == product.name
    assert Decimal(content["quantity_on_hand"]) == Decimal("0.000")


def test_read_missing_product_balance_returns_not_found(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/inventory/balances/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}


def test_sale_creates_negative_inventory_movement(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Sold inventory product")
    assert _create_movement(
        client,
        superuser_token_headers,
        product,
        quantity_delta="10.000",
    ).status_code == 201

    sale_response = client.post(
        f"{settings.API_V1_STR}/sales/",
        headers=superuser_token_headers,
        json={
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": "2.000",
                }
            ]
        },
    )

    assert sale_response.status_code == 201
    sale_id = sale_response.json()["id"]

    movements_response = client.get(
        f"{settings.API_V1_STR}/inventory/movements/",
        headers=superuser_token_headers,
        params={"product_id": str(product.id)},
    )
    assert movements_response.status_code == 200
    sale_movements = [
        movement
        for movement in movements_response.json()["data"]
        if movement["movement_type"] == "sale"
    ]
    assert len(sale_movements) == 1
    assert sale_movements[0]["sale_id"] == sale_id
    assert Decimal(sale_movements[0]["quantity_delta"]) == Decimal("-2.000")

    balance_response = client.get(
        f"{settings.API_V1_STR}/inventory/balances/{product.id}",
        headers=superuser_token_headers,
    )
    assert balance_response.status_code == 200
    assert Decimal(balance_response.json()["quantity_on_hand"]) == Decimal("8.000")


def test_failed_sale_does_not_create_inventory_movement(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Atomic inventory product")
    count_before = db.exec(
        select(func.count())
        .select_from(InventoryMovement)
        .where(InventoryMovement.product_id == product.id)
    ).one()

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
    count_after = db.exec(
        select(func.count())
        .select_from(InventoryMovement)
        .where(InventoryMovement.product_id == product.id)
    ).one()
    assert count_after == count_before


def test_delete_product_with_inventory_history_returns_conflict(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Protected inventory product")
    assert _create_movement(
        client,
        superuser_token_headers,
        product,
    ).status_code == 201

    response = client.delete(
        f"{settings.API_V1_STR}/products/{product.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Product has inventory history and cannot be deleted"
    }
