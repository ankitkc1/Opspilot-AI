from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    AIAutomationRunPublic,
    AIDailyAutomationPublic,
    AIDailyAutomationUpdate,
    AIDailyBriefingPublic,
    AIDailyBriefingsPublic,
    AIStatusPublic,
    AIWeeklyReviewPublic,
    AIWeeklyReviewsPublic,
)
from app.services.ai_automation import (
    execute_daily_briefing_automation,
    get_daily_automation_public,
    update_daily_automation,
)
from app.services.ai_briefing import (
    AIBriefingResponseError,
    generate_daily_briefing,
    get_daily_briefing_history,
    get_latest_daily_briefing,
    save_daily_briefing,
)
from app.services.ai_weekly_review import (
    AIWeeklyReviewResponseError,
    generate_weekly_review,
    get_latest_weekly_review,
    get_weekly_review_history,
    save_weekly_review,
)
from app.services.dashboard import (
    get_dashboard_summary,
    get_dashboard_trends,
    resolve_report_date,
)
from app.services.ollama import OllamaClient, OllamaServiceError

router = APIRouter(prefix="/ai", tags=["ai"])


def get_ollama_client() -> OllamaClient:
    return OllamaClient()


OllamaClientDep = Annotated[OllamaClient, Depends(get_ollama_client)]


@router.get("/status", response_model=AIStatusPublic)
def read_ai_status(
    _current_user: CurrentUser,
    ollama: OllamaClientDep,
) -> AIStatusPublic:
    """Report whether the configured local Ollama model is ready."""

    try:
        available_models = ollama.list_models()
    except OllamaServiceError:
        return AIStatusPublic(
            status="unavailable",
            model=ollama.model,
            available_models=[],
            message="Ollama is not reachable from the backend.",
        )

    if ollama.model not in available_models:
        return AIStatusPublic(
            status="model_missing",
            model=ollama.model,
            available_models=available_models,
            message=f"The configured model '{ollama.model}' is not installed.",
        )

    return AIStatusPublic(
        status="ready",
        model=ollama.model,
        available_models=available_models,
        message="Local AI is ready.",
    )


@router.post("/daily-briefing", response_model=AIDailyBriefingPublic)
def create_daily_briefing(
    session: SessionDep,
    current_user: CurrentUser,
    ollama: OllamaClientDep,
    report_date: date | None = None,
) -> AIDailyBriefingPublic:
    """Generate a grounded briefing from OpsPilot's deterministic daily metrics."""

    source = get_dashboard_summary(session, report_date=report_date)
    try:
        content = generate_daily_briefing(ollama, source)
    except OllamaServiceError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local AI is unavailable. Check Ollama and the configured model.",
        )
    except AIBriefingResponseError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Local AI returned a briefing in an invalid format.",
        )

    return save_daily_briefing(
        session,
        content=content,
        source=source,
        model=ollama.model,
        generated_by_id=current_user.id,
    )


@router.get("/daily-briefing", response_model=AIDailyBriefingPublic | None)
def read_latest_daily_briefing(
    session: SessionDep,
    _current_user: CurrentUser,
    report_date: date | None = None,
) -> AIDailyBriefingPublic | None:
    """Return the latest saved briefing for a business day, if one exists."""

    return get_latest_daily_briefing(
        session,
        report_date=resolve_report_date(report_date),
    )


@router.get("/daily-briefings", response_model=AIDailyBriefingsPublic)
def read_daily_briefing_history(
    session: SessionDep,
    _current_user: CurrentUser,
    report_date: date | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> AIDailyBriefingsPublic:
    """List saved briefings newest first, optionally for one business day."""

    return get_daily_briefing_history(
        session,
        report_date=report_date,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/automation/daily-briefing",
    response_model=AIDailyAutomationPublic,
)
def read_daily_briefing_automation(
    session: SessionDep,
    current_user: CurrentUser,
) -> AIDailyAutomationPublic:
    """Return the current user's daily briefing automation schedule."""

    return get_daily_automation_public(session, user_id=current_user.id)


@router.patch(
    "/automation/daily-briefing",
    response_model=AIDailyAutomationPublic,
)
def update_daily_briefing_automation(
    session: SessionDep,
    current_user: CurrentUser,
    automation_in: AIDailyAutomationUpdate,
) -> AIDailyAutomationPublic:
    """Enable, disable, or reschedule automatic daily briefings."""

    update_daily_automation(
        session,
        user_id=current_user.id,
        automation_in=automation_in,
    )
    return get_daily_automation_public(session, user_id=current_user.id)


@router.post(
    "/automation/daily-briefing/run",
    response_model=AIAutomationRunPublic,
)
def run_daily_briefing_automation(
    session: SessionDep,
    current_user: CurrentUser,
    ollama: OllamaClientDep,
) -> AIAutomationRunPublic:
    """Run the approved daily briefing automation immediately."""

    return execute_daily_briefing_automation(
        session,
        user_id=current_user.id,
        ollama=ollama,
        trigger="manual",
    )


@router.post("/weekly-review", response_model=AIWeeklyReviewPublic)
def create_weekly_review(
    session: SessionDep,
    current_user: CurrentUser,
    ollama: OllamaClientDep,
    end_date: date | None = None,
) -> AIWeeklyReviewPublic:
    """Generate a grounded review from a seven-day operations trend snapshot."""

    source = get_dashboard_trends(session, end_date=end_date, days=7)
    try:
        content = generate_weekly_review(ollama, source)
    except OllamaServiceError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local AI is unavailable. Check Ollama and the configured model.",
        )
    except AIWeeklyReviewResponseError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Local AI returned a weekly review in an invalid format.",
        )

    return save_weekly_review(
        session,
        content=content,
        source=source,
        model=ollama.model,
        generated_by_id=current_user.id,
    )


@router.get("/weekly-review", response_model=AIWeeklyReviewPublic | None)
def read_latest_weekly_review(
    session: SessionDep,
    _current_user: CurrentUser,
    end_date: date | None = None,
) -> AIWeeklyReviewPublic | None:
    """Return the latest saved weekly review for a period end date."""

    return get_latest_weekly_review(
        session,
        period_end_date=resolve_report_date(end_date),
    )


@router.get("/weekly-reviews", response_model=AIWeeklyReviewsPublic)
def read_weekly_review_history(
    session: SessionDep,
    _current_user: CurrentUser,
    end_date: date | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> AIWeeklyReviewsPublic:
    """List saved weekly reviews newest first, optionally by period end date."""

    return get_weekly_review_history(
        session,
        period_end_date=end_date,
        skip=skip,
        limit=limit,
    )
