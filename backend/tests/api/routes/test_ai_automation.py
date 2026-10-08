import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, time
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session, select

from app.api.routes.ai import get_ollama_client
from app.core.config import settings
from app.main import app
from app.models import AIDailyBriefing, AIWeeklyReview, User
from app.services.ai_automation import (
    get_or_create_automation_setting,
    run_due_daily_automations,
    run_due_weekly_automations,
)
from app.services.ollama import OllamaClient, OllamaMessage, OllamaServiceError
from tests.utils.user import authentication_token_from_email


class AutomationOllamaClient(OllamaClient):
    def __init__(
        self,
        *,
        chat_error: OllamaServiceError | None = None,
    ) -> None:
        self.model = "qwen3:4b"
        self.chat_error = chat_error

    def chat(
        self,
        *,
        messages: Sequence[OllamaMessage],
        response_format: str | dict[str, Any] | None = None,
    ) -> str:
        if self.chat_error is not None:
            raise self.chat_error
        properties = (
            response_format.get("properties", {})
            if isinstance(response_format, dict)
            else {}
        )
        if "wins" in properties:
            return json.dumps(
                {
                    "headline": "Automated weekly operations review",
                    "summary": "The completed seven-day period was reviewed.",
                    "wins": [],
                    "concerns": [],
                    "priorities": ["Review next week's stock requirements."],
                }
            )
        return json.dumps(
            {
                "headline": "Automated daily operations briefing",
                "summary": "The scheduled snapshot was reviewed successfully.",
                "priorities": ["Review the low-stock list."],
                "risks": [],
                "opportunities": [],
            }
        )


@pytest.fixture
def automation_user_headers(
    client: TestClient,
    db: Session,
) -> dict[str, str]:
    return authentication_token_from_email(
        client=client,
        email=f"automation-{uuid.uuid4()}@example.com",
        db=db,
    )


def _request_run(
    client: TestClient,
    headers: dict[str, str],
    ollama: AutomationOllamaClient,
) -> Response:
    previous_override = app.dependency_overrides.get(get_ollama_client)

    def override() -> OllamaClient:
        return ollama

    app.dependency_overrides[get_ollama_client] = override
    try:
        return cast(
            Response,
            client.post(
                f"{settings.API_V1_STR}/ai/automation/daily-briefing/run",
                headers=headers,
            ),
        )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_ollama_client, None)
        else:
            app.dependency_overrides[get_ollama_client] = previous_override


def _request_weekly_run(
    client: TestClient,
    headers: dict[str, str],
    ollama: AutomationOllamaClient,
) -> Response:
    previous_override = app.dependency_overrides.get(get_ollama_client)

    def override() -> OllamaClient:
        return ollama

    app.dependency_overrides[get_ollama_client] = override
    try:
        return cast(
            Response,
            client.post(
                f"{settings.API_V1_STR}/ai/automation/weekly-review/run",
                headers=headers,
            ),
        )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_ollama_client, None)
        else:
            app.dependency_overrides[get_ollama_client] = previous_override


def test_daily_automation_requires_authentication(client: TestClient) -> None:
    path = f"{settings.API_V1_STR}/ai/automation/daily-briefing"
    assert client.get(path).status_code == 401
    assert client.patch(path, json={"enabled": True}).status_code == 401
    assert client.post(f"{path}/run").status_code == 401


def test_daily_automation_schedule_can_be_configured(
    client: TestClient,
    automation_user_headers: dict[str, str],
) -> None:
    path = f"{settings.API_V1_STR}/ai/automation/daily-briefing"
    initial = client.get(path, headers=automation_user_headers)

    assert initial.status_code == 200
    assert initial.json() == {
        "enabled": False,
        "run_time": "08:00:00",
        "timezone": settings.BUSINESS_TIMEZONE,
        "next_run_at": None,
        "last_run": None,
    }

    updated = client.patch(
        path,
        headers=automation_user_headers,
        json={"enabled": True, "run_time": "06:30:00"},
    )

    assert updated.status_code == 200
    assert updated.json()["enabled"] is True
    assert updated.json()["run_time"] == "06:30:00"
    assert updated.json()["next_run_at"] is not None


def test_daily_automation_run_now_saves_automated_briefing(
    client: TestClient,
    automation_user_headers: dict[str, str],
    db: Session,
) -> None:
    response = _request_run(
        client,
        automation_user_headers,
        AutomationOllamaClient(),
    )

    assert response.status_code == 200
    content = response.json()
    assert content["trigger"] == "manual"
    assert content["status"] == "succeeded"
    assert content["briefing_id"]
    assert content["error"] is None

    briefing = db.get(AIDailyBriefing, content["briefing_id"])
    assert briefing is not None
    assert briefing.generation_mode == "automation"


