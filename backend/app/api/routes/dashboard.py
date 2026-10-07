from datetime import date
from enum import IntEnum
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.models import DashboardSummaryPublic, DashboardTrendsPublic
from app.services.dashboard import get_dashboard_summary, get_dashboard_trends

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class TrendDays(IntEnum):
    seven = 7
    fourteen = 14
    thirty = 30


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

    return get_dashboard_summary(
        session,
        report_date=report_date,
        top_limit=top_limit,
        low_stock_limit=low_stock_limit,
    )


@router.get("/trends/", response_model=DashboardTrendsPublic)
def read_dashboard_trends(
    session: SessionDep,
    _current_user: CurrentUser,
    end_date: date | None = None,
    days: TrendDays = TrendDays.seven,
) -> DashboardTrendsPublic:
    """Retrieve daily sales trends with a like-for-like period comparison."""

    return get_dashboard_trends(
        session,
        end_date=end_date,
        days=int(days),
    )
