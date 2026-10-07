from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser
from app.models import AIStatusPublic
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
