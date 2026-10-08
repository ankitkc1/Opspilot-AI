import json
import uuid
from collections.abc import Sequence
from typing import Any, cast

from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session

from app.api.routes.ai import get_ollama_client
from app.core.config import settings
from app.main import app
from app.models import AIDailyBriefing, AIWeeklyReview
from app.services.ollama import OllamaClient, OllamaMessage, OllamaServiceError


class StubOllamaClient(OllamaClient):
    def __init__(
        self,
        *,
        model: str = "qwen3:4b",
        available_models: list[str] | None = None,
        error: OllamaServiceError | None = None,
        chat_response: str | None = None,
        chat_error: OllamaServiceError | None = None,
    ) -> None:
        self.model = model
        self.available_models = available_models or []
        self.error = error
        self.chat_response = chat_response
        self.chat_error = chat_error
        self.last_messages: Sequence[OllamaMessage] | None = None
        self.last_response_format: str | dict[str, Any] | None = None

    def list_models(self) -> list[str]:
        if self.error is not None:
            raise self.error
        return self.available_models

    def chat(
        self,
        *,
        messages: Sequence[OllamaMessage],
        response_format: str | dict[str, Any] | None = None,
    ) -> str:
        self.last_messages = messages
        self.last_response_format = response_format
        if self.chat_error is not None:
            raise self.chat_error
        if self.chat_response is None:
            raise AssertionError("A chat response was not configured")
        return self.chat_response


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


def _request_briefing(
    client: TestClient,
    headers: dict[str, str],
    ollama: StubOllamaClient,
    *,
    report_date: str = "2099-01-01",
) -> Response:
    previous_override = app.dependency_overrides.get(get_ollama_client)

    def override() -> OllamaClient:
        return ollama

    app.dependency_overrides[get_ollama_client] = override
    try:
        return cast(
            Response,
            client.post(
                f"{settings.API_V1_STR}/ai/daily-briefing",
                headers=headers,
                params={"report_date": report_date},
            ),
        )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_ollama_client, None)
        else:
            app.dependency_overrides[get_ollama_client] = previous_override


