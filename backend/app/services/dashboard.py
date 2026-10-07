from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, func, select

from app.core.config import settings
from app.models import (
    DashboardSummaryPublic,
    DashboardTopProductPublic,
    DashboardTrendComparisonPublic,
    DashboardTrendDayPublic,
    DashboardTrendsPublic,
    Product,
    Sale,
    SaleItem,
)
from app.services.inventory import get_low_stock_balances

MONEY_QUANTUM = Decimal("0.01")
QUANTITY_QUANTUM = Decimal("0.001")
PERCENT_QUANTUM = Decimal("0.1")


def resolve_report_date(report_date: date | None = None) -> date:
    """Resolve an omitted report date in the configured business timezone."""

    if report_date is not None:
        return report_date
    return datetime.now(ZoneInfo(settings.BUSINESS_TIMEZONE)).date()


def get_dashboard_summary(
    session: Session,
    *,
    report_date: date | None = None,
    top_limit: int = 5,
    low_stock_limit: int = 10,
) -> DashboardSummaryPublic:
    """Build the deterministic operations snapshot used by the API and AI."""

    business_timezone = ZoneInfo(settings.BUSINESS_TIMEZONE)
    selected_date = resolve_report_date(report_date)
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


def _percent_change(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == 0:
        return Decimal("0.0") if current == 0 else None
    return (
        ((current - previous) / previous) * Decimal("100")
    ).quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP)


def get_dashboard_trends(
    session: Session,
    *,
    end_date: date | None = None,
    days: int = 7,
) -> DashboardTrendsPublic:
    """Aggregate daily sales trends and compare them with the prior period."""

    selected_end_date = resolve_report_date(end_date)
    selected_start_date = selected_end_date - timedelta(days=days - 1)
    previous_end_date = selected_start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=days - 1)

    business_timezone = ZoneInfo(settings.BUSINESS_TIMEZONE)
    query_start = datetime.combine(
        previous_start_date,
        time.min,
        tzinfo=business_timezone,
    ).astimezone(UTC)
    query_end = datetime.combine(
        selected_end_date + timedelta(days=1),
        time.min,
        tzinfo=business_timezone,
    ).astimezone(UTC)
    local_sale_date = func.date(
        func.timezone(settings.BUSINESS_TIMEZONE, Sale.sold_at)
    )

    sales_rows = session.exec(
        select(
            local_sale_date,
            func.count(col(Sale.id)),
            func.sum(Sale.total_amount),
        )
        .where(
            Sale.sold_at >= query_start,
            Sale.sold_at < query_end,
        )
        .group_by(local_sale_date)
    ).all()
    sales_by_date = {
        report_date: (
            int(sales_count),
            Decimal(revenue).quantize(MONEY_QUANTUM),
        )
        for report_date, sales_count, revenue in sales_rows
    }

    units_rows = session.exec(
        select(
            local_sale_date,
            func.sum(SaleItem.quantity),
        )
        .select_from(SaleItem)
        .join(Sale, col(Sale.id) == col(SaleItem.sale_id))
        .where(
            Sale.sold_at >= query_start,
            Sale.sold_at < query_end,
        )
        .group_by(local_sale_date)
    ).all()
    units_by_date = {
        report_date: Decimal(units).quantize(QUANTITY_QUANTUM)
        for report_date, units in units_rows
    }

    def period_totals(start: date, end: date) -> tuple[Decimal, int, Decimal]:
        period_revenue = Decimal("0.00")
        period_sales_count = 0
        period_units_sold = Decimal("0.000")
        current_date = start
        while current_date <= end:
            sales_count, revenue = sales_by_date.get(
                current_date,
                (0, Decimal("0.00")),
            )
            period_revenue += revenue
            period_sales_count += sales_count
            period_units_sold += units_by_date.get(
                current_date,
                Decimal("0.000"),
            )
            current_date += timedelta(days=1)
        return (
            period_revenue.quantize(MONEY_QUANTUM),
            period_sales_count,
            period_units_sold.quantize(QUANTITY_QUANTUM),
        )

    daily: list[DashboardTrendDayPublic] = []
    current_date = selected_start_date
    while current_date <= selected_end_date:
        sales_count, revenue = sales_by_date.get(
            current_date,
            (0, Decimal("0.00")),
        )
        units_sold = units_by_date.get(current_date, Decimal("0.000"))
        average_sale_value = (
            (revenue / sales_count).quantize(
                MONEY_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
            if sales_count
            else Decimal("0.00")
        )
        daily.append(
            DashboardTrendDayPublic(
                report_date=current_date,
                revenue=revenue,
                sales_count=sales_count,
                units_sold=units_sold,
                average_sale_value=average_sale_value,
            )
        )
        current_date += timedelta(days=1)

    revenue, sales_count, units_sold = period_totals(
        selected_start_date,
        selected_end_date,
    )
    previous_revenue, previous_sales_count, previous_units_sold = period_totals(
        previous_start_date,
        previous_end_date,
    )
    average_sale_value = (
        (revenue / sales_count).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        if sales_count
        else Decimal("0.00")
    )

    return DashboardTrendsPublic(
        start_date=selected_start_date,
        end_date=selected_end_date,
        timezone=settings.BUSINESS_TIMEZONE,
        days=days,
        revenue=revenue,
        sales_count=sales_count,
        units_sold=units_sold,
        average_sale_value=average_sale_value,
        previous_period=DashboardTrendComparisonPublic(
            start_date=previous_start_date,
            end_date=previous_end_date,
            revenue=previous_revenue,
            sales_count=previous_sales_count,
            units_sold=previous_units_sold,
            revenue_change_percent=_percent_change(revenue, previous_revenue),
            sales_count_change_percent=_percent_change(
                Decimal(sales_count),
                Decimal(previous_sales_count),
            ),
            units_sold_change_percent=_percent_change(
                units_sold,
                previous_units_sold,
            ),
        ),
        daily=daily,
    )
