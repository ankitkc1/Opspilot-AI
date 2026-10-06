import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import Product


def _create_product(db: Session, **overrides: object) -> Product:
    product_data = {
        "name": "Widget",
        "category": "Hardware",
        "selling_price": Decimal("12.50"),
        "unit": "each",
        "is_active": True,
    }
    product_data.update(overrides)
    product = Product.model_validate(product_data)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def test_create_product(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {
        "name": "Laptop",
        "category": "Electronics",
        "selling_price": 899.99,
        "unit": "unit",
        "is_active": True,
    }
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 201
    content = response.json()
    assert content["name"] == data["name"]
    assert content["category"] == data["category"]
    assert content["selling_price"] == str(data["selling_price"])
    assert content["unit"] == data["unit"]
    assert content["is_active"] is True
    assert "id" in content
    assert "created_at" in content


def test_create_product_defaults_to_active(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": "Default active",
            "category": "Hardware",
            "selling_price": 1,
            "unit": "each",
        },
    )
    assert response.status_code == 201
    assert response.json()["is_active"] is True


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "POST",
            "/",
            {
                "name": "Widget",
                "category": "Hardware",
                "selling_price": 1,
                "unit": "each",
            },
        ),
        ("GET", "/", None),
        ("GET", f"/{uuid.UUID(int=1)}", None),
        ("PATCH", f"/{uuid.UUID(int=1)}", {"name": "Updated"}),
        ("DELETE", f"/{uuid.UUID(int=1)}", None),
    ],
)
def test_product_endpoints_require_authentication(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    response = client.request(
        method,
        f"{settings.API_V1_STR}/products{path}",
        json=payload,
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("selling_price", -1),
        ("selling_price", "1.234"),
        ("name", ""),
        ("category", ""),
        ("unit", ""),
    ],
)
def test_create_product_rejects_invalid_values(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    field: str,
    value: int | str,
) -> None:
    data: dict[str, object] = {
        "name": "Invalid product",
        "category": "Hardware",
        "selling_price": 1,
        "unit": "each",
    }
    data[field] = value
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("selling_price", -1),
        ("selling_price", "1.234"),
        ("name", ""),
        ("category", ""),
        ("unit", ""),
    ],
)
def test_update_product_rejects_invalid_values(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    field: str,
    value: int | str,
) -> None:
    product = _create_product(db)
    response = client.patch(
        f"{settings.API_V1_STR}/products/{product.id}",
        headers=superuser_token_headers,
        json={field: value},
    )
    assert response.status_code == 422


def test_read_product(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    product = _create_product(db, name="Monitor", category="Electronics")
    response = client.get(
        f"{settings.API_V1_STR}/products/{product.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(product.id)
    assert content["name"] == product.name
    assert content["category"] == product.category
    assert content["selling_price"] == str(product.selling_price)
    assert content["unit"] == product.unit
    assert content["is_active"] == product.is_active


def test_read_product_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/products/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}


def test_read_products(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    _create_product(db, name="Keyboard")
    _create_product(db, name="Mouse")
    response = client.get(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) >= 2
    assert "count" in content
    assert {
        product["name"] for product in content["data"]
    } >= {"Keyboard", "Mouse"}


def test_read_products_supports_pagination(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    page_one = _create_product(db, name="Page one")
    page_two = _create_product(db, name="Page two")
    response = client.get(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        params={"skip": 0, "limit": 1},
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) == 1
    assert content["count"] >= 2
    assert "id" in content["data"][0]
    assert content["data"][0]["id"] in {str(page_one.id), str(page_two.id)}


def test_update_product(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    product = _create_product(db, name="Old product", category="Office")
    data = {
        "name": "Updated product",
        "category": "Office Supplies",
        "selling_price": 19.99,
        "unit": "box",
        "is_active": False,
    }
    response = client.patch(
        f"{settings.API_V1_STR}/products/{product.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(product.id)
    assert content["name"] == data["name"]
    assert content["category"] == data["category"]
    assert content["selling_price"] == str(data["selling_price"])
    assert content["unit"] == data["unit"]
    assert content["is_active"] is False


def test_update_product_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"name": "Updated product"}
    response = client.patch(
        f"{settings.API_V1_STR}/products/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}


def test_update_product_price_only_preserves_other_fields(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    product = _create_product(db, name="Preserve me", category="Tools")
    data = {"selling_price": 15.75}
    response = client.patch(
        f"{settings.API_V1_STR}/products/{product.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["selling_price"] == str(data["selling_price"])
    assert content["name"] == product.name
    assert content["category"] == product.category
    assert content["unit"] == product.unit
    assert content["is_active"] is product.is_active


def test_delete_product(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    product = _create_product(db, name="Delete me")
    response = client.delete(
        f"{settings.API_V1_STR}/products/{product.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Product deleted successfully"}
    read_response = client.get(
        f"{settings.API_V1_STR}/products/{product.id}",
        headers=superuser_token_headers,
    )
    assert read_response.status_code == 404
    assert read_response.json() == {"detail": "Product not found"}


def test_delete_product_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/products/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}
