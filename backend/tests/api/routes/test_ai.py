from typing import cast

from fastapi.testclient import TestClient
from httpx import Response

from app.api.routes.ai import get_ollama_client
from app.core.config import settings
from app.main import app
from app.services.ollama import OllamaClient, OllamaServiceError


class StubOllamaClient(OllamaClient):
    def __init__(
        self,
        *,
        model: str = "qwen3:4b",
        available_models: list[str] | None = None,
        error: OllamaServiceError | None = None,
    ) -> None:
        self.model = model
        self.available_models = available_models or []
        self.error = error

    def list_models(self) -> list[str]:
        if self.error is not None:
            raise self.error
        return self.available_models


def _request_status(
    client: TestClient,
    headers: dict[str, str],
    ollama: StubOllamaClient,
) -> Response:
    previous_override = app.dependency_overrides.get(get_ollama_client)

    def override() -> OllamaClient:
        return ollama

    app.dependency_overrides[get_ollama_client] = override
    try:
        return cast(
            Response,
            client.get(
                f"{settings.API_V1_STR}/ai/status",
                headers=headers,
            ),
        )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_ollama_client, None)
        else:
            app.dependency_overrides[get_ollama_client] = previous_override


def test_ai_status_requires_authentication(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/ai/status")
    assert response.status_code == 401


def test_ai_status_reports_ready(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = _request_status(
        client,
        superuser_token_headers,
        StubOllamaClient(available_models=["qwen3:4b", "embedding-model:latest"]),
    )

    assert response.status_code == 200
    assert response.json() == {
        "provider": "ollama",
        "status": "ready",
        "model": "qwen3:4b",
        "available_models": ["qwen3:4b", "embedding-model:latest"],
        "message": "Local AI is ready.",
    }


def test_ai_status_reports_missing_model(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = _request_status(
        client,
        superuser_token_headers,
        StubOllamaClient(available_models=["qwen3:1.7b"]),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "model_missing"
    assert response.json()["available_models"] == ["qwen3:1.7b"]
    assert response.json()["message"] == (
        "The configured model 'qwen3:4b' is not installed."
    )


def test_ai_status_reports_unavailable_provider(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = _request_status(
        client,
        superuser_token_headers,
        StubOllamaClient(error=OllamaServiceError("connection refused")),
    )

    assert response.status_code == 200
    assert response.json() == {
        "provider": "ollama",
        "status": "unavailable",
        "model": "qwen3:4b",
        "available_models": [],
        "message": "Ollama is not reachable from the backend.",
    }
