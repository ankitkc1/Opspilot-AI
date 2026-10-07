from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.models import AIDailyBriefingPublic, AIStatusPublic
from app.services.ai_briefing import (
    AIBriefingResponseError,
    generate_daily_briefing,
)
from app.services.dashboard import get_dashboard_summary
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
    _current_user: CurrentUser,
    ollama: OllamaClientDep,
    report_date: date | None = None,
) -> AIDailyBriefingPublic:
    """Generate a grounded briefing from OpsPilot's deterministic daily metrics."""

    source = get_dashboard_summary(session, report_date=report_date)
    try:
        return generate_daily_briefing(ollama, source)
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
