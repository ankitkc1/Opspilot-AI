import uuid

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    InventoryBalancePublic,
    InventoryBalancesPublic,
    InventoryMovement,
    InventoryMovementCreate,
    InventoryMovementPublic,
    InventoryMovementsPublic,
    Product,
)
from app.services.inventory import build_inventory_balance, get_low_stock_balances

router = APIRouter(prefix="/inventory", tags=["inventory"])

def _get_product_or_404(
    session: SessionDep,
    product_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> Product:
    if for_update:
        product = session.exec(
            select(Product).where(Product.id == product_id).with_for_update()
        ).first()
    else:
        product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/movements/", response_model=InventoryMovementPublic, status_code=201)
def create_inventory_movement(
    *,
    session: SessionDep,
    _current_user: CurrentUser,
    movement_in: InventoryMovementCreate,
) -> InventoryMovement:
    """
    Record an opening balance, stock receipt, or signed manual adjustment.
    """

    _get_product_or_404(session, movement_in.product_id, for_update=True)
    if movement_in.movement_type == "opening":
        existing_opening_id = session.exec(
            select(InventoryMovement.id)
            .where(
                InventoryMovement.product_id == movement_in.product_id,
                InventoryMovement.movement_type == "opening",
            )
            .limit(1)
        ).first()
        if existing_opening_id is not None:
            raise HTTPException(
                status_code=409,
                detail="Opening balance already exists for product",
            )
    movement = InventoryMovement(
        product_id=movement_in.product_id,
        movement_type=movement_in.movement_type,
        quantity_delta=movement_in.quantity_delta,
        occurred_at=movement_in.occurred_at,
        note=movement_in.note,
    )
    session.add(movement)
    session.commit()
    session.refresh(movement)
    return movement


@router.get("/movements/", response_model=InventoryMovementsPublic)
def read_inventory_movements(
    session: SessionDep,
    _current_user: CurrentUser,
    product_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> InventoryMovementsPublic:
    """
    Retrieve inventory movements, newest first.
    """

    count_statement = select(func.count()).select_from(InventoryMovement)
    statement = select(InventoryMovement)
    if product_id is not None:
        count_statement = count_statement.where(
            InventoryMovement.product_id == product_id
        )
        statement = statement.where(InventoryMovement.product_id == product_id)

    count = session.exec(count_statement).one()
    movements = session.exec(
        statement
        .order_by(
            col(InventoryMovement.occurred_at).desc(),
            col(InventoryMovement.created_at).desc(),
        )
        .offset(skip)
        .limit(limit)
    ).all()
    return InventoryMovementsPublic(data=movements, count=count)


@router.get("/balances/", response_model=InventoryBalancesPublic)
def read_inventory_balances(
    session: SessionDep,
    _current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> InventoryBalancesPublic:
    """
    Retrieve current stock balances for all products.
    """

    count = session.exec(select(func.count()).select_from(Product)).one()
    products = session.exec(
        select(Product).order_by(col(Product.name)).offset(skip).limit(limit)
    ).all()
    return InventoryBalancesPublic(
        data=[build_inventory_balance(session, product) for product in products],
        count=count,
    )


@router.get("/low-stock/", response_model=InventoryBalancesPublic)
def read_low_stock_products(
    session: SessionDep,
    _current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> InventoryBalancesPublic:
    """
    Retrieve active tracked products at or below their reorder level.
    """

    low_stock = get_low_stock_balances(session)
    return InventoryBalancesPublic(
        data=low_stock[skip : skip + limit],
        count=len(low_stock),
    )


@router.get("/balances/{product_id}", response_model=InventoryBalancePublic)
def read_inventory_balance(
    session: SessionDep,
    _current_user: CurrentUser,
    product_id: uuid.UUID,
) -> InventoryBalancePublic:
    """
    Retrieve the current stock balance for one product.
    """

    product = _get_product_or_404(session, product_id)
    return build_inventory_balance(session, product)
