import uuid

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Message,
    Product,
    ProductCreate,
    ProductPublic,
    ProductsPublic,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.post("/", response_model=ProductPublic, status_code=201)
def create_product(
    *,
    session: SessionDep,
    _current_user: CurrentUser,
    product_in: ProductCreate,
) -> Product:
    """
    Create a new product.
    """

    product = Product.model_validate(product_in)

    session.add(product)
    session.commit()
    session.refresh(product)

    return product


@router.get("/", response_model=ProductsPublic)
def read_products(
    session: SessionDep,
    _current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> ProductsPublic:
    """
    Retrieve products.
    """

    count_statement = select(func.count()).select_from(Product)
    count = session.exec(count_statement).one()

    statement = select(Product).offset(skip).limit(limit)

    products = session.exec(statement).all()

    return ProductsPublic(
        data=products,
        count=count,
    )

@router.get("/{product_id}", response_model=ProductPublic)
def read_product(
    session: SessionDep,
    _current_user: CurrentUser,
    product_id: uuid.UUID,
) -> Product:
    """
    Retrieve a product by ID.
    """

    product = session.get(Product, product_id)

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return product


@router.patch("/{product_id}", response_model=ProductPublic)
def update_product(
    *,
    session: SessionDep,
    _current_user: CurrentUser,
    product_id: uuid.UUID,
    product_in: ProductUpdate,
) -> Product:
    """
    Update a product.
    """

    product = session.get(Product, product_id)

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = product_in.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )

    product.sqlmodel_update(update_data)

    session.add(product)
    session.commit()
    session.refresh(product)

    return product


@router.delete("/{product_id}")
def delete_product(
    session: SessionDep,
    _current_user: CurrentUser,
    product_id: uuid.UUID,
) -> Message:
    """
    Delete a product.
    """

    product = session.get(Product, product_id)

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    session.delete(product)
    session.commit()

    return Message(message="Product deleted successfully")