def _request_weekly_review(
    client: TestClient,
    headers: dict[str, str],
    ollama: StubOllamaClient,
    *,
    end_date: str = "2099-03-07",
) -> Response:
    previous_override = app.dependency_overrides.get(get_ollama_client)

    def override() -> OllamaClient:
        return ollama

    app.dependency_overrides[get_ollama_client] = override
    try:
        return cast(
            Response,
            client.post(
                f"{settings.API_V1_STR}/ai/weekly-review",
                headers=headers,
                params={"end_date": end_date},
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


def test_daily_briefing_requires_authentication(client: TestClient) -> None:
    response = client.post(f"{settings.API_V1_STR}/ai/daily-briefing")
    assert response.status_code == 401

    response = client.get(f"{settings.API_V1_STR}/ai/daily-briefing")
    assert response.status_code == 401

    response = client.get(f"{settings.API_V1_STR}/ai/daily-briefings")
    assert response.status_code == 401

    response = client.post(f"{settings.API_V1_STR}/ai/weekly-review")
    assert response.status_code == 401

    response = client.get(f"{settings.API_V1_STR}/ai/weekly-review")
    assert response.status_code == 401

    response = client.get(f"{settings.API_V1_STR}/ai/weekly-reviews")
    assert response.status_code == 401


def test_daily_briefing_is_grounded_in_dashboard_snapshot(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    ollama = StubOllamaClient(
        chat_response=json.dumps(
            {
                "headline": "Quiet day: focus on stock readiness",
                "summary": "No sales were recorded for the selected day.",
                "priorities": ["Review the current low-stock list."],
                "risks": ["There is not enough sales data to identify trends."],
                "opportunities": ["Confirm products are ready for the next service."],
            }
        )
    )

    response = _request_briefing(client, superuser_token_headers, ollama)

    assert response.status_code == 200
    content = response.json()
    assert content["report_date"] == "2099-01-01"
    assert content["model"] == "qwen3:4b"
    assert content["generation_mode"] == "manual"
    assert content["headline"] == "Quiet day: focus on stock readiness"
    assert content["id"]
    assert content["generated_by_id"]
    assert content["source"]["sales_count"] == 0
    assert content["source"]["revenue"] == "0.00"
    assert content["generated_at"]

    assert isinstance(ollama.last_response_format, dict)
    assert ollama.last_response_format["type"] == "object"
    assert ollama.last_messages is not None
    assert "untrusted business data" in ollama.last_messages[0]["content"]
    assert '"report_date":"2099-01-01"' in ollama.last_messages[1]["content"]

    stored = db.get(AIDailyBriefing, uuid.UUID(content["id"]))
    assert stored is not None
    assert stored.headline == content["headline"]
    assert stored.source["report_date"] == "2099-01-01"


def test_daily_briefing_latest_and_history_use_saved_results(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    report_date = "2099-02-01"
    empty_response = client.get(
        f"{settings.API_V1_STR}/ai/daily-briefing",
        headers=superuser_token_headers,
        params={"report_date": report_date},
    )
    assert empty_response.status_code == 200
    assert empty_response.json() is None

    first = _request_briefing(
        client,
        superuser_token_headers,
        StubOllamaClient(
            chat_response=json.dumps(
                {
                    "headline": "First saved briefing",
                    "summary": "This is the first saved summary.",
                    "priorities": ["Review the first priority."],
                    "risks": [],
                    "opportunities": [],
                }
            )
        ),
        report_date=report_date,
    )
    second = _request_briefing(
        client,
        superuser_token_headers,
        StubOllamaClient(
            chat_response=json.dumps(
                {
                    "headline": "Updated saved briefing",
                    "summary": "This is the regenerated summary.",
                    "priorities": ["Review the updated priority."],
                    "risks": ["Data is limited."],
                    "opportunities": [],
                }
            )
        ),
        report_date=report_date,
    )
    assert first.status_code == 200
    assert second.status_code == 200

    latest = client.get(
        f"{settings.API_V1_STR}/ai/daily-briefing",
        headers=superuser_token_headers,
        params={"report_date": report_date},
    )
    assert latest.status_code == 200
    assert latest.json()["id"] == second.json()["id"]
    assert latest.json()["headline"] == "Updated saved briefing"

    history = client.get(
        f"{settings.API_V1_STR}/ai/daily-briefings",
        headers=superuser_token_headers,
        params={"report_date": report_date, "skip": 0, "limit": 1},
    )
    assert history.status_code == 200
    assert history.json()["count"] == 2
    assert [item["id"] for item in history.json()["data"]] == [second.json()["id"]]


def test_daily_briefing_reports_unavailable_ollama(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = _request_briefing(
        client,
        superuser_token_headers,
        StubOllamaClient(chat_error=OllamaServiceError("offline")),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Local AI is unavailable. Check Ollama and the configured model."
    )


def test_daily_briefing_rejects_invalid_model_output(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = _request_briefing(
        client,
        superuser_token_headers,
        StubOllamaClient(chat_response="not JSON"),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Local AI returned a briefing in an invalid format."
    )


def test_weekly_review_is_grounded_in_trend_snapshot(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    ollama = StubOllamaClient(
        chat_response=json.dumps(
            {
                "headline": "A quiet week needs a focused reset",
                "summary": "No sales were recorded in the selected seven days.",
                "wins": [],
                "concerns": ["The period contains no sales activity."],
                "priorities": ["Confirm trading data is being recorded each day."],
            }
        )
    )

    response = _request_weekly_review(
        client,
        superuser_token_headers,
        ollama,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["period_start_date"] == "2099-03-01"
    assert content["period_end_date"] == "2099-03-07"
    assert content["headline"] == "A quiet week needs a focused reset"
    assert content["source"]["days"] == 7
    assert content["source"]["sales_count"] == 0
    assert content["source"]["previous_period"]["sales_count"] == 0
    assert content["model"] == "qwen3:4b"
    assert content["generation_mode"] == "manual"
    assert content["generated_by_id"]

    assert isinstance(ollama.last_response_format, dict)
    assert ollama.last_response_format["type"] == "object"
    assert ollama.last_messages is not None
    assert "untrusted business data" in ollama.last_messages[0]["content"]
    assert '"days":7' in ollama.last_messages[1]["content"]
    assert '"previous_period"' in ollama.last_messages[1]["content"]

    stored = db.get(AIWeeklyReview, uuid.UUID(content["id"]))
    assert stored is not None
    assert stored.headline == content["headline"]
    assert stored.source["end_date"] == "2099-03-07"


def test_weekly_review_latest_and_history_use_saved_results(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    end_date = "2099-04-07"
    empty_response = client.get(
        f"{settings.API_V1_STR}/ai/weekly-review",
        headers=superuser_token_headers,
        params={"end_date": end_date},
    )
    assert empty_response.status_code == 200
    assert empty_response.json() is None

    first = _request_weekly_review(
        client,
        superuser_token_headers,
        StubOllamaClient(
            chat_response=json.dumps(
                {
                    "headline": "First saved weekly review",
                    "summary": "This is the first weekly summary.",
                    "wins": [],
                    "concerns": ["Sales data is limited."],
                    "priorities": ["Review daily sales recording."],
                }
            )
        ),
        end_date=end_date,
    )
    second = _request_weekly_review(
        client,
        superuser_token_headers,
        StubOllamaClient(
            chat_response=json.dumps(
                {
                    "headline": "Updated saved weekly review",
                    "summary": "This is the regenerated weekly summary.",
                    "wins": ["The review was refreshed."],
                    "concerns": [],
                    "priorities": ["Use the latest review for planning."],
                }
            )
        ),
        end_date=end_date,
    )
    assert first.status_code == 200
    assert second.status_code == 200

    latest = client.get(
        f"{settings.API_V1_STR}/ai/weekly-review",
        headers=superuser_token_headers,
        params={"end_date": end_date},
    )
    assert latest.status_code == 200
    assert latest.json()["id"] == second.json()["id"]

    history = client.get(
        f"{settings.API_V1_STR}/ai/weekly-reviews",
        headers=superuser_token_headers,
        params={"end_date": end_date, "skip": 0, "limit": 1},
    )
    assert history.status_code == 200
    assert history.json()["count"] == 2
    assert [item["id"] for item in history.json()["data"]] == [
        second.json()["id"]
    ]


def test_weekly_review_reports_unavailable_ollama(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = _request_weekly_review(
        client,
        superuser_token_headers,
        StubOllamaClient(chat_error=OllamaServiceError("offline")),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Local AI is unavailable. Check Ollama and the configured model."
    )


def test_weekly_review_rejects_invalid_model_output(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = _request_weekly_review(
        client,
        superuser_token_headers,
        StubOllamaClient(chat_response="not JSON"),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Local AI returned a weekly review in an invalid format."
    )