def test_daily_automation_records_local_ai_failure(
    client: TestClient,
    automation_user_headers: dict[str, str],
) -> None:
    response = _request_run(
        client,
        automation_user_headers,
        AutomationOllamaClient(chat_error=OllamaServiceError("offline")),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["briefing_id"] is None
    assert response.json()["error"] == (
        "Local AI is unavailable. Check Ollama and the configured model."
    )


def test_scheduled_automation_runs_once_per_business_day(
    db: Session,
) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    automation = get_or_create_automation_setting(db, user_id=user.id)
    automation.daily_briefing_enabled = True
    automation.daily_briefing_time = time(hour=8)
    db.add(automation)
    db.commit()
    now = datetime(2099, 1, 2, 1, 0, tzinfo=UTC)

    first = run_due_daily_automations(
        db,
        ollama=AutomationOllamaClient(),
        now=now,
    )
    second = run_due_daily_automations(
        db,
        ollama=AutomationOllamaClient(),
        now=now,
    )

    assert len(first) == 1
    assert first[0].trigger == "scheduled"
    assert first[0].status == "succeeded"
    assert second == []


def test_scheduled_automation_waits_until_configured_time(db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    automation = get_or_create_automation_setting(db, user_id=user.id)
    automation.daily_briefing_enabled = True
    automation.daily_briefing_time = time(hour=8)
    db.add(automation)
    db.commit()

    runs = run_due_daily_automations(
        db,
        ollama=AutomationOllamaClient(),
        now=datetime(2099, 1, 1, 20, 0, tzinfo=UTC),
    )

    assert runs == []


def test_weekly_automation_requires_authentication(client: TestClient) -> None:
    path = f"{settings.API_V1_STR}/ai/automation/weekly-review"
    assert client.get(path).status_code == 401
    assert client.patch(path, json={"enabled": True}).status_code == 401
    assert client.post(f"{path}/run").status_code == 401


def test_weekly_automation_schedule_can_be_configured(
    client: TestClient,
    automation_user_headers: dict[str, str],
) -> None:
    path = f"{settings.API_V1_STR}/ai/automation/weekly-review"
    initial = client.get(path, headers=automation_user_headers)

    assert initial.status_code == 200
    assert initial.json() == {
        "enabled": False,
        "weekday": 0,
        "run_time": "09:00:00",
        "timezone": settings.BUSINESS_TIMEZONE,
        "next_run_at": None,
        "last_run": None,
    }

    updated = client.patch(
        path,
        headers=automation_user_headers,
        json={"enabled": True, "weekday": 6, "run_time": "07:30:00"},
    )

    assert updated.status_code == 200
    assert updated.json()["enabled"] is True
    assert updated.json()["weekday"] == 6
    assert updated.json()["run_time"] == "07:30:00"
    assert updated.json()["next_run_at"] is not None


def test_weekly_automation_run_now_saves_automated_review(
    client: TestClient,
    automation_user_headers: dict[str, str],
    db: Session,
) -> None:
    response = _request_weekly_run(
        client,
        automation_user_headers,
        AutomationOllamaClient(),
    )

    assert response.status_code == 200
    content = response.json()
    assert content["automation_type"] == "weekly_review"
    assert content["trigger"] == "manual"
    assert content["status"] == "succeeded"
    assert content["weekly_review_id"]
    assert content["briefing_id"] is None

    review = db.get(AIWeeklyReview, content["weekly_review_id"])
    assert review is not None
    assert review.generation_mode == "automation"


def test_scheduled_weekly_automation_catches_up_once(
    db: Session,
) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    automation = get_or_create_automation_setting(db, user_id=user.id)
    now = datetime(2099, 1, 7, 1, 0, tzinfo=UTC)
    local_now = now.astimezone(ZoneInfo(settings.BUSINESS_TIMEZONE))
    automation.weekly_review_enabled = True
    automation.weekly_review_weekday = (local_now.weekday() - 1) % 7
    automation.weekly_review_time = time(hour=8)
    db.add(automation)
    db.commit()

    first = run_due_weekly_automations(
        db,
        ollama=AutomationOllamaClient(),
        now=now,
    )
    second = run_due_weekly_automations(
        db,
        ollama=AutomationOllamaClient(),
        now=now,
    )

    assert len(first) == 1
    assert first[0].automation_type == "weekly_review"
    assert first[0].trigger == "scheduled"
    assert first[0].status == "succeeded"
    assert second == []


def test_scheduled_weekly_automation_waits_until_configured_time(
    db: Session,
) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    automation = get_or_create_automation_setting(db, user_id=user.id)
    now = datetime(2099, 1, 7, 1, 0, tzinfo=UTC)
    local_now = now.astimezone(ZoneInfo(settings.BUSINESS_TIMEZONE))
    automation.weekly_review_enabled = True
    automation.weekly_review_weekday = local_now.weekday()
    automation.weekly_review_time = time(hour=23, minute=59)
    db.add(automation)
    db.commit()

    runs = run_due_weekly_automations(
        db,
        ollama=AutomationOllamaClient(),
        now=now,
    )

    assert runs == []
