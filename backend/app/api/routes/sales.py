import uuid
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    InventoryMovement,
    Product,
    Sale,
    SaleCreate,
    SaleItem,
    SalePublic,
    SalesPublic,
)
from app.services.inventory import get_quantity_on_hand

router = APIRouter(prefix="/sales", tags=["sales"])

MONEY_QUANTUM = Decimal("0.01")


@router.post("/", response_model=SalePublic, status_code=201)
def create_sale(
    *,
    session: SessionDep,
    _current_user: CurrentUser,
    sale_in: SaleCreate,
) -> SalePublic:
    """
    Create a sale using current Product prices.
    """

    product_ids = {item.product_id for item in sale_in.items}
    products = session.exec(
        select(Product)
        .where(col(Product.id).in_(product_ids))
        .order_by(col(Product.id))
        .with_for_update()
    ).all()
    products_by_id = {product.id: product for product in products}
    requested_quantities: dict[uuid.UUID, Decimal] = {}

    for item_in in sale_in.items:
        product = products_by_id.get(item_in.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        if not product.is_active:
            raise HTTPException(status_code=409, detail="Product is inactive")
        requested_quantities[item_in.product_id] = (
            requested_quantities.get(item_in.product_id, Decimal("0.000"))
            + item_in.quantity
        )

    for product_id, requested_quantity in requested_quantities.items():
        product = products_by_id[product_id]
        if not product.track_inventory:
            continue
        available_quantity = get_quantity_on_hand(session, product_id)
        if requested_quantity > available_quantity:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Insufficient stock",
                    "product_id": str(product_id),
                    "available": str(available_quantity),
                    "requested": str(requested_quantity),
                },
            )

    sale = Sale(
        sold_at=sale_in.sold_at,
        total_amount=Decimal("0.00"),
    )
    session.add(sale)
    session.flush()
    total_amount = Decimal("0.00")

    for item_in in sale_in.items:
        product = products_by_id[item_in.product_id]
        unit_price = product.selling_price
        line_total = (item_in.quantity * unit_price).quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )
        total_amount += line_total
        sale.items.append(
            SaleItem(
                product_id=product.id,
                quantity=item_in.quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        )
        session.add(
            InventoryMovement(
                product_id=product.id,
                sale_id=sale.id,
                movement_type="sale",
                quantity_delta=-item_in.quantity,
                occurred_at=sale.sold_at,
            )
        )

    sale.total_amount = total_amount.quantize(
        MONEY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )
    session.commit()
    session.refresh(sale)

    return SalePublic.model_validate(sale)


@router.get("/", response_model=SalesPublic)
def read_sales(
    session: SessionDep,
    _current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> SalesPublic:
    """
    Retrieve sales, newest first.
    """

    count = session.exec(select(func.count()).select_from(Sale)).one()
    sales = session.exec(
        select(Sale)
        .order_by(col(Sale.sold_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()

    return SalesPublic(
        data=[SalePublic.model_validate(sale) for sale in sales],
        count=count,
    )


@router.get("/{sale_id}", response_model=SalePublic)
def read_sale(
    session: SessionDep,
    _current_user: CurrentUser,
    sale_id: uuid.UUID,
) -> SalePublic:
    """
    Retrieve a sale by ID.
    """

    sale = session.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")

    return SalePublic.model_validate(sale)
