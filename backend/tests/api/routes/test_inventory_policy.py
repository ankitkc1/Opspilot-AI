from decimal import Decimal
from typing import cast

from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session, func, select

from app.core.config import settings
from app.models import InventoryMovement, Product, Sale


def _create_product(
    db: Session,
    *,
    name: str,
    track_inventory: bool = True,
    reorder_level: Decimal = Decimal("2.000"),
    is_active: bool = True,
) -> Product:
    product = Product(
        name=name,
        category="Inventory policy test",
        selling_price=Decimal("5.00"),
        unit="each",
        is_active=is_active,
        track_inventory=track_inventory,
        reorder_level=reorder_level,
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
    movement_type: str,
    quantity_delta: str,
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
            },
        ),
    )


def _create_sale(
    client: TestClient,
    headers: dict[str, str],
    product: Product,
    quantities: list[str],
) -> Response:
    return cast(
        Response,
        client.post(
            f"{settings.API_V1_STR}/sales/",
            headers=headers,
            json={
                "items": [
                    {
                        "product_id": str(product.id),
                        "quantity": quantity,
                    }
                    for quantity in quantities
                ]
            },
        ),
    )


def test_low_stock_endpoint_requires_authentication(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/inventory/low-stock/")
    assert response.status_code == 401


def test_product_api_creates_inventory_policy(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": "Tracked API product",
            "category": "Stocked",
            "selling_price": "8.50",
            "unit": "each",
            "track_inventory": True,
            "reorder_level": "4.500",
        },
    )

    assert response.status_code == 201
    content = response.json()
    assert content["track_inventory"] is True
    assert Decimal(content["reorder_level"]) == Decimal("4.500")


def test_product_api_updates_inventory_policy(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(
        db,
        name="Policy update product",
        track_inventory=False,
        reorder_level=Decimal("0.000"),
    )

    response = client.patch(
        f"{settings.API_V1_STR}/products/{product.id}",
        headers=superuser_token_headers,
        json={"track_inventory": True, "reorder_level": "6.000"},
    )

    assert response.status_code == 200
    content = response.json()
    assert content["track_inventory"] is True
    assert Decimal(content["reorder_level"]) == Decimal("6.000")


def test_negative_reorder_level_is_rejected(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": "Invalid reorder product",
            "category": "Stocked",
            "selling_price": "8.50",
            "unit": "each",
            "track_inventory": True,
            "reorder_level": "-1.000",
        },
    )
    assert response.status_code == 422


def test_opening_balance_can_only_be_recorded_once(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Opening balance product")

    first_response = _create_movement(
        client,
        superuser_token_headers,
        product,
        movement_type="opening",
        quantity_delta="12.000",
    )
    second_response = _create_movement(
        client,
        superuser_token_headers,
        product,
        movement_type="opening",
        quantity_delta="4.000",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": "Opening balance already exists for product"
    }

    openings = db.exec(
        select(InventoryMovement).where(
            InventoryMovement.product_id == product.id,
            InventoryMovement.movement_type == "opening",
        )
    ).all()
    assert len(openings) == 1


def test_opening_balance_must_be_positive(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Invalid opening product")

    response = _create_movement(
        client,
        superuser_token_headers,
        product,
        movement_type="opening",
        quantity_delta="-1.000",
    )

    assert response.status_code == 422


def test_tracked_sale_reduces_available_stock(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Tracked sale product")
    assert _create_movement(
        client,
        superuser_token_headers,
        product,
        movement_type="opening",
        quantity_delta="5.000",
    ).status_code == 201

    sale_response = _create_sale(
        client,
        superuser_token_headers,
        product,
        ["3.000"],
    )
    balance_response = client.get(
        f"{settings.API_V1_STR}/inventory/balances/{product.id}",
        headers=superuser_token_headers,
    )

    assert sale_response.status_code == 201
    assert balance_response.status_code == 200
    balance = balance_response.json()
    assert Decimal(balance["quantity_on_hand"]) == Decimal("2.000")
    assert balance["is_low_stock"] is True


def test_tracked_sale_rejects_insufficient_stock_atomically(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Oversell protected product")
    assert _create_movement(
        client,
        superuser_token_headers,
        product,
        movement_type="opening",
        quantity_delta="2.000",
    ).status_code == 201
    sale_count_before = db.exec(select(func.count()).select_from(Sale)).one()
    movement_count_before = db.exec(
        select(func.count())
        .select_from(InventoryMovement)
        .where(InventoryMovement.product_id == product.id)
    ).one()

    response = _create_sale(
        client,
        superuser_token_headers,
        product,
        ["3.000"],
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "message": "Insufficient stock",
            "product_id": str(product.id),
            "available": "2.000",
            "requested": "3.000",
        }
    }
    assert db.exec(select(func.count()).select_from(Sale)).one() == sale_count_before
    movement_count_after = db.exec(
        select(func.count())
        .select_from(InventoryMovement)
        .where(InventoryMovement.product_id == product.id)
    ).one()
    assert movement_count_after == movement_count_before


def test_duplicate_sale_lines_are_aggregated_for_stock_check(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(db, name="Aggregated stock product")
    assert _create_movement(
        client,
        superuser_token_headers,
        product,
        movement_type="opening",
        quantity_delta="3.000",
    ).status_code == 201

    response = _create_sale(
        client,
        superuser_token_headers,
        product,
        ["2.000", "2.000"],
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["available"] == "3.000"
    assert detail["requested"] == "4.000"


def test_untracked_product_can_have_negative_balance(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    product = _create_product(
        db,
        name="Untracked sale product",
        track_inventory=False,
    )

    sale_response = _create_sale(
        client,
        superuser_token_headers,
        product,
        ["2.000"],
    )
    balance_response = client.get(
        f"{settings.API_V1_STR}/inventory/balances/{product.id}",
        headers=superuser_token_headers,
    )

    assert sale_response.status_code == 201
    balance = balance_response.json()
    assert Decimal(balance["quantity_on_hand"]) == Decimal("-2.000")
    assert balance["is_low_stock"] is False


def test_low_stock_lists_only_active_tracked_products_below_threshold(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    low = _create_product(
        db,
        name="Low tracked product",
        reorder_level=Decimal("5.000"),
    )
    adequate = _create_product(
        db,
        name="Adequate tracked product",
        reorder_level=Decimal("5.000"),
    )
    untracked = _create_product(
        db,
        name="Untracked zero product",
        track_inventory=False,
        reorder_level=Decimal("5.000"),
    )
    inactive = _create_product(
        db,
        name="Inactive tracked product",
        reorder_level=Decimal("5.000"),
        is_active=False,
    )
    for product, quantity in ((low, "3.000"), (adequate, "8.000")):
        assert _create_movement(
            client,
            superuser_token_headers,
            product,
            movement_type="opening",
            quantity_delta=quantity,
        ).status_code == 201

    response = client.get(
        f"{settings.API_V1_STR}/inventory/low-stock/",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    ids = {item["product_id"] for item in response.json()["data"]}
    assert str(low.id) in ids
    assert str(adequate.id) not in ids
    assert str(untracked.id) not in ids
    assert str(inactive.id) not in ids
