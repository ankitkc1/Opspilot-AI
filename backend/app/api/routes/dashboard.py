from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.models import (
    DashboardSummaryPublic,
    DashboardTopProductPublic,
    Product,
    Sale,
    SaleItem,
)
from app.services.inventory import get_low_stock_balances

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

MONEY_QUANTUM = Decimal("0.01")
QUANTITY_QUANTUM = Decimal("0.001")


@router.get("/summary/", response_model=DashboardSummaryPublic)
def read_dashboard_summary(
    session: SessionDep,
    _current_user: CurrentUser,
    report_date: date | None = None,
    top_limit: Annotated[int, Query(ge=1, le=20)] = 5,
    low_stock_limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> DashboardSummaryPublic:
    """
    Retrieve daily sales KPIs and the current low-stock summary.
    """

    business_timezone = ZoneInfo(settings.BUSINESS_TIMEZONE)
    selected_date = report_date or datetime.now(business_timezone).date()
    local_start = datetime.combine(
        selected_date,
        time.min,
        tzinfo=business_timezone,
    )
    local_end = datetime.combine(
        selected_date + timedelta(days=1),
        time.min,
        tzinfo=business_timezone,
    )
    period_start = local_start.astimezone(UTC)
    period_end = local_end.astimezone(UTC)

    sales_count_value, revenue_value = session.exec(
        select(
            func.count(col(Sale.id)),
            func.coalesce(func.sum(Sale.total_amount), Decimal("0.00")),
        ).where(
            Sale.sold_at >= period_start,
            Sale.sold_at < period_end,
        )
    ).one()
    sales_count = int(sales_count_value)
    revenue = Decimal(revenue_value).quantize(MONEY_QUANTUM)

    units_sold_value = session.exec(
        select(
            func.coalesce(
                func.sum(SaleItem.quantity),
                Decimal("0.000"),
            )
        )
        .select_from(SaleItem)
        .join(Sale, col(Sale.id) == col(SaleItem.sale_id))
        .where(
            Sale.sold_at >= period_start,
            Sale.sold_at < period_end,
        )
    ).one()
    units_sold = Decimal(units_sold_value).quantize(QUANTITY_QUANTUM)

    quantity_sold_expression = func.sum(SaleItem.quantity)
    revenue_expression = func.sum(SaleItem.line_total)
    top_product_rows = session.exec(
        select(
            Product.id,
            Product.name,
            quantity_sold_expression,
            revenue_expression,
        )
        .select_from(SaleItem)
        .join(Product, col(Product.id) == col(SaleItem.product_id))
        .join(Sale, col(Sale.id) == col(SaleItem.sale_id))
        .where(
            Sale.sold_at >= period_start,
            Sale.sold_at < period_end,
        )
        .group_by(col(Product.id), col(Product.name))
        .order_by(
            revenue_expression.desc(),
            quantity_sold_expression.desc(),
            col(Product.name),
        )
        .limit(top_limit)
    ).all()
    top_products = [
        DashboardTopProductPublic(
            product_id=product_id,
            product_name=product_name,
            quantity_sold=Decimal(quantity_sold).quantize(QUANTITY_QUANTUM),
            revenue=Decimal(product_revenue).quantize(MONEY_QUANTUM),
        )
        for product_id, product_name, quantity_sold, product_revenue in top_product_rows
    ]

    low_stock = get_low_stock_balances(session)
    average_sale_value = (
        (revenue / sales_count).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        if sales_count
        else Decimal("0.00")
    )
    return DashboardSummaryPublic(
        report_date=selected_date,
        timezone=settings.BUSINESS_TIMEZONE,
        revenue=revenue,
        sales_count=sales_count,
        units_sold=units_sold,
        average_sale_value=average_sale_value,
        top_products=top_products,
        low_stock_count=len(low_stock),
        low_stock=low_stock[:low_stock_limit],
    )
